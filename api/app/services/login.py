"""Sign-in via identity provider or one-time code.

We store no passwords. Whoever signs in proves their identity through

* **Google** or **Microsoft** — we verify their ID token against the provider's public
  keys, or
* **Email** — we send a six-digit code valid for ten minutes.

Both paths are linked via the **verified** email address: signing in with Google today
and by code tomorrow lands in the same account.

Accounts don't spring into existence on their own here. Whoever shows up must already
have been created, or imported from manage2sail — otherwise anyone could get themselves
an account on an official league site with any address. Controlled via
``allow_self_signup``.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mail import MailError, send_login_code
from app.models.auth import Identity, IdentityProvider, LoginCode, User

_hasher = PasswordHasher()


class LoginError(Exception):
    """Sign-in failed — the message is meant for the end user."""


@dataclass(frozen=True)
class OidcProvider:
    name: str
    jwks_uri: str
    issuers: tuple[str, ...]
    client_id: str


def _providers() -> dict[str, OidcProvider]:
    return {
        IdentityProvider.GOOGLE: OidcProvider(
            name=IdentityProvider.GOOGLE,
            jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
            issuers=("https://accounts.google.com", "accounts.google.com"),
            client_id=settings.google_client_id,
        ),
        IdentityProvider.MICROSOFT: OidcProvider(
            name=IdentityProvider.MICROSOFT,
            jwks_uri=(
                f"https://login.microsoftonline.com/{settings.microsoft_tenant}"
                "/discovery/v2.0/keys"
            ),
            # With tenant "common", the issuer depends on the signing-in user's own
            # tenant, so verification only checks signature and audience. Anyone who
            # wants this narrower sets their tenant in SBL_MICROSOFT_TENANT.
            issuers=(
                (f"https://login.microsoftonline.com/{settings.microsoft_tenant}/v2.0",)
                if settings.microsoft_tenant != "common"
                else ()
            ),
            client_id=settings.microsoft_client_id,
        ),
    }


async def login_with_oidc(session: AsyncSession, provider_name: str, id_token: str) -> User:
    provider = _providers().get(provider_name)
    if provider is None:
        raise LoginError(f"Unknown provider: {provider_name}")
    if not provider.client_id:
        raise LoginError(
            f"No application ID is configured for {provider_name}. "
            "Please add one to the configuration."
        )

    claims = await asyncio.to_thread(_verify_id_token, provider, id_token)

    if not claims.get("email"):
        raise LoginError("The provider didn't supply an email address.")
    if claims.get("email_verified") is False:
        raise LoginError("The email address isn't confirmed with the provider.")

    return await _resolve_user(
        session,
        email=str(claims["email"]).lower(),
        provider=provider.name,
        subject=str(claims["sub"]),
        display_name=str(claims.get("name") or claims["email"]),
    )


def _verify_id_token(provider: OidcProvider, id_token: str) -> dict:
    try:
        signing_key = jwt.PyJWKClient(provider.jwks_uri).get_signing_key_from_jwt(id_token)
        options = {"verify_iss": bool(provider.issuers)}
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=provider.client_id,
            issuer=list(provider.issuers) if provider.issuers else None,
            options=options,
        )
    except jwt.ExpiredSignatureError as exc:
        raise LoginError("The provider's token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise LoginError("The provider's token is invalid.") from exc
    except Exception as exc:  # Network error while fetching keys
        raise LoginError(f"The provider could not be reached: {exc}") from exc


async def request_email_code(session: AsyncSession, email: str) -> None:
    """Creates a one-time code and sends it.

    Deliberately reports **nothing** back about whether an account exists for the
    address — otherwise this endpoint could be used to enumerate accounts.
    """
    email = email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        return

    code = "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))
    session.add(
        LoginCode(
            email=email,
            code_hash=_hasher.hash(code),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.otp_lifetime_minutes),
        )
    )
    await session.commit()
    try:
        await send_login_code(email, code)
    except MailError:
        # Swallowed deliberately, not a bug: for a nonexistent address this function
        # already returns before this point without a trace, so surfacing a send failure
        # only here would itself reveal that the address has an account. mail.py already
        # logged the failure (recipient, host, the underlying error) — that's how a broken
        # SBL_SMTP_* configuration is diagnosed, not via this function's return value.
        pass


async def verify_email_code(session: AsyncSession, email: str, code: str) -> User:
    email = email.strip().lower()
    now = datetime.now(UTC)

    entry = (
        await session.execute(
            select(LoginCode)
            .where(
                LoginCode.email == email,
                LoginCode.consumed_at.is_(None),
                LoginCode.expires_at > now,
            )
            .order_by(LoginCode.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if entry is None:
        raise LoginError("This code has expired or was already used.")
    if entry.attempts >= settings.otp_max_attempts:
        raise LoginError("Too many failed attempts. Please request a new code.")

    if not _matches(code, entry.code_hash):
        entry.attempts += 1
        await session.commit()
        raise LoginError("That code isn't correct.")

    entry.consumed_at = now
    user = await _resolve_user(
        session,
        email=email,
        provider=IdentityProvider.EMAIL,
        subject=email,
        display_name=email,
    )
    await session.commit()
    return user


def _matches(code: str, code_hash: str) -> bool:
    try:
        _hasher.verify(code_hash, code.strip())
    except (VerifyMismatchError, InvalidHashError):
        return False
    return True


async def _resolve_user(
    session: AsyncSession, *, email: str, provider: str, subject: str, display_name: str
) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    if user is None:
        if not settings.allow_self_signup:
            raise LoginError(
                "There's no account for this address. Please contact the league office."
            )
        user = User(email=email, display_name=display_name)
        session.add(user)
        await session.flush()

    if not user.is_active:
        raise LoginError("This account is suspended.")

    # Whoever proves themselves here has claimed the address — via a one-time code sent to
    # it, or via a provider that already verified it. That counts as a confirmed sign-up.
    user.email_verified = True

    known = {(row.provider, row.subject) for row in user.identities}
    if (provider, subject) not in known:
        session.add(Identity(user_id=user.id, provider=provider, subject=subject))

    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


async def register(session: AsyncSession, email: str, display_name: str) -> None:
    """Creates an account and sends the confirmation code — Story Z-4.

    Reports **nothing** about whether the address already had an account: otherwise this
    endpoint could be used to enumerate accounts. Either way, the flow looks the same to
    whoever's signing up — a code arrives, they enter it.

    The new account starts out **unconfirmed**, with neither role nor club. It can do
    exactly one thing: ask to join a club (Story Z-5). Only a redeemed code sets
    ``email_verified``.
    """
    if not settings.allow_registration:
        raise LoginError("Self-registration is disabled.")

    email = email.strip().lower()
    name = display_name.strip()
    if not name:
        raise LoginError("Please provide a name.")

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        session.add(User(email=email, display_name=name, email_verified=False))
        await session.commit()

    # Even for a known address: the flow must be indistinguishable from the outside.
    await request_email_code(session, email)
