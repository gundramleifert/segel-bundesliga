import { Button, Card } from "@heroui/react";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  emailRequest,
  emailVerify,
  me,
  passwordLogin,
  providers,
  registerAccount,
} from "../api/generated/sbl";
import type { Account as AccountData } from "../api/types";
import { getToken, onTokenChange, setToken } from "../api/session";
import { ErrorMessage, Loading, PageHeader } from "../components/Blocks";
import { INPUT_CLASS, errorText } from "../lib/admin";

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
      me()
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
              <p data-testid="account-session-error" className="mb-3 text-danger">
                {error}
              </p>
            )}
            <SignIn />
          </Card.Content>
        </Card>
      </>
    );
  }

  // Signed in, the account lives in my space (Story S-7); this address stays the
  // sign-in page, and a bookmark of it still lands somewhere sensible.
  return <Navigate to="/me/profile" replace />;
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
  const [mode, setMode] = useState<"password" | "signin" | "register">("signin");
  const [registrationOffered, setRegistrationOffered] = useState(false);
  const [passwordOffered, setPasswordOffered] = useState(false);
  const [password, setPassword] = useState("");
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
    providers()
      .then((p) => {
        setRegistrationOffered(p.allow_registration);
        setPasswordOffered(p.password.available);
        // Story Z-9: where passwords are open, they are the first tab — the code stays
        // one click away, and is also what "forgot password" leads to.
        if (p.password.available) setMode((current) => (current === "signin" ? "password" : current));
      })
      .catch(() => {});
  }, []);

  async function requestCode() {
    if (mode === "register") {
      await registerAccount({
        email: email.trim().toLowerCase(),
        display_name: displayName.trim(),
      });
    } else {
      await emailRequest({ email: email.trim().toLowerCase() });
    }
  }

  async function submitEmail(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "password") {
        const result = await passwordLogin({ email: email.trim().toLowerCase(), password });
        setToken(result.access_token);
        return;
      }
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
      const result = await emailVerify({ email: email.trim().toLowerCase(), code: code.trim() });
      setToken(result.access_token);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: "password" | "signin" | "register") {
    setMode(next);
    setError(null);
  }

  const tab = (key: "password" | "signin" | "register", label: string) => (
    <button
      type="button"
      onClick={() => switchMode(key)}
      data-testid={`account-signin-tab-${key}`}
      className={mode === key ? "font-semibold text-link" : "text-muted hover:text-foreground"}
    >
      {label}
    </button>
  );

  if (step === "email") {
    return (
      <form onSubmit={submitEmail} data-testid="account-signin-form" className="space-y-3">
        {(registrationOffered || passwordOffered) && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 border-b border-separator pb-2 text-sm">
            {passwordOffered && tab("password", t("signIn.tabPassword"))}
            {tab("signin", passwordOffered ? t("signIn.tabCode") : t("signIn.tabSignIn"))}
            {registrationOffered && tab("register", t("signIn.tabRegister"))}
          </div>
        )}

        {mode === "register" && (
          <div>
            <label
              htmlFor="signin-name"
              className="mb-1 block text-sm font-medium text-foreground"
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
          <label htmlFor="signin-email" className="mb-1 block text-sm font-medium text-foreground">
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
        {mode === "password" && (
          <div>
            <label htmlFor="signin-password" className="mb-1 block text-sm font-medium text-foreground">
              {t("signIn.passwordLabel")}
            </label>
            <input
              id="signin-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={INPUT_CLASS}
              data-testid="account-signin-password-input"
            />
          </div>
        )}
        {mode === "register" && <p className="text-sm text-muted">{t("signIn.registerHint")}</p>}
        {error && <ErrorMessage text={error} testId="account-signin-error" />}
        {mode === "password" ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              isDisabled={busy || !email.trim() || !password}
              data-testid="account-signin-password-button"
            >
              {busy ? t("signIn.verifying") : t("signIn.verify")}
            </Button>
            <button
              type="button"
              onClick={() => switchMode("signin")}
              data-testid="account-signin-forgot-button"
              className="text-sm text-muted underline underline-offset-2 hover:text-foreground"
            >
              {t("signIn.forgotPassword")}
            </button>
          </div>
        ) : (
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
        )}
      </form>
    );
  }

  return (
    <form onSubmit={submitCode} data-testid="account-signin-code-form" className="space-y-3">
      <div>
        <p className="font-medium text-foreground">{t("signIn.codeSentTitle")}</p>
        <p className="text-sm text-muted">
          {t(mode === "register" ? "signIn.codeSentHintRegister" : "signIn.codeSentHint", {
            email: email.trim().toLowerCase(),
          })}
        </p>
      </div>
      <div>
        <label htmlFor="signin-code" className="mb-1 block text-sm font-medium text-foreground">
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
        <p data-testid="account-signin-resent-message" className="text-sm text-success-soft-foreground">
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
          className="text-sm text-muted underline underline-offset-2 hover:text-foreground"
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
          className="text-sm text-muted underline underline-offset-2 hover:text-foreground"
        >
          {t("signIn.changeEmail")}
        </button>
      </div>
    </form>
  );
}
