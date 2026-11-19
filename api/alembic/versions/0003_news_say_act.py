"""The news say Act where they said Spieltag, and the 2027 dates are "Termine 2027".

Content, not schema: the posts live in the database, so the words change here, where
staging tries them on a copy of production first (docs/deploy-server.md § Deploying).
Only news — press releases are documents as they were sent out. Each replacement matches
the seeded wording; a post edited since keeps its own words. Slugs stay: a URL is made once.

Revision ID: 0003_news_say_act
Revises: 0002_post_drops_quote
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_news_say_act"
down_revision: str | None = "0002_post_drops_quote"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATES = "termine-2027-segel-bundesliga-junioren-liga-und-pokal"

# Exact phrases first: where the word order changes, or the table of the 2027 dates.
PHRASES = [
    ("den Sieg am 4. Spieltag", "den Sieg bei Act 4"),
    ("<td>1. + 2. Liga</td>", "<td>1. &amp; 2.</td>"),
    ("<td>1. Liga</td>", "<td>1.</td>"),
    ("die ACTs der", "die Acts der"),
    ("<th>ACT</th>", "<th>Act</th>"),
    ("<td>ACT ", "<td>Act "),
]
# Then the word in all its forms (\m \M: Postgres' word boundaries), the longest first.
WORDS = [("Spieltagen", "Acts"), ("Spieltage", "Acts"), ("Spieltags", "Acts"), ("Spieltag", "Act")]


def upgrade() -> None:
    post = sa.table(
        "post", sa.column("kind"), sa.column("slug"), sa.column("title"),
        sa.column("teaser"), sa.column("body"),
    )  # fmt: skip
    for column in ("title", "teaser", "body"):
        value = post.c[column]
        for old, new in PHRASES:
            value = sa.func.replace(value, old, new)
        for old, new in WORDS:
            value = sa.func.regexp_replace(value, rf"\m{old}\M", new, "g")
        op.execute(post.update().where(post.c.kind == "news").values({column: value}))
    op.execute(
        post.update()
        .where(
            post.c.slug == DATES,
            post.c.title == "Termine 2027: Segel-Bundesliga, Junioren-Liga und Pokal",
        )
        .values(title="Termine 2027")
    )


def downgrade() -> None:
    """Words are not put back: the old ones are what this removed on purpose."""
