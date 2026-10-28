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
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import create_access_token
from app.config import settings
from app.db import get_session
from app.i18n import Locale, catalog, resolve_locale, t
from app.jobs import jobs
from app.mail import MailError, send_login_code
from app.models import Club
from app.models.auth import ObjectType, Relation, Role, User
from app.problems import Problem
from app.schemas.auth import TokenOut
from app.services import people
from app.tracking.emulate_job import emulate_event

router = APIRouter(prefix="/api/dev", tags=["development"])


#: The switcher's groups, in the order it shows them — where the person's tuples are.
Group = Literal["league", "series", "event", "club", "sailor", "guest"]


class TestUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    roles: list[Role]
    club: str | None = None
    group: Group
    description: str


def _group(user: User) -> Group:
    """Where someone's tuples are, the widest first: on the site, a series, an event, a
    club beyond membership; a plain member is a sailor; no tuple at all, a guest."""
    held = authz.tuples(user)
    types = {obj.type for _, obj in held}
    for object_type, group in (
        (ObjectType.SITE, "league"),
        (ObjectType.SERIES, "series"),
        (ObjectType.EVENT, "event"),
    ):
        if object_type in types:
            return group  # type: ignore[return-value]
    if any(obj.type is ObjectType.CLUB and relation != Relation.MEMBER for relation, obj in held):
        return "club"
    return "sailor" if held else "guest"


class DevLogin(BaseModel):
    email: EmailStr


@router.get("/users", response_model=list[TestUserOut], summary="List test accounts")
async def list_test_users(
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> list[TestUserOut]:
    # Accounts someone signs in to: the invented sailors' accounts (#52) are nobody's.
    users = (
        (await session.execute(select(User).where(User.signs_in).order_by(User.display_name)))
        .scalars()
        .all()
    )
    clubs = {club.id: club.short_name for club in (await session.execute(select(Club))).scalars()}

    return [
        TestUserOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            roles=sorted(user.roles),
            club=", ".join(
                clubs[cid]
                for cid in sorted(
                    authz.list_objects(
                        user,
                        (Relation.MEMBER, Relation.MANAGER, Relation.TREASURER),
                        ObjectType.CLUB,
                    )
                )
                if cid in clubs
            )
            or None,
            group=_group(user),
            description=" ".join(
                t(locale, f"dev.roles.{role}")
                for role in sorted(user.roles)
                if f"dev.roles.{role}" in catalog(locale)
            )
            or t(locale, "dev.accounts.no_permissions"),
        )
        for user in users
    ]


@router.post("/login", response_model=TokenOut, summary="Sign in without verification")
async def dev_login(
    request: DevLogin,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    user = (
        await session.execute(select(User).where(User.email == request.email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise Problem(404, "test-account-not-found", "This test account does not exist.")

    # Like a real sign-in: whoever passes through here is considered verified. Otherwise
    # the role switcher couldn't be used for membership stories.
    user.email_verified = True
    await people.person_for(session, user)
    await session.commit()

    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)


# ---------------------------------------------------------------------- SMTP diagnostics
#
# Added to debug a former hosted test deployment's SMTP configuration without needing
# dashboard/log access — confirmed working end to end (STRATO SMTP was blocked outbound by
# the host). Disabled by default now that the question
# is settled; flip _MAIL_DIAGNOSTICS_ENABLED back to True if a future deployment needs the
# same investigation again, rather than rewriting this from scratch.
_MAIL_DIAGNOSTICS_ENABLED = False


def _require_mail_diagnostics_enabled() -> None:
    if not _MAIL_DIAGNOSTICS_ENABLED:
        raise Problem(404, "mail-diagnostics-disabled", "Not found.")


class SmtpConfigOut(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_ssl: bool
    smtp_starttls: bool
    smtp_user: str
    smtp_password_set: bool
    mail_from: str


@router.get("/smtp-config", response_model=SmtpConfigOut, summary="What mail config is resolved")
async def smtp_config() -> SmtpConfigOut:
    """Shows exactly what `app.config.settings` resolved to — from env vars, Secret
    Files, or defaults, whichever won — without exposing the password itself."""
    _require_mail_diagnostics_enabled()
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


@router.post("/test-email", response_model=TestEmailOut, summary="Attempt an actual send")
async def test_email(request: TestEmail) -> TestEmailOut:
    """Sends a real message with a throwaway code to the given address right now, and
    reports the outcome directly in the response — the same send path
    `app.services.login.request_email_code` uses (`app.mail.send_login_code`), just
    without needing a valid account or the
    anti-enumeration silence that endpoint deliberately has."""
    _require_mail_diagnostics_enabled()
    if not settings.smtp_host:
        return TestEmailOut(
            attempted=False,
            sent=False,
            error="SBL_SMTP_HOST is not set.",
        )
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


@router.get("/network-probe", response_model=NetworkProbeOut, summary="Diagnose outbound TCP")
async def network_probe(host: str | None = None, port: int | None = None) -> NetworkProbeOut:
    """Resolves `host` (default: the configured SMTP host) and tries a raw TCP connect to
    *each* resolved address individually — this tells apart a common container gotcha
    (DNS returns an address family, usually IPv6, with no actual outbound route, while the
    other family would work fine) from every address genuinely being blocked (e.g. the
    platform firewalling the port itself)."""
    _require_mail_diagnostics_enabled()
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
                    AddressProbe(family=family_name, address=addr, connect_ok=False, error=str(exc))
                )
        return probes

    resolved = await asyncio.to_thread(_probe)
    return NetworkProbeOut(host=target_host, port=target_port, resolved=resolved)


class EmulateIn(BaseModel):
    """Sail the event's current race with made-up boats (Story L-4, the emulator)."""

    event_id: int
    #: Sailing seconds per real second: 10 sails a short course in half a minute.
    speed: float = 10.0
    races: int = 1
    seed: int = 1
    leg_length_m: float | None = None


class EmulateOut(BaseModel):
    job_id: str


@router.post("/emulate", response_model=EmulateOut, summary="Simulate the current race")
async def start_emulation(request: EmulateIn) -> EmulateOut:
    """Lays the default course if none is laid, issues trackers, starts the current race,
    streams emulated fixes through the real ingest path, and enters the finish order when
    every boat is home — the whole race on the map, without a boat on the water.

    Development only, like everything under ``/api/dev``: it writes results.
    """
    job = jobs.start(
        "emulate",
        lambda job: emulate_event(
            request.event_id,
            speed=request.speed,
            races=request.races,
            seed=request.seed,
            leg_length_m=request.leg_length_m,
            job=job,
        ),
    )
    return EmulateOut(job_id=job.id)
