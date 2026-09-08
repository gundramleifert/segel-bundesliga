import { Button, Card } from "@heroui/react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { api, type Account as AccountData } from "../api/client";
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

  if (laedt) return <Laden />;

  if (!konto) {
    return (
      <>
        <Seitenkopf titel={t("title")} />
        <Card>
          <Card.Header>
            <Card.Title>{t("notSignedIn")}</Card.Title>
            <Card.Description>{t("description")}</Card.Description>
          </Card.Header>
          <Card.Content>
            {fehler && <p className="mb-3 text-red-700">{fehler}</p>}
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
        rechts={
          <Button variant="outline" onPress={() => setToken(null)}>
            {t("signOut")}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
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

        <Card>
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

      <DeleteAccount />
    </>
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
    <Card className="mt-4 border-red-200">
      <Card.Header>
        <Card.Title>{t("deleteAccount.title")}</Card.Title>
        <Card.Description>{t("deleteAccount.description")}</Card.Description>
      </Card.Header>
      <Card.Content>
        {fehler && <Fehler text={fehler} />}
        {confirming ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm font-medium text-red-800">
              {t("deleteAccount.confirmPrompt")}
            </p>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              isDisabled={busy}
              onPress={loeschen}
            >
              {busy ? t("deleteAccount.deleting") : t("deleteAccount.confirmButton")}
            </Button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={busy}
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
      <form onSubmit={codeAnfordern} className="space-y-3">
        {registrationOffered && (
          <div className="flex gap-4 border-b border-slate-200 pb-2 text-sm">
            <button
              type="button"
              onClick={() => wechseln("signin")}
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
          />
        </div>
        {mode === "register" && <p className="text-sm text-slate-500">{t("signIn.registerHint")}</p>}
        {fehler && <Fehler text={fehler} />}
        <Button
          type="submit"
          isDisabled={busy || !email.trim() || (mode === "register" && !displayName.trim())}
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
    <form onSubmit={anmelden} className="space-y-3">
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
        />
      </div>
      {fehler && <Fehler text={fehler} />}
      {hinweis && <p className="text-sm text-emerald-700">{hinweis}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" isDisabled={busy || !code.trim()}>
          {busy ? t("signIn.verifying") : t("signIn.verify")}
        </Button>
        <button
          type="button"
          onClick={erneutSenden}
          disabled={busy}
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
          className="text-sm text-slate-600 underline underline-offset-2 hover:text-slate-900"
        >
          {t("signIn.changeEmail")}
        </button>
      </div>
    </form>
  );
}
