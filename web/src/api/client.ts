/** Typed access to the API.
 *
 * The types in `schema.d.ts` are generated from the backend's OpenAPI schema
 * (`pnpm gen:api`). Hand-maintaining them here would be a source of bugs — if a response
 * shape changes, the build should fail, not the page in the browser.
 */
import i18n from "../i18n";
import { type ProblemDetail, describeProblem, isProblem, problemCode } from "./problems";
import type { components } from "./schema";
import { getToken } from "./session";

type S = components["schemas"];

export type Club = S["ClubOut"];
export type Series = S["SeriesOut"];
export type EventSummary = S["EventOut"];
export type EventDetail = S["EventDetail"];
export type SeriesTable = S["SeriesTable"];
export type PairingList = S["PairingList"];
export type BoatOut = S["BoatOut"];
export type StandingRow = S["EventStandingRow"];
export type ClubDetail = S["ClubDetail"];
export type SailorDetail = S["SailorDetail"];
// Story S-2: a sailor's own profile — name, birthdate, and whether a photo exists.
export type SailorMe = S["SailorMeOut"];
export type SailorMeUpdate = S["SailorMeUpdate"];
export type Member = S["MemberOut"];
export type SeriesRow = S["SeriesStandingRow"];
/** A fellow club member, as seen by another active member — no email, no pending requests. */
export type ClubMemberSummary = S["ClubMemberOut"];

// Admin
export type SeriesAdmin = S["SeriesAdminOut"];
export type ClubAdmin = S["ClubAdminOut"];
export type SeriesCreate = S["SeriesCreate"];
export type ClubCreate = S["ClubCreate"];
export type EventCreate = S["EventCreate"];
export type BoatSpec = S["BoatSpec"];
export type PairingCatalogEntry = S["KatalogEintragOut"];
export type PairingPublishResult = S["PublishResult"];
export type EventTeam = S["ParticipantOut"];
export type SailorAdmin = S["SailorAdminOut"];
export type SailorCreate = S["SailorCreate"];
export type Squad = S["KaderOut"];
export type SquadEntry = S["KaderEintrag"];
export type Providers = S["ProvidersOut"];
export type TokenOut = S["TokenOut"];
// Story WL-2: entering and correcting race results.
export type AdminRaces = S["AdminRacesOut"];
export type AdminRace = S["AdminRaceOut"];
export type AdminRaceEntry = S["RaceEntryOut"];
export type RaceResultInput = S["RaceResultIn"];
export type RaceResultsInput = S["RaceResultsIn"];
export type RaceResultsOut = S["RaceResultsOut"];

export class ApiError extends Error {
  // No constructor shorthand: this project builds with `erasableSyntaxOnly`.
  status: number;
  /** The RFC 9457 problem code, e.g. `waiver-already-confirmed` — null for non-typed errors. */
  code: string | null;
  /** The full problem body, for reading extension members. */
  problem: ProblemDetail | null;

  constructor(
    status: number,
    message: string,
    options: { code?: string | null; problem?: ProblemDetail | null } = {},
  ) {
    super(message);
    this.status = status;
    this.code = options.code ?? null;
    this.problem = options.problem ?? null;
  }
}

function headers(body?: BodyInit | null): HeadersInit {
  const result: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined && body !== null) result["Content-Type"] = "application/json";
  const token = getToken();
  if (token) result.Authorization = `Bearer ${token}`;
  return result;
}

async function request<T>(
  path: string,
  init: RequestInit & { signal?: AbortSignal } = {},
): Promise<T> {
  const response = await fetch(path, { ...init, headers: headers(init.body) });
  if (!response.ok) {
    throw await apiError(response);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** Turns a failed response into an {@link ApiError}.
 *
 * The backend answers with RFC 9457 `application/problem+json`: the `type` carries a
 * stable code the UI maps to a translation (see `./problems`). A non-problem body (an
 * old deployment, a proxy error page) still yields a readable message.
 */
async function apiError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    // Response wasn't JSON — fall through to the generic message.
  }
  if (isProblem(body)) {
    return new ApiError(response.status, describeProblem(body), {
      code: problemCode(body),
      problem: body,
    });
  }
  return new ApiError(
    response.status,
    i18n.t("common:errors.requestFailed", { status: response.status }),
  );
}

function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal });
}

