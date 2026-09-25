"""User Stories B-10 and V-12: the clubs this account has something to do with.

Two relationships that are deliberately not the same thing, and that this endpoint keeps
apart because the two screens reading it need different ones:

* **member** — the `member` tuple on the club (Story Z-5). That is what "my clubs" means
  on `/clubs` (B-10).
* **organizer** — `manager` or `admin` of that club. That is what `/club` needs (V-12), and it
  is often held by someone who never sails and is no member at all.

Neither implies the other, so an account appears here when either is true and each entry
says which. The club's series registrations come with it: the squad screen navigates by
them, and fetching them separately would mean a request per club.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Series, Team
from app.models.auth import Grant, Relation, Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

MINE = "/api/clubs/mine"


async def _club(slug: str) -> Club:
    async with SessionLocal() as session:
        return (await session.execute(select(Club).where(Club.slug == slug))).scalar_one()


async def _as(client, caplog, email: str, *roles: str, club_id: int | None = None):
    await make_user(email, *roles, club_id=club_id)
    return auth_headers(await login_as(client, email, caplog))


async def _make_member(email: str, club_id: int) -> None:
    """Writes the ``member`` tuple on the club for an existing account (Story Z-5)."""
    from app.models.auth import User

    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(Grant(relation=Relation.MEMBER, club_id=club_id, user_id=user.id))
        await session.commit()


class TestMyClubs:
    """B-10/V-12: what this account may act for, in one request."""

    async def test_a_guest_is_not_answered_at_all(self, client):
        """No token, no list — this is about a specific person, so there is no public form."""
        response = await client.get(MINE)
        assert response.status_code == 401, response.text

    async def test_an_account_with_no_club_gets_an_empty_list(self, client, caplog):
        """Not a 404. "You belong to nothing yet" is a normal answer, and the screen has
        a sentence for it (Story V-12)."""
        headers = await _as(client, caplog, "mine-nobody@example.com")
        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == []

    async def test_a_member_sees_their_club_as_a_member(self, client, caplog):
        club = await _club("nrv")
        email = "mine-member@example.com"
        # Signed in *before* the tuple is written, and the token kept: `make_user` deletes
        # an existing account and its tuples with it, so calling it a second time for the
        # same address would quietly undo the row this test is about.
        headers = await _as(client, caplog, email)
        await _make_member(email, club.id)

        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        entries = response.json()
        assert [entry["club"]["slug"] for entry in entries] == ["nrv"]
        assert entries[0]["is_member"] is True
        # A member is not thereby an organizer — that is the whole point of two fields.
        assert entries[0]["may_manage"] is False

    async def test_an_organizer_sees_the_club_they_manage_without_being_a_member(
        self, client, caplog
    ):
        """The case that makes `/club` reachable at all (Story V-12).

        A club's organizer is frequently not in the sailing squad, so requiring membership
        here would leave exactly the person who has the permission without a way in.
        """
        club = await _club("byc")
        headers = await _as(
            client, caplog, "mine-organizer@example.com", Role.CLUB_MANAGER, club_id=club.id
        )

        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        entries = response.json()
        assert [entry["club"]["slug"] for entry in entries] == ["byc"]
        assert entries[0]["may_manage"] is True
        assert entries[0]["is_member"] is False

    async def test_an_organizer_of_another_club_manages_only_that_one(self, client, caplog):
        """`club_manager` is granted per club, so the list is per club too."""
        byc = await _club("byc")
        headers = await _as(
            client, caplog, "mine-oneclub@example.com", Role.CLUB_MANAGER, club_id=byc.id
        )
        entries = (await client.get(MINE, headers=headers)).json()
        assert {entry["club"]["slug"] for entry in entries} == {"byc"}

    async def test_the_series_registrations_come_with_the_club(self, client, caplog):
        """What V-12 navigates by: a squad belongs to one series registration, so the
        screen needs the team ids without a request per club."""
        club = await _club("nrv")
        headers = await _as(
            client, caplog, "mine-teams@example.com", Role.CLUB_MANAGER, club_id=club.id
        )

        entry = (await client.get(MINE, headers=headers)).json()[0]
        assert entry["teams"], "the seeded club is registered for at least one series"

        async with SessionLocal() as session:
            expected = {
                team_id
                for (team_id,) in (
                    await session.execute(
                        select(Team.id).where(Team.club_id == club.id, Team.event_id.is_(None))
                    )
                ).all()
            }
        assert {team["team_id"] for team in entry["teams"]} == expected

        team = entry["teams"][0]
        assert team["series"]["name"]
        # The size is on the row so the screen can show "7 of 10" without opening each
        # squad in turn.
        assert isinstance(team["squad_size"], int)

    async def test_an_event_entry_is_not_a_series_registration(self, client, caplog):
        """`Team` carries both. Only the one with no `event_id` has a squad (Story V-1),
        and offering the other would produce a panel every save refuses."""
        club = await _club("nrv")
        headers = await _as(
            client, caplog, "mine-eventteams@example.com", Role.CLUB_MANAGER, club_id=club.id
        )
        entry = (await client.get(MINE, headers=headers)).json()[0]

        async with SessionLocal() as session:
            event_team_ids = {
                team_id
                for (team_id,) in (
                    await session.execute(
                        select(Team.id).where(Team.club_id == club.id, Team.event_id.is_not(None))
                    )
                ).all()
            }
        assert event_team_ids, "the seed enters this club into events"
        assert not {t["team_id"] for t in entry["teams"]} & event_team_ids

    async def test_an_admin_gets_the_clubs_they_belong_to_not_all_eighteen(self, client, caplog):
        """`admin` may manage every club, but this endpoint answers "mine", not "all".

        Handing an administrator all eighteen would make `/club` a second, worse copy of
        the admin screen, and would bury the one club they actually sail for.
        """
        headers = await _as(client, caplog, "mine-admin@example.com", Role.ADMIN)
        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == []

    async def test_the_series_is_named_once_per_registration(self, client, caplog):
        """No duplicate rows: a club registered for two series has two teams, not the same
        series twice, and the seeded club must not arrive with repeats."""
        club = await _club("nrv")
        headers = await _as(
            client, caplog, "mine-dupes@example.com", Role.CLUB_MANAGER, club_id=club.id
        )
        teams = (await client.get(MINE, headers=headers)).json()[0]["teams"]
        ids = [team["team_id"] for team in teams]
        assert len(ids) == len(set(ids))

        async with SessionLocal() as session:
            named = {
                slug
                for (slug,) in (
                    await session.execute(
                        select(Series.slug)
                        .join(Team, Team.series_id == Series.id)
                        .where(Team.club_id == club.id, Team.event_id.is_(None))
                    )
                ).all()
            }
        assert {team["series"]["slug"] for team in teams} == named


class TestMatchdays:
    """Story V-12: the club's matchdays come with the clubs, so the lineup screen (Story
    V-2) reaches an event entry without an admin-only list — the same defect the squad had."""

    async def test_the_clubs_matchdays_come_with_their_entries(self, client, caplog):
        club = await _club("kyc")
        headers = await _as(
            client, caplog, "mine-matchdays@example.com", Role.CLUB_MANAGER, club_id=club.id
        )
        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        mine = next(e for e in response.json() if e["club"]["slug"] == "kyc")

        registration = next(t for t in mine["teams"] if t["series"]["slug"] == "dsbl-1-2026")
        acts = [e for e in mine["events"] if e["series"] and e["series"]["slug"] == "dsbl-1-2026"]
        # The three seeded acts are there — "at least", not "exactly": other stories add
        # events to this series, and the club is adopted into each (see docs/gotchas).
        assert {"dsbl-1-2026-act-1", "dsbl-1-2026-act-2", "dsbl-1-2026-act-3"} <= {
            a["slug"] for a in acts
        }
        for act in acts:
            # The row names the *entry* to the matchday (what the lineup is set on) and the
            # *registration* the crew is drawn from — two different teams of the same club.
            assert act["team_id"] != registration["team_id"]
            assert act["squad_team_id"] == registration["team_id"]
            assert act["status"] in {"planned", "live", "final", "cancelled"}
            assert act["crew_size"] == 4
            assert act["title"]
        # Whether each is published is reported, not asserted: another story unpublishes a
        # seeded act on the shared database, and the row is right to say so.
        assert all(isinstance(a["published"], bool) for a in acts)
        # Chronological, so the next matchday is where the eye lands first.
        dated = [a["starts_on"] for a in acts if a["starts_on"] is not None]
        assert dated == sorted(dated)

    async def test_a_stand_alone_event_carries_its_own_squad(self, client, caplog):
        """An event in no series has no series registration, so its squad hangs off the
        entry itself (`squad_team`) — and the row says so, or the club could enter its own
        cup here and never register anyone for it."""
        admin = await _as(client, caplog, "mine-admin@example.com", Role.ADMIN)
        club = await _club("wyc")
        created = await client.post(
            "/api/admin/events",
            headers=admin,
            json={"title": "WYC Herbstcup", "starts_on": "2026-10-03"},
        )
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]
        entered = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=admin,
            json={"clubs": [club.id]},
        )
        assert entered.status_code == 200, entered.text

        manager = await _as(
            client, caplog, "mine-wyc@example.com", Role.CLUB_MANAGER, club_id=club.id
        )
        entries = (await client.get(MINE, headers=manager)).json()
        mine = next(e for e in entries if e["club"]["slug"] == "wyc")
        cup = next(e for e in mine["events"] if e["event_id"] == event_id)
        assert cup["series"] is None
        assert cup["squad_team_id"] == cup["team_id"]
        # A draft is listed for its own participants — they are the ones who have to line
        # up before it is published — and marked as such.
        assert cup["published"] is False

        # The squad really is reachable there for the club's organizer.
        squad = await client.get(f"/api/admin/teams/{cup['team_id']}/members", headers=manager)
        assert squad.status_code == 200, squad.text
        assert squad.json()["team_id"] == cup["team_id"]


class TestMemberReadsTheSquad:
    async def test_a_plain_member_can_read_their_clubs_squad_but_not_change_it(
        self, client, caplog
    ):
        """Story V-12 promises a member the read-only squad on `/club`. The panel reads
        `/api/admin/teams/{id}/members`, so a member has to be allowed to — the squad is
        public on the club page anyway. Writing stays with the leadership (Story V-1)."""
        club = await _club("fsc")
        email = "mine-reader@example.com"
        headers = await _as(client, caplog, email)
        await _make_member(email, club.id)

        entries = (await client.get(MINE, headers=headers)).json()
        mine = next(e for e in entries if e["club"]["slug"] == "fsc")
        team_id = mine["teams"][0]["team_id"]
        seen = await client.get(f"/api/admin/teams/{team_id}/members", headers=headers)
        assert seen.status_code == 200, seen.text
        assert seen.json()["team_id"] == team_id

        changed = await client.put(
            f"/api/admin/teams/{team_id}/members", headers=headers, json={"members": []}
        )
        assert changed.status_code == 403
