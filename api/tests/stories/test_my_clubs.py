"""User Stories B-10 and V-12: the clubs this account has something to do with.

Two relationships that are deliberately not the same thing, and that this endpoint keeps
apart because the two screens reading it need different ones:

* **member** — an accepted `ClubMember`. That is what "my clubs" means on `/clubs` (B-10).
* **organizer** — `club_manager` for that club. That is what `/club` needs (V-12), and it
  is often held by someone who never sails and is no member at all.

Neither implies the other, so an account appears here when either is true and each entry
says which. The club's series registrations come with it: the squad screen navigates by
them, and fetching them separately would mean a request per club.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, ClubMember, ClubMemberStatus, Series, Team
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

MINE = "/api/clubs/mine"


async def _club(slug: str) -> Club:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Club).where(Club.slug == slug))
        ).scalar_one()


async def _as(client, caplog, email: str, *roles: str, club_id: int | None = None):
    await make_user(email, *roles, club_id=club_id)
    return auth_headers(await login_as(client, email, caplog))


async def _make_member(email: str, club_id: int, status: ClubMemberStatus) -> None:
    """Puts an existing account into a club's roster at the given status."""
    from app.models.auth import User

    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        session.add(ClubMember(club_id=club_id, user_id=user.id, status=status))
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

    async def test_an_active_member_sees_their_club_as_a_member(self, client, caplog):
        club = await _club("nrv")
        email = "mine-member@example.com"
        # Signed in *before* the membership is added, and the token kept: `make_user`
        # deletes an existing account and its memberships with it, so calling it a second
        # time for the same address would quietly undo the row this test is about.
        headers = await _as(client, caplog, email)
        await _make_member(email, club.id, ClubMemberStatus.ACTIVE)

        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        entries = response.json()
        assert [entry["club"]["slug"] for entry in entries] == ["nrv"]
        assert entries[0]["is_member"] is True
        # A member is not thereby an organizer — that is the whole point of two fields.
        assert entries[0]["may_manage"] is False

    async def test_a_pending_request_is_not_a_club_of_mine(self, client, caplog):
        """Asking to join is not belonging. B-10 says so about the list; the endpoint has
        to say it, or the page would show a club the person was merely hoping for."""
        club = await _club("dtyc")
        email = "mine-pending@example.com"
        headers = await _as(client, caplog, email)
        await _make_member(email, club.id, ClubMemberStatus.PENDING_CLUB)

        response = await client.get(MINE, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == []

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
                        select(Team.id).where(
                            Team.club_id == club.id, Team.event_id.is_(None)
                        )
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
                        select(Team.id).where(
                            Team.club_id == club.id, Team.event_id.is_not(None)
                        )
                    )
                ).all()
            }
        assert event_team_ids, "the seed enters this club into events"
        assert not {t["team_id"] for t in entry["teams"]} & event_team_ids

    async def test_an_admin_gets_the_clubs_they_belong_to_not_all_eighteen(
        self, client, caplog
    ):
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
