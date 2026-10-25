# Editorial

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

Editorial writes what the site says beyond the results: the news on the association's
home and each league's page, and the releases in each league's press centre. It is the
`editor` relation (Story Z-2) — and the `admin`, who holds every relation — on one of
three levels (decided 2026-10-24): the **site's** editor writes about anything; a
**series'** editor about that series and its events; an **event's** editor about that
event. Editorial writes and keeps pictures; it **organizes nothing** — no clubs, series,
events, sailors, waivers or rosters. Until 2026-10-24 there was only the site's editor,
and it was also manager of every event and kept the master data with the admin.

## Writing

### R-1 ● Write news and press releases
As **editorial** I want to **write, publish, correct and withdraw news articles and press
releases on the site**, so that **a new article does not need a developer and a release**.

Acceptance criteria:
- **Only editorial writes** (decided 2026-10-19): an `editor`, and an `admin` through the
  model. A club, series or event organizer cannot — announcements from an event are Story
  VA-11, posts by participants VA-4.
- **A regatta's editor writes about that regatta** (decided 2026-10-24): a series' or an
  event's `editor` writes posts whose event or series is theirs — a series' editor also
  its events'. The post's league is **set from the regatta's league**, not chosen. A post
  about no regatta, or about another regatta, is refused (403); another regatta's post
  is not theirs to know of — their list leaves it out and its address answers 404. They
  organize nothing: the series cannot be changed by them, and an event's tools stay
  closed (`manage` is false). Until 2026-10-24 only the site's `editor` wrote.
- **Each editor works where they write** (decided 2026-10-25): a series' or an event's
  editor finds **News & pictures** in that regatta's context in My space — every post and
  picture about it, a series' including its events', drafts too, with *New post* about
  it — and the same two lists over every regatta they write about under *Me › News* and
  *Me › Pictures*. **Who may change a post is the regatta, never the author**: every
  editor of a regatta changes, publishes and deletes any post or picture about it,
  whoever wrote it, and none about another (`app/services/editorial.py`). The site's
  editor keeps the league office's *News* and *Media*, over everything.
- **One kind of post, two kinds of page.** A post is a **news** article or a **press**
  release. An article has a title, a lead (the teaser on its card), the text, an optional
  quote with who said it, a byline and a picture; a release has a title, a date and its
  text. Both belong to **one league or to the association**: the association's appear on
  every league's page and on the home page.
- **Saving never requires publishing** — the same rule as an event (Story VA-8). A post
  starts as a draft; the public site does not show it and its address answers 404. Publishing
  locks nothing, and withdrawing it makes it a draft again. *Publish* is the page's one
  primary button while the post is a draft and *Save draft* a quiet one, so publishing
  never looks like an ordinary save; the form shows a post as published only once the
  server has said so.
- **A report shows its regatta's photos by itself** (decided 2026-10-20 — a report with a
  cover and a gallery at its end is what most posts are, and a gallery placed by hand
  would ask editorial to do what the library already knows): a post may name an event or
  a series, and its page ends with that one's public pictures from the library — the
  first two dozen, each opening full screen, and the rest on the league's media page.
  Nothing is chosen or ordered by hand; a picture taken off the event leaves the post.
  A post that names nothing shows no gallery.
- **A draft can be read before it is published** (decided 2026-10-20): *Preview* shows the
  post as a reader will see it — its page, its picture, the text's pictures with their
  captions — marked as a preview, for the form as it stands, saved or not; nothing is
  stored by looking.
- **Work is not lost by leaving** (decided 2026-10-20): with changes not saved, leaving the
  page — a link, closing the tab, reloading — asks first. Unsaved changes are also kept
  **on this device** as they are typed; coming back to the post offers them again
  ("Restore" or "Discard"), so a crashed browser or an expired session costs nothing. They
  are never sent by themselves: an automatic save would put half an edit of a published
  post live.
- **The address is made once.** The slug comes from the title on creation and stays when
  the title is corrected, so a link someone shared keeps working. A taken slug gets a number
  rather than overwriting another post.
- **The date is the one shown**, set by editorial; it defaults to today. Lists are newest
  first, and a public list is paged — the news page and the press centre reach every post
  ever published, not only the newest fifty.
- **A list carries no text.** News cards and the press centre's lines show the title, date,
  lead and picture; the text is read from the post's own address — for a release, once it
  is opened.
- **A picture comes from the library** (R-2): chosen there, uploaded, or dropped onto the
  post's picture — never from a list of the site's own pictures (dropped 2026-10-20: a
  second way in that was not the library). Its credit is a line of text beside it.
  Without a picture the league's own stands in.
