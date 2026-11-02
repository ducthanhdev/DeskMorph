import { useI18n } from "./i18n/useI18n";
import React from "react";
import { Plus, Pin, PinOff, X, Flame } from "lucide-react";
import { DockContextMenuState } from "./types";

interface DockContextMenuProps {
  menu: DockContextMenuState;
  bottomOffset: number;
  onSpawnApp: (cmd?: string) => void;
  onTogglePin: (appId?: string, appName?: string, command?: string) => void;
  onCloseWindow: (windowId?: string) => void;
  onForceKill: (windowId?: string) => void;
}

export const DockContextMenu: React.FC<DockContextMenuProps> = ({
  menu,
  bottomOffset,
  onSpawnApp,
  onTogglePin,
  onCloseWindow,
  onForceKill,
}) => {
  const { t } = useI18n();
  // Clamping X so the menu always stays completely within the taskbar window
  const clampedX = Math.max(120, Math.min(menu.anchorX, 1100 - 120));

  return (
    <div
      className="dock-context-menu"
      style={{
        bottom: `${bottomOffset}px`,
        left: `${clampedX}px`,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header with App Title & Status */}
      <div className="dock-menu-header">
        <span className="dock-menu-title">{menu.appName}</span>
        <span className="dock-menu-subtitle">
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: menu.isRunning ? "var(--status-positive, #2e9e62)" : "#64748b",
              display: "inline-block",
            }}
          />
          {menu.isRunning ? t("running") : t("notRunning")}
        </span>
      </div>

      <div className="dock-menu-divider" />

      {/* Action 1: New Window / Spawn App */}
      <button
        className="dock-menu-item"
        onClick={() => onSpawnApp(menu.command)}
      >
        <span className="dock-menu-item-icon" style={{ color: "#38bdf8" }}>
          <Plus size={15} />
        </span>
        <span>{t("newWindow")}</span>
      </button>

      {/* Action 2: Toggle Pin to Dock */}
      <button
        className="dock-menu-item"
        onClick={() => onTogglePin(menu.appId, menu.appName, menu.command)}
      >
        <span className="dock-menu-item-icon" style={{ color: menu.isPinned ? "var(--status-warning, #e5a93b)" : "#94a3b8" }}>
          {menu.isPinned ? <PinOff size={15} /> : <Pin size={15} />}
        </span>
        <span>{menu.isPinned ? t("unpin") : t("pin")}</span>
      </button>

      {/* Actions when app is running */}
      {menu.isRunning && (
        <>
          <div className="dock-menu-divider" />

          {/* Action 3: Safe Close Window */}
          <button
            className="dock-menu-item"
            onClick={() => onCloseWindow(menu.windowId)}
          >
            <span className="dock-menu-item-icon" style={{ color: "#94a3b8" }}>
              <X size={15} />
            </span>
            <span>{t("close")}</span>
          </button>

          {/* Action 4: Force Kill Process */}
          <button
            className="dock-menu-item dock-menu-item-danger"
            onClick={() => onForceKill(menu.windowId)}
          >
            <span className="dock-menu-item-icon" style={{ color: "var(--status-negative, #e5484d)" }}>
              <Flame size={15} />
            </span>
            <span>{t("forceQuit")}</span>
          </button>
        </>
      )}
    </div>
  );
};
