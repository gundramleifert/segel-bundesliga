"""User story Z-9: sign in with a password.

A password is one more way into the same account — beside Google, Microsoft and the
one-time code, which stays the way an address is proven and doubles as the reset.
"""

from argon2 import PasswordHasher
from sqlalchemy import select

from app.auth import create_access_token
from app.config import settings
from app.db import SessionLocal
from app.models import AuditLog
from app.models.auth import PasswordCredential, Role, User
from tests.stories.test_login_and_roles import login_as, make_user

PASSWORD = "lee-side of the pontoon"
OTHER = "windward mark, port rounding"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def signed_in(client, caplog, email: str, *roles: str) -> dict[str, str]:
    """A verified account, signed in by code — the only way an address is proven."""
    await make_user(email, *roles)
    return bearer(await login_as(client, email, caplog))


async def with_password(client, caplog, email: str, *roles: str) -> dict[str, str]:
    headers = await signed_in(client, caplog, email, *roles)
    response = await client.put(
        "/api/auth/password", headers=headers, json={"new_password": PASSWORD}
    )
    assert response.status_code == 204, response.text
    return headers


async def password_login(client, email: str, password: str):
    return await client.post(
        "/api/auth/password/login", json={"email": email, "password": password}
    )


async def credential(email: str) -> PasswordCredential | None:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(PasswordCredential)
                .join(User, User.id == PasswordCredential.user_id)
                .where(User.email == email)
            )
        ).scalar_one_or_none()


