"""Sign-in and account management.

Three paths to the same account: Google, Microsoft, or a one-time code via email. All end
with a session token that carries roles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    current_user,
    require_admin,
    require_club_manager,
)
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import WaiverConfirmation
from app.models.auth import (
    MODEL,
    SCHEMA,
    Grant,
    ObjectType,
    Relation,
    User,
    parse_object,
    writable,
)
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.services import grants
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


class TupleOut(BaseModel):
    """One relation tuple in FGA's notation — ``user`` · ``relation`` · ``object`` — plus
    the names a screen shows without a lookup per row."""

    id: int
    user_id: int
    user: str = Field(description="The account's email — the user identifier of the tuple")
    user_name: str
    relation: str
    object: str = Field(description='"site", or "<type>:<id>" such as "event:3"')
    object_type: ObjectType
    object_id: int | None
    object_name: str | None = Field(
        default=None, description="Name of the club, series or event; null for the site"
    )

    @classmethod
    def of(cls, row: Grant, user: User) -> TupleOut:
        return cls(
            id=row.id,
            user_id=user.id,
            user=user.email,
            user_name=user.display_name,
            relation=row.relation,
            object=row.object,
            object_type=row.object_type,
            object_id=row.object_id,
            object_name=row.object_name,
        )


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool
    email_verified: bool
    roles: list[str] = Field(
        description="The summary roles derived from the tuples — what the navigation shows tabs by"
    )
    tuples: list[TupleOut]
    identities: list[IdentityOut]

    @classmethod
    def of(cls, user: User) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            email_verified=user.email_verified,
            roles=sorted(user.roles),
            tuples=[TupleOut.of(row, user) for row in sorted(user.grants, key=lambda r: r.id)],
            identities=[
                IdentityOut(provider=row.provider, subject=row.subject) for row in user.identities
            ],
        )


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    roles: list[Relation] = Field(
        default_factory=list, description="Site relations to start with; object tuples come after"
    )


class TupleWrite(BaseModel):
    """FGA's write: ``user`` (the account's email), ``relation``, ``object`` (``site`` or
    ``<type>:<id>``)."""

    user: EmailStr
    relation: Relation
    object: str = Field(examples=["event:3", "club:7", "site"])


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
async def register_account(
    request: Registration,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> dict[str, str]:
    """Creates an account and sends a confirmation code to the provided address.

    Confirmation works via the same path as sign-in: enter the code at
    ``POST /api/auth/email/verify``. Before confirmation, the address is considered
    merely claimed.

    The account initially has neither role nor club. A club's admin then makes it a
    member by writing the ``member`` tuple on the club (Story Z-5).
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
            "Bestand zu dieser Adresse schon ein Konto, ist es der gewohnte Anmeldecode.",
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


#: Story A-13 — the columns this list may be sorted by.
USER_SORT = {"display_name": User.display_name, "email": User.email}


@router.get(
    "/users",
    response_model=Page[UserOut],
    dependencies=[Depends(require_club_manager)],
    summary="List accounts",
)
async def list_users(
    q: str | None = None,
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[UserOut]:
    """Also for club managers: they need to find people to assign to their club.

    Paged since Story A-13 — there is one account per registered sailor, so this list is
    as long as the sailor register and had no limit at all.
    """
    stmt = select(User)
    stmt = apply_search(stmt, q, User.display_name, User.email)
    users, total = await paginate(
        session,
        stmt,
        params,
        sortable=USER_SORT,
        default_order=[User.display_name, User.id],
    )
    return page_of([UserOut.of(user) for user in users], total, params)


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
                de="Für diese Adresse gibt es schon ein Konto.",
            ),
        )

    # Created by administration: the address is considered verified because it comes from
    # an entry or import and was not claimed by the person themselves.
    user = User(
        email=email,
        display_name=request.display_name,
        email_verified=True,
    )
    # Relations at creation are site tuples: a club or event tuple names an object, which
    # the "＋" on the Accounts tab writes one at a time.
    for relation in dict.fromkeys(request.roles):
        grants.check_schema(relation, ObjectType.SITE)
    user.grants = [Grant(relation=relation) for relation in dict.fromkeys(request.roles)]
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
            detail=tr(locale, en="This account does not exist.", de="Dieses Konto gibt es nicht."),
        )
    if user.id == acting.id:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="You cannot remove your own account.",
                de="Das eigene Konto lässt sich nicht entfernen.",
            ),
        )

    user.is_active = False
    await session.commit()
    return UserOut.of(user)


