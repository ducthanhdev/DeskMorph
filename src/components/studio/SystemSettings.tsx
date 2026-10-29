import { ErrorText } from "../ErrorText";
import { Fragment, useEffect, useRef, useState } from "react";
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
  const { t } = useI18n();
  const [autostart, setAutostart] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [review, setReview] = useState<Review | null>(null);
  const [previous, setPrevious] = useState<{ config: TaskbarConfig; revision: number } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const reviewRequest = useRef(0);
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
      <div className="settings-inline"><button className="studio-button" onClick={() => void perform(async () => { const path = await invoke<string | null>("export_config"); if (path) setStatus(path); })}>{t("exportConfig")}</button><button className="studio-button" onClick={() => input.current?.click()}>{t("importConfig")}</button></div>
      <input ref={input} type="file" accept="application/json,.json" hidden onChange={async (e) => {
        const file = e.target.files?.[0]; e.target.value = "";
        if (!file) return;
        const request = ++reviewRequest.current;
        setReview(null);
        if (file.size > 1024 * 1024) { setError(t("fileTooLarge")); return; }
        try { await prepare(JSON.parse(await file.text()), "import", request); } catch (e) { if (request === reviewRequest.current) setError(errorMessage(e)); }
      }} />
      <p className="settings-help">{t("resetHelp")}</p><button className="studio-button danger" onClick={() => { void prepare({ schemaVersion: 1, config: { ...DEFAULT_CONFIG, presets: config.presets, language: config.language } }, "reset"); }}>{t("reset")}</button>
      {review && <section className="config-review" aria-label={t("importReview")}><h3>{t("importReview")}</h3><p>{review.changedFields.length ? t("changedFields") : t("noChanges")}</p><ul>{review.changedFields.map((field) => <li key={field}><strong>{field}</strong><pre>{JSON.stringify(review.config[field as keyof TaskbarConfig], null, 2)}</pre></li>)}</ul>
        <div className="settings-inline"><button className="studio-button" disabled={!review.changedFields.length} onClick={async () => {
          const old = config;
          if (await replaceConfigDocument({ schemaVersion: 1, config: review.config }, review.expectedRevision)) { setPrevious({ config: old, revision: review.expectedRevision + 1 }); setReview(null); setStatus(t("configSaved")); }
        }}>{review.kind === "reset" ? t("resetConfirm") : t("importConfirm")}</button><button className="studio-button" onClick={() => { reviewRequest.current++; setReview(null); }}>{t("cancel")}</button></div>
      </section>}
      {previous && <button className="studio-button" disabled={revision !== previous.revision} onClick={async () => { if (await replaceConfigDocument({ schemaVersion: 1, config: previous.config }, previous.revision)) setPrevious(null); }}>{t("undo")}</button>}
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
    {error && <p role="alert"><ErrorText error={error} /></p>}{status && <p role="status">{status}</p>}
  </>;
}
