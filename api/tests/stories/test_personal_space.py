"""My space (Stories S-5, S-6): a person's own documents and bank account.

The documents are seen by their owner and by the person's organizers — the managers of
the events they work at and of the clubs they belong to — and by nobody else; the bank
account by its owner alone.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog
from app.models.auth import Grant, Relation
from tests.stories.test_login_and_roles import _problem_code
from tests.stories.test_reimbursements import IBAN, _png, login, world


async def upload(client, headers, kind: str = "boat_licence_sea", **fields) -> dict:
    data = {"kind": kind} | {k: str(v) for k, v in fields.items()}
    response = await client.post(
        "/api/me/documents",
        headers=headers,
        data=data,
        files={"file": ("sbf.png", _png(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestMyDocuments:
    """Story S-5: labelled documents, uploaded and deleted by the owner."""

    async def test_upload_list_read_and_delete(self, client, caplog):
        me = await login(client, caplog, f"d-{uuid4().hex[:6]}@example.org")
        doc = await upload(client, me, valid_until="2020-01-01")
        assert doc["kind"] == "boat_licence_sea"
        # Past its date: shown as expired, not hidden.
        assert doc["expired"] is True

        listed = (await client.get("/api/me/documents", headers=me)).json()
        assert [d["id"] for d in listed] == [doc["id"]]
        assert (await client.get(f"/api/documents/{doc['id']}/file", headers=me)).content == _png()

        assert (
            await client.delete(f"/api/me/documents/{doc['id']}", headers=me)
        ).status_code == 204
        assert (await client.get("/api/me/documents", headers=me)).json() == []

    async def test_the_label_is_from_the_list_and_other_needs_a_title(self, client, caplog):
        me = await login(client, caplog, f"l-{uuid4().hex[:6]}@example.org")
        unknown = await client.post(
            "/api/me/documents",
            headers=me,
            data={"kind": "passport"},
            files={"file": ("x.png", _png(), "image/png")},
        )
        assert unknown.status_code == 422
        untitled = await client.post(
            "/api/me/documents",
            headers=me,
            data={"kind": "other"},
            files={"file": ("x.png", _png(), "image/png")},
        )
        assert _problem_code(untitled) == "document-title-required"
        assert (await upload(client, me, "other", title="Crane licence"))[
            "title"
        ] == "Crane licence"

    async def test_jury_and_race_officer_licences_are_labels_of_their_own(self, client, caplog):
        """S-5: a judge's and a race officer's licence are two labels — an organizer looking
        for the jury does not want the race officers — and the old combined one is gone."""
        me = await login(client, caplog, f"o-{uuid4().hex[:6]}@example.org")
        assert (await upload(client, me, "jury_licence"))["kind"] == "jury_licence"
        assert (await upload(client, me, "race_officer_licence"))["kind"] == "race_officer_licence"
        combined = await client.post(
            "/api/me/documents",
            headers=me,
            data={"kind": "official_licence"},
            files={"file": ("x.png", _png(), "image/png")},
        )
        assert combined.status_code == 422

    async def test_the_file_must_be_what_it_claims(self, client, caplog):
        me = await login(client, caplog, f"t-{uuid4().hex[:6]}@example.org")
        response = await client.post(
            "/api/me/documents",
            headers=me,
            data={"kind": "first_aid"},
            files={"file": ("x.png", b"GIF89a....", "image/png")},
        )
        assert response.status_code == 422

    async def test_someone_elses_document_cannot_be_deleted(self, client, caplog):
        owner = await login(client, caplog, f"o-{uuid4().hex[:6]}@example.org")
        doc = await upload(client, owner)
        other = await login(client, caplog, f"x-{uuid4().hex[:6]}@example.org")
        assert (
            await client.delete(f"/api/me/documents/{doc['id']}", headers=other)
        ).status_code == 404


class TestOrganizersSeeDocuments:
    """Story S-5: the person's organizers see the documents, every look is logged, and
    nobody else sees them."""

    async def test_event_and_club_organizers_see_others_do_not(self, client, caplog):
        w = await world()
        email = f"rib-{uuid4().hex[:6]}@example.org"
        helper = await login(
            client,
            caplog,
            email,
            Grant(relation=Relation.HELPER, event_id=w.event),
            Grant(relation=Relation.MEMBER, club_id=w.other_club),
        )
        doc = await upload(client, helper)
        helper_id = (await client.get("/api/auth/me", headers=helper)).json()["id"]

        event_manager = await login(
            client,
            caplog,
            f"em-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, event_id=w.event),
        )
        host_manager = await login(
            client,
            caplog,
            f"hm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, club_id=w.club),
        )
        own_club = await login(
            client,
            caplog,
            f"oc-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MANAGER, club_id=w.other_club),
        )
        fellow = await login(
            client,
            caplog,
            f"fm-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.MEMBER, club_id=w.other_club),
        )
        jury = await login(
            client,
            caplog,
            f"j-{uuid4().hex[:6]}@example.org",
            Grant(relation=Relation.JURY, event_id=w.event),
        )

        for organizer in (event_manager, host_manager, own_club):
            listed = await client.get(f"/api/people/{helper_id}/documents", headers=organizer)
            assert [d["id"] for d in listed.json()] == [doc["id"]], listed.text
            file = await client.get(f"/api/documents/{doc['id']}/file", headers=organizer)
            assert file.status_code == 200

        for outsider in (fellow, jury):
            listed = await client.get(f"/api/people/{helper_id}/documents", headers=outsider)
            assert listed.status_code == 403
            assert _problem_code(listed) == "documents-forbidden"
            file = await client.get(f"/api/documents/{doc['id']}/file", headers=outsider)
            assert file.status_code == 403

        async with SessionLocal() as session:
            looks = (
                (
                    await session.execute(
                        select(AuditLog).where(
                            AuditLog.entity_type == "personal_document",
                            AuditLog.entity_id == doc["id"],
                        )
                    )
                )
                .scalars()
                .all()
            )
        # Three organizers looked; the owner's own look is not logged.
        assert len(looks) == 3

    async def test_deleting_the_account_deletes_the_documents(self, client, caplog):
        email = f"gone-{uuid4().hex[:6]}@example.org"
        me = await login(client, caplog, email)
        doc = await upload(client, me)
        assert (await client.delete("/api/auth/me", headers=me)).status_code in (200, 204)

        admin = await login(
            client, caplog, f"a-{uuid4().hex[:6]}@example.org", Grant(relation=Relation.ADMIN)
        )
        assert (
            await client.get(f"/api/documents/{doc['id']}/file", headers=admin)
        ).status_code == 404


class TestBankAccount:
    """Story S-6: one checked IBAN, read by its owner alone."""

    async def test_save_read_and_delete(self, client, caplog):
        me = await login(client, caplog, f"b-{uuid4().hex[:6]}@example.org")
        assert (await client.get("/api/me/bank-account", headers=me)).json() is None

        saved = await client.put(
            "/api/me/bank-account",
            headers=me,
            json={"holder": "Ma Ria", "iban": "de89 3704 0044 0532 0130 00"},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["iban"] == IBAN

        assert (await client.get("/api/me/bank-account", headers=me)).json()["holder"] == "Ma Ria"
        assert (await client.delete("/api/me/bank-account", headers=me)).status_code == 204
        assert (await client.get("/api/me/bank-account", headers=me)).json() is None

    async def test_a_wrong_check_digit_is_refused(self, client, caplog):
        me = await login(client, caplog, f"w-{uuid4().hex[:6]}@example.org")
        response = await client.put(
            "/api/me/bank-account",
            headers=me,
            json={"holder": "X", "iban": "DE89370400440532013001"},
        )
        assert response.status_code == 422
        assert _problem_code(response) == "iban-invalid"

    async def test_no_account_serializer_carries_it(self, client, caplog):
        email = f"s-{uuid4().hex[:6]}@example.org"
        me = await login(client, caplog, email)
        saved = await client.put(
            "/api/me/bank-account", headers=me, json={"holder": "X", "iban": IBAN}
        )
        assert saved.status_code == 200
        assert IBAN not in (await client.get("/api/auth/me", headers=me)).text
