"""Sign-in and account management.

Three paths to the same account: Google, Microsoft, or a one-time code via email. All end
with a session token that carries roles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    current_user,
    require_admin,
    require_club_manager,
)
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import AuditLog, Club, ClubMember, WaiverConfirmation
from app.models.auth import Role, User, UserRole
from app.services.login import (
    LoginError,
    login_with_oidc,
    register,
    request_email_code,
    verify_email_code,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class EmailRequest(BaseModel):
    email: EmailStr


class Registration(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120, description="First and last name")


class EmailVerify(BaseModel):
    email: EmailStr
    code: str


class OidcLogin(BaseModel):
    id_token: str = Field(description="The ID token issued by the provider in the browser")


class IdentityOut(BaseModel):
    provider: str
    subject: str


class ProviderInfo(BaseModel):
    available: bool
    client_id: str | None = Field(
        default=None, description="Public OAuth client ID, only set when available"
    )


class MicrosoftProviderInfo(ProviderInfo):
    tenant: str | None = Field(
        default=None, description="Azure AD tenant to sign in against, e.g. 'common'"
    )


class ProvidersOut(BaseModel):
    """Everything the sign-in UI needs to decide which buttons to show and how to
    initialize each provider's SDK — one call instead of separate build-time config."""

    google: ProviderInfo
    microsoft: MicrosoftProviderInfo
    email: ProviderInfo
    allow_registration: bool = Field(
        description="Whether POST /api/auth/register is open, i.e. a 'create an account' "
        "link makes sense to show"
    )


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool
    email_verified: bool
    club_id: int | None
    roles: list[str]
    identities: list[IdentityOut]

    @classmethod
    def of(cls, user: User) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            email_verified=user.email_verified,
            club_id=user.club_id,
            roles=sorted(user.roles),
            identities=[
                IdentityOut(provider=row.provider, subject=row.subject)
                for row in user.identities
            ],
        )


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    roles: list[Role] = Field(default_factory=list)
    club_id: int | None = None


class RolesUpdate(BaseModel):
    roles: list[Role]


class ClubUpdate(BaseModel):
    club_id: int | None = Field(
        default=None, description="Club, or null to remove the assignment"
    )


@router.get(
    "/providers", response_model=ProvidersOut, summary="Which sign-in methods are available"
)
async def providers() -> ProvidersOut:
    """So the interface only shows buttons that actually work, and can initialize the
    Google/Microsoft SDKs without its own build-time configuration — the client ID is a
    public value, not a secret (the actual check is the ID-token signature verification
    against the provider's JWKS, done server-side in `app.services.login`)."""
    from app.config import settings

    return ProvidersOut(
        google=ProviderInfo(
            available=bool(settings.google_client_id),
            client_id=settings.google_client_id or None,
        ),
        microsoft=MicrosoftProviderInfo(
            available=bool(settings.microsoft_client_id),
            client_id=settings.microsoft_client_id or None,
            tenant=settings.microsoft_tenant if settings.microsoft_client_id else None,
        ),
        email=ProviderInfo(available=True),
        allow_registration=settings.allow_registration,
    )


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create an account",
)
async def registrieren(
    request: Registration,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> dict[str, str]:
    """Creates an account and sends a confirmation code to the provided address.

    Confirmation works via the same path as sign-in: enter the code at
    ``POST /api/auth/email/verify``. Before confirmation, the address is considered
    merely claimed.

    The account initially has neither role nor club. The next step is to request
    membership in a club (``POST /api/club-memberships``), which the club decides on.
    """
    try:
        await register(session, request.email, request.display_name)
    except LoginError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "detail": tr(
            locale,
            en="We've sent a confirmation code. It's valid for ten minutes. "
            "If an account already existed for this address, it's the usual sign-in code.",
            de="Wir haben einen Bestätigungscode geschickt. Er gilt zehn Minuten. "
            "Bestand zu dieser Adresse schon ein Konto, ist es der gewohnte Anmeldecode."
        )
    }


