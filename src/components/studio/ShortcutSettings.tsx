import { useEffect, useState } from "react";
import { invoke } from "../../ipc";
import { useConfig } from "../../config/store";
import { usePlatform } from "../../hooks/usePlatform";
import { usePolling } from "../../hooks/usePolling";
import { useI18n } from "../../i18n/useI18n";
import { Card } from "./Controls";
type Status = { requested: string | null; registered: boolean; pending: boolean; error: string | null };
export function ShortcutSettings() {
  const { config, updateConfig } = useConfig();
  const { platform } = usePlatform();
  const { t } = useI18n();
  const [draft, setDraft] = useState(config.launcherShortcut || "Ctrl+Super+K");
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => { if (config.launcherShortcut) setDraft(config.launcherShortcut); }, [config.launcherShortcut]);
  usePolling(async (signal) => {
    try { const value = await invoke<Status>("get_launcher_shortcut_status"); if (!signal.aborted) { setStatus(value); setFailed(false); } }
    catch { if (!signal.aborted) setFailed(true); }
  }, 700);
  const save = async (value: string | null) => {
    if (busy) return;
    setBusy(true);
    try { await updateConfig({ launcherShortcut: value }); }
    finally { setBusy(false); }
  };
  const error = status?.error === "shortcut_conflict" ? t("shortcutConflict") : status?.error === "shortcut_unsupported" ? t("shortcutUnsupported") : t("shortcutFailed");
  return <Card title={t("shortcutTitle")}>
    <p className="settings-help">{t("shortcutHelp")}</p>
    <form onSubmit={(event) => { event.preventDefault(); void save(draft.trim()); }}>
      <label className="settings-field">{t("shortcutLabel")}<input aria-label={t("shortcutLabel")} value={draft} maxLength={64} disabled={busy || platform?.session !== "x11"} onChange={(event) => setDraft(event.target.value)} /></label>
      <div className="settings-inline"><button className="studio-button" type="submit" disabled={busy || !draft.trim() || platform?.session !== "x11"}>{t("shortcutSave")}</button>
        <button className="studio-button" type="button" disabled={busy || config.launcherShortcut === null} onClick={() => void save(null)}>{t("shortcutDisable")}</button></div>
    </form>
    {platform && platform.session !== "x11" && <p role="status">{t("shortcutUnsupported")}</p>}
    <p role="status">{config.launcherShortcut === null ? t("shortcutOff") : !config.enabled ? t("shortcutPaused") : !status || status.pending || status.requested !== config.launcherShortcut ? t("shortcutPending") : status.registered ? `${t("shortcutActive")}: ${status.requested}` : t("shortcutOff")}</p>
    {(failed || (status?.error && config.launcherShortcut !== null)) && <div role="alert"><p>{error}</p><button className="studio-button" type="button" onClick={() => { void invoke("retry_launcher_shortcut").catch(() => setFailed(true)); }}>{t("retry")}</button></div>}
  </Card>;
}
