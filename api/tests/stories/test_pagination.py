"""Story A-13: one list mechanism, and every long list is paged.

Written against the *envelope* rather than against any one endpoint: the point of the
story is that a screen can page, sort and count without knowing which list it is looking
at, and a test per endpoint that checks its own shape would not notice the day one of them
drifts.
"""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Venue
from app.models.auth import Role
from tests.stories.test_master_data import as_role

#: Every list that grows with the database, with the role that may read it. A new paged
#: endpoint is one line here and is then held to all of the rules below.
PAGED = [
    ("/api/admin/sailors", Role.ADMIN),
    ("/api/auth/users", Role.ADMIN),
    ("/api/admin/clubs", Role.ADMIN),
    ("/api/admin/series", Role.ADMIN),
    ("/api/admin/events", Role.ADMIN),
    ("/api/clubs", None),
    ("/api/events", None),
]


async def headers_for(client, caplog, path: str, role: Role | None) -> dict[str, str]:
    if role is None:
        return {}
    # One account per path, because `as_role` creates the account and two tests sharing an
    # address would be the same person with the union of their roles.
    address = f"page-{path.strip('/').replace('/', '-')}@example.com"
    return await as_role(client, caplog, address, role)


class TestEveryPagedListSpeaksTheSameShape:
    """As a screen, every list answers the same way — so one table can show them all."""

    @pytest.mark.parametrize("path,role", PAGED)
    async def test_the_answer_is_an_envelope(self, client, caplog, path, role):
        response = await client.get(path, headers=await headers_for(client, caplog, path, role))
        assert response.status_code == 200, response.text

        page = response.json()
        assert set(page) == {"items", "total", "limit", "offset"}
        assert isinstance(page["items"], list)
        assert page["offset"] == 0
        assert page["total"] >= len(page["items"])

    @pytest.mark.parametrize("path,role", PAGED)
    async def test_the_page_size_is_honoured_and_capped(self, client, caplog, path, role):
        head = await headers_for(client, caplog, path, role)

        page = (await client.get(path, params={"limit": 2}, headers=head)).json()
        assert page["limit"] == 2
        assert len(page["items"]) <= 2

        # The cap is a refusal, not a silent clamp: a caller who asked for 5000 and got 100
        # would page through 5% of the list believing they had seen all of it.
        assert (await client.get(path, params={"limit": 5000}, headers=head)).status_code == 422

    @pytest.mark.parametrize("path,role", PAGED)
    async def test_an_offset_past_the_end_is_an_empty_page(self, client, caplog, path, role):
        head = await headers_for(client, caplog, path, role)
        page = (await client.get(path, params={"offset": 10_000}, headers=head)).json()

        assert page["items"] == []
        # Still says how many there are — that is what lets the screen offer "back to the
        # first page" rather than an error.
        assert page["total"] >= 0
        assert page["offset"] == 10_000

    @pytest.mark.parametrize("path,role", PAGED)
    async def test_an_unknown_sort_column_is_refused(self, client, caplog, path, role):
        head = await headers_for(client, caplog, path, role)
        response = await client.get(path, params={"sort": "no-such-column"}, headers=head)

        assert response.status_code == 422, response.text
        problem = response.json()
        assert problem["type"] == "/errors/unknown-sort-column"
        # The refusal names what it would have accepted, so the caller does not have to
        # read the router to find out.
        assert problem["sortable"]

    @pytest.mark.parametrize("path,role", PAGED)
    async def test_paging_walks_the_list_without_repeating_a_row(self, client, caplog, path, role):
        head = await headers_for(client, caplog, path, role)
        first = (await client.get(path, params={"limit": 3, "offset": 0}, headers=head)).json()
        second = (await client.get(path, params={"limit": 3, "offset": 3}, headers=head)).json()

        if first["total"] < 4:
            pytest.skip(f"{path} holds fewer than four rows in the seed")

        ids = [item["id"] for item in first["items"]]
        assert len(set(ids)) == len(ids)
        assert not set(ids) & {item["id"] for item in second["items"]}


