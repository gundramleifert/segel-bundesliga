"""A person's address is their account's — one column (Stories V-4, Z-5; review 5.1).

Person and account each kept a copy of the address. The league office changed the
person's, someone registered with it, and a second person was made for the same address
— the two copies disagreeing was the whole defect. Now there is one copy, so there is
nothing to disagree.
"""

from uuid import uuid4

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Person, User
from tests.accounts import account
from tests.stories.test_create_event import admin


async def _person(email: str) -> Person:
    async with SessionLocal() as session:
        return (await session.execute(select(Person).where(Person.email == email))).scalar_one()


class TestOneAddress:
    async def test_the_league_office_moves_the_address_and_the_account_moves_with_it(
        self, client, caplog
    ):
        office = await admin(client, caplog, f"office-{uuid4().hex[:6]}@example.com")
        old, new = (f"{tag}-{uuid4().hex[:6]}@example.com" for tag in ("old", "new"))
        # An account that signs in: there the two copies used to part.
        await account(old, email_verified=True)
        person = await _person(old)

        moved = await client.patch(
            f"/api/admin/people/{person.id}", headers=office, json={"email": new}
        )
        assert moved.status_code == 200, moved.text

        async with SessionLocal() as session:
            user = await session.get(User, person.user_id)
            assert user.email == new
            # The new address is proven before it signs in.
            assert user.email_verified is False

    async def test_registering_the_moved_address_makes_no_second_person(self, client, caplog):
        office = await admin(client, caplog, f"office-{uuid4().hex[:6]}@example.com")
        old, new = (f"{tag}-{uuid4().hex[:6]}@example.com" for tag in ("was", "now"))
        # An account that signs in: there the two copies used to part.
        await account(old, email_verified=True)
        person = await _person(old)
        await client.patch(f"/api/admin/people/{person.id}", headers=office, json={"email": new})

        registered = await client.post(
            "/api/auth/register", json={"email": new, "display_name": "Someone Else"}
        )

        assert registered.status_code < 500, registered.text
        async with SessionLocal() as session:
            count = (
                await session.execute(select(func.count(Person.id)).where(Person.email == new))
            ).scalar_one()
        assert count == 1
