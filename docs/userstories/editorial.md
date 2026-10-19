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
- **A list carries no text.** News cards and the press centre's lines show the title, date,
  lead and picture; the text is read from the post's own address — for a release, once it
  is opened.
- **A picture is uploaded or chosen from the site's pictures.** An upload is a JPEG, PNG
  or WebP, checked by content, re-encoded, stored under a random name and served publicly;
  its credit is a line of text beside it. Without a picture the league's own stands in.
- **A picture goes into the text the way it does in WordPress** (decided 2026-10-19 — the
  toolbar's file chooser alone was found fiddly): dragged from a folder onto the text, or
  pasted with Ctrl+V, it is uploaded and lands where it was dropped or where the cursor
  is. The post's own picture takes a dropped file the same way.
- **A link is one shortcut away.** Ctrl+K (⌘K) opens the address row; with text selected
  the text becomes the link, with nothing selected the link is inserted with a text of its
  own (the address if none is given). An address without its `https://` gets it, an email
  address becomes `mailto:`, a path on this site (`/1-liga/standings`) stays a path.
  Pasting an address over selected text links it. With the cursor in a link a row shows
  where it leads, to open, change or remove it.
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

## Pictures

### R-2 ● Keep the pictures in a library, fed by an import API
As **editorial** I want **every picture the site shows in one library, and photographers
able to deliver pictures into it without an account**, so that **a photo is uploaded once,
used in any post, and arrives from wherever the photographers already are**
(`docs/PLAN_MEDIA.md`, phase 1).

Acceptance criteria:
- **Every upload is a library entry** — from the editor (dropped, pasted, chosen) and from
  the import API alike. An entry knows the picture, a small preview, its measurements, the
  file's original name, alt text, credit, the camera's date and where it came from. The
  picture is re-encoded as for R-1 (upright, at most 2400 px, no EXIF — the camera's date is
  read before EXIF is dropped, the location never kept).
- **The same picture twice is one entry.** An upload whose bytes match an entry's answers
  that entry instead of storing a copy.
- **A picture is addressed by a random name** (`/api/media/<name>.jpg`), never by its row
  number, so an imported picture nobody used yet cannot be found by counting.
- **The import API is for machines** (decided 2026-10-19): `POST /api/import/media` takes a
  picture and, optionally, its alt text, credit and the source's own id for it, with an
  **import key** in the `X-Import-Key` header — not a person's sign-in. A source's id sent
  twice with the same key answers the entry already made, so a bridge that retries never
  duplicates. Every source — the upload page below, later a Nextcloud or Flickr bridge —
  uses this one endpoint and nothing else.
- **Import keys are made and revoked by editorial**, on the *Media* tab: a label ("Photos
  Kiel, act 3"), an optional credit put on every picture that arrives without one, and how
  long it is valid. The key is shown **once**, as an upload link; only its hash is stored.
  A revoked or expired key is refused, and what arrived with it stays. How many pictures a
  key delivered and when it was last used are counted, not stored.
- **The first source is our own upload page** (`/upload`), opened from that link on a
  phone: it says whose upload it is, takes several pictures at once — dropped or chosen —
  asks for the credit once and remembers it, and shows each picture's progress. It uses the
  import API like any other source would. The key travels in the link's `#fragment`, so it
  never appears in a server's log or a referrer.
- **A picture may belong to an event or to a series** (decided 2026-10-19), never
  required: a regatta's photos to its event, a season's portrait to its series. An event
  implies its series, so a series' pictures are its own and its events'. An upload link
  may carry one, and every picture sent with it belongs there on arrival — the
  photographer chooses nothing; the upload page says what the pictures are for. It can
  be changed or taken off on the *Media* tab.
- **The library is where a post's pictures come from.** The toolbar's picture button and
  the post's own picture open the library beside the text, with every way in at hand:
  - **pick one** from the library — search, and a filter by event or series;
  - **from the computer** or, on a phone, the camera or the gallery;
  - **from a web address** — the site fetches the picture into the library rather than
    linking to someone else's server (public addresses only, at most 25 MB; a page that
    is not a picture is refused);
  - and still **dropped or pasted** straight onto the text.

  Whatever arrives lands in the library first. A click puts the picture at the cursor
  (with its alt text), or makes it the post's picture (with its credit).
- **Whether a file is a picture is told by its content**, never its name or the type the
  browser declares for it — a JPEG saved as `chart.png` is a JPEG (decided 2026-10-19).
- **The *Media* tab** lists the library newest first with a search over name, alt text and
  credit; an entry's alt text and credit can be corrected there, and it says which posts use
  it. **Deleting is refused while a post uses the picture**, naming those posts.
- Editorial alone — like posts (R-1). The upload page needs nothing but a valid key.

Endpoints: `GET|POST /api/admin/media`, `GET|PATCH|DELETE /api/admin/media/{id}`,
`GET|POST /api/admin/import-keys`, `DELETE /api/admin/import-keys/{id}`,
`POST /api/admin/media/from-url`, `GET /api/import/key`, `POST /api/import/media`,
`GET /api/media/{name}`

Tests: `api/tests/stories/test_media.py::TestLibrary`,
`api/tests/stories/test_media.py::TestImport`,
`api/tests/stories/test_media.py::TestContext`,
`api/tests/stories/test_media.py::TestFromAddress`,
`e2e/media.spec.ts::R-2: a picture library fed by upload links`
