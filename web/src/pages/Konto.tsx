import { Button, Card } from "@heroui/react";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type Account as AccountData, type SailorMe } from "../api/client";
import { getToken, onTokenChange, setToken } from "../api/session";
import { Fehler, Laden, Seitenkopf } from "../components/Bausteine";
import { EINGABE, fehlertext } from "../lib/verwaltung";

/** Roles and what permissions they grant. Without this page, role switching would be invisible
 *  as long as there are no protected areas yet. */
const RECHTE: { rolle: string; key: string }[] = [
  { rolle: "admin", key: "roles.admin" },
  { rolle: "admin", key: "roles.admin_pairing" },
  { rolle: "editor", key: "roles.editor" },
  { rolle: "race_officer", key: "roles.race_officer" },
  { rolle: "club_manager", key: "roles.club_manager" },
  { rolle: "club_manager", key: "roles.club_manager_squad" },
];

export function Account() {
  const { t } = useTranslation("account");
  const [konto, setKonto] = useState<AccountData | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);

  useEffect(() => {
    const laden = () => {
      if (!getToken()) {
        setKonto(null);
        setFehler(null);
        setLaedt(false);
        return;
      }
      setLaedt(true);
      api
        .me()
        .then((daten) => {
          setKonto(daten);
          setFehler(null);
        })
        .catch(() => setFehler(t("sessionExpired")))
        .finally(() => setLaedt(false));
    };
    laden();
    return onTokenChange(laden);
  }, [t]);

  if (laedt) return <Laden testId="account-loading" />;

  if (!konto) {
    return (
      <>
        <Seitenkopf titel={t("title")} testId="account-header" />
        <Card data-testid="account-signin-card">
          <Card.Header>
            <Card.Title>{t("notSignedIn")}</Card.Title>
            <Card.Description>{t("description")}</Card.Description>
          </Card.Header>
          <Card.Content>
            {fehler && (
              <p data-testid="account-session-error" className="mb-3 text-red-700">
                {fehler}
              </p>
            )}
            <SignIn />
          </Card.Content>
        </Card>
      </>
    );
  }

  const meine = new Set(konto.roles);
  const erlaubt = RECHTE.filter((eintrag) => meine.has(eintrag.rolle));

  return (
    <>
      <Seitenkopf
        titel={t("title")}
        unterzeile={konto.email}
        testId="account-header"
        rechts={
          <Button variant="outline" onPress={() => setToken(null)} data-testid="account-signout-button">
            {t("signOut")}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card data-testid="account-info-card">
          <Card.Header>
            <Card.Title>{konto.display_name}</Card.Title>
            <Card.Description>
              {konto.roles.length ? konto.roles.join(", ") : t("signedInNoRole")}
            </Card.Description>
          </Card.Header>
          <Card.Content>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-slate-500">{t("labels.club")}</dt>
              <dd>{konto.club_id ? `#${konto.club_id}` : t("labels.notAssigned")}</dd>
              <dt className="text-slate-500">{t("labels.signInMethods")}</dt>
              <dd>{konto.identities.map((i) => i.provider).join(", ") || "—"}</dd>
              <dt className="text-slate-500">{t("labels.status")}</dt>
              <dd>{konto.is_active ? t("labels.active") : t("labels.disabled")}</dd>
            </dl>
          </Card.Content>
        </Card>

        <Card data-testid="account-permissions-card">
          <Card.Header>
            <Card.Title>{t("permissions")}</Card.Title>
          </Card.Header>
          <Card.Content>
            {erlaubt.length ? (
              <ul className="space-y-1.5 text-sm">
                {erlaubt.map((eintrag) => (
                  <li key={eintrag.key} className="flex gap-2">
                    <span aria-hidden className="text-marke-600">
                      ✓
                    </span>
                    {t(eintrag.key)}
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
  const [keinDatensatz, setKeinDatensatz] = useState(false);
  const [ladeFehler, setLadeFehler] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);

  const [vorname, setVorname] = useState("");
  const [nachname, setNachname] = useState("");
  const [geburtsdatum, setGeburtsdatum] = useState("");
  const [speichernLaeuft, setSpeichernLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  const [fotoUrl, setFotoUrl] = useState<string | null>(null);
  const [fotoLaeuft, setFotoLaeuft] = useState(false);

  useEffect(() => {
    let aktiv = true;
    setLaedt(true);
    api.sailors
      .me()
      .then((daten) => {
        if (!aktiv) return;
        setSailor(daten);
        setVorname(daten.first_name);
        setNachname(daten.last_name);
        setGeburtsdatum(daten.birth_date ?? "");
        setKeinDatensatz(false);
        setLadeFehler(null);
      })
      .catch((err) => {
        if (!aktiv) return;
        if (err instanceof ApiError && err.code === "no-linked-sailor-record") {
          setKeinDatensatz(true);
        } else {
          setLadeFehler(fehlertext(err));
        }
      })
      .finally(() => aktiv && setLaedt(false));
    return () => {
      aktiv = false;
    };
  }, []);

  // The photo itself needs the bearer token — a plain `<img src>` never sends it, and a
  // minor's photo is only ever served to a signed-in, connected account (see
  // `app/routers/sailors.py::_may_view_minor_photo`). Fetching it here and turning it
  // into an object URL works for that case exactly as it does for a public, adult photo.
  useEffect(() => {
    if (!sailor?.has_photo) {
      setFotoUrl(null);
      return;
    }
    let aktiv = true;
    let lokaleUrl: string | null = null;
    const token = getToken();
    fetch(api.sailorPhotoUrl(sailor.id), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((antwort) => (antwort.ok ? antwort.blob() : Promise.reject(antwort)))
      .then((blob) => {
        if (!aktiv) return;
        lokaleUrl = URL.createObjectURL(blob);
        setFotoUrl(lokaleUrl);
      })
      .catch(() => aktiv && setFotoUrl(null));
    return () => {
      aktiv = false;
      if (lokaleUrl) URL.revokeObjectURL(lokaleUrl);
    };
  }, [sailor?.id, sailor?.has_photo]);

  async function speichern(e: FormEvent) {
    e.preventDefault();
    setSpeichernLaeuft(true);
    setFehler(null);
    try {
      const aktualisiert = await api.sailors.updateMe({
        first_name: vorname.trim(),
        last_name: nachname.trim(),
        birth_date: geburtsdatum || null,
      });
      setSailor(aktualisiert);
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setSpeichernLaeuft(false);
    }
  }

  async function fotoHochladen(e: ChangeEvent<HTMLInputElement>) {
    const datei = e.target.files?.[0];
    e.target.value = "";
    if (!datei) return;
    setFotoLaeuft(true);
    setFehler(null);
    try {
      setSailor(await api.sailors.uploadMyPhoto(datei));
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setFotoLaeuft(false);
    }
  }

  async function fotoEntfernen() {
    setFotoLaeuft(true);
    setFehler(null);
    try {
      await api.sailors.deleteMyPhoto();
      setSailor((vorher) => (vorher ? { ...vorher, has_photo: false } : vorher));
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setFotoLaeuft(false);
    }
  }

  return (
    <Card className="mt-4" data-testid="account-profile-card">
      <Card.Header>
        <Card.Title>{t("profile.title")}</Card.Title>
        <Card.Description>{t("profile.description")}</Card.Description>
      </Card.Header>
      <Card.Content>
        {laedt ? (
          <Laden testId="account-profile-loading" />
        ) : ladeFehler ? (
          <Fehler text={ladeFehler} testId="account-profile-load-error" />
        ) : keinDatensatz ? (
          <p className="text-sm text-slate-600">{t("profile.noSailorRecord")}</p>
        ) : sailor ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-4">
              {fotoUrl ? (
                <img
                  src={fotoUrl}
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
                    (fotoLaeuft ? "pointer-events-none opacity-60" : "")
                  }
                >
                  {fotoLaeuft
                    ? t("profile.photoUploading")
                    : sailor.has_photo
                      ? t("profile.replacePhoto")
                      : t("profile.uploadPhoto")}
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    disabled={fotoLaeuft}
                    onChange={fotoHochladen}
                    data-testid="account-profile-photo-upload-input"
                  />
                </label>
                {sailor.has_photo && (
                  <Button
                    variant="outline"
                    isDisabled={fotoLaeuft}
                    onPress={fotoEntfernen}
                    data-testid="account-profile-photo-remove-button"
                  >
                    {t("profile.removePhoto")}
                  </Button>
                )}
              </div>
            </div>

            <form onSubmit={speichern} data-testid="account-profile-form" className="space-y-3">
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
                    value={vorname}
                    onChange={(e) => setVorname(e.target.value)}
                    className={EINGABE}
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
                    value={nachname}
                    onChange={(e) => setNachname(e.target.value)}
                    className={EINGABE}
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
                  value={geburtsdatum}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(e) => setGeburtsdatum(e.target.value)}
                  className={EINGABE}
                  data-testid="account-profile-birth-date-input"
                />
              </div>
              {fehler && <Fehler text={fehler} testId="account-profile-error" />}
              <Button type="submit" isDisabled={speichernLaeuft} data-testid="account-profile-save-button">
                {speichernLaeuft ? t("profile.saving") : t("profile.save")}
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
  const [fehler, setFehler] = useState<string | null>(null);

  async function loeschen() {
    setBusy(true);
    setFehler(null);
    try {
      await api.auth.deleteMyAccount();
      setToken(null);
    } catch (err) {
      setFehler(fehlertext(err));
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
        {fehler && <Fehler text={fehler} testId="account-delete-error" />}
        {confirming ? (
          <div className="flex flex-wrap items-center gap-3">
            <p data-testid="account-delete-confirm-prompt" className="text-sm font-medium text-red-800">
              {t("deleteAccount.confirmPrompt")}
            </p>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              isDisabled={busy}
              onPress={loeschen}
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
  const [fehler, setFehler] = useState<string | null>(null);
  const [hinweis, setHinweis] = useState<string | null>(null);

  useEffect(() => {
    // A registration tab is a nice-to-have — sign-in must keep working even if this
    // (or the network) fails, so no error state here, just leave the tab hidden.
    api.auth
      .providers()
      .then((p) => setRegistrationOffered(p.allow_registration))
      .catch(() => {});
  }, []);

  async function anfordern() {
    if (mode === "register") {
      await api.auth.register(email.trim().toLowerCase(), displayName.trim());
    } else {
      await api.auth.requestEmailCode(email.trim().toLowerCase());
    }
  }

  async function codeAnfordern(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFehler(null);
    try {
      await anfordern();
      setStep("code");
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setBusy(false);
    }
  }

  async function erneutSenden() {
    setBusy(true);
    setFehler(null);
    setHinweis(null);
    try {
      await anfordern();
      setHinweis(t("signIn.resent"));
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setBusy(false);
    }
  }

  async function anmelden(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFehler(null);
    try {
      const ergebnis = await api.auth.verifyEmailCode(email.trim().toLowerCase(), code.trim());
      setToken(ergebnis.access_token);
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setBusy(false);
    }
  }

  function wechseln(naechster: "signin" | "register") {
    setMode(naechster);
    setFehler(null);
  }

  if (step === "email") {
    return (
      <form onSubmit={codeAnfordern} data-testid="account-signin-form" className="space-y-3">
        {registrationOffered && (
          <div className="flex gap-4 border-b border-slate-200 pb-2 text-sm">
            <button
              type="button"
              onClick={() => wechseln("signin")}
              data-testid="account-signin-tab-signin"
              className={
                mode === "signin"
                  ? "font-semibold text-marke-700"
                  : "text-slate-500 hover:text-slate-700"
              }
            >
              {t("signIn.tabSignIn")}
            </button>
            <button
              type="button"
              onClick={() => wechseln("register")}
              data-testid="account-signin-tab-register"
              className={
                mode === "register"
                  ? "font-semibold text-marke-700"
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
              className={EINGABE}
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
            className={EINGABE}
            data-testid="account-signin-email-input"
          />
        </div>
        {mode === "register" && <p className="text-sm text-slate-500">{t("signIn.registerHint")}</p>}
        {fehler && <Fehler text={fehler} testId="account-signin-error" />}
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
    <form onSubmit={anmelden} data-testid="account-signin-code-form" className="space-y-3">
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
          className={EINGABE}
          data-testid="account-signin-code-input"
        />
      </div>
      {fehler && <Fehler text={fehler} testId="account-signin-verify-error" />}
      {hinweis && (
        <p data-testid="account-signin-resent-message" className="text-sm text-emerald-700">
          {hinweis}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" isDisabled={busy || !code.trim()} data-testid="account-signin-verify-button">
          {busy ? t("signIn.verifying") : t("signIn.verify")}
        </Button>
        <button
          type="button"
          onClick={erneutSenden}
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
            setFehler(null);
            setHinweis(null);
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
