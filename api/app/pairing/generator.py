"""Generate pairing lists — for now via the existing Java tool.

Why not in Python: The Java tool (``reference/PairingList``) optimizes not only opponent and
boat distribution but also **boat changes and shuttle trips** between flights.
Compared to an actual draw, it completes 16 flights with zero boat changes,
while the Python fallback in ``app.pairing.schedule`` achieves around 27 — operationally a
huge difference. Until the Python optimizer handles this criterion, the JAR is used.

The call crosses a process boundary with file exchange because the tool is a
command-line application:

    java -cp <jar> gundramleifert.pairing_list.Optimizer \\
         -s schedule_cfg.yml -oc opt_cfg.yml -dc display_cfg.yml -plo out.yml

**This takes time.** With production configuration (20,000 loops, 600 and 2,000
individuals), a matchday runs well over eight minutes. This call belongs therefore
never in an HTTP request, but in a background job.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import settings
from app.pairing.importer import BoatSpec, ImportedPairing, load_pairing_yaml
from app.pairing.logistics import LogisticsReport, logistics_report
from app.pairing.schedule import pairing_report

MAIN_CLASS = "gundramleifert.pairing_list.Optimizer"


class PairingGeneratorError(RuntimeError):
    """The generator could not produce a pairing list."""


@dataclass(frozen=True)
class GenerationProgress:
    """Status of an ongoing optimization run.

    The tool works through two phases: first opponent distribution (``matching``),
    flight by flight, then boat assignment (``boats``).
    """

    phase: str
    flight: int | None
    total_flights: int
    message: str

    @property
    def fraction(self) -> float:
        """Rough estimate of progress between 0 and 1.

        Deliberately rough: the tool reports no reliable remaining time, and a made-up
        percentage would be worse than an honestly imprecise one.
        """
        if self.total_flights <= 0:
            return 0.0
        done = (self.flight or 0) / self.total_flights
        # First half of the bar for opponent distribution, second for boat assignment.
        return min(1.0, 0.5 * done if self.phase == "matching" else 0.5 + 0.5 * done)


ProgressCallback = Callable[[GenerationProgress], None]

_FLIGHT_MARKER = re.compile(r"#+\s*Flight\s+(\d+)\s*#+")
_BOAT_PHASE = re.compile(r"run with OptBoatUsage")


@dataclass(frozen=True)
class OptimizerSettings:
    """Parameters of the Java optimizer.

    The defaults correspond to the configuration of an actual matchday
    (``events/2026_DSBL-1/opt_cfg.yml``). The weights control how expensive a boat change
    is compared to a shuttle trip — ``weight_change_between_boats`` is by far
    weighted highest because changing boats delays the schedule the most.
    """

    seed: int = 1240
    loops: int = 20_000
    match_individuals: int = 600
    boat_individuals: int = 2_000
    swap_teams: int = 200
    swap_boats: int = 400
    swap_races: int = 200
    weight_stay_on_boat: float = 2.03
    weight_stay_on_shuttle: float = 1.01
    weight_change_between_boats: float = 20.1

    def as_yaml(self) -> str:
        return yaml.safe_dump(
            {
                "seed": self.seed,
                "optMatchMatrix": {
                    "loops": self.loops,
                    "individuals": self.match_individuals,
                    "swapTeams": self.swap_teams,
                    "earlyStopping": 500,
                    "maxBranches": 1,
                    "saveEveryN": 250,
                },
                "optBoatUsage": {
                    "loops": self.loops,
                    "individuals": self.boat_individuals,
                    "weightStayOnBoat": self.weight_stay_on_boat,
                    "weightStayOnShuttle": self.weight_stay_on_shuttle,
                    "weightChangeBetweenBoats": self.weight_change_between_boats,
                    "swapBoats": self.swap_boats,
                    "swapRaces": self.swap_races,
                    "earlyStopping": 1_000,
                    "saveEveryN": 250,
                },
            },
            sort_keys=False,
            allow_unicode=True,
        )


@dataclass(frozen=True)
class GenerationRequest:
    teams: list[str]
    boats: list[BoatSpec]
    flights: int
    title: str = "Pairing List"
    optimizer: OptimizerSettings = field(default_factory=OptimizerSettings)

    def schedule_yaml(self) -> str:
        return yaml.safe_dump(
            {
                "flights": self.flights,
                "titles": [self.title],
                "teams": list(self.teams),
                "boats": [{"color": boat.color} for boat in self.boats],
            },
            sort_keys=False,
            allow_unicode=True,
        )


@dataclass
class GenerationResult:
    pairing: ImportedPairing
    quality: dict[str, int]
    logistics: LogisticsReport
    pdf_paths: list[Path]
    log: str

    def summary(self) -> dict:
        """Der Gütebericht, den der Veranstalter vor dem Veröffentlichen sieht (VA-3)."""
        return {**self.quality, **self.logistics.as_dict()}


async def generate_pairing(
    request: GenerationRequest,
    *,
    jar: Path | None = None,
    display_config: str | None = None,
    timeout: int | None = None,
    keep_workdir: bool = False,
    on_progress: ProgressCallback | None = None,
) -> GenerationResult:
    """Starts the Java optimizer and reads its result."""
    jar_path = Path(jar) if jar else Path(settings.pairing_jar)
    if not jar_path.is_file():
        raise PairingGeneratorError(
            f"The pairing JAR is missing at {jar_path}. "
            "Build with: mvn -DskipTests package in the reference/PairingList directory"
        )
    if shutil.which(settings.java_binary) is None:
        raise PairingGeneratorError(
            f"Java was not found ('{settings.java_binary}'). "
            "The pairing generator needs a Java runtime version 17 or later."
        )

    workdir = Path(tempfile.mkdtemp(prefix="sbl-pairing-"))
    try:
        schedule_cfg = workdir / "schedule_cfg.yml"
        schedule_cfg.write_text(request.schedule_yaml(), encoding="utf-8")
        (workdir / "opt_cfg.yml").write_text(request.optimizer.as_yaml(), encoding="utf-8")
        # Ohne Anzeigekonfiguration bricht das Werkzeug ab, auch wenn kein PDF verlangt ist.
        (workdir / "display_cfg.yml").write_text(
            display_config if display_config is not None else _DEFAULT_DISPLAY, encoding="utf-8"
        )

        log = await _run_optimizer(
            jar_path, workdir, timeout, request.flights, on_progress
        )

        out_yaml = workdir / "out.yml"
        if not out_yaml.is_file():
            raise PairingGeneratorError(
                "The optimizer did not write a pairing list.\n" + _tail(log)
            )

        pairing = load_pairing_yaml(
            schedule_cfg.read_text(encoding="utf-8"), out_yaml.read_text(encoding="utf-8")
        )
        return GenerationResult(
            pairing=pairing,
            quality=pairing_report(pairing.slots, len(request.teams), len(request.boats)),
            logistics=logistics_report(pairing.slots, len(request.boats)),
            pdf_paths=sorted(workdir.glob("*.pdf")),
            log=log,
        )
    finally:
        # Die PDFs liegen im Arbeitsverzeichnis; wer sie braucht, muss es behalten.
        if not keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)


async def _run_optimizer(
    jar: Path,
    workdir: Path,
    timeout: int | None,
    total_flights: int,
    on_progress: ProgressCallback | None,
) -> str:
    process = await asyncio.create_subprocess_exec(
        settings.java_binary,
        "-cp",
        str(jar.resolve()),
        MAIN_CLASS,
        "-s", "schedule_cfg.yml",
        "-oc", "opt_cfg.yml",
        "-dc", "display_cfg.yml",
        "-plo", "out.yml",
        cwd=workdir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    limit = timeout if timeout is not None else settings.pairing_timeout_seconds
    try:
        log = await asyncio.wait_for(
            _read_output(process, total_flights, on_progress), timeout=limit
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise PairingGeneratorError(
            f"The optimizer was stopped after {limit} seconds. "
            "Try again with fewer loops or individuals."
        ) from None

    if process.returncode != 0:
        raise PairingGeneratorError(
            f"The optimizer exited with code {process.returncode}.\n" + _tail(log)
        )
    return log


async def _read_output(
    process: asyncio.subprocess.Process,
    total_flights: int,
    on_progress: ProgressCallback | None,
) -> str:
    """Reads output line by line instead of all at once at the end.

    The tool processes flights one after another and reports each — this creates the
    progress display, without which a minute-long run would be a black box for the
    organizer.
    """
    assert process.stdout is not None
    lines: list[str] = []
    phase = "matching"

    async for raw in process.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        lines.append(line)
        if on_progress is None:
            continue

        if _BOAT_PHASE.search(line):
            phase = "boats"
            on_progress(GenerationProgress(phase, None, total_flights, line))
        elif match := _FLIGHT_MARKER.search(line):
            on_progress(
                GenerationProgress(phase, int(match.group(1)), total_flights, line)
            )

    await process.wait()
    return "\n".join(lines)


_SAVED_SHUTTLES = re.compile(
    r"saved Shuttles:\s*in habour:\s*(\d+)\s*at sea:\s*(\d+)\s*-\s*boat changes:\s*(\d+)"
)


def parse_optimizer_log(log: str) -> dict[str, int] | None:
    """Reads the quality numbers that the tool itself outputs — as a check against ours.

    If they differ, one side is measuring incorrectly; that should be investigated instead of
    silently trusting one number.
    """
    matches = _SAVED_SHUTTLES.findall(log)
    if not matches:
        return None
    harbour, at_sea, changes = matches[-1]
    return {
        "saved_shuttles_harbour": int(harbour),
        "saved_shuttles_at_sea": int(at_sea),
        "boat_changes": int(changes),
    }


def _tail(log: str, lines: int = 15) -> str:
    return "\n".join(log.strip().splitlines()[-lines:])


# Field names as in DisplayConfig of the Java tool. It would silently ignore unknown keys
# (FAIL_ON_UNKNOWN_PROPERTIES=false) — a typo would not be noticed, but silently lead to
# defaults.
_DEFAULT_DISPLAY = yaml.safe_dump(
    {
        "fontsize": 8,
        "factor_flight_race_width": 0.5,
        "show_match_stat": True,
        "show_boat_stat": True,
        "teamwise_list": True,
    },
    sort_keys=False,
)
