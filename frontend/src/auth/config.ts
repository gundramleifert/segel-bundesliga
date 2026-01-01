import { WebStorageStateStore } from 'oidc-client-ts';

export const oidcConfig = {
  authority: import.meta.env.VITE_ZITADEL_ISSUER,
  client_id: import.meta.env.VITE_ZITADEL_CLIENT_ID,
  redirect_uri: `${window.location.origin}/callback`,
  post_logout_redirect_uri: window.location.origin,
  scope: 'openid profile email',
  userStore: new WebStorageStateStore({ store: window.localStorage }),
};
