# Plan: password login, prepared for more ways to sign in

Status: **implemented 2026-10-05** (Story Z-9) — §1–§4 and §6; §5 stays preparation.
Decisions taken: **D1** 12 characters, **D2** on by default, **D3** yes
(`DELETE /api/auth/users/{id}/password`, audited). One rule of §3/§4 was dropped on the
way: removing a password is never refused as "the last way in", because the one-time code
always is one — that is also what makes it the reset. Authentication only; who may
do what stays the tuple model (`docs/PLAN_DATA_MODEL.md` §1).

## 0. This reverses a recorded decision

`CLAUDE.md` says "**We store no passwords**" (Google, Microsoft, one-time email code).
Adding passwords changes that. Update `CLAUDE.md` ("Authentication"), `docs/concepts.md`
("Identity and Rights") and Story Z-1 in the same change, and say why: not every sailor
has or wants a Google/Microsoft account, and a code by email on every sign-in is slow on
a pontoon.

## 1. Library: `argon2-cffi`, already a dependency

- **Algorithm: Argon2id** (OWASP Password Storage Cheat Sheet's first choice; RFC 9106).
- **`argon2.PasswordHasher`** from `argon2-cffi` (already in `api/pyproject.toml`; it
  hashes the one-time login codes today). It has the three things needed: `hash()`,
  `verify()`, and `check_needs_rehash()`, so stronger parameters later upgrade each hash
  on that person's next successful login. **No new dependency.**
- Not **passlib**: unmaintained, and it breaks on Python 3.13+.
- **pwdlib** (the maintained passlib successor, used in FastAPI's docs) only adds value
  for running several algorithms side by side, e.g. to migrate bcrypt hashes imported from
  another system. Switch to it only if that happens.

## 2. Data model: the existing `Identity` table already is the multi-login design

`User` 1—n `Identity(provider, subject)` already links Google, Microsoft and email code to
one account through the verified address. A password is one more provider:

- `IdentityProvider.PASSWORD`, with `Identity(provider="password", subject=<email>)`.
- **New table `PasswordCredential`**, 1:1 with the user: `user_id` (unique), `hash`,
  `changed_at`, `failed_attempts`, `locked_until`. It is separate from `Identity` so no
  serializer that lists a person's identities can ever carry a hash.
- **Reset needs no new mechanism.** "Forgot password" means signing in with the existing
  one-time email code, then setting a new password. No reset-token table.

## 3. Rules

- **Only a verified address gets a password** (`User.email_verified`). Accounts are still
  created by enrollment or import, never by setting a password (`allow_self_signup`
  unchanged).
- **Length is the only rule:** at least **12** characters (NIST SP 800-63B-4 asks for 15
  when the password is the only factor; decision D1), at most 128. No "one digit, one
  symbol" rules. Optional later: reject known-breached passwords via the HIBP range API
  (k-anonymity; never live in tests).
- **Answer the same way for every wrong combination.** Unknown email, no password set,
  wrong password and locked account all return one 401 problem code
  (`login-failed`), and an unknown email still runs one `verify` against a dummy hash, so
  the timing doesn't reveal who has an account.
- **Throttling per account:** after 5 failures, a growing lock (1, 5, 15 min) via
  `locked_until`. A successful code login clears it. Per-IP limits wait until deployment
  shows the need.
- **Audit:** set, change, remove and lockout each write an `AuditLog` row. The password
  itself is never logged, never echoed, and never stored in the clear, including in
  error bodies.
- **Switch:** `SBL_ALLOW_PASSWORD_LOGIN` (default on), like `SBL_ALLOW_REGISTRATION`.

## 4. Endpoints and screens

- `POST /api/auth/password/login {email, password}` returns the same token response as
  the other methods.
- `PUT /api/auth/password {current_password?, new_password}` sets or changes it, signed in
  (current password required when one exists). `DELETE /api/auth/password` removes it,
  refused if it is the account's last way in.
- Login page: email + password as a first tab beside "code by email", Google and
  Microsoft. Account page, card "Sign-in methods": which providers are linked, plus
  set/change/remove password.
- Run `scripts/gen-api-client.sh` after the routes exist (never hand-write the client).

## 5. Prepared for more ways to sign in

- **Any OpenID Connect provider becomes configuration, not code:** generalize today's
  Google/Microsoft token check into one OIDC verifier (issuer discovery + JWKS through
  PyJWT's `PyJWKClient`, already a dependency). A provider is then an entry with issuer,
  client id and display name, so adding the DSV, a club's Keycloak or Apple is one setting.
- **Manage2Sail: not possible yet, and never by password.** No public "Sign in with
  Manage2Sail" (OAuth/OIDC) could be found; what is known is an access token for importing
  results (`docs/findings.md` §4). If Manage2Sail offers OIDC, it plugs into the verifier
  above. The site must **never** ask for or store someone's Manage2Sail password. Action:
  the league office asks Manage2Sail whether they offer OAuth/OIDC.
- **Passkeys (WebAuthn)** are the stronger next step after passwords. `webauthn` (Duo's
  py_webauthn) would add a `PasskeyCredential` table beside `PasswordCredential`, with
  the same `Identity` link. Not now, but nothing in this plan blocks it.

## 6. Order of work (story → test → code)

1. Story **Z-9 "Sign in with a password"** in `docs/userstories/visitor.md` (beside Z-1),
   with the rules of §3 as acceptance criteria. Update Z-1, `CLAUDE.md` and
   `docs/concepts.md` (§0).
2. Story tests in `api/tests/stories/test_password_login.py`. Each must fail before the
   code exists:
   - set, then sign in;
   - a wrong password and an unknown email are indistinguishable (same body);
   - lock after 5 failures;
   - unverified accounts can't set a password;
   - removing the last way in is refused;
   - a hash with old parameters is upgraded on login;
   - the hash never appears in any response (`/api/auth/me`, user lists).
3. Model (`PasswordCredential`, `IdentityProvider.PASSWORD`), regenerate the single
   migration, `app/services/passwords.py` (hash/verify/rehash/lock), router.
4. Frontend: login tab and account card, en/de strings, `data-testid`s. One e2e test
   (`describeStory("Z-9: …")`): set a password on the account page, sign out, sign in.
5. `scripts/check.sh` green, `docs/traceability.md` regenerated.

## 7. Decisions for the user

- **D1** Minimum length: 12 (friendlier) or 15 (NIST's figure for password-only)?
- **D2** Should passwords be on by default, or opt-in per installation?
- **D3** Should an admin be able to *force* a password reset (clear someone's password)?
  Suggested: yes, audited. The person then signs in by code and sets a new one.