@router.post(
    "/email/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a one-time code",
)
async def email_request(
    request: EmailRequest,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> dict[str, str]:
    """Always responds the same — regardless of whether an account exists for this address.

    Otherwise, this endpoint could be used to enumerate existing accounts.
    """
    await request_email_code(session, request.email)
    return {
        "detail": tr(
            locale,
            en=(
                "If an account exists for this address, a code is on its way. "
                "It's valid for ten minutes."
            ),
            de=(
                "Falls zu dieser Adresse ein Konto besteht, ist ein Code unterwegs. "
                "Er gilt zehn Minuten."
            ),
        )
    }


@router.post("/email/verify", response_model=TokenOut, summary="Redeem a one-time code")
async def email_verify(
    request: EmailVerify, session: AsyncSession = Depends(get_session)
) -> TokenOut:
    try:
        user = await verify_email_code(session, request.email, request.code)
    except LoginError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)


@router.post(
    "/oidc/{provider}",
    response_model=TokenOut,
    summary="Sign in with Google or Microsoft",
)
async def oidc_login(
    provider: str, request: OidcLogin, session: AsyncSession = Depends(get_session)
) -> TokenOut:
    try:
        user = await login_with_oidc(session, provider, request.id_token)
    except LoginError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    await session.commit()
    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut, summary="Get my account")
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.of(user)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete my account",
)
async def delete_my_account(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> None:
    """Deletes the signed-in account outright — deliberately different from
    ``DELETE /api/auth/users/{id}`` (administration removing *someone else*, which keeps
    the row for its history, see Story Z-6).

    This is a temporary, testing-phase convenience (Story Z-7): while accounts are still
    mostly test data, being able to clean up your own is worth more than an audit trail.
    Once accounts are reachable from real season history (registrations, results, waiver
    confirmations someone else relies on), a real delete stops being safe, and this should
    become a deactivation too, or gain a precondition ("no active registrations"). Revisit
    before real seasons depend on this data — don't just leave it as-is.

    A ``Sailor`` is a separate record linked only by email, never by foreign key, so
    deleting the account never touches squad, series, or event history — only the account
    row and the administrative records that point at it by id.
    """
    # ClubMember has no ORM relationship back from User (one-directional), so it is not
    # cascaded automatically — remove it explicitly.
    await session.execute(delete(ClubMember).where(ClubMember.user_id == acting.id))
    # A waiver confirmation is someone else's evidence that they agreed to the waiver —
    # it must not disappear just because the staff member who recorded it deleted their
    # own account. Drop the reference, keep the confirmation.
    await session.execute(
        update(WaiverConfirmation)
        .where(WaiverConfirmation.recorded_by_user_id == acting.id)
        .values(recorded_by_user_id=None)
    )
    # UserRole and Identity cascade via the ORM relationship (cascade="all, delete-orphan").
    await session.delete(acting)
    await session.commit()


@router.get(
    "/users",
    response_model=list[UserOut],
    dependencies=[Depends(require_club_manager)],
    summary="List accounts",
)
async def list_users(
    club_id: int | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[UserOut]:
    """Also for club managers: they need to find people to assign to their club."""
    stmt = select(User).order_by(User.display_name)
    if club_id is not None:
        stmt = stmt.where(User.club_id == club_id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.display_name).like(pattern), User.email.like(pattern))
        )
    result = await session.execute(stmt)
    return [UserOut.of(user) for user in result.scalars()]


