# A PDF from the pairing tool is never byte-identical twice, so equal bytes prove the cache and unequal bytes prove nothing

**Symptom** — `test_the_same_list_renders_to_the_same_bytes` ("a printed list must be
reproducible") was green, and so was `test_a_different_title_renders_a_different_file`
(`assert first != second`). Both looked like checks on the rendering.

**Cause** — `PdfExport` stamps the render time into the file (`/CreationDate`, to the
second). With `app.pairing.pdf._CACHE` cleared between two renders of the same list the
bytes differ — the first test only passed because the second call was answered from the
in-process cache. The second could not fail at all: an ignored title still gives
different bytes.

**Rule** — compare equal bytes only to prove the cache answered (that test is now named
so). To check what a sheet *says*, inflate the page streams and look for the text
(`page_text()` in `tests/unit/test_pairing_pdf.py` — titles show up as `(Act 2)Tj`).

**Evidence** — two renders of `request_for()` with `_CACHE.clear()` between them:
`D:20261012214306` vs `D:20261012214308`, bytes unequal. And the title test asserts `b"(Act 2)Tj" in page_text(...)`; changing the
expected text to `(Act 9)Tj` makes it fail, which the old `first != second` never did.

**Seen** — 2026-10-12, pruning the backend suite.