def problem_code(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


class TestSettingAndSigningIn:
    """Z-9: as a sailor, I set a password and sign in with it."""

    async def test_set_then_sign_in(self, client, caplog):
        """Z-9: a password set on the account signs in to the same account."""
        await with_password(client, caplog, "pw-set@example.com", Role.CLUB_MANAGER)

        response = await password_login(client, "pw-set@example.com", PASSWORD)
        assert response.status_code == 200, response.text
        me = await client.get("/api/auth/me", headers=bearer(response.json()["access_token"]))
        assert me.json()["email"] == "pw-set@example.com"
        assert me.json()["roles"] == [Role.CLUB_MANAGER]
        assert "password" in {i["provider"] for i in me.json()["identities"]}

    async def test_the_address_is_case_insensitive(self, client, caplog):
        """Z-9: the address signs in however it is capitalised, like every other path."""
        await with_password(client, caplog, "pw-case@example.com")
        response = await password_login(client, "PW-Case@Example.com", PASSWORD)
        assert response.status_code == 200, response.text

    async def test_the_same_umlaut_typed_two_ways_is_the_same_password(self, client, caplog):
        """Z-9: NFKC — 'ü' as one code point and as 'u' + combining diaeresis match."""
        headers = await signed_in(client, caplog, "pw-nfkc@example.com")
        composed = "Segelflügel über der Kante"
        decomposed = "Segelflügel über der Kante"
        await client.put("/api/auth/password", headers=headers, json={"new_password": composed})
        response = await password_login(client, "pw-nfkc@example.com", decomposed)
        assert response.status_code == 200, response.text

    async def test_length_is_the_only_rule(self, client, caplog):
        """Z-9: 12 to 128 characters; no composition rules."""
        headers = await signed_in(client, caplog, "pw-length@example.com")

        short = await client.put(
            "/api/auth/password", headers=headers, json={"new_password": "elevenchars"}
        )
        assert short.status_code == 422
        assert problem_code(short) == "password-length"
        assert short.json()["min_length"] == 12

        long = await client.put(
            "/api/auth/password", headers=headers, json={"new_password": "x" * 129}
        )
        assert problem_code(long) == "password-length"

        # Twelve lowercase letters — no digit, no symbol — is fine.
        plain = await client.put(
            "/api/auth/password", headers=headers, json={"new_password": "twelveletter"}
        )
        assert plain.status_code == 204

    async def test_an_unverified_address_gets_no_password(self, client):
        """Z-9: only a verified address can carry a password — otherwise a typed-in,
        never-proven address would become a way in."""
        await make_user("pw-unverified@example.com")
        async with SessionLocal() as session:
            user = (
                await session.execute(select(User).where(User.email == "pw-unverified@example.com"))
            ).scalar_one()
            assert user.email_verified is False
            token, _ = create_access_token(user)

        response = await client.put(
            "/api/auth/password", headers=bearer(token), json={"new_password": PASSWORD}
        )
        assert response.status_code == 403
        assert problem_code(response) == "password-email-unverified"
        assert await credential("pw-unverified@example.com") is None

    async def test_the_providers_say_whether_passwords_are_open(self, client, monkeypatch):
        """Z-9: the sign-in card only offers the tab when the path is open."""
        assert (await client.get("/api/auth/providers")).json()["password"]["available"] is True
        monkeypatch.setattr(settings, "allow_password_login", False)
        assert (await client.get("/api/auth/providers")).json()["password"]["available"] is False

    async def test_switched_off_nobody_signs_in_by_password(self, client, caplog, monkeypatch):
        """Z-9: SBL_ALLOW_PASSWORD_LOGIN=false closes login and setting alike."""
        headers = await with_password(client, caplog, "pw-off@example.com")
        monkeypatch.setattr(settings, "allow_password_login", False)

        response = await password_login(client, "pw-off@example.com", PASSWORD)
        assert response.status_code == 403
        assert problem_code(response) == "password-login-disabled"
        again = await client.put(
            "/api/auth/password", headers=headers, json={"new_password": OTHER}
        )
        assert problem_code(again) == "password-login-disabled"


class TestNothingGivenAway:
    """Z-9: a wrong combination tells an attacker nothing."""

    async def test_wrong_password_and_unknown_address_are_indistinguishable(self, client, caplog):
        """Z-9: unknown address, no password, wrong password, suspended — one body."""
        await with_password(client, caplog, "pw-known@example.com")
        await make_user("pw-none@example.com")
        await make_user("pw-suspended@example.com", active=False)

        answers = [
            await password_login(client, "pw-known@example.com", "not the password"),
            await password_login(client, "pw-nobody@example.com", PASSWORD),
            await password_login(client, "pw-none@example.com", PASSWORD),
            await password_login(client, "pw-suspended@example.com", PASSWORD),
        ]
        assert {a.status_code for a in answers} == {401}
        assert len({a.text for a in answers}) == 1
        assert problem_code(answers[0]) == "login-failed"

    async def test_the_hash_never_leaves_the_server(self, client, caplog):
        """Z-9: neither /me nor the account list carries the hash."""
        headers = await with_password(client, caplog, "pw-hidden@example.com")
        admin = await signed_in(client, caplog, "pw-hidden-admin@example.com", Role.ADMIN)
        stored = (await credential("pw-hidden@example.com")).hash

        me = await client.get("/api/auth/me", headers=headers)
        users = await client.get(
            "/api/auth/users", headers=admin, params={"q": "pw-hidden", "page_size": 100}
        )
        for response in (me, users):
            assert response.status_code == 200
            assert stored not in response.text
            assert "$argon2" not in response.text
            assert PASSWORD not in response.text

    async def test_a_hash_with_old_parameters_is_upgraded_on_login(self, client, caplog):
        """Z-9: stronger parameters later reach every hash at its owner's next sign-in."""
        await with_password(client, caplog, "pw-rehash@example.com")
        weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(PasswordCredential)
                    .join(User, User.id == PasswordCredential.user_id)
                    .where(User.email == "pw-rehash@example.com")
                )
            ).scalar_one()
            row.hash = weak
            await session.commit()

        assert (await password_login(client, "pw-rehash@example.com", PASSWORD)).status_code == 200
        upgraded = (await credential("pw-rehash@example.com")).hash
        assert upgraded != weak
        assert not PasswordHasher().check_needs_rehash(upgraded)


class TestLockout:
    """Z-9: guessing is slowed down per account."""

    async def test_five_failures_lock_the_account(self, client, caplog):
        """Z-9: after five wrong passwords even the right one is refused, with the same
        answer — and the lock is audited."""
        await with_password(client, caplog, "pw-lock@example.com")
        wrong = [await password_login(client, "pw-lock@example.com", "guess") for _ in range(5)]
        assert {w.status_code for w in wrong} == {401}

        right = await password_login(client, "pw-lock@example.com", PASSWORD)
        assert right.status_code == 401
        assert right.text == wrong[0].text
        assert (await credential("pw-lock@example.com")).locked_until is not None
        assert "password_locked" in await audited("pw-lock@example.com")

    async def test_a_code_sign_in_lifts_the_lock(self, client, caplog):
        """Z-9: proving the address by code clears the count — that is the reset path."""
        await with_password(client, caplog, "pw-unlock@example.com")
        for _ in range(5):
            await password_login(client, "pw-unlock@example.com", "guess")

        await login_as(client, "pw-unlock@example.com", caplog)
        row = await credential("pw-unlock@example.com")
        assert row.locked_until is None and row.failed_attempts == 0
        assert (await password_login(client, "pw-unlock@example.com", PASSWORD)).status_code == 200

    async def test_a_wrong_current_password_counts_as_a_failure(self, client, caplog):
        """Z-9: a stolen session cannot guess the password through the change form."""
        headers = await with_password(client, caplog, "pw-change-guess@example.com")
        response = await client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "guess", "new_password": OTHER},
        )
        assert response.status_code == 403
        assert problem_code(response) == "password-current-wrong"
        assert (await credential("pw-change-guess@example.com")).failed_attempts == 1