- **A post never shows a picture from someone else's server** (decided 2026-10-20, the
  rule of R-2): a picture pasted from a web page is copied into the library as it lands
  in the text, and one that cannot be fetched is taken out again with a message. The
  server refuses an outside address in the text or as the post's picture
  (`post-picture-not-in-library`); an address the post already had — the seeded examples
  link the league's own photos — may stay until it is changed.
- **A picture in the text is the library's** (decided 2026-10-20): selected in the editor,
  it shows its alt text, and correcting that corrects the library's entry, in every post
  that shows it. The public page takes alt text, credit and size **from the library when
  it is read**, never from the stored text: each picture gets its width and height (so
  the page does not jump), the WebP sizes for the reader's screen, and its credit as a
  caption.
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
- **The title is set in the form, the text has paragraphs and one kind of heading**
  (decided 2026-10-19 — an article showed its title twice): the title is a field of its
  own, set above the lead as the page's only top-level heading. The editor offers
  *Paragraph* and *Heading* and nothing in between — a section heading inside the text,
  never a second title; any other heading pasted or sent (from Word, an `h1`, an `h3`)
  arrives as that one heading, its words kept. A text that starts with the title again is
  **refused**, never cut: the editor says so and will not save, the server answers
  `post-title-in-text`.
- **The text is written in a rich-text editor** (decided 2026-10-19 — editorial knows
  WordPress, not Markdown): a toolbar for bold, italic, underline, strike, lists, quote,
  link, picture and table, and the paragraph style (paragraph or heading), each with a
  tooltip. Pasting from Word or a web page keeps headings, lists and tables where the
  clipboard carries them — every heading as the one heading the text has. The editor is **TipTap** (MIT): CKEditor 5 and TinyMCE were the
  most complete, but are GPL or commercial, and a licence other than MIT or Apache rules an
  editor out; between TipTap and Plate, which scored the same, TipTap is the more
  established. It is loaded only on the editing page.
- **The server cleans the text on every write** (`app/services/rich_text.py`, `nh3`): only
  what the toolbar makes is kept — a pasted `<script>`, an `onclick`, a `javascript:` link
  or a word processor's styles are dropped before they are stored, so the public page can
  show the stored HTML as it is.
- **The examples the site shipped with are posts too**, seeded and marked as examples; each
  still says so on its page until editorial deletes or replaces it.
- In the administration the posts are a tab, *News*, for editorial alone — an editor of
  any level sees *News* and *Media* and no other tab (Story A-11): the list with
  drafts marked — filtered by kind, league and draft or published, searched by title,
  each league by its name — a page to create one and the same page to edit it.
- **On a phone** the toolbar stays one row that scrolls sideways, the picture panel scrolls
  inside itself instead of pushing the text a screen down, and keyboard tips (Ctrl+V,
  Ctrl+K) are not shown on a touch screen.

Endpoints: `GET /api/posts`, `GET /api/posts/{slug}`, `GET /api/admin/posts`,
`POST /api/admin/posts`, `GET|PATCH|DELETE /api/admin/posts/{id}`,
`POST /api/admin/posts/preview`

Tests: `api/tests/stories/test_posts.py::TestWritePosts`,
`api/tests/stories/test_posts.py::TestPicturesAndReading`,
`api/tests/stories/test_posts.py::TestReadPosts`,
`api/tests/stories/test_posts.py::TestRegattaGallery`,
`e2e/editorial.spec.ts::R-1: editorial writes news and press releases`,
`e2e/media-public.spec.ts::R-1: a report ends with its regatta's photos`,
`api/tests/stories/test_regatta_editorial.py::TestEditorialOfOneRegatta`

## Pictures

### R-2 ● Keep the pictures in a library, fed by an import API
As **editorial** I want **every picture the site shows in one library, and photographers
able to deliver pictures into it without an account**, so that **a photo is uploaded once,
used in any post, and arrives from wherever the photographers already are**
(`docs/PLAN_MEDIA.md`, phase 1).

Acceptance criteria:
- **Every upload is a library entry** — from the editor (dropped, pasted, chosen) and from
  the import API alike. An entry knows the picture, a small preview, its measurements, the
  file's original name, alt text, credit, the camera's date and where it came from.
- **The original is kept, the site serves WebP made from it** (decided 2026-10-20). The
  upload is stored as it came, privately — it still carries the camera's EXIF, its
  location included, so it is never served. The site serves the picture upright, without
  metadata, as WebP at 480, 960, 1600 and 2400 px on the longer edge (each one the
  picture is larger than, never blown up); the camera's date is read before. Those files
  are a cache: a missing size is made again from the original, so a new size or a better
  encoder needs nothing from the photographers. Pictures stored before keep their old
  `.jpg` addresses.
