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


#: A library address, as the editor stores it.
OURS = "/api/media/0123456789abcdef0123456789abcdef.webp"


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


class TestReadPosts:
    """As a fan I read a league's news and its press releases — Stories R-1, B-14."""

    async def test_a_league_shows_its_news_and_the_associations_newest_first(self, client):
        """R-1: a league's news are its own posts and the association's, newest first."""
        news = (await client.get("/api/posts", params={"league": "2-liga"})).json()["items"]

        assert news, "the seed carries the pages' articles"
        assert {post["league"] for post in news} <= {"2-liga", None}
        assert any(post["league"] is None for post in news)
        dates = [post["published_on"] for post in news]
        assert dates == sorted(dates, reverse=True)
        assert all(post["kind"] == "news" for post in news)

    async def test_a_list_carries_no_text_its_cards_do_not_show(self, client):
        """R-1: a list is cards and lines — the text is read on the article's own page."""
        news = (await client.get("/api/posts", params={"league": "1-liga"})).json()["items"]

        assert news
        assert all("body" not in post and "quote" not in post for post in news)
        assert all(post["slug"] and post["title"] for post in news)

    async def test_an_article_has_its_own_address(self, client):
        """R-1: one article by its slug, with the text as paragraphs — and no picture of
        another site: the seed's examples go without one (decided 2026-10-23)."""
        article = (await client.get("/api/posts/asvw-takes-the-lead")).json()

        assert article["league"] == "1-liga"
        assert article["quote_by"] == "the winning helm"
        assert article["body"].count("<p>") == 3
        assert article["photo_url"] is None
        assert article["example"] is True

    async def test_press_releases_are_a_list_of_their_own(self, client):
        """R-1: the press centre lists releases, not articles."""
        press = (
            await client.get("/api/posts", params={"kind": "press", "league": "1-liga"})
        ).json()["items"]

        assert press
        assert all(post["kind"] == "press" for post in press)

    async def test_the_association_s_own_release_is_on_every_league_s_press_page(self, client):
        """R-1: the Wannsee release of 2026-09-16, as editorial wrote it — headings, quotes
        and links kept, cleaned like any write — in the 1. and the 2. Liga's press centre."""
        for league in ("1-liga", "2-liga"):
            press = (
                await client.get("/api/posts", params={"kind": "press", "league": league})
            ).json()["items"]
            release = next(p for p in press if p["title"].startswith("Segel-Bundesliga am Wannsee"))
            assert release["published_on"] == "2026-09-16" and release["example"] is False

        article = (await client.get(f"/api/posts/{release['slug']}")).json()
        assert article["author"] == "Sven Jürgensen"
        body = article["body"]
        assert body.count("<h2>") == 12 and body.count("<blockquote>") == 3
        assert "Tobias Schadewaldt, Skipper NRV Bundesliga Team" in body
        assert 'href="mailto:presse@deutsche-segelliga.de"' in body

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
        listed = (await client.get("/api/posts", params={"league": "junioren-liga"})).json()[
            "items"
        ]
        assert post["slug"] not in [p["slug"] for p in listed]

        published = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=headers, json={"published": True}
        )
        assert published.status_code == 200, published.text

        public = (await client.get(f"/api/posts/{post['slug']}")).json()
        assert public["league"] == "junioren-liga"
        listed = (await client.get("/api/posts", params={"league": "junioren-liga"})).json()[
            "items"
        ]
        assert listed[0]["slug"] == post["slug"]
        other = (await client.get("/api/posts", params={"league": "1-liga"})).json()["items"]
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
            listed = (await client.get("/api/posts", params={"league": league})).json()["items"]
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
        assert served.headers["content-type"] == "image/webp"

        webp = io.BytesIO()
        Image.new("RGB", (40, 30), "navy").save(webp, format="WEBP")
        from_phone = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("harbour.webp", webp.getvalue(), "image/webp")},
        )
        assert from_phone.status_code == 201, from_phone.text
        stored = await client.get(from_phone.json()["url"])
        assert stored.headers["content-type"] == "image/webp"

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

    async def test_a_title_with_an_ampersand_is_read_as_the_editor_reads_it(self, client, caplog):
        """R-1: the text is compared as a reader sees it — `&amp;` is `&`, as in the editor."""
        headers = await editor(client, caplog)
        refused = await client.post(
            "/api/admin/posts",
            headers=headers,
            json={
                "title": "Kiel & Travemünde",
                "body": "<p>Kiel &amp; Travemünde</p><p>Two acts.</p>",
            },
        )
        assert refused.status_code == 422
        assert refused.json()["type"].endswith("/post-title-in-text")

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
                        f'<img src="{OURS}" alt="Harbour" onerror="steal()">'
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
        assert f'<img src="{OURS}" alt="Harbour">' in body
        assert '<th colspan="2"><p>Club</p></th>' in body
        for gone in ("script", "onclick", "onerror", "style", "javascript:"):
            assert gone not in body

        emptied = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=headers, json={"body": "<p></p>"}
        )
        assert emptied.json()["body"] == ""


