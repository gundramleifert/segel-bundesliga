import { Button, Card } from "@heroui/react";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type Account as AccountData, type SailorMe } from "../api/client";
import { getToken, onTokenChange, setToken } from "../api/session";
import { ErrorMessage, Loading, PageHeader } from "../components/Blocks";
import { INPUT_CLASS, errorText } from "../lib/admin";

/** Roles and what permissions they grant. Without this page, role switching would be invisible
 *  as long as there are no protected areas yet. */
const PERMISSIONS: { role: string; key: string }[] = [
  { role: "admin", key: "roles.admin" },
  { role: "admin", key: "roles.admin_pairing" },
  { role: "editor", key: "roles.editor" },
  { role: "race_officer", key: "roles.race_officer" },
  { role: "club_manager", key: "roles.club_manager" },
  { role: "club_manager", key: "roles.club_manager_squad" },
];

export function Account() {
  const { t } = useTranslation("account");
  const [account, setAccount] = useState<AccountData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => {
      if (!getToken()) {
        setAccount(null);
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      api
        .me()
        .then((data) => {
          setAccount(data);
          setError(null);
        })
        .catch(() => setError(t("sessionExpired")))
        .finally(() => setLoading(false));
    };
    load();
    return onTokenChange(load);
  }, [t]);

  if (loading) return <Loading testId="account-loading" />;

  if (!account) {
    return (
      <>
        <PageHeader title={t("title")} testId="account-header" />
        <Card data-testid="account-signin-card">
          <Card.Header>
            <Card.Title>{t("notSignedIn")}</Card.Title>
            <Card.Description>{t("description")}</Card.Description>
          </Card.Header>
          <Card.Content>
            {error && (
              <p data-testid="account-session-error" className="mb-3 text-red-700">
                {error}
              </p>
            )}
            <SignIn />
          </Card.Content>
        </Card>
      </>
    );
  }

  const myRoles = new Set(account.roles);
  const allowed = PERMISSIONS.filter((entry) => myRoles.has(entry.role));

  return (
    <>
      <PageHeader
        title={t("title")}
        subtitle={account.email}
        testId="account-header"
        right={
          <Button variant="outline" onPress={() => setToken(null)} data-testid="account-signout-button">
            {t("signOut")}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card data-testid="account-info-card">
          <Card.Header>
            <Card.Title>{account.display_name}</Card.Title>
            <Card.Description>
              {account.roles.length ? account.roles.join(", ") : t("signedInNoRole")}
            </Card.Description>
          </Card.Header>
          <Card.Content>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-slate-500">{t("labels.club")}</dt>
              <dd>{account.club_id ? `#${account.club_id}` : t("labels.notAssigned")}</dd>
              <dt className="text-slate-500">{t("labels.signInMethods")}</dt>
              <dd>{account.identities.map((i) => i.provider).join(", ") || "—"}</dd>
              <dt className="text-slate-500">{t("labels.status")}</dt>
              <dd>{account.is_active ? t("labels.active") : t("labels.disabled")}</dd>
            </dl>
          </Card.Content>
        </Card>

        <Card data-testid="account-permissions-card">
          <Card.Header>
            <Card.Title>{t("permissions")}</Card.Title>
          </Card.Header>
          <Card.Content>
            {allowed.length ? (
              <ul className="space-y-1.5 text-sm">
                {allowed.map((entry) => (
                  <li key={entry.key} className="flex gap-2">
                    <span aria-hidden className="text-brand-600">
                      ✓
                    </span>
                    {t(entry.key)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-600">{t("noPermissions")}</p>
            )}
          </Card.Content>
        </Card>
      </div>

      <Profile />
      <DeleteAccount />
    </>
  );
}

/** Story S-2: a sailor's self-service profile — own name, birthdate, and photo.
 *
 * Not every account has a linked `Sailor` row (an admin-only test account, for
 * instance) — that's not an error, just nothing to edit here, so the 404 the backend
 * sends for it (`no-linked-sailor-record`) gets its own quiet message instead of the
 * generic error banner.
 */
function Profile() {
  const { t } = useTranslation("account");
  const [sailor, setSailor] = useState<SailorMe | null>(null);
  const [noRecord, setNoRecord] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.sailors
      .me()
      .then((data) => {
        if (!active) return;
        setSailor(data);
        setFirstName(data.first_name);
        setLastName(data.last_name);
        setBirthDate(data.birth_date ?? "");
        setNoRecord(false);
        setLoadError(null);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && err.code === "no-linked-sailor-record") {
          setNoRecord(true);
        } else {
          setLoadError(errorText(err));
        }
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  // The photo itself needs the bearer token — a plain `<img src>` never sends it, and a
  // minor's photo is only ever served to a signed-in, connected account (see
  // `app/routers/sailors.py::_may_view_minor_photo`). Fetching it here and turning it
  // into an object URL works for that case exactly as it does for a public, adult photo.
  useEffect(() => {
    if (!sailor?.has_photo) {
      setPhotoUrl(null);
      return;
    }
    let active = true;
    let localUrl: string | null = null;
    const token = getToken();
    fetch(api.sailorPhotoUrl(sailor.id), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((response) => (response.ok ? response.blob() : Promise.reject(response)))
      .then((blob) => {
        if (!active) return;
        localUrl = URL.createObjectURL(blob);
        setPhotoUrl(localUrl);
      })
      .catch(() => active && setPhotoUrl(null));
    return () => {
      active = false;
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
  }, [sailor?.id, sailor?.has_photo]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.sailors.updateMe({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        birth_date: birthDate || null,
      });
      setSailor(updated);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  async function uploadPhoto(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setPhotoBusy(true);
    setError(null);
    try {
      setSailor(await api.sailors.uploadMyPhoto(file));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPhotoBusy(false);
    }
  }

  async function removePhoto() {
    setPhotoBusy(true);
    setError(null);
    try {
      await api.sailors.deleteMyPhoto();
      setSailor((prev) => (prev ? { ...prev, has_photo: false } : prev));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPhotoBusy(false);
    }
  }

  return (
    <Card className="mt-4" data-testid="account-profile-card">
      <Card.Header>
        <Card.Title>{t("profile.title")}</Card.Title>
        <Card.Description>{t("profile.description")}</Card.Description>
      </Card.Header>
      <Card.Content>
        {loading ? (
          <Loading testId="account-profile-loading" />
        ) : loadError ? (
          <ErrorMessage text={loadError} testId="account-profile-load-error" />
        ) : noRecord ? (
          <p className="text-sm text-slate-600">{t("profile.noSailorRecord")}</p>
        ) : sailor ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-4">
              {photoUrl ? (
                <img
                  src={photoUrl}
                  alt={t("profile.photoAlt")}
                  data-testid="account-profile-photo"
                  className="h-20 w-20 rounded-full object-cover ring-1 ring-slate-200"
                />
              ) : (
                <div
                  aria-hidden
                  data-testid="account-profile-photo-placeholder"
                  className="flex h-20 w-20 items-center justify-center rounded-full bg-slate-100 text-lg font-semibold text-slate-400 ring-1 ring-slate-200"
                >
                  {`${sailor.first_name.charAt(0)}${sailor.last_name.charAt(0)}`.toUpperCase()}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <label
                  data-testid="account-profile-photo-upload-label"
                  className={
                    "inline-flex cursor-pointer items-center justify-center rounded-md " +
                    "border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 " +
                    (photoBusy ? "pointer-events-none opacity-60" : "")
                  }
                >
                  {photoBusy
                    ? t("profile.photoUploading")
                    : sailor.has_photo
                      ? t("profile.replacePhoto")
                      : t("profile.uploadPhoto")}
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    disabled={photoBusy}
                    onChange={uploadPhoto}
                    data-testid="account-profile-photo-upload-input"
                  />
                </label>
                {sailor.has_photo && (
                  <Button
                    variant="outline"
                    isDisabled={photoBusy}
                    onPress={removePhoto}
                    data-testid="account-profile-photo-remove-button"
                  >
                    {t("profile.removePhoto")}
                  </Button>
                )}
              </div>
            </div>

            <form onSubmit={save} data-testid="account-profile-form" className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="profile-first-name"
                    className="mb-1 block text-sm font-medium text-slate-700"
                  >
                    {t("profile.firstNameLabel")}
                  </label>
                  <input
                    id="profile-first-name"
                    type="text"
                    required
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className={INPUT_CLASS}
                    data-testid="account-profile-first-name-input"
                  />
                </div>
                <div>
                  <label
                    htmlFor="profile-last-name"
                    className="mb-1 block text-sm font-medium text-slate-700"
                  >
                    {t("profile.lastNameLabel")}
                  </label>
                  <input
                    id="profile-last-name"
                    type="text"
                    required
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className={INPUT_CLASS}
                    data-testid="account-profile-last-name-input"
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="profile-birth-date"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  {t("profile.birthDateLabel")}
                </label>
                <input
                  id="profile-birth-date"
                  type="date"
                  value={birthDate}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(e) => setBirthDate(e.target.value)}
                  className={INPUT_CLASS}
                  data-testid="account-profile-birth-date-input"
                />
              </div>
              {error && <ErrorMessage text={error} testId="account-profile-error" />}
              <Button type="submit" isDisabled={saving} data-testid="account-profile-save-button">
                {saving ? t("profile.saving") : t("profile.save")}
              </Button>
            </form>
          </div>
        ) : null}
      </Card.Content>
    </Card>
  );
}

/** Story Z-7: delete the signed-in account outright — a testing-phase convenience, not
 *  the permanent behavior (see the endpoint's docstring and docs/userstories.md). A plain
 *  two-step confirm instead of a modal: this project has no dialog primitive elsewhere,
 *  and a destructive action deserves an explicit second click regardless. */
function DeleteAccount() {
  const { t } = useTranslation("account");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function deleteAccount() {
    setBusy(true);
    setError(null);
    try {
      await api.auth.deleteMyAccount();
      setToken(null);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <Card className="mt-4 border-red-200" data-testid="account-delete-card">
      <Card.Header>
        <Card.Title>{t("deleteAccount.title")}</Card.Title>
        <Card.Description>{t("deleteAccount.description")}</Card.Description>
      </Card.Header>
      <Card.Content>
        {error && <ErrorMessage text={error} testId="account-delete-error" />}
        {confirming ? (
          <div className="flex flex-wrap items-center gap-3">
            <p data-testid="account-delete-confirm-prompt" className="text-sm font-medium text-red-800">
              {t("deleteAccount.confirmPrompt")}
            </p>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              isDisabled={busy}
              onPress={deleteAccount}
              data-testid="account-delete-confirm-button"
            >
              {busy ? t("deleteAccount.deleting") : t("deleteAccount.confirmButton")}
            </Button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={busy}
              data-testid="account-delete-cancel-button"
              className="text-sm text-slate-600 underline underline-offset-2 hover:text-slate-900"
            >
              {t("deleteAccount.cancelButton")}
            </button>
          </div>
        ) : (
          <Button
            variant="outline"
            className="border-red-300 text-red-700 hover:bg-red-50"
            onPress={() => setConfirming(true)}
            data-testid="account-delete-button"
          >
            {t("deleteAccount.button")}
          </Button>
        )}
      </Card.Content>
    </Card>
  );
}

/** Sign in with a one-time code sent by email — or create an account the same way, when
 * self-registration is open.
 *
 * Both converge on the same two steps: enter the address (plus a name, for a new
 * account), then the 6-digit code that arrives by mail — registering sends its first
 * code through the exact same path a sign-in does (`app.services.login.register`). The
 * backend deliberately never reveals whether an address already has an account, so the
 * "check your email" step reads the same either way.
 */
function SignIn() {
  const { t } = useTranslation("account");
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [registrationOffered, setRegistrationOffered] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"email" | "code">("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    // A registration tab is a nice-to-have — sign-in must keep working even if this
    // (or the network) fails, so no error state here, just leave the tab hidden.
    api.auth
      .providers()
      .then((p) => setRegistrationOffered(p.allow_registration))
      .catch(() => {});
  }, []);

  async function requestCode() {
    if (mode === "register") {
      await api.auth.register(email.trim().toLowerCase(), displayName.trim());
    } else {
      await api.auth.requestEmailCode(email.trim().toLowerCase());
    }
  }

  async function submitEmail(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await requestCode();
      setStep("code");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function resendCode() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await requestCode();
      setNotice(t("signIn.resent"));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.auth.verifyEmailCode(email.trim().toLowerCase(), code.trim());
      setToken(result.access_token);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: "signin" | "register") {
    setMode(next);
    setError(null);
  }

  if (step === "email") {
    return (
      <form onSubmit={submitEmail} data-testid="account-signin-form" className="space-y-3">
        {registrationOffered && (
          <div className="flex gap-4 border-b border-slate-200 pb-2 text-sm">
            <button
              type="button"
              onClick={() => switchMode("signin")}
              data-testid="account-signin-tab-signin"
              className={
                mode === "signin"
                  ? "font-semibold text-brand-700"
                  : "text-slate-500 hover:text-slate-700"
              }
            >
              {t("signIn.tabSignIn")}
            </button>
            <button
              type="button"
              onClick={() => switchMode("register")}
              data-testid="account-signin-tab-register"
              className={
                mode === "register"
                  ? "font-semibold text-brand-700"
                  : "text-slate-500 hover:text-slate-700"
              }
            >
              {t("signIn.tabRegister")}
            </button>
          </div>
        )}

        {mode === "register" && (
          <div>
            <label
              htmlFor="signin-name"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              {t("signIn.nameLabel")}
            </label>
            <input
              id="signin-name"
              type="text"
              required
              minLength={2}
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("signIn.namePlaceholder")}
              className={INPUT_CLASS}
              data-testid="account-signin-name-input"
            />
          </div>
        )}

        <div>
          <label htmlFor="signin-email" className="mb-1 block text-sm font-medium text-slate-700">
            {t("signIn.emailLabel")}
          </label>
          <input
            id="signin-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("signIn.emailPlaceholder")}
            className={INPUT_CLASS}
            data-testid="account-signin-email-input"
          />
        </div>
        {mode === "register" && <p className="text-sm text-slate-500">{t("signIn.registerHint")}</p>}
        {error && <ErrorMessage text={error} testId="account-signin-error" />}
        <Button
          type="submit"
          isDisabled={busy || !email.trim() || (mode === "register" && !displayName.trim())}
          data-testid="account-signin-send-code-button"
        >
          {busy
            ? t("signIn.sending")
            : mode === "register"
              ? t("signIn.sendCodeRegister")
              : t("signIn.sendCode")}
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={submitCode} data-testid="account-signin-code-form" className="space-y-3">
      <div>
        <p className="font-medium text-slate-900">{t("signIn.codeSentTitle")}</p>
        <p className="text-sm text-slate-600">
          {t(mode === "register" ? "signIn.codeSentHintRegister" : "signIn.codeSentHint", {
            email: email.trim().toLowerCase(),
          })}
        </p>
      </div>
      <div>
        <label htmlFor="signin-code" className="mb-1 block text-sm font-medium text-slate-700">
          {t("signIn.codeLabel")}
        </label>
        <input
          id="signin-code"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          required
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={t("signIn.codePlaceholder")}
          className={INPUT_CLASS}
          data-testid="account-signin-code-input"
        />
      </div>
      {error && <ErrorMessage text={error} testId="account-signin-verify-error" />}
      {notice && (
        <p data-testid="account-signin-resent-message" className="text-sm text-emerald-700">
          {notice}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" isDisabled={busy || !code.trim()} data-testid="account-signin-verify-button">
          {busy ? t("signIn.verifying") : t("signIn.verify")}
        </Button>
        <button
          type="button"
          onClick={resendCode}
          disabled={busy}
          data-testid="account-signin-resend-button"
          className="text-sm text-slate-600 underline underline-offset-2 hover:text-slate-900"
        >
          {t("signIn.resendCode")}
        </button>
        <button
          type="button"
          onClick={() => {
            setStep("email");
            setCode("");
            setError(null);
            setNotice(null);
          }}
          disabled={busy}
          data-testid="account-signin-change-email-button"
          className="text-sm text-slate-600 underline underline-offset-2 hover:text-slate-900"
        >
          {t("signIn.changeEmail")}
        </button>
      </div>
    </form>
  );
}
