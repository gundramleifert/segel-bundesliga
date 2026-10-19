"""Story R-1: editorial writes news and press releases on the site.

A post is a draft until editorial publishes it, belongs to one league or to the
association, and keeps its address when its title is corrected.
"""

import io

from PIL import Image

from app.models.auth import Role
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers


async def editor(client, caplog, email: str = "posts-editor@example.com") -> dict[str, str]:
    await make_user(email, Role.EDITOR)
    return auth_headers(await login_as(client, email, caplog))


async def league_id(client, slug: str) -> int:
    return (await client.get(f"/api/leagues/{slug}")).json()["league"]["id"]


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


class TestReadPosts:
    """As a fan I read a league's news and its press releases — Stories R-1, B-14."""

    async def test_a_league_shows_its_news_and_the_associations_newest_first(self, client):
        """R-1: a league's news are its own posts and the association's, newest first."""
        news = (await client.get("/api/posts", params={"league": "2-liga"})).json()

        assert news, "the seed carries the pages' articles"
        assert {post["league"] for post in news} <= {"2-liga", None}
        assert any(post["league"] is None for post in news)
        dates = [post["published_on"] for post in news]
        assert dates == sorted(dates, reverse=True)
        assert all(post["kind"] == "news" for post in news)

    async def test_a_list_carries_no_text_its_cards_do_not_show(self, client):
        """R-1: a list is cards and lines — the text is read on the article's own page."""
        news = (await client.get("/api/posts", params={"league": "1-liga"})).json()

        assert news
        assert all("body" not in post and "quote" not in post for post in news)
        assert all(post["slug"] and post["title"] for post in news)

    async def test_an_article_has_its_own_address(self, client):
        """R-1: one article by its slug, with the text as paragraphs and its picture."""
        article = (await client.get("/api/posts/nrv-takes-the-lead")).json()

        assert article["league"] == "1-liga"
        assert article["quote_by"] == "the winning helm"
        assert article["body"].count("<p>") == 3
        assert article["photo_url"].startswith("https://")
        assert article["example"] is True

    async def test_press_releases_are_a_list_of_their_own(self, client):
        """R-1: the press centre lists releases, not articles."""
        press = (
            await client.get("/api/posts", params={"kind": "press", "league": "1-liga"})
        ).json()

        assert press
        assert all(post["kind"] == "press" for post in press)

    async def test_an_unknown_article_is_not_found(self, client):
        response = await client.get("/api/posts/no-such-article")
        assert response.status_code == 404
        assert response.json()["type"].endswith("/post-not-found")


