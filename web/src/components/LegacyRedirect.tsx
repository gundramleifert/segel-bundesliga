import { Navigate, generatePath, useLocation, useParams } from "react-router-dom";

/** Redirects a retired German route to its English replacement, carrying params along.
 *
 * `<Navigate to="/standings/:id" />` would send someone to the literal string ":id" — it
 * doesn't substitute route params. This does, using the same param names as the old path.
 */
export function LegacyRedirect({ to }: { to: string }) {
  const params = useParams();
  return <Navigate to={generatePath(to, params)} replace />;
}

/** Sends `/<from>/…` to the same page under `/<to>/…`, query and hash included — for a
 *  league whose addresses moved (the DSBL's became the 1. Liga's, Story B-16). */
export function PrefixRedirect({ from, to }: { from: string; to: string }) {
  const { pathname, search, hash } = useLocation();
  return <Navigate to={`/${to}${pathname.slice(from.length + 1)}${search}${hash}`} replace />;
}
