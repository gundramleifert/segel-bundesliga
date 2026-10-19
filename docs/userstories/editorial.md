# Editorial

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

Editorial writes what the site says beyond the results: the news on the association's
home and each league's page, and the releases in each league's press centre. It is the
site's `editor` relation (Story Z-2) — and the site's `admin`, who holds every relation.

## Writing

### R-1 ● Write news and press releases
As **editorial** I want to **write, publish, correct and withdraw news articles and press
releases on the site**, so that **a new article does not need a developer and a release**.

Acceptance criteria:
- **Only editorial writes** (decided 2026-10-19): the site's `editor`, and its `admin`
  through the model. A club, series or event organizer cannot — announcements from an
  event are Story VA-11, posts by participants VA-4.
- **One kind of post, two kinds of page.** A post is a **news** article or a **press**
  release. An article has a title, a lead (the teaser on its card), the text, an optional
  quote with who said it, a byline and a picture; a release has a title, a date and its
  text. Both belong to **one league or to the association**: the association's appear on
  every league's page and on the home page.
- **Saving never requires publishing** — the same rule as an event (Story VA-8). A post
  starts as a draft; the public site does not show it and its address answers 404. Publishing
  locks nothing, and withdrawing it makes it a draft again.
- **The address is made once.** The slug comes from the title on creation and stays when
  the title is corrected, so a link someone shared keeps working. A taken slug gets a number
  rather than overwriting another post.
- **The date is the one shown**, set by editorial; it defaults to today. Lists are newest
  first.
- **A picture is uploaded or chosen from the site's pictures.** An upload is a JPEG or PNG,
  checked by content, stored under a random name and served publicly; its credit is a line
  of text beside it. Without a picture the league's own stands in.
- **The text is written in a rich-text editor** (decided 2026-10-19 — editorial knows
  WordPress, not Markdown): a toolbar for the paragraph style (text, heading, subheading),
  bold, italic, underline, strike, lists, quote, link, picture and table, each with a
  tooltip. Pasting from Word or a web page keeps headings, lists and tables where the
  clipboard carries them. The editor is **TipTap** (MIT): CKEditor 5 and TinyMCE were the
  most complete, but are GPL or commercial, and a licence other than MIT or Apache rules an
  editor out; between TipTap and Plate, which scored the same, TipTap is the more
  established. It is loaded only on the editing page.
- **The server cleans the text on every write** (`app/services/rich_text.py`, `nh3`): only
  what the toolbar makes is kept — a pasted `<script>`, an `onclick`, a `javascript:` link
  or a word processor's styles are dropped before they are stored, so the public page can
  show the stored HTML as it is.
- **The examples the site shipped with are posts too**, seeded and marked as examples; each
  still says so on its page until editorial deletes or replaces it.
- In the administration the posts are a tab, *News*, for editorial alone: the list with
  drafts marked, a page to create one and the same page to edit it.

Endpoints: `GET /api/posts`, `GET /api/posts/{slug}`, `GET /api/admin/posts`,
`POST /api/admin/posts`, `GET|PATCH|DELETE /api/admin/posts/{id}`,
`POST /api/admin/posts/photo`

Tests: `api/tests/stories/test_posts.py::TestWritePosts`,
`api/tests/stories/test_posts.py::TestReadPosts`,
`e2e/editorial.spec.ts::R-1: editorial writes news and press releases`