class TestChangingAndRemoving:
    """Z-9: a password is changed with the old one, removed freely, cleared by the admin."""

    async def test_changing_needs_the_current_password(self, client, caplog):
        """Z-9: without the current password, a password is not replaced."""
        headers = await with_password(client, caplog, "pw-change@example.com")

        missing = await client.put(
            "/api/auth/password", headers=headers, json={"new_password": OTHER}
        )
        assert problem_code(missing) == "password-current-wrong"

        changed = await client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": OTHER},
        )
        assert changed.status_code == 204
        assert (await password_login(client, "pw-change@example.com", PASSWORD)).status_code == 401
        assert (await password_login(client, "pw-change@example.com", OTHER)).status_code == 200

    async def test_removing_leaves_the_code_as_the_way_in(self, client, caplog):
        """Z-9: removing a password is never 'the last way in' — the code always is one."""
        headers = await with_password(client, caplog, "pw-remove@example.com")
        assert (await client.delete("/api/auth/password", headers=headers)).status_code == 204

        assert await credential("pw-remove@example.com") is None
        assert (await password_login(client, "pw-remove@example.com", PASSWORD)).status_code == 401
        me = await client.get("/api/auth/me", headers=headers)
        assert "password" not in {i["provider"] for i in me.json()["identities"]}
        await login_as(client, "pw-remove@example.com", caplog)

    async def test_the_admin_can_clear_a_password(self, client, caplog):
        """Z-9 (D3): administration clears a password; the person signs in by code and
        sets a new one. Nobody else may."""
        await with_password(client, caplog, "pw-cleared@example.com")
        admin = await signed_in(client, caplog, "pw-clear-admin@example.com", Role.ADMIN)
        other = await signed_in(client, caplog, "pw-clear-other@example.com", Role.EDITOR)
        user_id = (await credential("pw-cleared@example.com")).user_id

        refused = await client.delete(f"/api/auth/users/{user_id}/password", headers=other)
        assert refused.status_code == 403
        cleared = await client.delete(f"/api/auth/users/{user_id}/password", headers=admin)
        assert cleared.status_code == 204
        assert await credential("pw-cleared@example.com") is None
        assert "password_cleared" in await audited("pw-cleared@example.com")

    async def test_set_change_and_remove_are_audited_without_the_password(self, client, caplog):
        """Z-9: each step leaves a row; none of them carries the password or the hash."""
        headers = await with_password(client, caplog, "pw-audit@example.com")
        await client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": OTHER},
        )
        await client.delete("/api/auth/password", headers=headers)

        rows = await audit_rows("pw-audit@example.com")
        assert [r.action for r in rows] == ["password_set", "password_changed", "password_removed"]
        for row in rows:
            assert PASSWORD not in str(row.payload) and OTHER not in str(row.payload)
            assert "argon2" not in str(row.payload)

    async def test_the_password_goes_with_a_deleted_account(self, client, caplog):
        """Z-9 with Z-7: deleting the account deletes its password — SQLite reuses ids,
        and a credential left behind would belong to the next account."""
        headers = await with_password(client, caplog, "pw-gone@example.com")
        assert (await client.delete("/api/auth/me", headers=headers)).status_code == 204
        async with SessionLocal() as session:
            orphans = (
                await session.execute(
                    select(PasswordCredential).where(
                        PasswordCredential.user_id.not_in(select(User.id))
                    )
                )
            ).all()
        assert orphans == []


async def audit_rows(email: str) -> list[AuditLog]:
    async with SessionLocal() as session:
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        return list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_type == "user",
                        AuditLog.entity_id == user_id,
                        AuditLog.action.like("password_%"),
                    )
                    .order_by(AuditLog.id)
                )
            ).scalars()
        )


async def audited(email: str) -> set[str]:
    return {row.action for row in await audit_rows(email)}
