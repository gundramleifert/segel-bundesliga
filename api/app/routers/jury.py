"""The league's pool of judges and who sits on which jury — Stories JU-1–JU-5,
`app/services/jury.py`.

``router`` is the jury organizer's (`/office/jury`), ``me_router`` the judge's
(*Me › Jury*). Each write commits first and mails after: a mail about a row that did not
land would be a mail about nothing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_user, require_site
from app.config import settings
from app.db import get_session
from app.filters import JudgeFilter
from app.listing import ListDepends
from app.mail import send_jury_approval, send_jury_invitation, send_jury_message
from app.models import Event, JuryRequest
from app.models.auth import ObjectType, Relation, User
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.schemas.jury import (
    AnswerIn,
    CandidateOut,
    InvitationsIn,
    InvitationsOut,
    JudgeIn,
    JudgeOut,
    JuryEventOut,
    JuryRequestOut,
    LicencesIn,
    MessageIn,
    MessageOut,
    MyJuryOut,
)
from app.services import grants, jury

router = APIRouter(
    prefix="/api/jury",
    tags=["jury"],
    dependencies=[Depends(require_site(Relation.JURY_ORGANIZER))],
)
me_router = APIRouter(prefix="/api/me/jury", tags=["jury"])

MY_JURY = "/me/profile/jury"


def _event_out(event: Event) -> JuryEventOut:
    return JuryEventOut(
        id=event.id,
        title=event.title,
        starts_on=event.starts_on,
        ends_on=event.ends_on,
        status=event.status,
        published=event.published,
        series=event.series.short_name if event.series else None,
    )


def _request_out(request: JuryRequest) -> JuryRequestOut:
    return JuryRequestOut(
        event=_event_out(request.event),
        user_id=request.user_id,
        state=request.state,
        invited_at=request.invited_at,
        answered_at=request.answered_at,
    )


async def _with_series(session: AsyncSession, request: JuryRequest) -> JuryRequest:
    """The request's event with its series, for :func:`_event_out`."""
    request.event = (
        await session.execute(
            select(Event).options(selectinload(Event.series)).where(Event.id == request.event_id)
        )
    ).scalar_one()
    return request


async def _pool_ids(session: AsyncSession) -> set[int]:
    return {
        g.user_id for g in await grants.grants_on(session, ObjectType.SITE, None, Relation.JUDGE)
    }


def _event_ids(events: str | None) -> list[int]:
    try:
        return [int(e) for e in events.split(",") if e.strip()] if events else []
    except ValueError:
        raise Problem(422, "jury-filter-invalid", "`events` is a list of event ids.") from None


# ---------------------------------------------------------------- the pool (JU-1, JU-2, JU-3)


@router.get("/judges", response_model=Page[JudgeOut], summary="The pool of judges")
async def list_judges(
    filters: JudgeFilter = ListDepends(JudgeFilter),
    params: PageParams = PageInput,
    events: str | None = Query(
        default=None, description="Event ids, comma-separated: each judge's state at each"
    ),
    session: AsyncSession = Depends(get_session),
) -> Page[JudgeOut]:
    """Stories JU-1, JU-3: every judge, their licences and their state at the events picked."""
    stmt = filters.sort(filters.filter(select(User).where(User.id.in_(await _pool_ids(session)))))
    users, total = await paginate(session, stmt, params)
    ids = [u.id for u in users]
    licences = await jury.licences_of(session, ids)
    states: dict[int, dict[str, str]] = {}
    if event_ids := _event_ids(events):
        rows = await session.execute(
            select(JuryRequest).where(
                JuryRequest.user_id.in_(ids), JuryRequest.event_id.in_(event_ids)
            )
        )
        for r in rows.scalars():
            states.setdefault(r.user_id, {})[str(r.event_id)] = r.state
    items = [
        JudgeOut(
            user_id=u.id,
            name=u.display_name,
            email=u.email,
            licences=licences.get(u.id, []),
            states=states.get(u.id, {}),
        )
        for u in users
    ]
    return page_of(items, total, params)


