import { useEffect, useState } from "react";
import { invoke } from "../../ipc";
import { Shuffle, Sparkles, Volume2 } from "lucide-react";
import { useConfig } from "../../config/store";
import { useInstalledApps } from "../../hooks/useInstalledApps";
import { usePlatform } from "../../hooks/usePlatform";
import { usePolling } from "../../hooks/usePolling";
import { desktopIdForPin, desktopIsMissing, installedForClass, installedForPin } from "../../appSearch";
import { dockMetrics, dockSurface, dockAppStyle, magnificationScale } from "../../dockAppearance";
import { getPinnedVisual, getAppVisual } from "../../dockVisuals";
import { groupWindows } from "../../windowGroups";
import { useI18n } from "../../i18n/useI18n";
import type { OpenWindow, SystemStats } from "../../types";
import { DEFAULT_PINNED_APPS } from "../../types";
import { SystemWidgets } from "../SystemWidgets";
import { DockAppTile, DockStats } from "../DockParts";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import { useClock } from "../../hooks/useClock";
import { formatClock } from "../../dateTime";
export function DockPreview() {
  const { config, ready } = useConfig();
  const { apps, loading, error } = useInstalledApps();
  const { platform } = usePlatform();
  const { t, locale, count, pinName } = useI18n();
  const { iconSize, glyphSize, maxScale } = dockMetrics(config);
  const launcherSize = Math.max(28, iconSize - 2);
  const now = useClock(config.showClock);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [windowError, setWindowError] = useState(false);
  const [windows, setWindows] = useState<OpenWindow[]>([]);
  const reducedMotion = useReducedMotion(config.reduceMotion);
  const [sample, setSample] = useState(false);
  useEffect(() => { if (!sample) return; const timer = setTimeout(() => setSample(false), 1700); return () => clearTimeout(timer); }, [sample]);
  const [hover, setHover] = useState<number | null>(null);
  usePolling(async (signal) => {
    const snapshot = await invoke<SystemStats>("get_system_stats");
    if (!signal.aborted) setStats(snapshot);
  }, 2000, ready && config.showStats);
  usePolling(async (signal) => {
    try {
      const snapshot = await invoke<OpenWindow[]>("get_open_windows");
      if (!signal.aborted) { setWindows(snapshot); setWindowError(false); }
    } catch { if (!signal.aborted) { setWindows([]); setWindowError(true); } }
  }, 1500, ready && config.showApps && Boolean(platform?.windows.enumerate));
  const { pinnedItems, unpinnedGroups } = groupWindows(platform?.windows.enumerate ? windows : [], (config.pinnedApps || DEFAULT_PINNED_APPS).filter(pin => pin.enabled !== false));
  const item = (id: string, name: string, visual: ReturnType<typeof getPinnedVisual>, iconPath: string | null | undefined, rows: OpenWindow[], pinned: boolean, missing = false) => {
    const running = rows.length > 0, active = rows.some(row => row.is_active);
    return <span key={id} role="img" aria-label={`${name} • ${platform?.windows.enumerate && !windowError ? count("window", rows.length) : t("windowStatusUnavailable")}${missing ? ` • ${t("unavailable")}` : ""}`}
      className={`running-app-icon-btn ${active ? "app-active" : running ? "" : "app-idle"} ${sample && id === pinnedItems[0]?.pinned.id ? "app-launching" : ""}`}
      ref={element => {
        // A fixed hit slot keeps decorative magnification from changing layout.
        if (!element) return;
        const rect = element.getBoundingClientRect();
        element.style.setProperty("--magnify-scale", String(hover !== null && config.magnification !== false && !reducedMotion ? magnificationScale(Math.abs(rect.left + rect.width / 2 - hover), maxScale) : 1));
      }} style={dockAppStyle(config, visual, pinned, running, active)}>
      <DockAppTile visual={visual} iconPath={iconPath} glyphSize={glyphSize} running={running} active={active} count={rows.length} missing={missing} bouncing={sample && id === pinnedItems[0]?.pinned.id && config.bouncingLaunch !== false && !reducedMotion} shadow={sample && id === pinnedItems[0]?.pinned.id && config.dynamicShadow !== false && !reducedMotion} />
    </span>;
  };
  return <section className="dock-preview" aria-label={t("preview")}><h2>{t("preview")}</h2><p className="settings-help">{t("previewHelp")}</p>
    {!config.enabled && <p role="status">{t("previewDockOff")}</p>}
    {windowError && <p role="status">{t("windowStatusUnavailable")}</p>}
    <div className={`dock-preview-stage ${config.position === "top" ? "preview-top" : ""}`}>
      <div className={`taskbar-container preview-surface ${reducedMotion ? "reduce-motion" : ""}`} style={dockSurface(config)}>
        <div className="dock-left"><span className="dock-launcher-btn" role="img" aria-label={t("searchApps")} style={{ width: launcherSize, height: launcherSize, background: config.accentColor }}><Sparkles className="dock-launcher-glyph" size={Math.round(launcherSize * .48)} color="#0c1017" /></span><div className="dock-divider" /></div>
        {config.showApps && <div className="dock-apps-viewport"><div className={`dock-apps ${hover !== null ? "is-magnifying" : ""}`} onMouseMove={event => setHover(event.clientX)} onMouseLeave={() => setHover(null)}>
          <div className="dock-pinned-group">{pinnedItems.map(({ pinned, windows }) => {
            const installed = installedForPin(pinned, apps);
            return item(pinned.id, pinName(pinned), getPinnedVisual(pinned), installed?.iconPath, windows, true, desktopIsMissing(desktopIdForPin(pinned), installed, { loading, error }));
          })}</div>
          {unpinnedGroups.length > 0 && pinnedItems.length > 0 && <div className="dock-apps-separator" aria-hidden="true" />}
          {unpinnedGroups.length > 0 && <div className="dock-unpinned-group">{unpinnedGroups.map(rows => item(rows[0].class_name, rows[0].class_name, getAppVisual(rows[0].class_name), installedForClass(rows[0].class_name, apps)?.iconPath, rows, false))}</div>}
        </div></div>}
        <div className="dock-right">
          {config.showStats && <><div className="dock-divider" /><DockStats stats={stats} accentColor={config.accentColor} /></>}
          {config.showShuffle && <span className="dock-action-btn" role="img" aria-label={t("shuffle")}><Shuffle size={14} /></span>}
          {config.showAudio && <span className="dock-action-btn" role="img" aria-label={t("audio")}><Volume2 size={16} /></span>}
          <SystemWidgets preview />
          {config.showClock && <div className="taskbar-section clock-section interactive-widget"><time className="clock-time" dateTime={now.toISOString()}>{formatClock(now, locale, config)}</time><time className="clock-date" dateTime={now.toISOString()}>{new Intl.DateTimeFormat(locale, { weekday: "short", month: "short", day: "numeric" }).format(now)}</time></div>}
        </div>
      </div>
    </div>
    <button className="studio-button preview-animation" disabled={sample || reducedMotion || !config.showApps || !pinnedItems.length || (config.bouncingLaunch === false && config.dynamicShadow === false)} onClick={() => setSample(true)}>{t("previewAnimation")}</button>
  </section>;
}
