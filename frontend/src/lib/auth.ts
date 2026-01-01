import type { User } from 'oidc-client-ts';

/**
 * Check if user has admin role in Zitadel claims.
 * Zitadel stores roles in a claim like: urn:zitadel:iam:org:project:{projectId}:roles
 */
export function hasAdminRole(user: User | null | undefined): boolean {
  if (!user) return false;
  const claims = user.profile as Record<string, unknown>;
  for (const key of Object.keys(claims)) {
    if (key.includes(':roles')) {
      const roles = claims[key] as Record<string, unknown> | undefined;
      if (roles && typeof roles === 'object' && 'ADMIN' in roles) {
        return true;
      }
    }
  }
  return false;
}
