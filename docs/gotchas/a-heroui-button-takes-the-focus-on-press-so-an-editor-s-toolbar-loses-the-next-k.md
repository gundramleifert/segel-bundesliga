# A HeroUI Button takes the focus on press, so an editor's toolbar loses the next keystroke unless it sets preventFocusOnPress

**Symptom** — in the news editor (Story R-1), clicking **B** and typing "Ten o'clock" made
"en o'clock" bold — the first character vanished — and clicking **B** again did not switch
bold off, so the rest of the line was bold too. Only in the `chromium` project; on `mobile`
(a tap) the same spec passed.

**Cause** — HeroUI 3's `Button` is React Aria's, which moves the focus to the button when
it is pressed. The toolbar's handler calls `editor.chain().focus()…`, which gives the
focus back to the text — but a moment after Playwright's next keystroke had already gone
to the button. What misled me: TipTap's own examples use plain `<button>`s, which keep the
focus because a mouse click on them does not move it in the editor's direction, so "call
`focus()` in the handler" looked like enough. My first fix replaced HeroUI's button with a
native one plus `onMouseDown={preventDefault}` — which works, but leaves the site's one
button component behind.

**Rule** — a control that acts on a text selection (an editor's toolbar, a formatting
palette) is a HeroUI `Button` with **`preventFocusOnPress`**. React Aria passes it through
HeroUI unchanged; the focus and the selection stay in the text, and Tab still reaches the
button. Do not swap in a native `<button>` for it.

**Evidence** — `e2e/editorial.spec.ts`, "write an article with the editor…": failed on
`chromium` with `Received: "en o'clock— the boats are open to visitors."` before, passes
with `preventFocusOnPress` on `Tool` in `web/src/components/RichTextEditor.tsx`. The prop
is declared in `react-aria/dist/types/src/button/useButton.d.ts`.

**Seen** — 2026-10-19
