"""Where the wind comes from, and how hard.

On a windward/leeward course the direction is the course axis — the committee lays the
course square to the wind, and that is a better estimate than anything a few phones could
compute. The strength is typed in by the committee until a track-estimated wind exists;
ranking needs it only to pick the polar column, and a few knots either way change no rank.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Wind:
    #: True wind speed in knots.
    tws: float
    #: True wind direction, degrees the wind comes *from*.
    twd: float
