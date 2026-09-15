"""A boat's polar: how fast it goes at a true wind angle and speed (decision 10).

Reads SAP Sailing Analytics' CSV shape, so their 49er and 505 files and our J/70 file
(``api/tests/fixtures/polars/j70.csv``, ORC data) go through one loader:

    wind speed,4,6,8,...        the columns
    beat angles,45.8,...        optimum upwind angle per column
    beat sog,3.03,...           and the speed there
    52,3.3,4.64,...             one row per true wind angle
    ...
    jibe sog,3.18,...           optimum downwind speed per column
    jibe angles,140.3,...       and the angle

The optimum angles **and their speeds** come from the ``beat …``/``jibe …`` rows — they
must, because every J/70 beat angle lies below the table's first column (52°). The table
serves every other angle. Lines starting with ``#`` and a first line without a comma (the
boat's name) are skipped.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from pathlib import Path

#: Metres per second in one knot.
KNOT = 1852.0 / 3600.0


def _interp(x: float, xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    """Linear interpolation, clamped at both ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


@dataclass(frozen=True)
class Polar:
    """Speeds in knots, angles in degrees, wind speeds in knots — as the files have them."""

    name: str
    tws: tuple[float, ...]
    twa: tuple[float, ...]
    #: table[i][j] — boat speed at twa[i] and tws[j].
    table: tuple[tuple[float, ...], ...]
    beat_angle: tuple[float, ...]
    beat_speed: tuple[float, ...]
    gybe_angle: tuple[float, ...]
    gybe_speed: tuple[float, ...]

    @classmethod
    def load(cls, path: Path | str) -> Polar:
        rows: dict[str, tuple[float, ...]] = {}
        table: list[tuple[float, tuple[float, ...]]] = []
        name = Path(path).stem
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "," not in line:
                name = line
                continue
            head, *values = [cell.strip() for cell in line.split(",")]
            numbers = tuple(float(v) for v in values if v != "")
            try:
                table.append((float(head), numbers))
            except ValueError:
                rows[head.lower()] = numbers
        tws = rows["wind speed"]
        table.sort()
        beat_angle = rows["beat angles"]
        gybe_angle = rows.get("jibe angles") or rows["gybe angles"]
        beat_speed = rows.get("beat sog") or _sog_from_vmg(rows["beat vmg"], beat_angle)
        gybe_speed = rows.get("jibe sog") or _sog_from_vmg(rows["run vmg"], gybe_angle)
        return cls(
            name=name,
            tws=tws,
            twa=tuple(a for a, _ in table),
            table=tuple(v for _, v in table),
            beat_angle=beat_angle,
            beat_speed=beat_speed,
            gybe_angle=gybe_angle,
            gybe_speed=gybe_speed,
        )

    def _column(self, values_per_tws: tuple[float, ...], tws: float) -> float:
        return _interp(tws, self.tws, values_per_tws)

    def speed(self, tws: float, twa: float) -> float:
        """Boat speed in knots at this true wind speed and angle (0..180)."""
        twa = abs(angle_to_180(twa))
        beat_a, beat_s = self.best_upwind(tws)
        gybe_a, gybe_s = self.best_downwind(tws)
        if twa <= beat_a:
            # Pinching: speed falls off to nothing head to wind.
            return beat_s * max(0.0, twa / beat_a) ** 1.5
        rows = tuple(self._column(row, tws) for row in self.table)
        angles: tuple[float, ...] = (beat_a, *self.twa, gybe_a)
        speeds: tuple[float, ...] = (beat_s, *rows, gybe_s)
        # The optimum points are known-good anchors; the table between them is what the
        # certificate measured. Keep them monotone in angle so interpolation stays sane.
        pairs = sorted(zip(angles, speeds, strict=True))
        xs = tuple(a for a, _ in pairs)
        ys = tuple(s for _, s in pairs)
        if twa >= xs[-1]:
            # Dead downwind is slower than the gybe angle.
            return ys[-1] * max(0.6, 1 - (twa - xs[-1]) / 90)
        return _interp(twa, xs, ys)

    def best_upwind(self, tws: float) -> tuple[float, float]:
        """(true wind angle, boat speed) of the best VMG to windward."""
        return self._column(self.beat_angle, tws), self._column(self.beat_speed, tws)

    def best_downwind(self, tws: float) -> tuple[float, float]:
        """(true wind angle, boat speed) of the best VMG downwind."""
        return self._column(self.gybe_angle, tws), self._column(self.gybe_speed, tws)

    def vmg_upwind(self, tws: float) -> float:
        angle, speed = self.best_upwind(tws)
        return speed * math.cos(math.radians(angle))

    def vmg_downwind(self, tws: float) -> float:
        angle, speed = self.best_downwind(tws)
        return -speed * math.cos(math.radians(angle))

    def scaled(self, factor: float) -> Polar:
        """The same shape, every speed multiplied — for the ranking's invariance test."""
        return Polar(
            name=f"{self.name}×{factor}",
            tws=self.tws,
            twa=self.twa,
            table=tuple(tuple(v * factor for v in row) for row in self.table),
            beat_angle=self.beat_angle,
            beat_speed=tuple(v * factor for v in self.beat_speed),
            gybe_angle=self.gybe_angle,
            gybe_speed=tuple(v * factor for v in self.gybe_speed),
        )


def angle_to_180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def _sog_from_vmg(vmg: tuple[float, ...], angles: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(v / abs(math.cos(math.radians(a))) for v, a in zip(vmg, angles, strict=True))


#: The league's boat, for anything that has no better polar at hand.
J70 = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "polars" / "j70.csv"
