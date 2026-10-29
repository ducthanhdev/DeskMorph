import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "../ipc";
import { Pin, PinOff, RefreshCw, Search, Settings } from "lucide-react";
import { useInstalledApps } from "../hooks/useInstalledApps";
import { useConfig, errorMessage } from "../config/store";
import { installedForPin, pinFromApp, searchApps } from "../appSearch";
import type { InstalledApp } from "../types";
import { useI18n } from "../i18n/useI18n";
import { useAsyncLifetime } from "../hooks/useAsyncLifetime";
import { completePopupAction } from "../hooks/asyncLifetime";
import { usePopupActive } from "../hooks/usePopupActive";
import { AppIcon } from "./AppIcon";

export function AppLauncher({ generation }: { generation?: number }) {
  const lifetime = useAsyncLifetime();
  const active = usePopupActive(generation);
  const close = () => generation === undefined ? Promise.resolve(false) : invoke<boolean>("hide_dock_context_menu", { generation });
  const { t, count } = useI18n();
  const { apps, loading, error, refresh } = useInstalledApps();
  const { config, mutatePin, error: configError } = useConfig();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [launching, setLaunching] = useState<string | null>(null);
  const [failedApp, setFailedApp] = useState<InstalledApp | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const rows = useRef(new Map<string, HTMLButtonElement>());
  const launchLock = useRef(false);
  const allMatches = useMemo(() => searchApps(apps, query), [apps, query]);
  const results = allMatches.slice(0, 60);
  const current = Math.min(selected, Math.max(0, results.length - 1));
  useEffect(() => { input.current?.focus(); }, []);
  useEffect(() => { if (results[current]) rows.current.get(results[current].id)?.scrollIntoView({ block: "nearest" }); }, [current, query, apps]);
  const launch = async (app?: InstalledApp) => {
    if (!app || launchLock.current || !active) return;
    const signal = lifetime.capture();
    launchLock.current = true; setLaunching(app.id); setLaunchError(null); setFailedApp(null);
    try {
      await completePopupAction(() => invoke("launch_installed_app", { id: app.id, action: null }), close, signal);
    } catch (e) { if (!signal.aborted) { setLaunchError(errorMessage(e)); setFailedApp(app); } }
    finally { launchLock.current = false; if (!signal.aborted) setLaunching(null); }
  };
  return <section className="app-launcher" aria-label={t("searchApps")} onKeyDown={(e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault(); setSelected((i) => results.length ? (i + (e.key === "ArrowDown" ? 1 : -1) + results.length) % results.length : 0);
    } else if (e.key === "Home" && e.ctrlKey) { e.preventDefault(); setSelected(0); }
    else if (e.key === "End" && e.ctrlKey) { e.preventDefault(); setSelected(Math.max(0, results.length - 1)); }
  }}>
    <header><Search size={18} /><input ref={input} placeholder={t("searchApps")} aria-label={t("searchApps")} value={query}
      onChange={(e) => { setQuery(e.target.value); setSelected(0); }}
      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void launch(results[current]); } }} />
      <button onClick={refresh} aria-label={t("refresh")} title={t("refresh")}><RefreshCw size={16} /></button></header>
    {(error || configError || launchError) && <p role="alert">{error || configError || launchError} {launchError && failedApp && <button disabled={!!launching} onClick={() => void launch(failedApp)}>{t("retry")}</button>}</p>}
    {loading && <p role="status">{t("scanningApps")}</p>}
    {!loading && !error && !results.length && <p role="status">{t("noApps")}</p>}
    {launching && <p role="status" aria-live="polite">{t("launching")} {apps.find((app) => app.id === launching)?.name}</p>}
    <div className="app-launcher-results" aria-label={t("appsTab")}>
      {results.map((app, index) => {
        const existing = config.pinnedApps?.find((pin) => installedForPin(pin, apps)?.id === app.id);
        const pinned = existing?.enabled !== false && Boolean(existing);
        return <div className={`app-launcher-row ${index === current ? "is-selected" : ""}`} key={app.id}>
          <button className="app-launcher-open" ref={(el) => { if (el) rows.current.set(app.id, el); else rows.current.delete(app.id); }}
            aria-current={index === current ? "true" : undefined} onFocus={() => setSelected(index)} disabled={launching === app.id} onClick={() => void launch(app)} aria-label={`${t("open")} ${app.name}`}>
            <AppIcon path={app.iconPath} size={32} /><span><strong>{app.name}</strong><small>{launching === app.id ? t("launching") : app.genericName || app.id}</small></span>
          </button>
          <button className="app-launcher-pin" aria-label={`${pinned ? t("unpin") : t("pin")} ${app.name}`} aria-pressed={pinned}
            onClick={() => void mutatePin(pinned ? "remove" : "add", existing?.id || app.id, existing || pinFromApp(app))}>
            {pinned ? <PinOff size={16} /> : <Pin size={16} />}
          </button>
        </div>;
      })}
    </div>
    <footer><span>{count("app", allMatches.length)}{allMatches.length > 60 ? ` • ${t("firstResults")}` : ""}</span>
      <button onClick={async () => {
        if (!active) return;
        const signal = lifetime.capture();
        try { if (await close() && !signal.aborted) await invoke("show_studio"); }
        catch (e) { if (!signal.aborted) setLaunchError(errorMessage(e)); }
      }}><Settings size={14} /> Studio</button></footer>
  </section>;
}