def photo(size: tuple[int, int]) -> bytes:
    """A picture no other test uploaded — the library would answer that one's entry."""
    import secrets

    buffer = io.BytesIO()
    image = Image.new("RGB", size, tuple(secrets.randbelow(256) for _ in range(3)))
    image.putpixel((secrets.randbelow(size[0]), secrets.randbelow(size[1])), (255, 255, 255))
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


class TestPicturesAndReading:
    """As editorial I use the library's pictures and read a draft before it goes out —
    Story R-1."""

    async def test_a_picture_from_another_site_is_refused(self, client, caplog):
        """R-1: an outside address in the text or as the picture is refused; ours are not."""
        headers = await editor(client, caplog)
        outside = "https://example.org/boat.jpg"
        for fields in (
            {"body": f'<p>Text</p><img src="{outside}" alt="">'},
            {"photo_url": outside},
        ):
            refused = await client.post(
                "/api/admin/posts", headers=headers, json={"title": "Outside", **fields}
            )
            assert refused.status_code == 422, fields
            assert refused.json()["type"].endswith("/post-picture-not-in-library")
            assert refused.json()["addresses"] == [outside]

        ours = await client.post(
            "/api/admin/posts",
            headers=headers,
            json={
                "title": "Ours",
                "photo_url": "/media/DSF3979.jpg",
                "body": '<p>Text</p><img src="/api/media/0123456789abcdef0123456789abcdef.webp">',
            },
        )
        assert ours.status_code == 201, ours.text

    async def test_a_seeded_example_keeps_its_picture_until_it_is_changed(self, client, caplog):
        """R-1: an outside address the post already has may stay; a new one may not. The
        seed links none any more, so the post gets one here, as older data may carry."""
        from app.db import SessionLocal
        from app.models import Post

        headers = await editor(client, caplog)
        listed = (await client.get("/api/admin/posts", headers=headers)).json()["items"]
        example = next(p for p in listed if p["example"])
        example["photo_url"] = "https://example.org/older-picture.jpg"
        async with SessionLocal() as session:
            (await session.get(Post, example["id"])).photo_url = example["photo_url"]
            await session.commit()
        kept = await client.patch(
            f"/api/admin/posts/{example['id']}",
            headers=headers,
            json={"title": example["title"] + " ", "photo_url": example["photo_url"]},
        )
        assert kept.status_code == 200, kept.text
        changed = await client.patch(
            f"/api/admin/posts/{example['id']}",
            headers=headers,
            json={"photo_url": "https://example.org/other.jpg"},
        )
        assert changed.status_code == 422

    async def test_the_reader_gets_the_librarys_alt_text_sizes_and_credit(self, client, caplog):
        """R-1, R-2: a library picture is shown with its size, its WebP sizes and its credit
        as a caption — taken from the library on every read."""
        headers = await editor(client, caplog)
        item = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("start.jpg", photo((2000, 1000)), "image/jpeg")},
                data={"alt": "The start", "credit": "A. Photographer"},
            )
        ).json()
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={
                    "title": "Pictures for readers",
                    "body": f'<p>Text</p><img src="{item["url"]}" alt="as pasted">',
                    "photo_url": item["url"],
                    "published": True,
                },
            )
        ).json()
        assert post["body"].endswith(f'<img src="{item["url"]}" alt="as pasted">')

        read = (await client.get(f"/api/posts/{post['slug']}")).json()
        name = item["url"].removeprefix("/api/media/").removesuffix(".webp")
        assert 'width="2000" height="1000"' in read["body"]
        assert f"/api/media/{name}-960.webp 960w" in read["body"]
        assert 'alt="The start"' in read["body"]
        assert "<figcaption>A. Photographer</figcaption>" in read["body"]
        assert f"/api/media/{name}-480.webp 480w" in read["photo_srcset"]

        await client.patch(
            f"/api/admin/media/{item['id']}", headers=headers, json={"credit": "B. Corrected"}
        )
        again = (await client.get(f"/api/posts/{post['slug']}")).json()
        assert "<figcaption>B. Corrected</figcaption>" in again["body"]

    async def test_a_draft_is_previewed_as_readers_will_see_it(self, client, caplog):
        """R-1: the preview answers what the public page would, for fields not even saved —
        for editorial alone, and under the rules of a save."""
        headers = await editor(client, caplog)
        item = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("p.jpg", photo((900, 600)), "image/jpeg")},
                data={"credit": "P. Review"},
            )
        ).json()
        fields = {"title": "Not yet", "body": f'<p>Hi</p><img src="{item["url"]}">'}
        preview = await client.post("/api/admin/posts/preview", headers=headers, json=fields)
        assert preview.status_code == 200, preview.text
        assert "<figcaption>P. Review</figcaption>" in preview.json()["body"]
        listed = (await client.get("/api/admin/posts", headers=headers)).json()["items"]
        assert "Not yet" not in {p["title"] for p in listed}

        repeated = await client.post(
            "/api/admin/posts/preview",
            headers=headers,
            json={"title": "Hi", "body": "<p>Hi</p>"},
        )
        assert repeated.status_code == 422
        guest = await client.post("/api/admin/posts/preview", json=fields)
        assert guest.status_code == 401

    async def test_a_public_list_is_paged(self, client):
        """R-1: the news page reaches every post, a page at a time."""
        first = (await client.get("/api/posts", params={"limit": 2})).json()
        assert len(first["items"]) == 2 and first["total"] > 2
        second = (await client.get("/api/posts", params={"limit": 2, "offset": 2})).json()
        assert not {p["id"] for p in first["items"]} & {p["id"] for p in second["items"]}

    async def test_the_admin_list_filters_by_league_and_state(self, client, caplog):
        """R-1: editorial's list filters by league (or the association's) and draft."""
        headers = await editor(client, caplog)
        await client.post("/api/admin/posts", headers=headers, json={"title": "A draft of ours"})
        association = (
            await client.get(
                "/api/admin/posts",
                headers=headers,
                params={"league": "association", "published": False, "limit": 100},
            )
        ).json()["items"]
        assert association
        assert all(p["league_id"] is None and not p["published"] for p in association)
        first = (
            await client.get("/api/admin/posts", headers=headers, params={"league": "1-liga"})
        ).json()["items"]
        assert first and {p["league_name"] for p in first} == {"1. Liga"}


