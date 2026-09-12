# HeroUI owns `--color-surface`; naming our own token that overrode it made every card invisible

**Symptom** — Every `<Card>` on the site rendered in exactly the page's background colour.
Border and shadow were the only sign a card was there. Nothing in our own code mentions
card backgrounds.

**Cause** — A token-name collision, not a style. HeroUI 3's theme defines `--surface`
(white) and exposes it as the `bg-surface` utility, and `.card--default` is literally
`@apply bg-surface`. Our `@theme` block declared `--color-surface: #ebedf2` for the page
backdrop — which is the Tailwind 4 spelling of that same utility — so `.card--default`
compiled to `background-color: var(--color-surface)`, the page colour.

**Rule** — Before naming a design token, check whether the component library already uses
that name: `grep -o -- "--color-<name>" node_modules/.pnpm/@heroui+styles@*/node_modules/@heroui/styles/dist/heroui.min.css`
and the per-component CSS under `.../dist/components/`. Our tokens are named for *our*
concepts (`--color-page`, `--color-ink`); generic UI words like `surface`, `content`,
`muted`, `border` belong to the library. Note that `@heroui/react/dist/styles.css` is a
two-line re-export — the real CSS lives in the separate `@heroui/styles` package, which
pnpm does not link into `node_modules/@heroui/`.

**Evidence** — `web/src/index.css`; `.card--default` compiles back to `var(--surface)`,
checkable in `web/dist/assets/*.css` after `pnpm build`.

**Seen** — 2026-09-10, commit `17d4346`.
