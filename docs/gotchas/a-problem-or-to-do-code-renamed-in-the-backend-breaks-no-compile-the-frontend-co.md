# A problem or to-do code renamed in the backend breaks no compile: the frontend compares it as a string

**Symptom** — after renaming Sailor to Person (#42), the profile's quiet "no person record"
line never showed (a generic error came instead), and the club's "no date of birth" to-do
lost its section link and its words — with `pnpm typecheck` and every test green.

**Cause** — the rename regenerated the API client, so every *type* and *hook* that changed
failed to compile and was fixed; but a problem code (`err.code === "no-linked-sailor-record"`)
and a need code (`needs: ["sailor_without_birth_date"]`, `needs.<code>` in `space.json`) are
plain strings in the frontend, typed `string`. The compile being green misled: it covers
the generated names, not the codes.

**Rule** — when a problem code or a `NeedCode` changes, grep the old string across
`web/src` (pages, `i18n/locales/*/errors.json`, `space.json` `needs`) and `e2e/`, not only
the compiler's errors.

**Evidence** — `web/src/pages/me/Profile.tsx` and `Waivers.tsx` compared
`no-linked-sailor-record` until 8ce628c; `web/src/pages/me/ClubPage.tsx` listed
`sailor_without_birth_date` until fbfd3e1, while `api/app/services/contexts.py` sent
`person_without_birth_date` from 73c0a2b on.

**Seen** — 2026-10-26
