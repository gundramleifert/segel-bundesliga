# A browser declares a file's type from its name, not its content

**Symptom** — an upload of a picture the browser itself previews fine is refused with
"This file is not a readable picture" (`media-invalid`); another file from the same folder
goes through.

**Cause** — the file was a JPEG saved as `Organizational_chart.png`. A browser sets a
`File`'s `type` (and so the multipart part's content type) from the **extension**, so it
declared `image/png`, and `uploads.validated` refuses a file whose bytes are not what it
declares. What misled: the message says "not readable", but the image was perfectly
readable — the *declared-vs-found* mismatch shares the `-invalid` code with a broken file.

**Rule** — never trust the declared type to describe the bytes. Where the file is
re-encoded before it is stored (pictures: `app/services/media.py`), let the content decide
(`validated(..., by_content=True)`). Keep the strict mismatch check only where the file is
stored and served as uploaded (waiver scans, receipts, personal documents).

**Evidence** — `file ~/Downloads/Organizational_chart.png` → "JPEG image data … 3377x1540";
`api/tests/stories/test_media.py::TestLibrary::test_a_picture_with_the_wrong_extension_is_taken_by_its_content`
failed with 422 before `by_content`, passes after.

**Seen** — 2026-10-19
