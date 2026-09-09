/** `data-testid` naming convention for this codebase.
 *
 * Kebab-case, hierarchical: `<page>-<element>[-<qualifier>]`, e.g.
 * `"account-signin-email-input"`, `"admin-events-create-button"`, `"matchday-results-tab"`.
 * A repeated list item interpolates its own id (or slug, where one exists) as the
 * qualifier, so a Playwright test can target *one specific* row instead of "some row":
 * `"club-card-12"`, `"event-row-34"`, `"admin-series-row-7"`. State-dependent regions
 * (loading/error/empty/success) get their own testid too, since those are exactly what a
 * flow test asserts on. Reusable building-block components
 * (`components/Bausteine.tsx`, `pages/verwaltungBausteine.tsx`) accept an optional
 * `testId` prop that they forward to their root element, with a sensible default derived
 * from context (via `slugify` below) when one is available — call sites pass an explicit
 * `testId` whenever they need something more specific than that default.
 */
export function slugify(text: string): string {
  const slug = text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "item";
}