class TestRegattaGallery:
    """As a reader I see a report's regatta photos at its end — Story R-1."""

    async def test_a_post_about_an_event_ends_with_its_pictures(self, client, caplog, ids):
        """R-1: naming an event puts its public pictures under the post, by themselves."""
        headers = await editor(client, caplog)
        event_id = ids.event("dsbl-1-2026-act-3")
        item = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("g.jpg", photo((800, 600)), "image/jpeg")},
                data={"event_id": str(event_id), "credit": "G. Allery"},
            )
        ).json()
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={"title": "Act 3 in pictures", "event_id": event_id, "published": True},
            )
        ).json()
        read = (await client.get(f"/api/posts/{post['slug']}")).json()
        assert read["regatta"] and read["event_id"] == event_id
        assert item["id"] in {p["id"] for p in read["gallery"]}
        assert read["gallery_total"] >= 1
        shown = next(p for p in read["gallery"] if p["id"] == item["id"])
        assert shown["credit"] == "G. Allery" and shown["srcset"]

        # Taken off the event, the picture leaves the post.
        await client.patch(
            f"/api/admin/media/{item['id']}", headers=headers, json={"event_id": None}
        )
        again = (await client.get(f"/api/posts/{post['slug']}")).json()
        assert item["id"] not in {p["id"] for p in again["gallery"]}

    async def test_a_post_about_nothing_has_no_gallery_and_a_series_replaces_the_event(
        self, client, caplog, ids
    ):
        """R-1: no regatta, no gallery; a post is about an event or a series, never both."""
        headers = await editor(client, caplog)
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={"title": "About nothing", "published": True},
            )
        ).json()
        assert (await client.get(f"/api/posts/{post['slug']}")).json()["gallery"] == []

        both = await client.post(
            "/api/admin/posts",
            headers=headers,
            json={
                "title": "About both",
                "event_id": ids.event("dsbl-1-2026-act-3"),
                "series_id": ids.series("dsbl-1-2026"),
            },
        )
        assert both.status_code == 422
        await client.patch(
            f"/api/admin/posts/{post['id']}",
            headers=headers,
            json={"event_id": ids.event("dsbl-1-2026-act-3")},
        )
        moved = (
            await client.patch(
                f"/api/admin/posts/{post['id']}",
                headers=headers,
                json={"series_id": ids.series("dsbl-1-2026")},
            )
        ).json()
        assert (moved["event_id"], moved["series_id"]) == (None, ids.series("dsbl-1-2026"))


