import { useParams } from "react-router-dom";

import { findLeague } from "./data";

/** The five options, in the order they are shown. `inspiredBy` says which reference site
 *  the option borrows its structure from (issue #13). */
export const OPTIONS = [
  {
    n: 1,
    name: "Corporate",
    inspiredBy: "telekom.com",
    summary:
      "Dark utility bar with the leagues, mega-menu main bar, full-width video hero, " +
      "\"information for\" audience switch, news, facts, press centre.",
  },
  {
    n: 2,
    name: "Pathfinder",
    inspiredBy: "vodafone.de",
    summary:
      "Segment tabs on top, hero carousel, a row of round entry tiles (Results, Live, " +
      "Calendar, Media, Press, Clubs), horizontally scrolling card rows.",
  },
  {
    n: 3,
    name: "Results first",
    inspiredBy: "sports portals",
    summary:
      "Live ticker under the header, standings of every league side by side, latest " +
      "results, then news, media and press in a sidebar.",
  },
  {
    n: 4,
    name: "Magazine",
    inspiredBy: "deutsche-segelbundesliga.de",
    summary:
      "Image-led editorial mosaic, video row, photo gallery, a press centre with " +
      "downloads; the table is a compact widget.",
  },
  {
    n: 5,
    name: "League hub",
    inspiredBy: "one page per league",
    summary:
      "The top bar is the main navigation. Home is one card per league with leader, " +
      "next date and live state; news, media and press sit in tabs below.",
  },
  {
    n: 6,
    name: "Open water",
    inspiredBy: "none — the water itself",
    summary:
      "The picture starts at the very top, the bar lies over it. The three leagues are the " +
      "hero, side by side; the season is a course with its matchdays as marks; huge " +
      "typographic standings, news as a logbook, media as a film strip.",
  },
  {
    n: 7,
    name: "Broadcast",
    inspiredBy: "TV sports graphics (a variant of 6)",
    summary:
      "Opens on the water itself: a chart with the six boats lapping the course in their " +
      "event colours, wind and live ranking. Standings as lower thirds, the calendar as a " +
      "departures board, videos as replays.",
  },
  {
    n: 8,
    name: "Chapters",
    inspiredBy: "scroll stories (a variant of 6)",
    summary:
      "The home page as a story in full-screen chapters that snap into place — now, table, " +
      "season, leagues, stories, media, press — each over its own picture, with a column " +
      "of dots on the right to jump between them.",
  },
] as const;

export const wireHref = (option: number, league?: string | null) =>
  league ? `/wireframes/${option}/${league}` : `/wireframes/${option}`;

/** Which option and which league the URL names. */
export function useWireframe() {
  const params = useParams();
  const option = Number(params.option ?? 0);
  const league = findLeague(params.league);
  return { option, league, home: wireHref(option), to: (slug: string | null) => wireHref(option, slug) };
}

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
