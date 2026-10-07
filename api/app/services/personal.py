"""A person's own space (Stories S-5, S-6): who sees their documents, a checked IBAN, and
what goes with the account when it is deleted.
"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BankAccount,
    Club,
    Event,
    ExpenseClaim,
    ExpenseDocument,
    Payment,
    PersonalDocument,
)
from app.models.auth import Grant, Relation, User
from app.models.finance import ClaimStatus
from app.problems import Problem
from app.services import uploads

#: Where personal documents live, under the uploads directory.
DOCUMENTS = "documents"
#: Where receipts on claims live.
RECEIPTS = "expenses"

#: The relations on an event that make its organizers the person's organizers (Story S-5):
#: whoever works the event. A plain participant is not among them — a sailor's papers are
#: the club's business, which the ``member`` tuple covers.
WORKS_THE_EVENT = (Relation.HELPER, Relation.JURY, Relation.RACE_OFFICER, Relation.MANAGER)


def normalised_iban(raw: str) -> str:
    """The IBAN without spaces, upper case, its check digits verified (ISO 13616: move
    the first four characters to the end, letters to numbers, the result mod 97 is 1) —
    or ``iban-invalid``. Catches a mistyped digit before a transfer bounces."""
    iban = "".join(raw.split()).upper()
    if not (15 <= len(iban) <= 34) or not iban[:2].isalpha() or not iban[2:4].isdigit():
        raise Problem(422, "iban-invalid", "This is not a valid IBAN.")
    if not iban.isalnum():
        raise Problem(422, "iban-invalid", "This is not a valid IBAN.")
    digits = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    if int(digits) % 97 != 1:
        raise Problem(
            422,
            "iban-invalid",
            "This is not a valid IBAN.",
            detail="The check digits do not match.",
        )
    return iban


async def may_see_documents(session: AsyncSession, viewer: User, owner_id: int) -> bool:
    """The owner, and the owner's organizers (Story S-5): whoever is ``manager`` — by the
    model, so the host club's and the series' managers are included — of an event the
    owner works directly, or of a club the owner is a member of."""
    if viewer.id == owner_id:
        return True
    grants = (await session.execute(select(Grant).where(Grant.user_id == owner_id))).scalars().all()
    for club_id in {g.club_id for g in grants if g.relation == Relation.MEMBER and g.club_id}:
        if viewer.can(Relation.MANAGER, on=Club(id=club_id)):
            return True
    event_ids = {g.event_id for g in grants if g.relation in WORKS_THE_EVENT and g.event_id}
    if event_ids:
        events = (await session.execute(select(Event).where(Event.id.in_(event_ids)))).scalars()
        if any(viewer.can(Relation.MANAGER, on=event) for event in events):
            return True
    return False


async def forget(session: AsyncSession, user: User) -> None:
    """What goes with a deleted account (Story Z-7), not yet committed: the documents and
    their files, the bank account, the claims never submitted. A submitted claim stays —
    it is the paying club's record — with the account link cleared, its claimant's name
    and IBAN copy kept for the books (open question Q5 of the plan)."""
    documents = (
        (await session.execute(select(PersonalDocument).where(PersonalDocument.user_id == user.id)))
        .scalars()
        .all()
    )
    for document in documents:
        uploads.discard(DOCUMENTS, document.stored_name)
        await session.delete(document)
    await session.execute(delete(BankAccount).where(BankAccount.user_id == user.id))

    drafts = (
        (
            await session.execute(
                select(ExpenseClaim).where(
                    ExpenseClaim.claimant_user_id == user.id,
                    ExpenseClaim.status == ClaimStatus.DRAFT,
                )
            )
        )
        .scalars()
        .all()
    )
    for claim in drafts:
        for receipt in claim.documents:
            uploads.discard(RECEIPTS, receipt.stored_name)
        await session.delete(claim)

    await session.execute(
        update(ExpenseClaim)
        .where(ExpenseClaim.claimant_user_id == user.id)
        .values(claimant_user_id=None)
    )
    await session.execute(
        update(ExpenseClaim)
        .where(ExpenseClaim.decided_by_user_id == user.id)
        .values(decided_by_user_id=None)
    )
    await session.execute(
        update(ExpenseDocument)
        .where(ExpenseDocument.uploaded_by_user_id == user.id)
        .values(uploaded_by_user_id=None)
    )
    await session.execute(
        update(Payment).where(Payment.payee_user_id == user.id).values(payee_user_id=None)
    )
    await session.execute(
        update(Payment).where(Payment.issued_by_user_id == user.id).values(issued_by_user_id=None)
    )