class TestSeededPictures:
    """R-2: the league office's press pictures of the 2026 Finale, in the library."""

    async def test_a_club_s_finale_picture_is_on_its_league_s_media_page(self, client):
        """R-2: stored like an upload, credited "© DSBL GmbH", named after the club, under
        its series; a second run finds the same entry instead of a copy, and a picture that
        cannot be fetched is left out rather than failing the seed. Never fetched live: a
        picture is made here instead."""
        import io

        from PIL import Image

        from app.seed_media import PICTURES, seed_media

        def made(colour: str) -> bytes:
            buffer = io.BytesIO()
            Image.new("RGB", (64, 48), colour).save(buffer, "JPEG")
            return buffer.getvalue()

        nrv = next(p for p in PICTURES if p.club == "NRV")
        asvw = next(p for p in PICTURES if p.club == "ASVW")
        gone = next(p for p in PICTURES if p.club == "MYC")
        pictures = {nrv.name: made("navy"), asvw.name: made("teal")}

        def fetch(picture):
            return pictures.get(picture.name)

        assert await seed_media([nrv, asvw, gone], fetch) == 2
        assert await seed_media([nrv, asvw, gone], fetch) == 0

        first = (await client.get("/api/media", params={"league": "1-liga"})).json()["items"]
        picture = next(p for p in first if "Norddeutscher Regatta Verein" in p["alt"])
        assert picture["credit"] == "© DSBL GmbH"
        second = (await client.get("/api/media", params={"league": "2-liga"})).json()["items"]
        assert any("Akademischer Segelverein" in p["alt"] for p in second)
