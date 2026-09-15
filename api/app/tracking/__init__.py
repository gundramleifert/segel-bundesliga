"""Boats on the water: positions, the course, mark passings, a live ranking.

Stories L-1 to L-4 and ``docs/PLAN_LIVE_IMPLEMENTATION.md`` §5. Pure functions over
immutable inputs — no session, no ORM — so every algorithm here runs on a recorded track
without a server, and can be swapped for another implementation of the same ``Protocol``
where a second one is already known. ``analysis.default_pipeline`` is the one place the
concrete classes are named.
"""
