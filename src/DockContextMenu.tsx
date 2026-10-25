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
              background: menu.isRunning ? "#10b981" : "#64748b",
              display: "inline-block",
            }}
          />
          {menu.isRunning ? "Đang chạy" : "Chưa khởi chạy"}
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
        <span>Mở cửa sổ mới</span>
      </button>

      {/* Action 2: Toggle Pin to Dock */}
      <button
        className="dock-menu-item"
        onClick={() => onTogglePin(menu.appId, menu.appName, menu.command)}
      >
        <span className="dock-menu-item-icon" style={{ color: menu.isPinned ? "#f59e0b" : "#94a3b8" }}>
          {menu.isPinned ? <PinOff size={15} /> : <Pin size={15} />}
        </span>
        <span>{menu.isPinned ? "Bỏ ghim khỏi Dock" : "Ghim vào Dock"}</span>
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
            <span>Đóng cửa sổ</span>
          </button>

          {/* Action 4: Force Kill Process */}
          <button
            className="dock-menu-item dock-menu-item-danger"
            onClick={() => onForceKill(menu.windowId)}
          >
            <span className="dock-menu-item-icon" style={{ color: "#ef4444" }}>
              <Flame size={15} />
            </span>
            <span>Buộc dừng (Force Kill)</span>
          </button>
        </>
      )}
    </div>
  );
};
