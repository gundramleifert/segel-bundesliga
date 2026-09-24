"""User Story B-5: follow live updates.

The transport half of the story: a spectator's page holds a stream open on the event, the
race committee enters a result, the stream says "something changed" and the page refetches.
What these tests pin down:

* **A published event streams; a draft does not** — and "draft" is the public router's own
  predicate, so an event published inside a draft series is a draft too.
* **Live is an event.** The only topic is ``event:{id}``; a series table listens on its
  running event, because that is what changes it.
* **Every writer publishes, after its commit:** a result, the event transitions (publish
  and unpublish included — they change who may see the event), the draw.
* **The token is a version, not the data.** The frame names the topic and a number; the
  page refetches through the same client it always used.

Reading a stream over the ASGI transport needs one trick: ``httpx`` runs the application
to completion before it hands back a response, and a live stream never completes on its
own. So the stream is opened in a task, the change is made, and then the hub's own
``shutdown`` ends every stream — the same thing the server does when it stops — and the
task's response then holds everything that was sent. The hub stays usable afterwards.
"""

import asyncio

from app.live import hub
from app.models.auth import Role
from tests.stories.test_create_event import admin, event_with_participants
from tests.stories.test_create_series import as_role
from tests.stories.test_event_lifecycle import draw, enter_result, first_race


async def stream_until(client, topic: str, change, headers: dict[str, str] | None = None) -> str:
    """Opens the stream, runs ``change`` once someone is listening, returns what was sent."""
    listening = asyncio.create_task(client.get(f"/api/live?topic={topic}", headers=headers))
    for _ in range(200):
        if hub.subscribers(topic) >= 1:
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError(f"nobody subscribed to {topic} — did the stream answer 404?")

    await change()
    await hub.shutdown()
    response = await listening
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return response.text


class TestTheStream:
    """B-5: As a spectator I want the page to change when a result comes in."""

    async def test_a_result_reaches_a_spectator_of_a_published_event(self, client, caplog):
        headers = await admin(client, caplog, "live1@example.com")
        event_id = await event_with_participants(client, headers, "Live Cup", "2027-07-03")
        await draw(client, headers, event_id)
        race_id, boats = await first_race(event_id)
        version_before = hub.version(f"event:{event_id}")

        sent = await stream_until(
            client,
            f"event:{event_id}",
            lambda: enter_result(client, headers, event_id, race_id, boats),
        )

        assert "retry: 3000" in sent
        assert "event: change" in sent
        assert f'"topic":"event:{event_id}"' in sent
        assert f'"version":{version_before + 1}' in sent

    async def test_a_draft_event_has_no_stream(self, client, caplog):
        headers = await admin(client, caplog, "live3@example.com")
        created = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Secret Cup", "starts_on": "2027-07-17", "published": False},
        )
        assert created.status_code == 201, created.text

        response = await client.get(f"/api/live?topic=event:{created.json()['id']}")
        assert response.status_code == 404
        assert response.json()["type"] == "/errors/event-not-found"

    async def test_a_published_event_in_a_draft_series_is_a_draft_too(self, client, caplog):
        headers = await as_role(client, caplog, "live4@example.com", Role.ADMIN)
        series = await client.post(
            "/api/admin/series",
            headers=headers,
            json={"name": "Hidden Series 2028", "year": 2028},
        )
        assert series.status_code == 201, series.text
        created = await client.post(
            "/api/admin/events",
            headers=headers,
            json={
                "title": "Hidden Act",
                "starts_on": "2028-05-06",
                "series": series.json()["id"],
                "published": True,
            },
        )
        assert created.status_code == 201, created.text

        response = await client.get(f"/api/live?topic=event:{created.json()['id']}")
        assert response.status_code == 404

    async def test_live_is_an_event_and_nothing_else_is_a_topic(self, client, ids):
        # A series is never live — it only has an event that is. The series table listens
        # on that event, so there is no `series:` topic to keep in step.
        for topic in ("kitchen:sink", f"series:{ids.series('dsbl-1-2026')}", "event:x"):
            response = await client.get(f"/api/live?topic={topic}")
            assert response.status_code == 422, topic
            assert response.json()["type"] == "/errors/live-topic-invalid"

    async def test_a_reconnecting_page_that_missed_a_change_hears_it_at_once(self, client, caplog):
        headers = await admin(client, caplog, "live5@example.com")
        event_id = await event_with_participants(client, headers, "Reconnect Cup", "2027-07-24")
        topic = f"event:{event_id}"
        hub.publish(topic)
        behind = hub.version(topic) - 1

        # The browser sends the last id it saw; the hub is one ahead of it, so the very
        # first frame after `retry:` is a change — no waiting for the next result.
        sent = await stream_until(
            client, topic, lambda: asyncio.sleep(0), headers={"Last-Event-ID": str(behind)}
        )
        assert f'"version":{behind + 1}' in sent


class TestEveryWriterPublishes:
    """B-5: every change a live page must hear bumps the event's version."""

    async def test_each_event_transition_publishes_including_visibility(self, client, caplog):
        headers = await admin(client, caplog, "live6@example.com")
        event_id = await event_with_participants(client, headers, "Transition Cup", "2027-08-07")
        await draw(client, headers, event_id)
        topic = f"event:{event_id}"

        for action in ("unpublish", "publish", "start", "finish", "reopen", "cancel", "reopen"):
            before = hub.version(topic)
            response = await client.post(f"/api/admin/events/{event_id}/{action}", headers=headers)
            assert response.status_code == 200, (action, response.text)
            assert hub.version(topic) == before + 1, f"{action} did not publish"

    async def test_the_draw_publishes(self, client, caplog):
        headers = await admin(client, caplog, "live7@example.com")
        event_id = await event_with_participants(client, headers, "Draw Cup", "2027-08-14")
        before = hub.version(f"event:{event_id}")

        await draw(client, headers, event_id)

        assert hub.version(f"event:{event_id}") == before + 1


class TestWhereToGoNow:
    """B-5: if there is no matchday now, the page leads to the next date."""

    async def test_now_names_a_running_event_when_there_is_one(self, client, caplog):
        headers = await admin(client, caplog, "live8@example.com")
        event_id = await event_with_participants(client, headers, "Now Cup", "2027-09-04")
        await draw(client, headers, event_id)
        started = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
        assert started.status_code == 200, started.text

        response = await client.get("/api/live/now")
        assert response.status_code == 200
        body = response.json()
        assert body["running"] is True
        assert body["event"]["status"] == "live"

    async def test_now_falls_back_to_the_next_published_date(self, client, caplog):
        # Whatever else the suite left running, a `now` answer is never empty while any
        # published event lies ahead — the seed alone guarantees one.
        response = await client.get("/api/live/now")
        assert response.status_code == 200
        body = response.json()
        assert body["event"] is not None
        assert body["event"]["published"] is True