class ModelTypeOut(BaseModel):
    type: ObjectType
    relations: list[Relation]


class ModelOut(BaseModel):
    """The authorization model: the DSL as written, and per object type the relations
    that can be written on it — what the "＋" offers."""

    dsl: str
    types: list[ModelTypeOut]


@router.get(
    "/model",
    response_model=ModelOut,
    dependencies=[Depends(current_user)],
    summary="The authorization model (OpenFGA DSL)",
)
async def get_model() -> ModelOut:
    """One table, read here rather than copied into the frontend, so a relation added to
    a type is offered without a release there."""
    return ModelOut(
        dsl=MODEL.strip(),
        types=[
            ModelTypeOut(
                type=object_type, relations=sorted(writable(object_type), key=list(Relation).index)
            )
            for object_type in SCHEMA
        ],
    )


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_admin)],
    summary="One account with its tuples",
)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> UserOut:
    return UserOut.of(await _user(session, user_id, locale))


@router.get(
    "/tuples",
    response_model=list[TupleOut],
    summary="Who holds what on one object (FGA read)",
)
async def read_tuples(
    object: str = Query(description='"site" or "<type>:<id>", e.g. "event:3"'),
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[TupleOut]:
    """The access list of one object — the event panel shows its managers, race officers
    and jury here. Open to the site's admin and to the object's own managers."""
    object_type, object_id = _object(object)
    obj = await grants.resolve(session, object_type, object_id)
    _may_administer(acting, object_type, obj)
    rows = await grants.grants_on(session, object_type, object_id)
    return [TupleOut.of(row, row.user) for row in rows]


@router.post(
    "/tuples",
    response_model=TupleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Write one tuple (FGA write)",
)
async def write_tuple(
    request: TupleWrite,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> TupleOut:
    """Story Z-2. The rules — the schema, the object must exist, no duplicate — live in
    `app/services/grants.py`, shared with the club screen. The site's admin writes any
    tuple; an object's manager writes tuples on that object, so an organizer names the
    race officers and the jury of their own event without administration."""
    object_type, object_id = _object(request.object)
    obj = await grants.resolve(session, object_type, object_id)
    _may_administer(acting, object_type, obj)
    target = (
        await session.execute(select(User).where(User.email == request.user.lower()))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="No account with this address. Create it first.",
                de="Kein Konto mit dieser Adresse. Bitte zuerst anlegen.",
            ),
        )
    row = await grants.grant(
        session, target, request.relation, object_type, object_id, actor=acting
    )
    await session.commit()
    return TupleOut.of(row, target)


@router.delete(
    "/tuples/{tuple_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one tuple (FGA delete)",
)
async def delete_tuple(
    tuple_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> None:
    """Exactly this tuple goes; every other one the person holds stays. Refuses to delete
    the caller's own `admin` and a club's last organizer (Story A-8)."""
    row = await session.get(Grant, tuple_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale, en="This tuple does not exist.", de="Diese Berechtigung gibt es nicht."
            ),
        )
    obj = await grants.resolve(session, row.object_type, row.object_id)
    # Leaving a club is the one write a person makes on themselves (Story Z-5): their
    # own `member` tuple. Everything else needs the object's admin.
    leaving = row.relation == Relation.MEMBER and row.user_id == acting.id
    if not leaving:
        _may_administer(acting, row.object_type, obj)
    # The account through its own query, so its `grants` collection is loaded — reached
    # through `row.user` it is not, and touching it would lazy-load outside the async
    # context (docs/gotchas: a relationship on a row you just appended is not loaded).
    target = await _user(session, row.user_id, locale)
    # The row the user's collection holds is the one to drop (same identity map).
    mine = next(g for g in target.grants if g.id == row.id)
    await grants.revoke(session, target, mine, actor=acting)
    await session.commit()


def _object(text: str) -> tuple[ObjectType, int | None]:
    try:
        return parse_object(text)
    except ValueError as exc:
        raise Problem(422, "tuple-object-invalid", "Not an object.", detail=str(exc)) from exc


def _may_administer(acting: User, object_type: ObjectType, obj) -> None:
    if not grants.may_administer(acting, object_type, obj):
        raise Problem(
            403,
            "tuple-forbidden",
            "Only the site's admin or the object's manager may change who holds what on it.",
            object=object_type.value,
        )


async def _user(session: AsyncSession, user_id: int, locale: Locale) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=tr(locale, en="This account does not exist.", de="Dieses Konto gibt es nicht."),
        )
    return user