- **Editorial downloads a picture at its full size** for the press — the original's
  pixels, re-encoded as a JPEG without its metadata.
- **The same picture twice is one entry.** An upload whose bytes match an entry's answers
  that entry instead of storing a copy.
- **A picture is addressed by a random name** (`/api/media/<name>.webp`, a size as
  `<name>-960.webp`), never by its row number, so an imported picture nobody used yet
  cannot be found by counting.
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
  asks for the credit once and remembers it, and shows each picture's progress — a
  picture that has arrived is shown by the library's small copy, so a phone sending 150
  photos does not hold them all in memory. It uses the import API like any other source
  would. The key travels in the link's `#fragment`, so it
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
- **Editorial uploads without a link** (decided 2026-10-19): on the *Media* tab, and on the
  upload page itself when signed in — several pictures at once, under their own account.
  On the *Media* tab it is **one step** (decided 2026-10-20 — a "+" that opened a form
  with a "choose pictures" of its own was one too many): the "+" opens the file chooser,
  or pictures are dropped onto the library. They arrive credited to the name this device
  last used, else the editor's own, and belong to the event or series the library's
  filter shows; when the batch is in, *Edit these* selects exactly those pictures for
  one credit, event or series. A link is for those without
  one; without either, the upload page says what is needed.
- **The *Media* tab** lists the library newest first with a search over name, alt text and
  credit; an entry's alt text and credit can be corrected there, and it says which posts use
  it. **Deleting is refused while a post uses the picture**, naming those posts.
- **Alt text still taken from the file's name is marked** on its tile, and a filter shows
  only those — a screen reader reading "DSC 0471" is a picture nobody described yet.
- **Many pictures are changed at once** (decided 2026-10-20 — a regatta's 150 photos one by
  one was the review's finding): selected on the *Media* tab, they get one credit, one
  event or series, or are deleted together; a picture a post uses is kept and named.
- Editorial alone — like posts (R-1). The upload page needs nothing but a valid key.
- **A regatta's editor keeps that regatta's pictures** (decided 2026-10-24): a series' or
  an event's `editor` uploads pictures that belong to their series or event (a series'
  editor also its events'), sees only those in the library, and cannot move one to
  another regatta (403); another regatta's picture answers 404. A picture about no
  regatta, fetching a picture from a web address, and import keys stay the **site's**
  editor's. Until 2026-10-24 only the site's `editor` kept the library.

Endpoints: `GET|POST|PATCH /api/admin/media`, `GET|PATCH|DELETE /api/admin/media/{id}`,
`GET /api/admin/media/{id}/original`, `POST /api/admin/media/delete`,
`GET|POST /api/admin/import-keys`, `DELETE /api/admin/import-keys/{id}`,
`POST /api/admin/media/from-url`, `GET /api/import/key`, `POST /api/import/media`,
`GET /api/media/{name}`

Tests: `api/tests/stories/test_media.py::TestLibrary`,
`api/tests/stories/test_posts.py::TestSeededPictures`,
`api/tests/stories/test_media.py::TestImport`,
`api/tests/stories/test_media.py::TestContext`,
`api/tests/stories/test_media.py::TestFromAddress`,
`api/tests/stories/test_media.py::TestManyAtOnce`,
`api/tests/stories/test_media.py::TestByName`,
`e2e/media.spec.ts::R-2: a picture library fed by upload links`,
`e2e/media.spec.ts::R-2: editorial changes many pictures at once`,
`api/tests/stories/test_regatta_editorial.py::TestEditorialOfOneRegatta`

### R-3 ● Show the library's photos on the league's media page
As a **visitor** I want **a league's media page to show the photos of its regattas**, and as **editorial** I want **what photographers delivered to appear there
without placing each picture in a post**, so that **the library is what the public sees**.

Acceptance criteria:
- **A league's media page shows the library's pictures of that league** — those of its
  series and of their events — newest regatta first, grouped by event or series, each with
  its credit. Only what is public: a picture of an unpublished event or series is not
  shown. A picture belonging to nothing appears on no media page.
- **Paged**, a page of pictures at a time with a *more* button — a season brings hundreds.
- **A tap shows the picture full screen**, at the size the screen needs, with its alt
  text and credit; swipe or the arrow keys go to the next and the previous, Escape closes.
- **Until the library has a league's pictures**, the page shows the site's own selection
  as before, so a new league's page is never empty. The videos stay the site's own
  selection (a video library was built and taken out again on 2026-10-20 — not wanted
  for now).

Endpoints: `GET /api/media?league=`

Tests: `api/tests/stories/test_media_public.py`,
`e2e/media-public.spec.ts::R-3: the league's media page shows the library`
