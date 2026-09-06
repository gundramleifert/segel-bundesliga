import { Navigate, generatePath, useParams } from "react-router-dom";

/** Redirects a retired German route to its English replacement, carrying params along.
 *
 * `<Navigate to="/standings/:id" />` would send someone to the literal string ":id" — it
 * doesn't substitute route params. This does, using the same param names as the old path.
 */
export function LegacyRedirect({ to }: { to: string }) {
  const params = useParams();
  return <Navigate to={generatePath(to, params)} replace />;
}