@router.get("/candidates", response_model=Page[CandidateOut], summary="Accounts to add as judges")
async def list_jury_candidates(
    q: str | None = Query(default=None, description="Search in name and address"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[CandidateOut]:
    """Story JU-1: active accounts not yet in the pool."""
    stmt = select(User).where(User.is_active.is_(True), User.id.not_in(await _pool_ids(session)))
    stmt = apply_search(stmt, q, User.display_name, User.email).order_by(User.display_name, User.id)
    users, total = await paginate(session, stmt, params)
    items = [CandidateOut(user_id=u.id, name=u.display_name, email=u.email) for u in users]
    return page_of(items, total, params)


@router.post(
    "/judges",
    response_model=JudgeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a judge to the pool",
)
async def add_judge(
    body: JudgeIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> JudgeOut:
    """Story JU-1: ``user:judge:site`` — grants nothing on any event."""
    user = await jury.add_judge(session, body.user_id, actor=acting)
    await session.commit()
    licences = (await jury.licences_of(session, [user.id])).get(user.id, [])
    return JudgeOut(
        user_id=user.id, name=user.display_name, email=user.email, licences=licences, states={}
    )


@router.delete(
    "/judges/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a judge"
)
async def remove_judge(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Response:
    """Story JU-1: out of the pool; open requests withdrawn, an approved jury kept."""
    await jury.remove_judge(session, user_id, actor=acting)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- asking (JU-3)


@router.get("/events", response_model=Page[JuryEventOut], summary="Events to staff")
async def list_jury_events(
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[JuryEventOut]:
    """Story JU-3: every event not over, drafts included, the next first."""
    stmt = (
        select(Event)
        .options(selectinload(Event.series))
        .where(Event.status.not_in(jury.CLOSED))
        .order_by(Event.starts_on.is_(None), Event.starts_on, Event.id)
    )
    events, total = await paginate(session, stmt, params)
    return page_of([_event_out(e) for e in events], total, params)


@router.post("/invitations", response_model=InvitationsOut, summary="Ask judges for events")
async def invite_judges(
    body: InvitationsIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> InvitationsOut:
    """Story JU-3: the events × the judges, one mail per judge naming every event newly
    asked; a pair asked before is left as it was."""
    invited = await jury.invite(session, body.event_ids, body.user_ids)
    await session.commit()
    for asked in invited.asked:
        await send_jury_invitation(
            asked.user.email,
            name=asked.user.display_name,
            organizer=acting.display_name,
            events=[e.title for e in asked.events],
            note=body.note,
            link=f"{settings.site_url}{MY_JURY}",
        )
    return InvitationsOut(
        created=invited.created, existing=invited.existing, mailed=len(invited.asked)
    )


@router.post("/messages", response_model=MessageOut, summary="Write to judges")
async def message_judges(
    body: MessageIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> MessageOut:
    """Story JU-3: one mail to each judge ticked — only the pool."""
    users = await jury.judges(session, body.user_ids)
    for user in users.values():
        await send_jury_message(
            user.email,
            name=user.display_name,
            organizer=acting.display_name,
            subject=body.subject,
            text=body.text,
        )
    return MessageOut(mailed=len(users))


# ---------------------------------------------------------------- approving (JU-5)


@router.put(
    "/events/{event_id}/judges/{user_id}",
    response_model=JuryRequestOut,
    summary="Put a judge on an event's jury",
)
async def approve_judge(
    event_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> JuryRequestOut:
    """Story JU-5: from any state, or with no request at all; writes the event's ``jury``."""
    before = await jury.request_of(session, event_id, user_id)
    newly = before is None or not before.approved
    request = await jury.approve(session, event_id, user_id, actor=acting)
    await session.commit()
    request = await _with_series(session, request)
    if newly:
        judge = await session.get(User, user_id)
        assert judge is not None
        await send_jury_approval(
            judge.email,
            name=judge.display_name,
            organizer=acting.display_name,
            event=request.event.title,
            link=f"{settings.site_url}/me/event/{event_id}",
        )
    return _request_out(request)


@router.delete(
    "/events/{event_id}/judges/{user_id}",
    response_model=JuryRequestOut,
    summary="Take a judge off an event's jury",
)
async def take_judge_off(
    event_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> JuryRequestOut:
    """Story JU-5: the ``jury`` tuple goes, the judge's answer stays."""
    request = await jury.take_off(session, event_id, user_id, actor=acting)
    await session.commit()
    return _request_out(await _with_series(session, request))


# ---------------------------------------------------------------- the judge (JU-2, JU-4)


async def _my_jury(session: AsyncSession, user: User) -> MyJuryOut:
    requests = [await _with_series(session, r) for r in await jury.requests_of(session, user.id)]
    return MyJuryOut(
        judge=jury.is_judge(user),
        licences=(await jury.licences_of(session, [user.id])).get(user.id, []),
        requests=[_request_out(r) for r in requests],
    )


@me_router.get("", response_model=MyJuryOut, summary="My jury")
async def get_my_jury(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> MyJuryOut:
    """Stories JU-2, JU-4: am I a judge, my licences, the events I was asked for."""
    return await _my_jury(session, user)


@me_router.put("/licences", response_model=MyJuryOut, summary="Say which licences I hold")
async def set_my_licences(
    body: LicencesIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> MyJuryOut:
    """Story JU-2: the judge's own word, replacing what was said before."""
    await jury.set_licences(session, user, body.licences)
    await session.commit()
    return await _my_jury(session, user)


@me_router.put(
    "/requests/{event_id}", response_model=JuryRequestOut, summary="Answer a jury request"
)
async def answer_jury_request(
    event_id: int,
    body: AnswerIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> JuryRequestOut:
    """Story JU-4: available (my application) or declined, until I am approved."""
    request = await jury.answer(session, user, event_id, available=body.available)
    await session.commit()
    return _request_out(await _with_series(session, request))
