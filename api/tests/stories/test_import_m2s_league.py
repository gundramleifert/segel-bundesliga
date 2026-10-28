"""Story A-14: the 1. and 2. Liga 2026's notice boards on the seed, from Manage2Sail."""

from sqlalchemy import select

from app.models import EventDocumentKind, ExternalId, Source


class TestManage2SailOnTheSeed:
    """Story A-14: the 1. and 2. Liga 2026's notice boards come from Manage2Sail alone,
    recorded in `app/seed_data/m2s-2026/` (decided 2026-10-28)."""

    async def test_the_season_s_notice_of_race_is_on_each_league_s_board(self, client):
        """Story A-14: the season event's notice of race, on the 1. and the 2. Liga's
        series; nothing invented beside it."""
        for slug in ("dsbl-1-2026", "dsbl-2-2026"):
            series = next(
                s for s in (await client.get("/api/series")).json() if s.get("slug") == slug
            )
            documents = (await client.get(f"/api/series/{series['id']}/documents")).json()
            assert [(d["title"], d["kind"]) for d in documents] == [
                ("Notice of Race 2026_NEU.pdf", EventDocumentKind.NOTICE_OF_RACE)
            ]
            assert documents[0]["url"].startswith("https://www.manage2sail.com/")

    async def test_every_act_is_linked_to_its_weekend(self):
        """Story A-14: each of the eleven acts is linked to its weekend's Manage2Sail
        event and its league's class — the place later notices arrive from."""
        from app.db import SessionLocal

        async with SessionLocal() as session:
            keys = (
                await session.execute(
                    select(ExternalId.external_key).where(
                        ExternalId.source == Source.MANAGE2SAIL, ExternalId.entity_type == "event"
                    )
                )
            ).scalars()
            league = [key for key in keys if "Segel-Bundesliga" in key]
        assert len(league) == 11
        assert sum(key.endswith("|1.Segel-Bundesliga") for key in league) == 6

    async def test_a_second_run_changes_nothing(self):
        """Story A-14: the recorded import is repeatable on the seed."""
        from app.db import SessionLocal
        from app.imports.m2s import import_recorded_league

        report = await import_recorded_league(SessionLocal, log=lambda _: None)
        assert not report.errors and not report.warnings, report.render()
        assert not report.created and not report.updated, report.render()
