import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen, emit } from "@tauri-apps/api/event";
import { Plus, Pin, PinOff, X, Flame } from "lucide-react";
import { DockContextMenuState, PinnedApp, TaskbarConfig } from "./types";

const DEFAULT_PINNED_APPS: PinnedApp[] = [
  {
    id: "chrome",
    name: "Google Chrome",
    command: "google-chrome",
    matchClasses: ["google-chrome", "chromium"],
    iconType: "chrome",
    color: "#38bdf8",
    enabled: true,
  },
  {
    id: "code",
    name: "VS Code / IDE",
    command: "code",
    matchClasses: ["code", "vscodium", "antigravity"],
    iconType: "code",
    color: "#a855f7",
    enabled: true,
  },
  {
    id: "terminal",
    name: "Terminal",
    command: "gnome-terminal",
    matchClasses: ["terminal", "alacritty", "kitty", "ptyxis"],
    iconType: "terminal",
    color: "#34d399",
    enabled: true,
  },
  {
    id: "nautilus",
    name: "Files",
    command: "nautilus",
    matchClasses: ["nautilus", "files"],
    iconType: "files",
    color: "#fbbf24",
    enabled: true,
  },
];

export const DockContextMenuStandalone: React.FC = () => {
  const [menu, setMenu] = useState<DockContextMenuState | null>(null);

  useEffect(() => {
    const unlisten = listen<DockContextMenuState>("deskmorph:context-menu-data", (event) => {
      if (event.payload) {
        setMenu(event.payload);
      }
    });

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        invoke("hide_dock_context_menu").catch(console.error);
      }
    };

    const handleBlur = () => {
      invoke("hide_dock_context_menu").catch(console.error);
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("blur", handleBlur);

    return () => {
      unlisten.then((fn) => fn());
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("blur", handleBlur);
    };
  }, []);

  const closeMenu = () => {
    invoke("hide_dock_context_menu").catch(console.error);
  };

  const handleSpawnApp = async (cmd?: string) => {
    if (cmd) {
      try {
        await invoke("spawn_app", { execCmd: cmd });
      } catch (err) {
        console.error("Failed to spawn app", err);
      }
    }
    closeMenu();
  };

  const handleTogglePin = (appId?: string, appName?: string, command?: string) => {
    let savedConfig: TaskbarConfig | null = null;
    try {
      const saved = localStorage.getItem("deskmorph_config");
      if (saved) savedConfig = JSON.parse(saved);
    } catch (e) {
      console.error(e);
    }

    const currentPinned = savedConfig?.pinnedApps || DEFAULT_PINNED_APPS;
    let nextPinned: PinnedApp[];

    if (appId && currentPinned.some((p) => p.id === appId)) {
      nextPinned = currentPinned.filter((p) => p.id !== appId);
    } else {
      const newId = appId || (command ? command.toLowerCase() : "custom-app");
      const newPin: PinnedApp = {
        id: newId,
        name: appName || newId,
        command: command || newId,
        matchClasses: [newId],
        iconType: "custom",
        color: "#38bdf8",
        enabled: true,
      };
      nextPinned = [...currentPinned, newPin];
    }

    const updatedConfig = {
      ...(savedConfig || {
        enabled: true,
        position: "bottom" as const,
        opacity: 0.85,
        borderRadius: 16,
        showClock: true,
        showStats: true,
        showShuffle: true,
        showApps: true,
        accentColor: "#48b9c7",
      }),
      pinnedApps: nextPinned,
    };

    localStorage.setItem("deskmorph_config", JSON.stringify(updatedConfig));
    emit("deskmorph:config-update", updatedConfig).catch(console.error);
    closeMenu();
  };

  const handleCloseWindow = async (windowId?: string) => {
    if (windowId) {
      try {
        await invoke("close_window", { xid: windowId });
      } catch (err) {
        console.error("Failed to close window", err);
      }
    }
    closeMenu();
  };

  const handleForceKill = async (windowId?: string) => {
    if (windowId) {
      try {
        await invoke("force_kill_window", { xid: windowId });
      } catch (err) {
        console.error("Failed to force kill window", err);
      }
    }
    closeMenu();
  };

  if (!menu) {
    return <div className="standalone-context-menu-empty" />;
  }

  return (
    <div
      className="standalone-context-menu-wrapper"
      onClick={closeMenu}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div
        className="dock-context-menu standalone"
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
          onClick={() => handleSpawnApp(menu.command)}
        >
          <span className="dock-menu-item-icon" style={{ color: "#38bdf8" }}>
            <Plus size={15} />
          </span>
          <span>Mở cửa sổ mới</span>
        </button>

        {/* Action 2: Toggle Pin to Dock */}
        <button
          className="dock-menu-item"
          onClick={() => handleTogglePin(menu.appId, menu.appName, menu.command)}
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
              onClick={() => handleCloseWindow(menu.windowId)}
            >
              <span className="dock-menu-item-icon" style={{ color: "#94a3b8" }}>
                <X size={15} />
              </span>
              <span>Đóng cửa sổ</span>
            </button>

            {/* Action 4: Force Kill Process */}
            <button
              className="dock-menu-item dock-menu-item-danger"
              onClick={() => handleForceKill(menu.windowId)}
            >
              <span className="dock-menu-item-icon" style={{ color: "#ef4444" }}>
                <Flame size={15} />
              </span>
              <span>Buộc dừng (Force Kill)</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
};
