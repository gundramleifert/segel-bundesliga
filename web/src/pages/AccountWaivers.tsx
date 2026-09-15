import { Button, Card } from "@heroui/react";
import { useCallback, useEffect, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  confirmForEvent,
  confirmForSeries,
  getCurrentWaiver,
  getGetWaiverScanUrl,
  getWaiverFormUrl,
  myWaivers,
  uploadEventWaiverScan,
  uploadSeriesWaiverScan,
} from "../api/generated/sbl";
import { ApiError } from "../api/http";
import type { MyCompetitionWaiver, MyWaivers, WaiverText } from "../api/types";
import { ErrorMessage, Loading } from "../components/Blocks";
import { Message } from "../components/Form";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { downloadFile, openFile } from "../lib/files";
import { formatDate } from "../lib/format";

/** Story S-1: the liability waiver, one statement per competition, from the sailor's own
 * account.
 *
 * The list is what `GET /api/waiver/me` says the sailor has to sign for — every series
 * they are registered in, every stand-alone event they are entered in — with the same
 * status the organizer's check-in list computes. Which path a row offers follows from the
 * date of birth: an adult reads the wording and confirms it here; a minor downloads the
 * form, has a guardian sign it, and uploads the scan. Without a date of birth neither is
 * offered — the row points at the profile form above instead, where the sailor enters it.
 *
 * The card renders nothing when the account has no sailor record: the profile card right
 * above already says so, and saying it twice helps nobody.
 */
