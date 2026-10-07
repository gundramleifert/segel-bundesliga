# Appending a Tailwind class to override one in a shared class string does nothing when the shared one comes later in the stylesheet

**Symptom** — The club picker on the pairing-list tab spanned the whole page (992 px on a
1280 px screen) although its `className` ended in `w-auto`.

**Cause** — The class string was `${INPUT_CLASS} w-auto py-1 text-sm`, and `INPUT_CLASS`
(`web/src/lib/admin.ts`) carries `w-full` and `py-2`. Two utilities that set the same
property have equal specificity, so the one *later in the generated stylesheet* wins —
not the one later in the `class` attribute. `w-full` won, and so did `py-2`. What misled:
the list reads like "base, then override", which is how inline styles and CSS-in-JS work,
and Tailwind does not.

**Rule** — Never override a utility by appending a conflicting one. Give the element its
own class string, or split the shared constant so the conflicting property is not in it
(or use Tailwind's `!` important modifier, sparingly).

**Evidence** — `web/src/pages/Matchday.tsx`, the `matchday-pairing-pdf-club` select:
bounding box 992 × 36 px before, 97 × 28 px after.

**Seen** — 2026-10-07
