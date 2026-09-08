"""Development aids for trying out different roles.

**This router is off by default.** It is only included when ``SBL_DEV_LOGIN=true``
is set, and it issues access tokens **without any verification**. In a reachable
environment this would be a wide-open door — that's why it has its own setting instead of
being coupled to ``debug``, and why the server warns on startup.

Purpose: while developing, move through the interface as admin, editor, race officer, or club
manager without fetching a one-time code from the log each time.
"""

from __future__ import annotations

import asyncio
import socket

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.config import settings
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.mail import MailError, send_login_code
from app.models import Club
from app.models.auth import User

router = APIRouter(prefix="/api/dev", tags=["development"])


class TestUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    roles: list[str]
    club: str | None = None
    description: str


class DevLogin(BaseModel):
    email: EmailStr


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


DESCRIPTION: dict[str, str] = {
    "admin": "Sees and can do everything: master data, accounts, roles, pairing lists.",
    "editor": "Editorial: write messages, approve club posts.",
    "race_officer": "Race officer: record and correct results.",
    "club_manager": "Club account: own roster, submit posts, club assignment.",
}


@router.get("/users", response_model=list[TestUserOut], summary="List test accounts")
async def list_test_users(
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> list[TestUserOut]:
    users = (
        await session.execute(select(User).order_by(User.display_name))
    ).scalars().all()
    clubs = {
        club.id: club.short_name
        for club in (await session.execute(select(Club))).scalars()
    }

    return [
        TestUserOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            roles=sorted(user.roles),
            club=clubs.get(user.club_id) if user.club_id else None,
            description=tr(
                locale,
                en=" ".join(
                    DESCRIPTION[rolle] for rolle in sorted(user.roles) if rolle in DESCRIPTION
                )
                or "Signed in, but no special permissions.",
                de=" ".join(
                    DESCRIPTION[rolle] for rolle in sorted(user.roles) if rolle in DESCRIPTION
                )
                or "Angemeldet, aber ohne besondere Rechte.",
            ),
        )
        for user in users
    ]


@router.post("/login", response_model=TokenOut, summary="Sign in without verification")
async def dev_login(
    request: DevLogin,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> TokenOut:
    user = (
        await session.execute(select(User).where(User.email == request.email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This test account does not exist.",
                de="Dieses Testkonto gibt es nicht."
            )
        )

    # Like a real sign-in: whoever passes through here is considered verified. Otherwise
    # the role switcher couldn't be used for membership stories.
    user.email_verified = True
    await session.commit()

    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)


# ---------------------------------------------------------------------- SMTP diagnostics
#
# TEMPORARY — added to debug a specific deployment's SMTP configuration without needing
# dashboard/log access. Both are only reachable behind SBL_DEV_LOGIN like the rest of this
# router; still, remove this section once STRATO delivery is confirmed working — it isn't
# meant to be a permanent part of the API.


class SmtpConfigOut(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_ssl: bool
    smtp_starttls: bool
    smtp_user: str
    smtp_password_set: bool
    mail_from: str


@router.get(
    "/smtp-config", response_model=SmtpConfigOut, summary="What SMTP config is resolved"
)
async def smtp_config() -> SmtpConfigOut:
    """Shows exactly what `app.config.settings` resolved to — from env vars, Secret
    Files, or defaults, whichever won — without exposing the password itself."""
    return SmtpConfigOut(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_ssl=settings.smtp_ssl,
        smtp_starttls=settings.smtp_starttls,
        smtp_user=settings.smtp_user,
        smtp_password_set=bool(settings.smtp_password),
        mail_from=settings.mail_from,
    )


class TestEmail(BaseModel):
    email: EmailStr


class TestEmailOut(BaseModel):
    attempted: bool
    sent: bool
    error: str | None = None


@router.post(
    "/test-email", response_model=TestEmailOut, summary="Attempt an actual SMTP send"
)
async def test_email(request: TestEmail) -> TestEmailOut:
    """Sends a real message with a throwaway code to the given address right now, and
    reports the outcome directly in the response — the same send path
    `app.services.login.request_email_code` uses, just without needing a valid account or
    the anti-enumeration silence that endpoint deliberately has."""
    if not settings.smtp_host:
        return TestEmailOut(attempted=False, sent=False, error="SBL_SMTP_HOST is not set.")
    try:
        await send_login_code(request.email, "000000")
    except MailError as exc:
        return TestEmailOut(attempted=True, sent=False, error=str(exc))
    return TestEmailOut(attempted=True, sent=True)


class AddressProbe(BaseModel):
    family: str
    address: str
    connect_ok: bool
    error: str | None = None


class NetworkProbeOut(BaseModel):
    host: str
    port: int
    resolved: list[AddressProbe]


@router.get(
    "/network-probe", response_model=NetworkProbeOut, summary="Diagnose outbound TCP"
)
async def network_probe(host: str | None = None, port: int | None = None) -> NetworkProbeOut:
    """Resolves `host` (default: the configured SMTP host) and tries a raw TCP connect to
    *each* resolved address individually — this tells apart a common container gotcha
    (DNS returns an address family, usually IPv6, with no actual outbound route, while the
    other family would work fine) from every address genuinely being blocked (e.g. the
    platform firewalling the port itself)."""
    target_host = host or settings.smtp_host
    target_port = port or settings.smtp_port
    if not target_host:
        return NetworkProbeOut(host="", port=target_port, resolved=[])

    def _probe() -> list[AddressProbe]:
        try:
            infos = socket.getaddrinfo(target_host, target_port, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            return [AddressProbe(family="dns", address="", connect_ok=False, error=str(exc))]

        probes: list[AddressProbe] = []
        seen: set[str] = set()
        for family, _type, _proto, _canon, sockaddr in infos:
            addr = sockaddr[0]
            if addr in seen:
                continue
            seen.add(addr)
            family_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
            try:
                with socket.socket(family, socket.SOCK_STREAM) as s:
                    s.settimeout(6)
                    s.connect((addr, target_port))
                probes.append(AddressProbe(family=family_name, address=addr, connect_ok=True))
            except OSError as exc:
                probes.append(
                    AddressProbe(
                        family=family_name, address=addr, connect_ok=False, error=str(exc)
                    )
                )
        return probes

    resolved = await asyncio.to_thread(_probe)
    return NetworkProbeOut(host=target_host, port=target_port, resolved=resolved)