export function Waivers() {
  const { t, i18n } = useTranslation("account");
  const lang: "en" | "de" = i18n.language.startsWith("de") ? "de" : "en";
  const [data, setData] = useState<MyWaivers | null>(null);
  const [text, setText] = useState<WaiverText | null>(null);
  const [noRecord, setNoRecord] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    let active = true;
    Promise.all([myWaivers(), getCurrentWaiver().catch(() => null)])
      .then(([mine, wording]) => {
        if (!active) return;
        setData(mine);
        setText(wording);
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

  useEffect(() => load(), [load]);

  if (noRecord) return null;

  return (
    <Card className="mt-4" data-testid="account-waivers-card">
      <Card.Header>
        <Card.Title>{t("waiver.title")}</Card.Title>
        <Card.Description>{t("waiver.description")}</Card.Description>
      </Card.Header>
      <Card.Content>
        {loading ? (
          <Loading testId="account-waivers-loading" />
        ) : loadError ? (
          <ErrorMessage text={loadError} testId="account-waivers-error" />
        ) : data && data.competitions.length === 0 ? (
          <p className="text-sm text-slate-600" data-testid="account-waivers-empty">
            {t("waiver.none")}
          </p>
        ) : data ? (
          <ul className="grid grid-cols-[minmax(0,1fr)] gap-4" data-testid="account-waivers-list">
            {data.competitions.map((row) => (
              <li key={`${row.scope}-${row.scope_id}`}>
                <CompetitionRow
                  row={row}
                  text={text}
                  lang={lang}
                  birthDateKnown={data.birth_date_known}
                  onChanged={load}
                />
              </li>
            ))}
          </ul>
        ) : null}
      </Card.Content>
    </Card>
  );
}

const STATUS_STYLE: Record<string, string> = {
  cleared: "bg-emerald-100 text-emerald-800 ring-emerald-300",
  missing: "bg-amber-100 text-amber-800 ring-amber-300",
  version_outdated: "bg-amber-100 text-amber-800 ring-amber-300",
  guardian_signature_missing: "bg-amber-100 text-amber-800 ring-amber-300",
  birth_date_unknown: "bg-slate-100 text-slate-700 ring-slate-300",
  not_required: "bg-slate-100 text-slate-600 ring-slate-200",
};

const OPEN = new Set(["missing", "version_outdated", "guardian_signature_missing"]);

function CompetitionRow({
  row,
  text,
  lang,
  birthDateKnown,
  onChanged,
}: {
  row: MyCompetitionWaiver;
  text: WaiverText | null;
  lang: "en" | "de";
  birthDateKnown: boolean;
  onChanged: () => void;
}) {
  const { t } = useTranslation("account");
  const [reading, setReading] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [guardianName, setGuardianName] = useState(row.guardian_name ?? "");
  const [busy, setBusy] = useState<"confirm" | "download" | "upload" | "scan" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const id = `${row.scope}-${row.scope_id}`;
  const open = OPEN.has(row.status) && birthDateKnown && row.minor !== null;
  const noBirthDate = !birthDateKnown || row.status === "birth_date_unknown";

  async function run<T>(what: typeof busy, action: () => Promise<T>, done?: string) {
    setBusy(what);
    setError(null);
    setSuccess(null);
    try {
      await action();
      if (done) setSuccess(done);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  const confirm = () =>
    run(
      "confirm",
      async () => {
        const body = { sailor_id: row.sailor_id, locale_shown: lang };
        if (row.scope === "series") await confirmForSeries(row.scope_id, body);
        else await confirmForEvent(row.scope_id, body);
        setReading(false);
        onChanged();
      },
      t("waiver.adult.done"),
    );

  const download = () =>
    run("download", () =>
      downloadFile(
        getWaiverFormUrl({
          scope: row.scope,
          scope_id: row.scope_id,
          sailor_id: row.sailor_id,
          locale: lang,
        }),
        `waiver-${id}.pdf`,
      ),
    );

  const upload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    void run(
      "upload",
      async () => {
        const body = {
          file,
          sailor_id: row.sailor_id,
          guardian_name: guardianName.trim() || null,
          locale_shown: lang,
        };
        if (row.scope === "series") await uploadSeriesWaiverScan(row.scope_id, body);
        else await uploadEventWaiverScan(row.scope_id, body);
        onChanged();
      },
      t("waiver.minor.done"),
    );
  };

  const viewScan = () =>
    row.confirmation_id != null &&
    run("scan", () => openFile(getGetWaiverScanUrl(row.confirmation_id!)));

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white p-4"
      data-testid={`account-waiver-${id}`}
      data-status={row.status}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium" data-testid={`account-waiver-name-${id}`}>
            {row.name}
          </p>
          <p className="text-xs text-slate-500">
            {t("waiver.forCompetition", { date: formatDate(row.reference_date) })}
            {row.confirmed_at && row.confirmed_version != null && (
              <>
                {" · "}
                {t("waiver.confirmedOn", {
                  version: row.confirmed_version,
                  date: formatDate(row.confirmed_at),
                })}
                {row.method === "guardian" && row.guardian_name
                  ? `, ${t("waiver.methodGuardian", { name: row.guardian_name })}`
                  : row.method === "online"
                    ? `, ${t("waiver.methodOnline")}`
                    : ""}
              </>
            )}
          </p>
        </div>
        <span
          data-testid={`account-waiver-status-${id}`}
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
            STATUS_STYLE[row.status] ?? STATUS_STYLE.not_required
          }`}
        >
          {t(`waiver.status.${row.status}`)}
        </span>
      </div>

      {noBirthDate && row.status !== "cleared" && (
        <p className="mt-3 text-sm text-slate-700" data-testid={`account-waiver-need-birth-date-${id}`}>
          {t("waiver.needBirthDate")}
        </p>
      )}

      {open && row.minor === false && (
        <div className="mt-3 space-y-3">
          {reading && text ? (
            <div
              className="rounded-md bg-slate-50 p-3 text-sm"
              data-testid={`account-waiver-text-${id}`}
            >
              <p className="font-semibold">{lang === "de" ? text.title_de : text.title_en}</p>
              <p className="mt-2 whitespace-pre-line text-slate-700">
                {lang === "de" ? text.body_de : text.body_en}
              </p>
              <label className="mt-3 flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-0.5"
                  data-testid={`account-waiver-agree-${id}`}
                />
                <span>{t("waiver.adult.agree")}</span>
              </label>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={reading ? "outline" : "primary"}
              onPress={() => setReading((v) => !v)}
              data-testid={`account-waiver-read-${id}`}
            >
              {reading ? t("waiver.adult.hide") : t("waiver.adult.read")}
            </Button>
            {reading && (
              <Button
                size="sm"
                isDisabled={!agreed || busy !== null}
                onPress={confirm}
                data-testid={`account-waiver-confirm-${id}`}
              >
                {busy === "confirm" ? t("waiver.adult.confirming") : t("waiver.adult.confirm")}
              </Button>
            )}
          </div>
        </div>
      )}

      {open && row.minor === true && (
        <div className="mt-3 space-y-3">
          <p className="text-sm text-slate-700">{t("waiver.minor.explain")}</p>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
            <Button
              size="sm"
              variant="outline"
              isDisabled={busy !== null}
              onPress={download}
              data-testid={`account-waiver-download-${id}`}
            >
              {busy === "download" ? t("waiver.minor.downloading") : t("waiver.minor.download")}
            </Button>
            <div />
            <div>
              <label
                htmlFor={`guardian-${id}`}
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                {t("waiver.minor.guardianName")}
              </label>
              <input
                id={`guardian-${id}`}
                type="text"
                value={guardianName}
                onChange={(e) => setGuardianName(e.target.value)}
                className={INPUT_CLASS}
                data-testid={`account-waiver-guardian-${id}`}
              />
            </div>
            <div className="self-end">
              <label
                data-testid={`account-waiver-upload-label-${id}`}
                className={
                  "inline-flex cursor-pointer items-center justify-center rounded-md " +
                  "border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 " +
                  (busy !== null ? "pointer-events-none opacity-60" : "")
                }
              >
                {busy === "upload"
                  ? t("waiver.minor.uploading")
                  : row.scan_available
                    ? t("waiver.minor.replace")
                    : t("waiver.minor.upload")}
                <input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  className="hidden"
                  disabled={busy !== null}
                  onChange={upload}
                  data-testid={`account-waiver-upload-${id}`}
                />
              </label>
            </div>
          </div>
        </div>
      )}

      {row.scan_available && row.confirmation_id != null && (
        <div className="mt-3">
          <button
            type="button"
            onClick={viewScan}
            disabled={busy !== null}
            className="text-sm underline underline-offset-2"
            data-testid={`account-waiver-scan-${id}`}
          >
            {t("waiver.viewScan")}
          </button>
        </div>
      )}

      <div className="mt-3">
        <Message testId={`account-waiver-message-${id}`} error={error} success={success} />
      </div>
    </div>
  );
}
