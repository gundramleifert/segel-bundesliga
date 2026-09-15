/** The names this application calls the API's types by.
 *
 * Every type here is generated (`scripts/gen-api-client.sh`) and only renamed: `EventOut`
 * is what the backend's schema calls it, `EventSummary` is what a component that shows one
 * in a list is talking about. Keeping the renaming in one file means a component never
 * imports from `generated/`, and the day a schema name changes exactly one line moves.
 *
 * **Nothing is declared here.** A type that is written out by hand rather than re-exported
 * is a copy of a contract, and a copy drifts — the hand-written `Account` had been missing
 * `email_verified` since the field was added to the backend, and nothing failed to compile.
 */
export type { ClubOut as Club } from "./generated/model/clubOut";
export type { ClubDetail } from "./generated/model/clubDetail";
export type { ClubMemberOut as ClubMemberSummary } from "./generated/model/clubMemberOut";
export type { MemberOut as Member } from "./generated/model/memberOut";
export type { SeriesOut as Series } from "./generated/model/seriesOut";
export type { SeriesTable } from "./generated/model/seriesTable";
export type { SeriesStandingRow as SeriesRow } from "./generated/model/seriesStandingRow";
export type { EventOut as EventSummary } from "./generated/model/eventOut";
export type { EventDetail } from "./generated/model/eventDetail";
export type { EventStandingRow as StandingRow } from "./generated/model/eventStandingRow";
/** Story B-12: one team entered in a matchday, and the crew sailing it there. */
export type { TeamCrewOut as TeamCrew } from "./generated/model/teamCrewOut";
export type { PairingList } from "./generated/model/pairingList";
export type { BoatOut } from "./generated/model/boatOut";
export type { SailorDetail } from "./generated/model/sailorDetail";
/** Stories L-1, L-2: the live picture of an event — course, running race, every boat. */
export type { LiveRaceOut as LiveRace } from "./generated/model/liveRaceOut";
export type { LiveBoatOut as LiveBoat } from "./generated/model/liveBoatOut";
export type { CourseOut as Course } from "./generated/model/courseOut";

/** Story S-2: a sailor's own profile — name, birthdate, and whether a photo exists. */
export type { SailorMeOut as SailorMe } from "./generated/model/sailorMeOut";
export type { SailorMeUpdate } from "./generated/model/sailorMeUpdate";

// Administration
export type { SeriesAdminOut as SeriesAdmin } from "./generated/model/seriesAdminOut";
export type { ClubAdminOut as ClubAdmin } from "./generated/model/clubAdminOut";
export type { SeriesCreate } from "./generated/model/seriesCreate";
export type { ClubCreate } from "./generated/model/clubCreate";
export type { EventCreate } from "./generated/model/eventCreate";
export type { EventUpdate } from "./generated/model/eventUpdate";
export type { BoatSpec } from "./generated/model/boatSpec";
export type { CatalogEntryOut as PairingCatalogEntry } from "./generated/model/catalogEntryOut";
export type { PublishResult as PairingPublishResult } from "./generated/model/publishResult";
export type { ParticipantOut as EventTeam } from "./generated/model/participantOut";
export type { SailorAdminOut as SailorAdmin } from "./generated/model/sailorAdminOut";
/** One series registration of a person. There is one row per registration and somebody
 *  legitimately has several — sailing for more than one club is allowed (Story V-1). */
export type { SailorRegistrationOut as SailorRegistration } from "./generated/model/sailorRegistrationOut";
export type { SailorCreate } from "./generated/model/sailorCreate";
export type { SquadOut as Squad } from "./generated/model/squadOut";
export type { SquadMemberIn as SquadEntry } from "./generated/model/squadMemberIn";

/** Story VA-8: whether an event may be drawn and started, and what's missing if not. */
export type { EventReadinessOut as EventReadiness } from "./generated/model/eventReadinessOut";
export type { ReadinessReasonOut as ReadinessReason } from "./generated/model/readinessReasonOut";

// Story WL-2: entering and correcting race results.
export type { AdminRacesOut as AdminRaces } from "./generated/model/adminRacesOut";
export type { AdminRaceOut as AdminRace } from "./generated/model/adminRaceOut";
export type { RaceEntryOut as AdminRaceEntry } from "./generated/model/raceEntryOut";
export type { RaceResultIn as RaceResultInput } from "./generated/model/raceResultIn";
export type { RaceResultsIn as RaceResultsInput } from "./generated/model/raceResultsIn";
export type { RaceResultsOut } from "./generated/model/raceResultsOut";

// My clubs (Stories B-10, V-12)
export type { MyClubOut as MyClub } from "./generated/model/myClubOut";
export type { MyEventOut as MyEvent } from "./generated/model/myEventOut";

// Liability waiver (Stories S-1, S-3, VA-5)
export type { MyWaivers } from "./generated/model/myWaivers";
export type { MyCompetitionWaiver } from "./generated/model/myCompetitionWaiver";
export type { WaiverTextOut as WaiverText } from "./generated/model/waiverTextOut";
export type { EventWaiverList } from "./generated/model/eventWaiverList";
export type { SailorWaiverRow } from "./generated/model/sailorWaiverRow";

// Accounts and sign-in
export type { UserOut as Account } from "./generated/model/userOut";
export type { TestUserOut as TestAccount } from "./generated/model/testUserOut";
export type { ProvidersOut as Providers } from "./generated/model/providersOut";
export type { TokenOut } from "./generated/model/tokenOut";

export { ApiError } from "./http";
