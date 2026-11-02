import { Cpu, HardDrive } from "lucide-react";
import { AppIcon } from "./AppIcon";
import type { getPinnedVisual } from "../dockVisuals";
import type { SystemStats } from "../types";

export function DockAppTile({ visual, iconPath, glyphSize, running = false, active = false, count = 0, missing = false, bouncing = false, shadow = false }: {
  visual: ReturnType<typeof getPinnedVisual>; iconPath?: string | null; glyphSize: number;
  running?: boolean; active?: boolean; count?: number; missing?: boolean; bouncing?: boolean; shadow?: boolean;
}) {
  return <span className="app-icon-tile">
    <span className="app-icon-visual"><span className={`app-icon-glyph ${bouncing ? "glyph-bouncing" : ""}`}>
      {iconPath ? <AppIcon path={iconPath} size={glyphSize} /> : visual.icon}
    </span></span>
    {missing && <span className="app-unavailable-mark" aria-hidden="true">!</span>}
    {shadow && <span className="dock-launch-shadow" style={{ ["--shadow-color" as string]: visual.color }} />}
    {count > 1 && <span className="dock-window-count" aria-hidden="true">{count > 9 ? "9+" : count}</span>}
    {running && <span className={`running-dot ${active ? "dot-active" : "dot-inactive"}`} style={{
      background: active ? visual.color : "rgba(255,255,255,.55)", boxShadow: active ? `0 0 8px ${visual.color}` : "none",
    }} />}
  </span>;
}

export function DockStats({ stats, accentColor }: { stats: SystemStats | null; accentColor: string }) {
  if (!stats) return null;
  const ramDescription = `RAM: ${(stats.ram_used_mb / 1024).toFixed(1)} GiB / ${(stats.ram_total_mb / 1024).toFixed(1)} GiB (${stats.ram_percent}%)`;
  return <div className="taskbar-section stats-section">
    <div className="stat-pill" role="img" aria-label={`CPU: ${stats.cpu_usage}%`} data-dock-tooltip={`CPU: ${stats.cpu_usage}%`}>
      <Cpu size={14} className="stat-icon cpu-icon" /><div className="stat-bar-mini"><div className="stat-bar-fill" style={{ width: `${Math.min(stats.cpu_usage, 100)}%`, background: stats.cpu_usage > 75 ? "var(--status-negative, #e5484d)" : accentColor }} /></div><span className="stat-text">{stats.cpu_usage.toFixed(0)}%</span>
    </div>
    <div className="stat-pill" role="img" aria-label={ramDescription} data-dock-tooltip={ramDescription}>
      <HardDrive size={14} className="stat-icon ram-icon" /><div className="stat-bar-mini"><div className="stat-bar-fill" style={{ width: `${Math.min(stats.ram_percent, 100)}%`, background: stats.ram_percent > 85 ? "var(--status-negative, #e5484d)" : accentColor }} /></div><span className="stat-text">{stats.ram_percent.toFixed(0)}%</span>
    </div>
  </div>;
}
