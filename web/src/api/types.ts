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
/** Issue #14, Story B-14: a competition that runs year after year, and one year of it. */
export type { LeagueOut as League } from "./generated/model/leagueOut";
export type { LeagueSeason } from "./generated/model/leagueSeason";
export type { SeriesOut as Series } from "./generated/model/seriesOut";
/** Story R-1: a news article or a press release, as the public site and editorial see it. */
export type { PostOut as Post } from "./generated/model/postOut";
export type { PostSummary } from "./generated/model/postSummary";
export type { PostAdminOut as PostAdmin } from "./generated/model/postAdminOut";
export type { PostAdminSummary } from "./generated/model/postAdminSummary";
export type { PagePostAdminSummary as PostPage } from "./generated/model/pagePostAdminSummary";
export type { PostCreate, PostUpdate } from "./generated/model";
export type { MediaOut as Media } from "./generated/model/mediaOut";
export type { MediaDetail } from "./generated/model/mediaDetail";
export type { ImportedOut } from "./generated/model/importedOut";
export type { ImportKeyOut as ImportKey } from "./generated/model/importKeyOut";
export type { ImportKeyCreated } from "./generated/model/importKeyCreated";
export type { SeriesTable } from "./generated/model/seriesTable";
export type { SeriesStandingRow as SeriesRow } from "./generated/model/seriesStandingRow";
export type { EventOut as EventSummary } from "./generated/model/eventOut";
export type { EventDetail } from "./generated/model/eventDetail";
/** Story WL-3: what the person asking may do on one event — gates the committee's tools. */
export type { EventAccess } from "./generated/model/eventAccess";
/** Story VA-11: a notice on an event's notice board, and the documents beside it. */
export type { AnnouncementOut as Announcement } from "./generated/model/announcementOut";
export type { EventDocumentOut as EventDocument } from "./generated/model/eventDocumentOut";
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

/** Story Z-8: everything I am part of, and what needs me there. */
export type { MySpaceOut as MySpace } from "./generated/model/mySpaceOut";
export type { MyContextOut as MyContext } from "./generated/model/myContextOut";
export type { NeedOut as Need } from "./generated/model/needOut";

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
export type { TupleOut as AccessTuple } from "./generated/model/tupleOut";
export type { TestUserOut as TestAccount } from "./generated/model/testUserOut";
export type { ProvidersOut as Providers } from "./generated/model/providersOut";
export type { TokenOut } from "./generated/model/tokenOut";

export { ApiError } from "./http";
/** Stories S-5, S-6: a person's own documents and bank account. */
export type { PersonalDocumentOut as PersonalDocument } from "./generated/model/personalDocumentOut";
export { DocumentKind } from "./generated/model/documentKind";
export type { BankAccountOut as BankAccount } from "./generated/model/bankAccountOut";
/** Stories F-2 to F-6: an expense claim, its items, and what it may be filed on. */
export type { ClaimOut as Claim } from "./generated/model/claimOut";
export type { ItemOut as ClaimItem } from "./generated/model/itemOut";
export type { ClaimDocumentOut as ClaimDocument } from "./generated/model/claimDocumentOut";
export type { ClaimTarget } from "./generated/model/claimTarget";
export type { UnavailableEvent } from "./generated/model/unavailableEvent";
export { UnclaimableReason } from "./generated/model/unclaimableReason";
export { ExpenseKind } from "./generated/model/expenseKind";

/** The closed sets the backend types as enums. Each is a type *and* a constant object
 *  (`EventStatus.live`), so a comparison names a member the compiler knows — a typo or a
 *  renamed value is a build error rather than a branch that silently never runs. */
export { EventStatus } from "./generated/model/eventStatus";
export { AnnouncementIssuer } from "./generated/model/announcementIssuer";
export { PostKind } from "./generated/model/postKind";
export { MediaSource } from "./generated/model/mediaSource";
export { RaceStatus } from "./generated/model/raceStatus";
export { RaceSignal } from "./generated/model/raceSignal";
export { PreparatoryFlag } from "./generated/model/preparatoryFlag";
export { ResultCode } from "./generated/model/resultCode";
export { MarkRole } from "./generated/model/markRole";
export { CrewRole } from "./generated/model/crewRole";
export { WaiverStatus } from "./generated/model/waiverStatus";
export { Role } from "./generated/model/role";
export { Relation } from "./generated/model/relation";
/** Story Z-10: what I am to a context — a relation, or `sailor` (a squad, a crew). */
export { ContextRelation } from "./generated/model/contextRelation";
export { Severity } from "./generated/model/severity";
export type { TodoOut as Todo } from "./generated/model/todoOut";
export { ObjectType } from "./generated/model/objectType";
export { WaiverMethod } from "./generated/model/waiverMethod";
export { ClaimStatus } from "./generated/model/claimStatus";
export { PaymentState } from "./generated/model/paymentState";
export { PaymentStatus } from "./generated/model/paymentStatus";
