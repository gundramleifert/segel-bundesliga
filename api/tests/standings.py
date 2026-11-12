"""Points as a test reads them: computed from the raw results, as every read does —
nothing about them is stored (review 2.1)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring import TeamScore
from app.services.standings import compute_event


async def points(session: AsyncSession, event_id: int) -> dict[tuple[int, int], float]:
    """(team id, race id) → points, for every scored result of the event."""
    return {
        (score.team_id, race_id): value
        for score in await compute_event(session, event_id)
        for race_id, value in score.points_by_race.items()
    }


async def table(session: AsyncSession, event_id: int) -> list[TeamScore]:
    """The event's daily standings, best first."""
    return await compute_event(session, event_id)
