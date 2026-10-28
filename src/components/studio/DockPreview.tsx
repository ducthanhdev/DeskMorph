import { useState } from "react";
import { invoke } from "../../ipc";
import { Cpu, HardDrive, Shuffle, Sparkles, Volume2 } from "lucide-react";
import { useConfig } from "../../config/store";
import { useInstalledApps } from "../../hooks/useInstalledApps";
import { usePolling } from "../../hooks/usePolling";
import { installedForPin } from "../../appSearch";
import { dockMetrics, dockSurface } from "../../dockAppearance";
import { useI18n } from "../../i18n/useI18n";
import type { SystemStats } from "../../types";
import { SystemWidgets } from "../SystemWidgets";
import { AppIcon } from "../AppIcon";
export function DockPreview() {
  const { config } = useConfig();
  const { apps } = useInstalledApps();
  const { t, locale } = useI18n();
  const { iconSize } = dockMetrics(config);
  const [now, setNow] = useState(new Date());
  const [stats, setStats] = useState<SystemStats | null>(null);
  usePolling(async () => setNow(new Date()), 1000, config.showClock);
  usePolling(async (signal) => {
    const snapshot = await invoke<SystemStats>("get_system_stats");
    if (!signal.aborted) setStats(snapshot);
  }, 2000, config.showStats);
  return <section className="dock-preview" aria-label={t("preview")}><h2>{t("preview")}</h2>
    <div className={`dock-preview-stage ${config.position === "top" ? "preview-top" : ""}`}>
      <div className="taskbar-container preview-surface" style={dockSurface(config)}>
        <Sparkles size={iconSize * .7} color={config.accentColor} />
        {config.showApps && <div className="dock-pinned-group">{config.pinnedApps?.filter((pin) => pin.enabled !== false).map((pin) => <span className="preview-app" key={pin.id} title={pin.name} style={{ width: iconSize, height: iconSize }}><AppIcon path={installedForPin(pin, apps)?.iconPath} size={Math.round(iconSize * .68)} /></span>)}</div>}
        <div className="dock-right">
          {config.showStats && <div className="taskbar-section stats-section"><span className="stat-pill"><Cpu size={14} /><span className="stat-text">{stats ? `${stats.cpu_usage.toFixed(0)}%` : "…"}</span></span><span className="stat-pill"><HardDrive size={14} /><span className="stat-text">{stats ? `${stats.ram_percent.toFixed(0)}%` : "…"}</span></span></div>}
          {config.showShuffle && <Shuffle size={14} />}
          {config.showAudio && <Volume2 size={16} />}
          <SystemWidgets preview />
          {config.showClock && <div className="clock-section"><time className="clock-time">{new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", second: config.clockSeconds ? "2-digit" : undefined, hour12: !config.clock24 }).format(now)}</time><span className="clock-date">{new Intl.DateTimeFormat(locale, { weekday: "short", month: "short", day: "numeric" }).format(now)}</span></div>}
        </div>
      </div>
    </div>
  </section>;
}