class TestWritePosts:
    """As editorial I write, publish, correct and withdraw posts — Story R-1."""

    async def test_a_draft_is_invisible_until_editorial_publishes_it(self, client, caplog):
        """R-1: saving never requires publishing; the public site shows published posts only."""
        headers = await editor(client, caplog)
        created = await client.post(
            "/api/admin/posts",
            headers=headers,
            json={
                "title": "Junioren-Liga: entries open",
                "league_id": await league_id(client, "junioren-liga"),
                "teaser": "Every club may enter a youth crew.",
                "body": "<p>First paragraph.</p><p>Second paragraph.</p>",
                "published_on": "2026-10-19",
            },
        )
        assert created.status_code == 201, created.text
        post = created.json()
        assert post["published"] is False
        assert post["slug"] == "junioren-liga-entries-open"

        assert (await client.get(f"/api/posts/{post['slug']}")).status_code == 404
        listed = (await client.get("/api/posts", params={"league": "junioren-liga"})).json()
        assert post["slug"] not in [p["slug"] for p in listed]

        published = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=headers, json={"published": True}
        )
        assert published.status_code == 200, published.text

        public = (await client.get(f"/api/posts/{post['slug']}")).json()
        assert public["league"] == "junioren-liga"
        listed = (await client.get("/api/posts", params={"league": "junioren-liga"})).json()
        assert listed[0]["slug"] == post["slug"]
        other = (await client.get("/api/posts", params={"league": "1-liga"})).json()
        assert post["slug"] not in [p["slug"] for p in other]

        withdrawn = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=headers, json={"published": False}
        )
        assert withdrawn.json()["published"] is False
        assert (await client.get(f"/api/posts/{post['slug']}")).status_code == 404

        drafts = await client.get("/api/admin/posts", headers=headers, params={"q": "entries open"})
        assert [p["id"] for p in drafts.json()["items"]] == [post["id"]]

    async def test_the_associations_post_appears_in_every_league(self, client, caplog):
        """R-1: a post without a league is the association's, shown on every league's page."""
        headers = await editor(client, caplog)
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={"title": "General assembly in March", "published": True},
            )
        ).json()

        assert post["league"] is None
        for league in ("1-liga", "dsl-pokal"):
            listed = (await client.get("/api/posts", params={"league": league})).json()
            assert post["slug"] in [p["slug"] for p in listed]

    async def test_the_address_is_made_once(self, client, caplog):
        """R-1: correcting the title keeps the slug; a taken slug gets a number."""
        headers = await editor(client, caplog)
        first = (
            await client.post("/api/admin/posts", headers=headers, json={"title": "Season review"})
        ).json()
        second = (
            await client.post("/api/admin/posts", headers=headers, json={"title": "Season review"})
        ).json()
        assert second["slug"] == f"{first['slug']}-2"

        corrected = await client.patch(
            f"/api/admin/posts/{first['id']}",
            headers=headers,
            json={"title": "Season review 2026", "teaser": "  "},
        )
        assert corrected.json()["slug"] == first["slug"]
        assert corrected.json()["title"] == "Season review 2026"
        assert corrected.json()["teaser"] is None

        for blank in (None, "   "):
            refused = await client.patch(
                f"/api/admin/posts/{first['id']}", headers=headers, json={"title": blank}
            )
            assert refused.status_code == 422, blank

    async def test_a_post_is_deleted(self, client, caplog):
        headers = await editor(client, caplog)
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={"title": "A release written twice", "kind": "press", "published": True},
            )
        ).json()

        assert (
            await client.delete(f"/api/admin/posts/{post['id']}", headers=headers)
        ).status_code == 204
        assert (await client.get(f"/api/posts/{post['slug']}")).status_code == 404
        missing = await client.get(f"/api/admin/posts/{post['id']}", headers=headers)
        assert missing.status_code == 404

    async def test_only_editorial_writes(self, client, caplog):
        """R-1: the site's editor and admin — not a club's organizer, not a guest."""
        assert (
            await client.post("/api/admin/posts", json={"title": "Guest post"})
        ).status_code == 401

        await make_user("posts-manager@example.com", Role.TEAM_MANAGER)
        manager = auth_headers(await login_as(client, "posts-manager@example.com", caplog))
        refused = await client.post(
            "/api/admin/posts", headers=manager, json={"title": "Club post"}
        )
        assert refused.status_code == 403
        assert (await client.get("/api/admin/posts", headers=manager)).status_code == 403

        headers = await admin(client, caplog, "posts-admin@example.com")
        allowed = await client.post(
            "/api/admin/posts", headers=headers, json={"title": "Admin post"}
        )
        assert allowed.status_code == 201

    async def test_a_picture_is_uploaded_and_served(self, client, caplog):
        """R-1, R-2: a JPEG, PNG or WebP, checked by content, into the library, served publicly."""
        headers = await editor(client, caplog)
        uploaded = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("harbour.png", png(), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        url = uploaded.json()["url"]
        assert url.startswith("/api/media/")

        served = await client.get(url)
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/jpeg"

        webp = io.BytesIO()
        Image.new("RGB", (40, 30), "navy").save(webp, format="WEBP")
        from_phone = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("harbour.webp", webp.getvalue(), "image/webp")},
        )
        assert from_phone.status_code == 201, from_phone.text
        stored = await client.get(from_phone.json()["url"])
        assert stored.headers["content-type"] == "image/jpeg"

        refused = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("notes.pdf", b"%PDF-1.4 not a picture", "application/pdf")},
        )
        assert refused.status_code == 422
        assert refused.json()["type"].endswith("/media-invalid-type")

        assert (await client.get("/api/media/..%2Fsbl.db")).status_code == 404

    async def test_the_title_is_a_field_never_the_texts_first_line(self, client, caplog):
        """R-1: a text that starts with the title again is refused — nothing is cut away."""
        headers = await editor(client, caplog)
        refused = await client.post(
            "/api/admin/posts",
            headers=headers,
            json={"title": "Harbour day", "body": "<h2>Harbour day</h2><p>Open doors.</p>"},
        )
        assert refused.status_code == 422
        assert refused.json()["type"].endswith("/post-title-in-text")

        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={"title": "Harbour day", "body": "<p>Open doors.</p><h2>Harbour day</h2>"},
            )
        ).json()
        # The same words further down are text, and stay as they were written.
        assert post["body"] == "<p>Open doors.</p><h2>Harbour day</h2>"

        bold = await client.patch(
            f"/api/admin/posts/{post['id']}",
            headers=headers,
            json={"body": "<p><strong> harbour  DAY </strong></p><p>Open doors.</p>"},
        )
        assert bold.status_code == 422
        renamed = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=headers, json={"title": "Open doors."}
        )
        assert renamed.status_code == 422
        unchanged = await client.get(f"/api/admin/posts/{post['id']}", headers=headers)
        assert unchanged.json()["title"] == "Harbour day"
        assert unchanged.json()["body"] == "<p>Open doors.</p><h2>Harbour day</h2>"

    async def test_the_text_has_one_kind_of_heading(self, client, caplog):
        """R-1: a pasted title (h1) or subheading (h3) arrives as the text's one heading."""
        headers = await editor(client, caplog)
        post = await client.post(
            "/api/admin/posts",
            headers=headers,
            json={
                "title": "Levels",
                "body": "<p>Intro</p><h1>From Word</h1><h3 class='x'>Smaller</h3><p>End</p>",
            },
        )
        assert post.json()["body"] == "<p>Intro</p><h2>From Word</h2><h2>Smaller</h2><p>End</p>"

    async def test_the_text_keeps_its_formatting_and_nothing_else(self, client, caplog):
        """R-1: the editor's HTML is cleaned to what its toolbar makes, on every write."""
        headers = await editor(client, caplog)
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={
                    "title": "Formatted text",
                    "body": (
                        '<h2 style="color:red">Sunday</h2>'
                        '<p onclick="steal()">Six <strong>wins</strong>, <em>no</em> fouls.'
                        "<script>alert(1)</script></p>"
                        '<ul><li><a href="/1-liga/standings">Standings</a></li>'
                        '<li><a href="javascript:alert(1)">Trap</a></li></ul>'
                        '<img src="/api/posts/photos/abc.jpg" alt="Harbour" onerror="steal()">'
                        '<table style="min-width: 50px"><tbody><tr>'
                        '<th colspan="2" style="width: 9px"><p>Club</p></th></tr></tbody></table>'
                    ),
                },
            )
        ).json()

        body = post["body"]
        assert "<h2>Sunday</h2>" in body
        assert "<strong>wins</strong>" in body and "<em>no</em>" in body
        assert 'href="/1-liga/standings"' in body
        assert 'rel="noopener noreferrer"' in body
        assert '<img src="/api/posts/photos/abc.jpg" alt="Harbour">' in body
        assert '<th colspan="2"><p>Club</p></th>' in body
        for gone in ("script", "onclick", "onerror", "style", "javascript:"):
            assert gone not in body

        emptied = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=headers, json={"body": "<p></p>"}
        )
        assert emptied.json()["body"] == ""