function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** A multipart file upload (Story S-2's photo endpoint) — deliberately not `send`:
 *  a `FormData` body must not get the `application/json` content type `headers()` sets
 *  for everything else, and the browser needs to add its own boundary. */
async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const token = getToken();
  const requestHeaders: Record<string, string> = { Accept: "application/json" };
  if (token) requestHeaders.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { method: "POST", headers: requestHeaders, body });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<T>;
}

export interface Account {
  id: number;
  email: string;
  display_name: string;
  is_active: boolean;
  club_id: number | null;
  roles: string[];
  identities: { provider: string; subject: string }[];
}

export interface TestAccount {
  id: number;
  email: string;
  display_name: string;
  roles: string[];
  club: string | null;
  description: string;
}

export const api = {
  me: (signal?: AbortSignal) => get<Account>("/api/auth/me", signal),
  testAccounts: (signal?: AbortSignal) => get<TestAccount[]>("/api/dev/users", signal),
  async devLogin(email: string): Promise<string> {
    const response = await fetch("/api/dev/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!response.ok) {
      throw new ApiError(response.status, i18n.t("common:errors.loginFailed"));
    }
    const data = (await response.json()) as { access_token: string };
    return data.access_token;
  },
  /** Sign-in — Google/Microsoft/email one-time code, on top of the already-verified
   *  backend in `app.services.login`. */
  auth: {
    providers: (signal?: AbortSignal) => get<Providers>("/api/auth/providers", signal),
    requestEmailCode: (email: string) =>
      send<{ detail: string }>("POST", "/api/auth/email/request", { email }),
    verifyEmailCode: (email: string, code: string) =>
      send<TokenOut>("POST", "/api/auth/email/verify", { email, code }),
    /** Creates an account and sends its first one-time code — Story Z-4. Redeemed the
     *  same way as a sign-in code, via verifyEmailCode. */
    register: (email: string, displayName: string) =>
      send<{ detail: string }>("POST", "/api/auth/register", {
        email,
        display_name: displayName,
      }),
    /** Deletes the signed-in account outright — a testing-phase convenience (Story Z-7). */
    deleteMyAccount: () => send<void>("DELETE", "/api/auth/me"),
    /** Search accounts — Story Z-2/Z-3. Club managers may call this too (to find people
     *  for their own club), but the roles/club endpoints below check permissions per call. */
    list: (params: { q?: string; clubId?: number } = {}, signal?: AbortSignal) => {
      const qs = new URLSearchParams();
      if (params.q) qs.set("q", params.q);
      if (params.clubId != null) qs.set("club_id", String(params.clubId));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return get<Account[]>(`/api/auth/users${suffix}`, signal);
    },
    /** Grant/revoke roles outright (admin only) — Story Z-2. */
    setRoles: (userId: number, roles: string[]) =>
      send<Account>("PUT", `/api/auth/users/${userId}/roles`, { roles }),
    /** Assign (or clear, with null) the club an account acts for — Story Z-3. */
    setClub: (userId: number, clubId: number | null) =>
      send<Account>("PUT", `/api/auth/users/${userId}/club`, { club_id: clubId }),
  },

  clubs: (signal?: AbortSignal) => get<Club[]>("/api/clubs", signal),
  club: (id: number, signal?: AbortSignal) => get<ClubDetail>(`/api/clubs/${id}`, signal),
  /** Fellow members of a club — 403 unless the caller is an active member (or staff). */
  clubMembers: (id: number, signal?: AbortSignal) =>
    get<ClubMemberSummary[]>(`/api/clubs/${id}/members`, signal),
  sailor: (id: number, signal?: AbortSignal) =>
    get<SailorDetail>(`/api/sailors/${id}`, signal),
  /** The URL of a sailor's photo — a minor's is only ever returned by the server to a
   *  signed-in account connected to them (see `app/routers/sailors.py`); a plain `<img>`
   *  tag sends the same Authorization the rest of the app uses only if the browser has
   *  it in a cookie, which it doesn't here, so this is really only reliably public for
   *  an adult sailor. The profile page's own photo always goes through `sailors.me()`
   *  and `sailors.uploadMyPhoto` instead, which do carry the bearer token. */
  sailorPhotoUrl: (id: number) => `/api/sailors/${id}/photo`,
  /** Story S-2: a sailor's self-service profile — own name, birthdate, and photo. */
  sailors: {
    me: (signal?: AbortSignal) => get<SailorMe>("/api/sailors/me", signal),
    updateMe: (data: Partial<SailorMeUpdate>) =>
      send<SailorMe>("PATCH", "/api/sailors/me", data),
    uploadMyPhoto: (file: File) => upload<SailorMe>("/api/sailors/me/photo", file),
    deleteMyPhoto: () => send<void>("DELETE", "/api/sailors/me/photo"),
  },
  series: (signal?: AbortSignal) => get<Series[]>("/api/series", signal),
  events: (signal?: AbortSignal) => get<EventSummary[]>("/api/events", signal),
  event: (id: number, signal?: AbortSignal) => get<EventDetail>(`/api/events/${id}`, signal),
  pairing: (id: number, signal?: AbortSignal) =>
    get<PairingList>(`/api/events/${id}/pairing`, signal),
  table: (seriesId: number, signal?: AbortSignal) =>
    get<SeriesTable>(`/api/series/${seriesId}/table`, signal),
  /** The table of the first series of the current year — the home page's entry point. */
  async firstSeries(signal?: AbortSignal): Promise<SeriesTable> {
    const list = await api.series(signal);
    if (!list.length) throw new ApiError(404, i18n.t("common:errors.noSeriesThisYear"));
    return api.table(list[0].id, signal);
  },

  /** Admin. Unlike the public queries, these show **every** year, including what hasn't
   *  been published yet. */
  admin: {
    series: (signal?: AbortSignal) => get<SeriesAdmin[]>("/api/admin/series", signal),
    createSeries: (data: SeriesCreate) => send<SeriesAdmin>("POST", "/api/admin/series", data),
    updateSeries: (id: number, data: Partial<SeriesCreate>) =>
      send<SeriesAdmin>("PATCH", `/api/admin/series/${id}`, data),
    setSeriesClubs: (id: number, clubs: number[]) =>
      send<SeriesAdmin>("PUT", `/api/admin/series/${id}/clubs`, { clubs }),

    clubs: (signal?: AbortSignal) => get<ClubAdmin[]>("/api/admin/clubs", signal),
    createClub: (data: ClubCreate) => send<Club>("POST", "/api/admin/clubs", data),

    createEvent: (data: EventCreate) => send<EventSummary>("POST", "/api/admin/events", data),
    eventClubs: (eventId: number, signal?: AbortSignal) =>
      get<EventTeam[]>(`/api/admin/events/${eventId}/clubs`, signal),
    setEventClubs: (eventId: number, clubs: number[]) =>
      send<EventTeam[]>("PUT", `/api/admin/events/${eventId}/clubs`, { clubs }),

    // Pre-computed pairing-list sizes (teams/boats/flights). The optimization run behind
    // a size takes minutes, so event creation only ever picks among these instead of
    // triggering a fresh computation (see app/pairing/catalog.py).
    pairingCatalog: (signal?: AbortSignal) =>
      get<PairingCatalogEntry[]>("/api/admin/pairing/catalog", signal),
    /** Takes the catalog's pre-optimized list for the event's size and shuffles starting
     *  positions by `seed` — deterministic, milliseconds (Story VA-7). Called right after
     *  event creation so a newly created event has a pairing list immediately. */
    pairingFromCatalog: (eventId: number, seed: number) =>
      send<PairingPublishResult>(
        "POST",
        `/api/admin/events/${eventId}/pairing/from-catalog`,
        { seed },
      ),

    sailors: (q: string, signal?: AbortSignal) =>
      get<SailorAdmin[]>(`/api/admin/sailors?q=${encodeURIComponent(q)}`, signal),
    createSailor: (data: SailorCreate) => send<SailorAdmin>("POST", "/api/admin/sailors", data),
    updateSailor: (id: number, data: Partial<SailorCreate>) =>
      send<SailorAdmin>("PATCH", `/api/admin/sailors/${id}`, data),

    squad: (teamId: number, signal?: AbortSignal) =>
      get<Squad>(`/api/admin/teams/${teamId}/members`, signal),
    setSquad: (teamId: number, members: SquadEntry[]) =>
      send<Squad>("PUT", `/api/admin/teams/${teamId}/members`, { members }),

    /** Pairing plus current result state, for the entry screen (Story WL-2). */
    races: (eventId: number, signal?: AbortSignal) =>
      get<AdminRaces>(`/api/admin/events/${eventId}/races`, signal),
    /** Writes one race's result. `admin`/`race_officer` only; a correction always
     *  recomputes standings immediately — see `app/services/standings.py`. */
    setRaceResult: (eventId: number, raceId: number, data: RaceResultsInput) =>
      send<RaceResultsOut>(
        "PUT",
        `/api/admin/events/${eventId}/races/${raceId}/result`,
        data,
      ),
  },
};
