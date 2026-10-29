import { ErrorText } from "../ErrorText";
import { useRemovalFocus } from "../../hooks/useRemovalFocus";
import { useState } from "react";
import { invoke } from "../../ipc";
import { useConfig, errorMessage } from "../../config/store";
import { useInstalledApps } from "../../hooks/useInstalledApps";
import { desktopIdForPin, desktopIsMissing, installedForPin, pinFromApp, searchApps } from "../../appSearch";
import { useI18n } from "../../i18n/useI18n";
import { AppIcon } from "../AppIcon";
import type { OpenWindow, PinnedApp } from "../../types";
import { Card } from "./Controls";
import { usePlatform, type PlatformInfo } from "../../hooks/usePlatform";
import { capabilityReason } from "../../capabilities";
function ClassMapping({ pin, platform, platformError }: { pin: PinnedApp; platform: PlatformInfo | null; platformError: string | null }) {
  const { mutatePin } = useConfig();
  const { t, pinName } = useI18n();
  const [draft, setDraft] = useState(pin.matchClasses.join("\n"));
  const [expanded, setExpanded] = useState(false);
  const [classes, setClasses] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <details className="class-mapping" onToggle={(event) => setExpanded(event.currentTarget.open)}><summary role="button" aria-expanded={expanded}>{t("classMapping")} {pinName(pin)}</summary>
    <p>{t("classMappingHelp")}</p>
    <label>{t("classMapping")}<textarea aria-label={`${t("classMapping")} ${pinName(pin)}`} rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} /></label>
    <button disabled={busy || !platform?.windows.enumerate} onClick={async () => {
      if (!platform?.windows.enumerate) return;
      setBusy(true);
      try {
        const windows = await invoke<OpenWindow[]>("get_open_windows");
        setClasses([...new Set(windows.map((w) => w.class_name).filter(Boolean))].sort()); setError("");
      } catch (e) { setError(errorMessage(e)); }
      finally { setBusy(false); }
    }}>{t("readWindowClasses")}</button>
    {!platform?.windows.enumerate && <p role="status">{capabilityReason(platform, "windowEnumeration", t, platformError)}</p>}
    {classes.length > 0 && <select aria-label={`${t("runningClasses")} ${pinName(pin)}`} value="" onChange={(e) => {
      if (e.target.value) setDraft((value) => [...new Set([...value.split("\n").filter(Boolean), e.target.value])].join("\n"));
    }}><option value="">{t("runningClasses")}</option>{classes.map((cls) => <option key={cls} value={cls}>{cls}</option>)}</select>}
    <button disabled={busy} onClick={async () => {
      setBusy(true);
      try { await mutatePin("setClasses", pin.id, { matchClasses: draft.split("\n").map((s) => s.trim()).filter(Boolean) }); }
      finally { setBusy(false); }
    }}>{t("save")}</button>
    <button disabled={busy} onClick={() => setDraft(pin.matchClasses.join("\n"))}>{t("cancel")}</button>
    {error && <p role="alert"><ErrorText error={error} /></p>}
  </details>;
}
export function AppsSettings() {
  const { platform, error: platformError } = usePlatform();
  const { config, mutatePin, error: configError } = useConfig();
  const { apps, loading, error, refresh } = useInstalledApps();
  const { t, pinName } = useI18n();
  const removalFocus = useRemovalFocus();
  const [query, setQuery] = useState("");
  const [operationError, setOperationError] = useState("");
  return <div ref={removalFocus.root} onFocusCapture={removalFocus.onFocusCapture}>
    <Card title={t("pinnedApps")}>
      {configError && <p role="alert"><ErrorText error={configError} /></p>}
      {config.pinnedApps?.map((pin, index) => {
        const app = installedForPin(pin, apps);
        return <div className="studio-app-row" key={pin.id}><AppIcon path={app?.iconPath} size={28} /><span><strong>{pinName(pin)}</strong>{desktopIsMissing(desktopIdForPin(pin), app, { loading, error }) && <small>{t("unavailable")}</small>}</span>
          <input type="checkbox" aria-label={`${t("pin")} ${pinName(pin)}`} checked={pin.enabled !== false} onChange={() => void mutatePin("toggleEnabled", pin.id)} />
          <button aria-label={`${t("moveLeft")} ${pinName(pin)}`} disabled={index === 0} onClick={() => void mutatePin("move", pin.id, undefined, index - 1)}>←</button>
          <button aria-label={`${t("moveRight")} ${pinName(pin)}`} disabled={index === config.pinnedApps!.length - 1} onClick={() => void mutatePin("move", pin.id, undefined, index + 1)}>→</button>
          <button data-remove-focus aria-label={`${t("unpin")} ${pinName(pin)}`} onClick={() => void mutatePin("remove", pin.id)}>{t("unpin")}</button>
          <ClassMapping key={JSON.stringify(pin.matchClasses)} pin={pin} platform={platform} platformError={platformError} />
        </div>;
      })}
    </Card>
    <Card title={t("appsTab")}>
      <div className="settings-inline"><input ref={removalFocus.fallback} aria-label={t("searchApps")} placeholder={t("searchApps")} value={query} onChange={(e) => setQuery(e.target.value)} /><button className="studio-button" onClick={refresh}>{t("refresh")}</button></div>
      {(error || operationError) && <p role="alert"><ErrorText error={error || operationError} /></p>}{loading && <p role="status">{t("scanningApps")}</p>}
      {!loading && !error && !searchApps(apps, query).length && <p role="status">{t("noApps")}</p>}
      <div className="studio-app-list">{searchApps(apps, query).slice(0, 60).map((app) => {
        const existing = config.pinnedApps?.find((pin) => installedForPin(pin, apps)?.id === app.id);
        const pinned = existing && existing.enabled !== false;
        return <div className="studio-app-row" key={app.id}><AppIcon path={app.iconPath} size={28} /><span><strong>{app.name}</strong><small>{app.genericName || app.id}</small></span>
          <button aria-label={`${t("open")} ${app.name}`} onClick={async () => { try { await invoke("launch_installed_app", { id: app.id, action: null }); setOperationError(""); } catch (e) { setOperationError(errorMessage(e)); } }}>{t("open")}</button>
          <button aria-label={`${pinned ? t("unpin") : t("pin")} ${app.name}`} onClick={() => void mutatePin(pinned ? "remove" : "add", existing?.id || app.id, existing || pinFromApp(app))}>{pinned ? t("unpin") : t("pin")}</button>
        </div>;
      })}</div>
    </Card>
  </div>;
}
