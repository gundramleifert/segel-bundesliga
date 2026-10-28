# A picture smaller than 1600 px offered a srcset size the server refused — large seed pictures hid it

**Symptom** — on a desktop the page has no picture behind it, and the B-13 spec "the glass
blurs the picture behind it" fails with `/1-liga: blurred`; on a phone the same page shows
the picture. The `<img>` is there, `complete`, with `naturalWidth` 0.

**Cause** — `srcset` lists every size up to the picture's own longer edge
(`media.edges_of`: a 683 × 1024 picture offers `-480`, `-960`, `-1024.webp`), but
`media.file_key` refused any edge not in `EDGES` before looking, so `-1024.webp` was a 404
— and a desktop browser picks the largest entry. What misled: the spec reads as a CSS
blur bug, and the bug had never shown because the seed's pictures (the Finale's, removed
2026-10-27) were all 1600 px or more, so their largest size was always one of `EDGES`.

**Rule** — an address a page is handed must be an address the server answers: test every
`srcset` entry of a picture *between* two sizes, not only the standard sizes. When a fixed
set of seed data goes away, expect a spec that leaned on its shape to find a real bug.

**Evidence** — `api/tests/stories/test_media.py::TestLibrary::test_every_size_a_srcset_offers_is_served`
(fails with 404 on the old `file_key`); `api/app/services/media.py::file_key`.

**Seen** — 2026-10-28
