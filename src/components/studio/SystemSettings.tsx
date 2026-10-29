import { configFieldLabel, configReviewValue } from "../../i18n/configFields";
import { ErrorText } from "../ErrorText";
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";
import { invoke } from "../../ipc";
import { DEFAULT_CONFIG, type TaskbarConfig } from "../../types";
import { useConfig, errorMessage } from "../../config/store";
import { usePlatform } from "../../hooks/usePlatform";
import { useI18n } from "../../i18n/useI18n";
import { Card, Toggle } from "./Controls";
import { ShortcutSettings } from "./ShortcutSettings";
import { capabilityReason } from "../../capabilities";
interface Review { config: TaskbarConfig; changedFields: string[]; expectedRevision: number; kind: "import" | "reset" }
export function SystemSettings() {
  const { config, revision, updateConfig, replaceConfigDocument } = useConfig();
  const { platform, error: platformError, refresh: refreshPlatform } = usePlatform();
  const { t, language, text } = useI18n();
  const [autostart, setAutostart] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [review, setReview] = useState<Review | null>(null);
  const [previous, setPrevious] = useState<{ config: TaskbarConfig; revision: number } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const reviewRequest = useRef(0);
  const reviewRegion = useRef<HTMLElement>(null);
  const reviewTrigger = useRef<HTMLButtonElement | null>(null);
  const undoButton = useRef<HTMLButtonElement>(null);
  const focusReview = useRef(false);
  const restoreFocus = useRef<"trigger" | "undo" | null>(null);
  const savingLock = useRef(false);
  const [saving, setSaving] = useState(false);
  const ownsFocus = (scope: HTMLElement | null) => document.hasFocus() &&
    (document.activeElement === document.body || !!scope?.contains(document.activeElement));
  const closeReview = (destination: "trigger" | "undo") => {
    if (ownsFocus(reviewRegion.current)) restoreFocus.current = destination;
    focusReview.current = false;
    setReview(null);
  };
  useLayoutEffect(() => {
    const settleFocus = () => {
      // GTK may return the WebView's native focus after the async review rendered.
      if (!document.hasFocus()) return;
      if (review && focusReview.current) {
        focusReview.current = false;
        if (ownsFocus(reviewTrigger.current) || document.activeElement === input.current) reviewRegion.current?.focus();
      } else if (!review && restoreFocus.current) {
        const destination = restoreFocus.current;
        restoreFocus.current = null;
        if (document.activeElement === document.body)
          (destination === "undo" ? undoButton.current : reviewTrigger.current)?.focus();
      }
    };
    settleFocus();
    window.addEventListener("focus", settleFocus);
    return () => window.removeEventListener("focus", settleFocus);
  }, [review, previous, saving]);
  useEffect(() => {
    let disposed = false;
    invoke<boolean>("is_autostart_enabled").then((value) => { if (!disposed) setAutostart(value); }).catch((e) => { if (!disposed) setError(errorMessage(e)); });
    return () => { disposed = true; reviewRequest.current++; };
  }, []);
  const perform = async (task: () => Promise<unknown>) => { try { await task(); setError(""); } catch (e) { setError(errorMessage(e)); } };
  const prepare = async (document: unknown, kind: Review["kind"], request = ++reviewRequest.current) => {
    if (request !== reviewRequest.current) return;
    setReview(null);
    try {
      const reviewed = await invoke<Omit<Review, "kind">>("review_config_document", { document });
      if (request === reviewRequest.current) { setReview({ ...reviewed, kind }); setError(""); }
    } catch (e) { if (request === reviewRequest.current) setError(errorMessage(e)); }
  };
  return <>
    <Card title={t("systemTab")}>
      <label className="settings-field">{t("language")}<select value={config.language} aria-label={t("language")} onChange={(e) => void updateConfig({ language: e.target.value as "vi" | "en" })}><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label>
      <Toggle label={t("keepDock")} value={config.keepDockOnClose} onChange={(keepDockOnClose) => updateConfig({ keepDockOnClose })} />
      <Toggle label={t("autostart")} value={autostart} onChange={(enabled) => perform(async () => setAutostart(await invoke<boolean>("set_autostart", { enabled })))} />
      <div className="settings-inline"><button className="studio-button" onClick={() => void perform(() => invoke("install_app_icon"))}>{t("installIcon")}</button><button className="studio-button danger" onClick={() => void invoke("quit_app")}>{t("quit")}</button></div>
    </Card>
    <ShortcutSettings />
    <Card title={t("importConfig")}>
      <p className="settings-help">{t("exportHelp")}</p>
      <div className="settings-inline"><button className="studio-button" onClick={() => void perform(async () => { const path = await invoke<string | null>("export_config"); if (path) setStatus(path); })}>{t("exportConfig")}</button><button className="studio-button" disabled={saving} onClick={(event) => { if (savingLock.current) return; reviewTrigger.current = event.currentTarget; focusReview.current = true; input.current?.click(); }}>{t("importConfig")}</button></div>
      <input ref={input} type="file" accept="application/json,.json" hidden onChange={async (e) => {
        if (savingLock.current) return;
        const file = e.target.files?.[0]; e.target.value = "";
        if (!file) return;
        const request = ++reviewRequest.current;
        setReview(null);
        if (file.size > 1024 * 1024) { setError(t("fileTooLarge")); return; }
        try { await prepare(JSON.parse(await file.text()), "import", request); } catch (e) { if (request === reviewRequest.current) setError(errorMessage(e)); }
      }} />
      <p className="settings-help">{t("resetHelp")}</p><button className="studio-button danger" disabled={saving} onClick={(event) => { if (savingLock.current) return; reviewTrigger.current = event.currentTarget; focusReview.current = true; void prepare({ schemaVersion: 1, config: { ...DEFAULT_CONFIG, presets: config.presets, language: config.language } }, "reset"); }}>{t("reset")}</button>
      {review && <section ref={reviewRegion} tabIndex={-1} aria-busy={saving} className="config-review" aria-label={t("importReview")}><h3>{t("importReview")}</h3><p>{review.changedFields.length ? t("changedFields") : t("noChanges")}</p><ul>{review.changedFields.map((field) => <li key={field}><strong>{configFieldLabel(language, field)}</strong><pre>{configReviewValue(language, field, review.config[field as keyof TaskbarConfig])}</pre></li>)}</ul>
        <div className="settings-inline"><button className="studio-button" disabled={saving || !review.changedFields.length} onClick={async () => {
          if (savingLock.current || !review.changedFields.length) return;
          savingLock.current = true; setSaving(true);
          const old = config;
          const request = reviewRequest.current;
          try {
            if (await replaceConfigDocument({ schemaVersion: 1, config: review.config }, review.expectedRevision) && request === reviewRequest.current) {
              setPrevious({ config: old, revision: review.expectedRevision + 1 }); closeReview("undo"); setStatus(t("configSaved"));
            } else if (request === reviewRequest.current && ownsFocus(reviewRegion.current)) focusReview.current = true;
          } finally { savingLock.current = false; if (request === reviewRequest.current) setSaving(false); }
        }}>{review.kind === "reset" ? t("resetConfirm") : t("importConfirm")}</button><button className="studio-button" disabled={saving} onClick={() => { if (savingLock.current) return; reviewRequest.current++; closeReview("trigger"); }}>{t("cancel")}</button></div>
      </section>}
      {previous && <button ref={undoButton} className="studio-button" disabled={saving || revision !== previous.revision} onClick={async () => {
        if (savingLock.current || revision !== previous.revision) return;
        savingLock.current = true; setSaving(true);
        const request = reviewRequest.current;
        try {
          if (await replaceConfigDocument({ schemaVersion: 1, config: previous.config }, previous.revision) && request === reviewRequest.current) {
            if (ownsFocus(undoButton.current)) restoreFocus.current = "trigger";
            setPrevious(null);
          } else if (request === reviewRequest.current && ownsFocus(undoButton.current)) restoreFocus.current = "undo";
        } finally { savingLock.current = false; if (request === reviewRequest.current) setSaving(false); }
      }}>{t("undo")}</button>}
    </Card>
    <Card title={t("systemInfo")}><dl className="system-info"><dt>{t("desktop")}</dt><dd>{platform?.desktop || t("unknown")}</dd><dt>{t("session")}</dt><dd>{platform?.session.toUpperCase() || t("unknown")}</dd>
      {([
        ["dockPlacement", "dockPlacement", platform?.dockPlacement], ["autoHide", "autoHide", platform?.autoHide],
        ["enumerateWindows", "windowEnumeration", platform?.windows.enumerate], ["activateWindows", "windowActivation", platform?.windows.activate],
        ["closeWindows", "windowClose", platform?.windows.close], ["forceQuit", "forceQuit", platform?.forceQuit],
        ["wallpaperSupport", "wallpaper", platform?.wallpaper], ["workspaces", "workspaces", platform?.workspaces],
      ] as const).map(([label, feature, available]) => <Fragment key={label}><dt>{t(label)}</dt><dd>{available === undefined ? (platformError ? t("capabilityProbeFailed") : t("loading")) : available ? t("supported") : feature === "workspaces" ? t("developing") : t("unsupported")}
        {available === false && <small>{capabilityReason(platform, feature, t, platformError)}</small>}
      </dd></Fragment>)}
    </dl><p className="settings-help">{t("updatesUnsupported")}</p><button onClick={refreshPlatform}>{t("refreshCapabilities")}</button></Card>
    {error && <p role="alert"><ErrorText error={error} /></p>}{status && <p role="status">{text(status)}</p>}
  </>;
}
