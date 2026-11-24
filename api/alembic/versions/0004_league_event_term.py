"""A league says what its numbered events are called: the 1. and 2. Liga *Spieltag*, the
Junioren-Liga *Act*, the DSL-Pokal neither (decided 2026-11-19, `League.event_term`).

And the Bundesliga's news say *Spieltag* again, where 0003 made them say *Act* the same
day: the Junioren keep *Act*. Content, not schema — each replacement is an exact phrase of
the seeded wording, so a post edited since keeps its own words.

Revision ID: 0004_league_event_term
Revises: 0003_news_say_act
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_league_event_term"
down_revision: str | None = "0003_news_say_act"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TERMS = {"1-liga": "matchday", "2-liga": "matchday", "junioren-liga": "act", "dsl-pokal": "name"}

# 0003's replacements in the Bundesliga's posts, undone; the Junioren's "Acts" stay.
PHRASES = [
    ("alle Acts der 1. und 2.", "alle Spieltage der 1. und 2."),
    (
        "Freitag bis Sonntag</em></p><table><thead><tr><th>Act</th>",
        "Freitag bis Sonntag</em></p><table><thead><tr><th>Spieltag</th>",
    ),
    ("den fünften Act", "den fünften Spieltag"),
    ("Den Act gewinnen", "Den Spieltag gewinnen"),
    ("den Sieg bei Act 4", "den Sieg am 4. Spieltag"),
    ("seinen eigenen Act gewonnen", "seinen eigenen Spieltag gewonnen"),
    ("vor dem Act in Hamburg", "vor dem Spieltag in Hamburg"),
    ("Der vierte Act der Saison", "Der vierte Spieltag der Saison"),
    ("dritten Act", "dritten Spieltag"),
    ("den Act mit 35 Punkten", "den Spieltag mit 35 Punkten"),
    ("drei von sechs Acts", "drei von sechs Spieltagen"),
    ("drei von fünf Acts", "drei von fünf Spieltagen"),
]


def upgrade() -> None:
    op.add_column(
        "league",
        sa.Column("event_term", sa.String(length=16), server_default="name", nullable=False),
    )
    league = sa.table("league", sa.column("slug"), sa.column("event_term"))
    for slug, term in TERMS.items():
        op.execute(league.update().where(league.c.slug == slug).values(event_term=term))

    post = sa.table(
        "post", sa.column("kind"), sa.column("title"), sa.column("teaser"), sa.column("body"),
    )  # fmt: skip
    for column in ("title", "teaser", "body"):
        value = post.c[column]
        for old, new in PHRASES:
            value = sa.func.replace(value, old, new)
        op.execute(post.update().where(post.c.kind == "news").values({column: value}))


def downgrade() -> None:
    """The words are not put back; the column goes."""
    op.drop_column("league", "event_term")