class TestSearchingAndSorting:
    """As an administrator, I want the list I am looking at to be the list I asked for."""

    async def test_the_total_counts_the_filter_not_the_table(self, client, caplog):
        head = await as_role(client, caplog, "page-total@example.com", Role.ADMIN)

        everyone = (await client.get("/api/admin/sailors", headers=head)).json()
        matching = (await client.get("/api/admin/sailors", params={"q": "a"}, headers=head)).json()

        assert everyone["total"] > 0
        assert matching["total"] <= everyone["total"]
        # The number the paging control is built from. Counting the unfiltered table would
        # promise pages of results that the search cannot fill.
        assert matching["total"] >= len(matching["items"])

    async def test_sorting_reverses_with_a_minus(self, client, caplog):
        head = await as_role(client, caplog, "page-sort@example.com", Role.ADMIN)

        up = (
            await client.get(
                "/api/admin/sailors", params={"sort": "last_name", "limit": 50}, headers=head
            )
        ).json()
        down = (
            await client.get(
                "/api/admin/sailors", params={"sort": "-last_name", "limit": 50}, headers=head
            )
        ).json()

        ascending = [s["last_name"] for s in up["items"]]
        descending = [s["last_name"] for s in down["items"]]
        assert ascending == sorted(ascending, key=str.lower)
        assert descending == sorted(descending, key=str.lower, reverse=True)

        # Not the reverse of each other: with 180 people and a page of 50, these are
        # opposite *ends* of the register. Which is the point — the first page of "Z first"
        # has to hold different people from the first page of "A first".
        assert descending[0].lower() >= ascending[-1].lower()

    async def test_the_whole_list_is_reachable_by_paging(self, client, caplog):
        """The old `/api/sailors` answered with at most 500 rows and no way to ask for 501."""
        head = await as_role(client, caplog, "page-walk@example.com", Role.ADMIN)

        seen: list[int] = []
        offset = 0
        while True:
            page = (
                await client.get(
                    "/api/admin/sailors", params={"limit": 100, "offset": offset}, headers=head
                )
            ).json()
            seen.extend(item["id"] for item in page["items"])
            offset += page["limit"]
            if offset >= page["total"]:
                break

        assert len(seen) == len(set(seen)) == page["total"]
        assert page["total"] >= 180  # the seed registers one sailor per squad place


#: Every paged list someone would *search*, with a term the seed already answers to.
#: Same idea as ``PAGED``: the rules below hold for all of them, so a new searchable list
#: is one line rather than five tests.
SEARCHABLE = [
    ("/api/clubs", None, "hamburg"),
    ("/api/events", None, "act"),
    ("/api/admin/clubs", Role.ADMIN, "hamburg"),
    ("/api/admin/events", Role.ADMIN, "act"),
    ("/api/admin/series", Role.ADMIN, "2026"),
    ("/api/admin/sailors", Role.ADMIN, "a"),
    ("/api/auth/users", Role.ADMIN, "example.com"),
]


