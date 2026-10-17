# A semicolon in a Mermaid diagram ends the line — the diagram silently becomes an error box

**Symptom** — a journey's diagram does not render on GitHub. Instead there is a red
"Parse error on line N … Expecting 'SOLID_ARROW' … got 'NEWLINE'" box, while
`scripts/check-docs.py` is green.

**Cause** — Mermaid treats `;` as the end of a statement, the same as a line break. So
`… frozen; the title still changes` ends the arrow at "frozen", and "the title still
changes" is left over as a broken statement. What misled: the checker read the step IDs
out of the text with a regex and passed. It never parsed the diagram, so "the checker is
green" said nothing about whether the diagram renders.

**Rule** — no `;` inside a ```` ```mermaid ```` block; write `—` or `,`. `check-docs.py`
now refuses one. When a diagram changes in a way the checker cannot see (new syntax, odd
characters), parse it with Mermaid itself before trusting it.

**Evidence** — J-1.12 ("frozen; the title still changes") and J-5.2 ("guidance, saved
anyway; my space says so") were in `docs/journeys/lifecycle.md` and `crew-cleared.md`
from #23 until 2026-10-17. Parsing every journey diagram with `mermaid@11.4.1`
(`mermaid.parse` under jsdom) found exactly these two. After the fix all 18 parse.

**Seen** — 2026-10-17
