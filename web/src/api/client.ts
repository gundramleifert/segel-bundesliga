/** Typed access to the API.
 *
 * The types in `schema.d.ts` are generated from the backend's OpenAPI schema
 * (`pnpm gen:api`). Hand-maintaining them here would be a source of bugs — if a response
 * shape changes, the build should fail, not the page in the browser.
 */
import i18n from "../i18n";
import type { components } from "./schema";
import { getToken } from "./session";

type S = components["schemas"];

export type Club = S["ClubOut"];
export type Series = S["SeriesOut"];
export type EventSummary = S["EventOut"];
export type EventDetail = S["EventDetail"];
export type SeriesTable = S["SeriesTable"];
export type PairingList = S["PairingList"];
export type StandingRow = S["EventStandingRow"];
export type ClubDetail = S["ClubDetail"];
export type SailorDetail = S["SailorDetail"];
export type Member = S["MemberOut"];
export type SeriesRow = S["SeriesStandingRow"];

// Admin
export type SeriesAdmin = S["SeriesAdminOut"];
export type ClubAdmin = S["ClubAdminOut"];
export type SeriesCreate = S["SeriesCreate"];
export type ClubCreate = S["ClubCreate"];
export type EventCreate = S["EventCreate"];
export type EventTeam = S["ParticipantOut"];
export type SailorAdmin = S["SailorAdminOut"];
export type SailorCreate = S["SailorCreate"];
export type Squad = S["KaderOut"];
export type SquadEntry = S["KaderEintrag"];

export class ApiError extends Error {
  // No constructor shorthand: this project builds with `erasableSyntaxOnly`.
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
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
    throw new ApiError(response.status, await errorText(response));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** The server's own error message, not a made-up one.
 *
 * FastAPI returns a list per field on validation errors; that gets summarised readably
 * instead of showing up as "[object Object]".
 */
async function errorText(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((entry) => {
          const field = Array.isArray(entry?.loc) ? entry.loc.slice(1).join(".") : "";
          return field ? `${field}: ${entry.msg}` : entry.msg;
        })
        .join(" · ");
    }
  } catch {
    // Response wasn't JSON — the generic message is enough.
  }
  return i18n.t("common:errors.requestFailed", { status: response.status });
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
  beschreibung: string;
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
  clubs: (signal?: AbortSignal) => get<Club[]>("/api/clubs", signal),
  club: (id: number, signal?: AbortSignal) => get<ClubDetail>(`/api/clubs/${id}`, signal),
  sailor: (id: number, signal?: AbortSignal) =>
    get<SailorDetail>(`/api/sailors/${id}`, signal),
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

    sailors: (q: string, signal?: AbortSignal) =>
      get<SailorAdmin[]>(`/api/admin/sailors?q=${encodeURIComponent(q)}`, signal),
    createSailor: (data: SailorCreate) => send<SailorAdmin>("POST", "/api/admin/sailors", data),
    updateSailor: (id: number, data: Partial<SailorCreate>) =>
      send<SailorAdmin>("PATCH", `/api/admin/sailors/${id}`, data),

    squad: (teamId: number, signal?: AbortSignal) =>
      get<Squad>(`/api/admin/teams/${teamId}/members`, signal),
    setSquad: (teamId: number, members: SquadEntry[]) =>
      send<Squad>("PUT", `/api/admin/teams/${teamId}/members`, { members }),
  },
};