async def unique_club(client, headers, name: str, short: str, city: str) -> int:
    response = await client.post(
        "/api/admin/clubs",
        headers=headers,
        json={"name": name, "short_name": short, "city": city},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def seed_id(model, slug: str) -> int:
    """The primary key of a seeded row, which the API offers no way to look up by slug."""
    async with SessionLocal() as session:
        return (await session.execute(select(model.id).where(model.slug == slug))).scalar_one()


async def make_event(client, headers, title: str, **fields) -> int:
    body = {"title": title, "starts_on": "2026-09-05", "published": True, **fields}
    response = await client.post("/api/admin/events", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestEverySearchableListSearchesTheSameWay:
    """As someone looking for one row, I want the server to find it — on any of the lists.

    The searches themselves are the point of the story: a screen that fetches a page and
    filters it in the browser can only ever find what happened to be on that page.
    """

    @pytest.mark.parametrize("path,role,term", SEARCHABLE)
    async def test_a_search_that_matches_nothing_is_an_empty_page(
        self, client, caplog, path, role, term
    ):
        head = await headers_for(client, caplog, path, role)
        response = await client.get(path, params={"q": "quokkaburg"}, headers=head)

        assert response.status_code == 200, response.text
        page = response.json()
        assert page["items"] == []
        # And `total` follows the filter rather than the table: the same list without a
        # search has rows in it.
        assert page["total"] == 0
        assert (await client.get(path, headers=head)).json()["total"] > 0

    @pytest.mark.parametrize("path,role,term", SEARCHABLE)
    async def test_the_total_counts_the_matches_and_not_the_page(
        self, client, caplog, path, role, term
    ):
        head = await headers_for(client, caplog, path, role)
        page = (await client.get(path, params={"q": term, "limit": 1}, headers=head)).json()

        assert len(page["items"]) == 1
        # The number the paging control is built from. Counting the page would make every
        # search claim to be complete on its first screen.
        assert page["total"] > 1

    @pytest.mark.parametrize("path,role,term", SEARCHABLE)
    async def test_searching_ignores_case(self, client, caplog, path, role, term):
        head = await headers_for(client, caplog, path, role)
        lower = (await client.get(path, params={"q": term.lower()}, headers=head)).json()
        upper = (await client.get(path, params={"q": term.upper()}, headers=head)).json()

        assert lower["total"] > 0
        assert upper["total"] == lower["total"]
        assert [i["id"] for i in upper["items"]] == [i["id"] for i in lower["items"]]

    @pytest.mark.parametrize("path,role,term", SEARCHABLE)
    async def test_whitespace_alone_is_not_a_search(self, client, caplog, path, role, term):
        """An emptied search box must show the whole list, not nothing.

        The trap is the `%%` pattern a blank term turns into: it looks like "match
        everything" and quietly drops every row whose searched columns are all NULL.
        """
        head = await headers_for(client, caplog, path, role)
        blank = (await client.get(path, params={"q": "   "}, headers=head)).json()
        unfiltered = (await client.get(path, headers=head)).json()

        assert blank["total"] == unfiltered["total"]


class TestSearchingTheClubList:
    """As a visitor, I want to find my club by what I remember of it."""

    async def test_searching_the_club_list_finds_a_club_by_its_city(self, client):
        """Tutzing is in DTYC's *city*, not in its name — so this can only be the search."""
        page = (await client.get("/api/clubs", params={"q": "tutzing"})).json()

        assert "DTYC" in {club["short_name"] for club in page["items"]}
        assert all("tutzing" in club["city"].lower() for club in page["items"])

    async def test_a_club_that_is_not_public_cannot_be_found_by_searching(self, client, caplog):
        """Searching narrows what a visitor may see; it never widens it (Story VA-8).

        A club is public only once it is registered for a published series — and a search
        term is not a way around that.
        """
        head = await as_role(client, caplog, "page-hidden-club@example.com", Role.ADMIN)
        await unique_club(client, head, "Quokka Segelclub", "QUOKKA", "Quokkastadt")

        public = (await client.get("/api/clubs", params={"q": "quokka"})).json()
        assert public["total"] == 0

        # The admin list is the one that has to find it — that is where it gets registered.
        admin = (await client.get("/api/admin/clubs", params={"q": "quokka"}, headers=head)).json()
        assert [club["short_name"] for club in admin["items"]] == ["QUOKKA"]


class TestSearchingTheEventCalendar:
    """As a visitor, I want to find a matchday by where it is sailed or who runs it."""

    async def test_searching_the_calendar_finds_an_event_by_its_venue(self, client, caplog, ids):
        """The venue is not in the title, so only a join can find this one."""
        head = await as_role(client, caplog, "page-event-venue@example.com", Role.ADMIN)
        event_id = await make_event(
            client,
            head,
            "Wombat Cup",
            venue_id=await seed_id(Venue, "berlin-wannsee"),
        )

        found = {
            event["id"]
            for event in (
                await client.get("/api/events", params={"q": "wannsee", "limit": 100})
            ).json()["items"]
        }
        assert event_id in found
        # And the search narrows: an act sailed somewhere else is not in the answer.
        assert ids.event("dsbl-1-2026-act-1") not in found

    async def test_searching_the_calendar_finds_an_event_by_its_host_club(
        self, client, caplog, ids
    ):
        head = await as_role(client, caplog, "page-event-host@example.com", Role.ADMIN)
        event_id = await make_event(
            client,
            head,
            "Wombat Trophy",
            host_club_id=await seed_id(Club, "fsc"),
        )

        found = {
            event["id"]
            for event in (
                await client.get("/api/events", params={"q": "flensburger", "limit": 100})
            ).json()["items"]
        }
        assert event_id in found
        assert ids.event("dsbl-1-2026-act-1") not in found

    async def test_the_calendar_counts_every_match_even_off_the_page(self, client, caplog):
        """Three of them, a page holding two, and a count that says three."""
        head = await as_role(client, caplog, "page-event-count@example.com", Role.ADMIN)
        for number in (1, 2, 3):
            await make_event(client, head, f"Pangolin Regatta {number}")

        page = (await client.get("/api/events", params={"q": "pangolin", "limit": 2})).json()
        assert page["total"] == 3
        assert len(page["items"]) == 2

    async def test_searching_narrows_the_year_it_is_asked_for(self, client, ids):
        """A search and a filter are applied together, not one instead of the other.

        Worth its own test because the year filter joins the series and the search joins
        the venue and the host: three joins that have to be one readable query.
        """
        page = (
            await client.get("/api/events", params={"q": "kiel", "year": 2026, "limit": 100})
        ).json()

        found = {event["id"] for event in page["items"]}
        assert ids.event("dsbl-1-2026-act-2") in found  # the act sailed in Kiel
        assert ids.event("dsbl-1-2026-act-1") not in found

    async def test_a_draft_event_is_not_findable_by_searching(self, client, caplog):
        """The public calendar answers for published events only — search included."""
        head = await as_role(client, caplog, "page-event-draft@example.com", Role.ADMIN)
        event_id = await make_event(client, head, "Numbat Invitational", published=False)

        assert (await client.get("/api/events", params={"q": "numbat"})).json()["total"] == 0

        admin = (await client.get("/api/admin/events", params={"q": "numbat"}, headers=head)).json()
        assert [event["id"] for event in admin["items"]] == [event_id]


class TestSearchingTheSeriesList:
    """As an administrator planning several years ahead, I want to find one series."""

    async def test_searching_the_series_list_finds_a_series_by_its_short_name(self, client, caplog):
        """'SCL' is only in the short name; the series is called Sailing Champions League."""
        head = await as_role(client, caplog, "page-series@example.com", Role.ADMIN)
        page = (await client.get("/api/admin/series", params={"q": "scl"}, headers=head)).json()

        assert [series["short_name"] for series in page["items"]] == ["SCL 2026"]
