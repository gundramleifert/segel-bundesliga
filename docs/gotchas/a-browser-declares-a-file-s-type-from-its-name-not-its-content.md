# A browser declares a file's type from its name, not its content

**Symptom** — an upload of a picture the browser itself previews fine is refused with
"This file is not a readable picture" (`media-invalid`); another file from the same folder
goes through.

**Cause** — the file was a JPEG saved as `Organizational_chart.png`. A browser sets a
`File`'s `type` (and so the multipart part's content type) from the **extension**, so it
declared `image/png`, and `uploads.validated` refuses a file whose bytes are not what it
declares. What misled: the message says "not readable", but the image was perfectly
readable — the *declared-vs-found* mismatch shares the `-invalid` code with a broken file.

**Rule** — a file's name and its declared type are not evidence of what it is, anywhere.
The server sniffs the type from the bytes (`uploads.sniffed`, libmagic — the library behind
`file`) and never reads `UploadFile.content_type`; the browser, where it refuses early, reads
the first bytes too (`web/src/lib/sniff.ts`), never `File.type`. A picture must then also
decode in Pillow, so a file with only the right first bytes is still refused. `accept` on a
file input is a hint for the chooser, never a check.

**Evidence** — `file ~/Downloads/Organizational_chart.png` → "JPEG image data … 3377x1540";
`api/tests/stories/test_media.py::TestLibrary::test_a_picture_with_the_wrong_extension_is_taken_by_its_content`
failed with 422 when the declared type decided, passes now that `uploads.sniffed` does.

**Seen** — 2026-10-19
