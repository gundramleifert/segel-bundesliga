"""The one writer of ``AuditLog`` rows: the actor is resolved once, the strings never drift."""

from app.models import User
from app.services.audit import SYSTEM_ACTOR, EntityType, audit


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)


def test_an_account_is_its_email_and_nobody_is_the_system():
    session = FakeSession()
    person = User(email="wl@example.com")
    by_person = audit(session, EntityType.RACE, 7, "start", person, preparatory="P")
    by_name = audit(session, EntityType.RACE, 7, "finish", "emulator")
    by_nobody = audit(session, EntityType.USER, 3, "grant", None)

    assert session.added == [by_person, by_name, by_nobody]
    assert [r.actor for r in session.added] == ["wl@example.com", "emulator", SYSTEM_ACTOR]
    assert SYSTEM_ACTOR == "system"
    assert by_person.entity_type == "race" and type(by_person.entity_type) is str
    assert by_person.payload == {"preparatory": "P"}
    assert by_nobody.payload == {}
