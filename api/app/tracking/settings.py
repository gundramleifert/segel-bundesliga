"""The tuned constants of the tracking code, as settings rather than literals.

Every number here is a judgement — how close is "at the mark", how far a boat overstands,
how noisy a phone's GPS is — and every one of them will be re-tuned on the first real
tracks. So they are pydantic settings: overridable per installation through
``SBL_TRACKING_*`` environment variables or ``.env`` today, and the same object is what a
race committee's screen would edit once they move to the UI (then per event, in the
database — the field list is the contract either way).

Read through ``tracking_settings``; the algorithms take them as constructor defaults, so a
test can still pass its own value without touching the environment.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TrackingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SBL_TRACKING_", extra="ignore")

    # ----------------------------------------------------------------- detection
    #: Inside this distance a boat is "at" a mark — about three J/70 lengths.
    mark_radius_m: float = 20.0
    #: A start or finish line counts this far beyond its ends: a boat crossing a metre
    #: outside the pin is a start to the tracking, and the position noise is this size.
    line_margin_m: float = 5.0
    #: A gate counts this far beyond its marks: boats round a gate mark close to it, and
    #: the noised track of a boat passing a metre inside may fall a few metres outside.
    gate_margin_m: float = 15.0

    # ------------------------------------------------------------------- ranking
    #: True wind speed assumed for the polar column when nobody has typed one in.
    default_tws_kn: float = 10.0

    # ------------------------------------------------------ the course, when laid here
    #: A short course: the emulator's and the "lay a default course" button's leg.
    default_leg_length_m: float = 300.0
    default_line_length_m: float = 80.0
    default_gate_width_m: float = 40.0
    #: Where a course is laid when the venue has no coordinates: Kiel Fjord.
    default_lat: float = 54.42
    default_lon: float = 10.19
    default_wind_from_deg: float = 20.0

    # ------------------------------------------------------------------ emulator
    #: Inside this the emulator considers a mark rounded and turns for the next waypoint.
    rounding_distance_m: float = 12.0
    #: How far to the side of a mark an emulated boat aims, to leave it to port.
    rounding_offset_m: float = 8.0
    #: Standard deviation of the position noise on an emitted fix, in metres.
    gps_noise_m: float = 5.0
    #: Emulated boats set off this long before the gun, from below the line.
    emulator_warmup_s: float = 30.0
    #: One fix per boat this often.
    emulator_tick_s: float = 1.0

    # ------------------------------------------------------------------- spectator
    #: How long a boat's trail on the map is.
    trail_seconds: int = 60


tracking_settings = TrackingSettings()