@router.put("/users/{user_id}/club", response_model=UserOut, summary="Assign a club")
async def set_club(
    user_id: int,
    request: ClubUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(require_club_manager),
    locale: Locale = Depends(resolve_locale),
) -> UserOut:
    """Assigns an account to a club — permanently, not per matchday.

    A club manager may only assign a club **they organize** (Story A-8 — that can now be
    more than one), and may only move people who have no club or are already assigned to
    one of those clubs. Otherwise they could seize other teams. Administration is exempt
    from these restrictions.
    """
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=tr(locale, en="This account does not exist.", de="Dieses Konto gibt es nicht.")
        )

    if request.club_id is not None:
        club = (
            await session.execute(select(Club).where(Club.id == request.club_id))
        ).scalar_one_or_none()
        if club is None:
            raise HTTPException(
                status_code=404,
                detail=tr(
                    locale,
                    en=f"Club {request.club_id} is not known.",
                    de=f"Verein {request.club_id} ist nicht bekannt."
                )
            )

    if not acting.has_any(Role.ADMIN):
        managed = acting.managed_club_ids
        if not managed:
            raise HTTPException(
                status_code=409,
                detail=tr(
                    locale,
                    en="Your account does not organize any club.",
                    de="Ihr Konto leitet keinen Verein."
                ),
            )
        if request.club_id is not None and request.club_id not in managed:
            raise HTTPException(
                status_code=403,
                detail=tr(
                    locale,
                    en="You can only assign a club you organize.",
                    de="Sie können nur einen Verein zuordnen, den Sie leiten."
                )
            )
        if user.club_id is not None and user.club_id not in managed:
            raise HTTPException(
                status_code=403,
                detail=tr(
                    locale,
                    en="This person already belongs to a different club.",
                    de="Diese Person gehört bereits zu einem anderen Verein."
                ),
            )

    vorher = user.club_id
    if vorher == request.club_id:
        return UserOut.of(user)

    user.club_id = request.club_id
    # Who assigned which club to whom must remain traceable: entries, contributions,
    # and check-in depend on it.
    session.add(
        AuditLog(
            entity_type="app_user",
            entity_id=user.id,
            action="set_club",
            actor=acting.email,
            payload={"from": vorher, "to": request.club_id},
        )
    )
    await session.commit()
    return UserOut.of(user)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Create an account",
)
async def create_user(
    request: UserCreate,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> UserOut:
    email = request.email.lower()
    if (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="An account already exists for this address.",
                de="Für diese Adresse gibt es schon ein Konto."
            )
        )

    # Created by administration: the address is considered verified because it comes from
    # an entry or import and was not claimed by the person themselves.
    user = User(
        email=email,
        display_name=request.display_name,
        club_id=request.club_id,
        email_verified=True,
    )
    user.role_rows = [UserRole(role=role) for role in dict.fromkeys(request.roles)]
    # A fresh account has no sign-in method yet — the identity is created only on first sign-in.
    # Explicitly empty, otherwise the response tries to load it.
    user.identities = []
    session.add(user)
    await session.commit()
    return UserOut.of(user)


@router.delete(
    "/users/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_admin)],
    summary="Remove an account",
)
async def remove_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(require_admin),
    locale: Locale = Depends(resolve_locale),
) -> UserOut:
    """Removing an account never deletes its row — too much points at it by id (audit
    log entries, past decisions, results someone entered) for that to be safe. Instead
    it's deactivated: `is_active=False` blocks sign-in immediately, same as a suspended
    account, and the row — along with its history — stays intact.
    """
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=tr(locale, en="This account does not exist.", de="Dieses Konto gibt es nicht.")
        )
    if user.id == acting.id:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="You cannot remove your own account.",
                de="Das eigene Konto lässt sich nicht entfernen."
            ),
        )

    user.is_active = False
    await session.commit()
    return UserOut.of(user)


@router.put(
    "/users/{user_id}/roles",
    response_model=UserOut,
    summary="Grant or revoke roles",
)
async def set_roles(
    user_id: int,
    request: RolesUpdate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(require_admin),
    locale: Locale = Depends(resolve_locale),
) -> UserOut:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=tr(locale, en="This account does not exist.", de="Dieses Konto gibt es nicht.")
        )

    wanted = list(dict.fromkeys(request.roles))
    # If someone revokes their own admin role, they might lock themselves out.
    if user.id == acting.id and Role.ADMIN not in wanted:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="You cannot revoke your own admin role.",
                de="Die eigene Verwaltungsrolle lässt sich nicht selbst entziehen."
            ),
        )

    user.role_rows = [UserRole(user_id=user.id, role=role) for role in wanted]
    await session.commit()
    await session.refresh(user)
    return UserOut.of(user)
