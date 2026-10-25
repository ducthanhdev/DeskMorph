import React, { useEffect, useState, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  SystemStats,
  TaskbarConfig,
  WallpaperInfo,
  OpenWindow,
  PinnedApp,
  DEFAULT_PINNED_APPS,
} from "./types";
import {
  Cpu,
  HardDrive,
  Shuffle,
  Terminal,
  Folder,
  Globe,
  Sparkles,
  AppWindow,
  Code2,
  Settings,
} from "lucide-react";

export const Taskbar: React.FC = () => {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [openWindows, setOpenWindows] = useState<OpenWindow[]>([]);
  const [time, setTime] = useState("");
  const [date, setDate] = useState("");
  const [isHovered, setIsHovered] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(true);
  const [launchingAppIds, setLaunchingAppIds] = useState<Set<string>>(new Set());
  const launchTimeouts = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Magnification Engine State & Tracking
  const [magnifyScales, setMagnifyScales] = useState<Record<string, number>>({});
  const [isMagnifying, setIsMagnifying] = useState(false);
  const [contextMenuVisible, setContextMenuVisible] = useState(false);
  const iconRefs = useRef<Map<string, HTMLElement>>(new Map());
  const rafId = useRef<number | null>(null);

  const [config, setConfig] = useState<TaskbarConfig>({
    enabled: true,
    position: "bottom",
    height: 52,
    autoHide: false,
    opacity: 0.85,
    borderRadius: 16,
    showClock: true,
    showStats: true,
    showShuffle: true,
    showApps: true,
    accentColor: "#48b9c7",
    pinnedApps: DEFAULT_PINNED_APPS,
    bouncingLaunch: true,
    dynamicShadow: true,
    magnification: true,
    maxMagnificationScale: 1.35,
  });
  const [wallpapers, setWallpapers] = useState<WallpaperInfo[]>([]);

  const keepVisibleBriefly = (durationMs = 7000) => {
    setPreviewVisible(true);
    if (previewTimer.current) {
      clearTimeout(previewTimer.current);
    }
    previewTimer.current = setTimeout(() => {
      setPreviewVisible(false);
    }, durationMs);
  };

  // Load config from localStorage & listen to real-time events
  useEffect(() => {
    const saved = localStorage.getItem("deskmorph_config");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setConfig((prev) => ({
          ...prev,
          ...parsed,
          autoHide: false,
          pinnedApps: parsed.pinnedApps || DEFAULT_PINNED_APPS,
        }));
      } catch (e) {
        console.error(e);
      }
    }
    keepVisibleBriefly(7000);

    const handleStorage = () => {
      const updated = localStorage.getItem("deskmorph_config");
      if (updated) {
        try {
          const parsed = JSON.parse(updated);
          setConfig((prev) => ({
            ...prev,
            ...parsed,
            pinnedApps: parsed.pinnedApps || DEFAULT_PINNED_APPS,
          }));
          keepVisibleBriefly(7000);
        } catch (e) {
          console.error(e);
        }
      }
    };
    window.addEventListener("storage", handleStorage);

    let unlisten: (() => void) | null = null;
    listen<TaskbarConfig>("deskmorph:config-update", (event) => {
      if (event.payload) {
        setConfig((prev) => ({
          ...prev,
          ...event.payload,
          pinnedApps: event.payload.pinnedApps || prev.pinnedApps || DEFAULT_PINNED_APPS,
        }));
        keepVisibleBriefly(8000);
      }
    }).then((fn) => {
      unlisten = fn;
    });

    let unlistenMenu: (() => void) | null = null;
    listen<boolean>("deskmorph:context-menu-visibility", (event) => {
      const isVisible = Boolean(event.payload);
      setContextMenuVisible(isVisible);
      if (isVisible) {
        setIsMagnifying(false);
        setMagnifyScales({});
      }
    }).then((fn) => {
      unlistenMenu = fn;
    });

    return () => {
      window.removeEventListener("storage", handleStorage);
      if (unlisten) unlisten();
      if (unlistenMenu) unlistenMenu();
      if (previewTimer.current) clearTimeout(previewTimer.current);
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, []);

  // Close context menu on any click inside Taskbar window
  useEffect(() => {
    if (!contextMenuVisible) return;
    const handleTaskbarClick = (e: MouseEvent) => {
      if (e.button === 0) {
        invoke("hide_dock_context_menu").catch(console.error);
      }
    };
    window.addEventListener("pointerdown", handleTaskbarClick, true);
    return () => {
      window.removeEventListener("pointerdown", handleTaskbarClick, true);
    };
  }, [contextMenuVisible]);

  // Update clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
      setDate(
        now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch open windows, stats, and wallpapers
  useEffect(() => {
    const fetchWindows = async () => {
      try {
        const wins = await invoke<OpenWindow[]>("get_open_windows");
        setOpenWindows(wins);
      } catch (err) {
        console.error("Failed to fetch open windows", err);
      }
    };

    const fetchStats = async () => {
      try {
        const res = await invoke<SystemStats>("get_system_stats");
        setStats(res);
      } catch (err) {
        console.error("Failed to fetch stats", err);
      }
    };

    fetchWindows();
    fetchStats();

    const winInterval = setInterval(fetchWindows, 1500);
    const statInterval = setInterval(fetchStats, 2000);

    invoke<WallpaperInfo[]>("get_wallpapers")
      .then((res) => setWallpapers(res))
      .catch((err) => console.error(err));

    return () => {
      clearInterval(winInterval);
      clearInterval(statInterval);
    };
  }, []);

  // Auto-cancel bouncing as soon as the app window appears in openWindows
  useEffect(() => {
    if (launchingAppIds.size === 0) return;

    setLaunchingAppIds((prev) => {
      let changed = false;
      const next = new Set(prev);
      const activePinned = (config.pinnedApps || DEFAULT_PINNED_APPS).filter((a) => a.enabled !== false);

      activePinned.forEach((app) => {
        if (next.has(app.id)) {
          const hasOpenWin = openWindows.some((w) =>
            app.matchClasses.some((cls) => w.class_name.toLowerCase().includes(cls.toLowerCase()))
          );
          if (hasOpenWin) {
            next.delete(app.id);
            changed = true;
            if (launchTimeouts.current.has(app.id)) {
              clearTimeout(launchTimeouts.current.get(app.id)!);
              launchTimeouts.current.delete(app.id);
            }
          }
        }
      });

      return changed ? next : prev;
    });
  }, [openWindows, config.pinnedApps, launchingAppIds.size]);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      launchTimeouts.current.forEach((t) => clearTimeout(t));
      launchTimeouts.current.clear();
    };
  }, []);

  const currentHeight = config.height || 52;
  const isHidden = Boolean(config.autoHide && !isHovered && !previewVisible);

  // Sync window physical size when hidden state changes
  useEffect(() => {
    invoke("set_taskbar_autohide_state", {
      hidden: isHidden,
      height: currentHeight,
      position: config.position,
    }).catch(console.error);
  }, [isHidden, currentHeight, config.position]);

  // Context Menu Management
  const openContextMenu = async (
    e: React.MouseEvent,
    item: {
      appId?: string;
      appName: string;
      command?: string;
      windowId?: string;
      isPinned: boolean;
      isRunning: boolean;
    }
  ) => {
    e.preventDefault();
    e.stopPropagation();

    // Freeze magnification immediately when opening context menu
    setContextMenuVisible(true);
    setIsMagnifying(false);
    setMagnifyScales({});

    const btnEl = e.currentTarget as HTMLElement;
    const btnRect = btnEl.getBoundingClientRect();
    // Center of the icon relative to the taskbar window (0 to 1100px)
    const iconCenterX = Math.round(btnRect.left + btnRect.width / 2);

    try {
      await invoke("show_dock_context_menu", {
        iconCenterX,
        menuData: {
          ...item,
          anchorX: iconCenterX,
        },
      });
    } catch (err) {
      console.error("Failed to show dock context menu", err);
    }
  };

  // Magnification Engine: Cosine Wave Algorithm
  const isMagnifyActive = config.magnification !== false && !contextMenuVisible;

  const handleDockMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isMagnifyActive) {
      if (isMagnifying) {
        setIsMagnifying(false);
        setMagnifyScales({});
      }
      return;
    }

    const mouseViewportX = e.clientX;

    if (rafId.current) {
      cancelAnimationFrame(rafId.current);
    }

    rafId.current = requestAnimationFrame(() => {
      const R = 110; // Influence radius in pixels
      const maxScale = config.maxMagnificationScale ?? 1.35;
      const nextScales: Record<string, number> = {};

      iconRefs.current.forEach((el, id) => {
        if (!el) return;
        const rect = el.getBoundingClientRect();
        // Since transform-origin is bottom center, horizontal center is invariant under scaling
        const centerX = rect.left + rect.width / 2;
        const d = Math.abs(centerX - mouseViewportX);

        if (d <= R) {
          // Cosine wave: scale = 1 + (maxScale - 1) * cos((d / R) * (PI / 2))
          const cosine = Math.cos((d / R) * (Math.PI / 2));
          const scale = 1 + (maxScale - 1) * cosine;
          nextScales[id] = Math.round(scale * 1000) / 1000;
        } else {
          nextScales[id] = 1;
        }
      });

      setIsMagnifying(true);
      setMagnifyScales(nextScales);
    });
  };

  const handleDockMouseLeave = () => {
    if (rafId.current) {
      cancelAnimationFrame(rafId.current);
    }
    setIsMagnifying(false);
    setMagnifyScales({});
  };

  const handleMouseEnter = () => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
    setIsHovered(true);
    if (config.autoHide) {
      invoke("set_taskbar_autohide_state", {
        hidden: false,
        height: currentHeight,
        position: config.position,
      }).catch(console.error);
    }
  };

  const handleMouseLeave = () => {
    if (config.autoHide) {
      hideTimer.current = setTimeout(() => {
        setIsHovered(false);
      }, 500);
    }
  };

  const handleShuffle = async () => {
    if (wallpapers.length === 0) return;
    const randomIndex = Math.floor(Math.random() * wallpapers.length);
    const chosen = wallpapers[randomIndex];
    try {
      await invoke("set_wallpaper", { path: chosen.path });
    } catch (err) {
      console.error(err);
    }
  };

  const handleActivateWindow = async (id: string) => {
    try {
      await invoke("activate_window", { windowId: id });
    } catch (err) {
      console.error("Failed to activate window", err);
    }
  };

  const handleLaunchApp = async (appId: string, cmd: string) => {
    // 1. Add appId to launchingAppIds to start bouncing
    setLaunchingAppIds((prev) => new Set(prev).add(appId));

    // 2. Set safety timeout of 3000ms
    if (launchTimeouts.current.has(appId)) {
      clearTimeout(launchTimeouts.current.get(appId)!);
    }
    const timeout = setTimeout(() => {
      setLaunchingAppIds((prev) => {
        const next = new Set(prev);
        next.delete(appId);
        return next;
      });
      launchTimeouts.current.delete(appId);
    }, 3000);
    launchTimeouts.current.set(appId, timeout);

    // 3. Launch app process via Tauri
    try {
      await invoke("launch_app", { command: cmd });
    } catch (err) {
      console.error("Failed to launch app", err);
      // Remove bouncing immediately on error
      setLaunchingAppIds((prev) => {
        const next = new Set(prev);
        next.delete(appId);
        return next;
      });
      if (launchTimeouts.current.has(appId)) {
        clearTimeout(launchTimeouts.current.get(appId)!);
        launchTimeouts.current.delete(appId);
      }
    }
  };

  const getPinnedVisual = (app: PinnedApp) => {
    switch (app.iconType) {
      case "chrome":
      case "browser":
        return {
          icon: <Globe size={20} />,
          color: app.color || "#38bdf8",
          bg: "rgba(56, 189, 248, 0.18)",
          border: "rgba(56, 189, 248, 0.45)",
        };
      case "code":
        return {
          icon: <Code2 size={20} />,
          color: app.color || "#818cf8",
          bg: "rgba(129, 140, 248, 0.2)",
          border: "rgba(129, 140, 248, 0.5)",
        };
      case "terminal":
        return {
          icon: <Terminal size={20} />,
          color: app.color || "#34d399",
          bg: "rgba(52, 211, 153, 0.18)",
          border: "rgba(52, 211, 153, 0.45)",
        };
      case "files":
        return {
          icon: <Folder size={20} />,
          color: app.color || "#fbbf24",
          bg: "rgba(251, 191, 36, 0.18)",
          border: "rgba(251, 191, 36, 0.45)",
        };
      case "settings":
        return {
          icon: <Settings size={20} />,
          color: app.color || "#94a3b8",
          bg: "rgba(148, 163, 184, 0.18)",
          border: "rgba(148, 163, 184, 0.45)",
        };
      default:
        return {
          icon: <AppWindow size={20} />,
          color: app.color || "#c084fc",
          bg: "rgba(192, 132, 252, 0.18)",
          border: "rgba(192, 132, 252, 0.45)",
        };
    }
  };

  const getAppVisual = (className: string) => {
    const lower = className.toLowerCase();
    if (lower.includes("chrome") || lower.includes("chromium")) {
      return {
        icon: <Globe size={20} />,
        color: "#38bdf8",
        bg: "rgba(56, 189, 248, 0.18)",
        border: "rgba(56, 189, 248, 0.45)",
      };
    }
    if (lower.includes("firefox")) {
      return {
        icon: <Globe size={20} />,
        color: "#fb923c",
        bg: "rgba(251, 146, 60, 0.18)",
        border: "rgba(251, 146, 60, 0.45)",
      };
    }
    if (
      lower.includes("terminal") ||
      lower.includes("console") ||
      lower.includes("pty") ||
      lower.includes("kitty") ||
      lower.includes("alacritty")
    ) {
      return {
        icon: <Terminal size={20} />,
        color: "#34d399",
        bg: "rgba(52, 211, 153, 0.18)",
        border: "rgba(52, 211, 153, 0.45)",
      };
    }
    if (
      lower.includes("code") ||
      lower.includes("cursor") ||
      lower.includes("ide") ||
      lower.includes("antigravity")
    ) {
      return {
        icon: <Code2 size={20} />,
        color: "#818cf8",
        bg: "rgba(129, 140, 248, 0.2)",
        border: "rgba(129, 140, 248, 0.5)",
      };
    }
    if (lower.includes("nautilus") || lower.includes("file") || lower.includes("thunar")) {
      return {
        icon: <Folder size={20} />,
        color: "#fbbf24",
        bg: "rgba(251, 191, 36, 0.18)",
        border: "rgba(251, 191, 36, 0.45)",
      };
    }
    if (lower.includes("setting") || lower.includes("preference")) {
      return {
        icon: <Settings size={20} />,
        color: "#94a3b8",
        bg: "rgba(148, 163, 184, 0.18)",
        border: "rgba(148, 163, 184, 0.45)",
      };
    }
    if (lower.includes("deskmorph")) {
      return {
        icon: <Sparkles size={20} />,
        color: "#48b9c7",
        bg: "rgba(72, 185, 199, 0.2)",
        border: "rgba(72, 185, 199, 0.5)",
      };
    }
    return {
      icon: <AppWindow size={20} />,
      color: "#c084fc",
      bg: "rgba(192, 132, 252, 0.18)",
      border: "rgba(192, 132, 252, 0.45)",
    };
  };

  const btnSize = Math.max(30, Math.min(42, currentHeight - 16));
  const launcherSize = Math.max(28, btnSize - 2);

  // Group windows into Pinned vs Unpinned Running Apps
  const pinnedList = config.pinnedApps || DEFAULT_PINNED_APPS;
  const activePinned = pinnedList.filter((app) => app.enabled !== false);
  const matchedWindowIds = new Set<string>();

  const pinnedItems = activePinned.map((app) => {
    const matchingWin = openWindows.find((w) =>
      app.matchClasses.some((cls) => w.class_name.toLowerCase().includes(cls.toLowerCase()))
    );
    if (matchingWin) {
      matchedWindowIds.add(matchingWin.id);
    }
    return {
      pinned: app,
      window: matchingWin || null,
    };
  });

  const unpinnedWindows = openWindows.filter((w) => !matchedWindowIds.has(w.id));

  return (
    <div
      className="taskbar-wrapper"
      onContextMenu={(e) => e.preventDefault()}
    >
      {/* Hit test trigger area at the edge when hidden */}
      {isHidden && (
        <div
          className="dock-edge-trigger"
          onMouseEnter={handleMouseEnter}
          style={{
            [config.position === "top" ? "top" : "bottom"]: 0,
          }}
        />
      )}


      <div
        className={`taskbar-container ${isHidden ? "dock-autohidden" : ""}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onContextMenu={(e) => e.preventDefault()}
        style={{
          height: `${currentHeight}px`,
          transform: isHidden
            ? config.position === "top"
              ? "translateY(-120%)"
              : "translateY(120%)"
            : "translateY(0)",
          transition: "transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease, background 0.3s ease",
          background: isHidden ? "transparent" : `rgba(13, 17, 28, ${config.opacity})`,
          borderRadius: `${config.borderRadius}px`,
          borderWidth: isHidden ? "0px" : "1px",
          borderColor: isHidden ? "transparent" : "rgba(255, 255, 255, 0.14)",
          boxShadow: isHidden ? "none" : "0 12px 40px rgba(0, 0, 0, 0.65)",
          opacity: isHidden ? 0 : 1,
          pointerEvents: isHidden ? "none" : "auto",
        }}
      >
        {/* 1. Left Area: Launcher button */}
        <div className="dock-left">
          <div
            className="dock-launcher-btn"
            title="DeskMorph Studio"
            onContextMenu={(e) => e.preventDefault()}
            style={{
              width: `${launcherSize}px`,
              height: `${launcherSize}px`,
              background: `linear-gradient(135deg, ${config.accentColor}, #8b5cf6)`,
            }}
          >
            <Sparkles size={Math.round(launcherSize * 0.48)} color="#0c1017" />
          </div>
          <div className="dock-divider" />
        </div>

        {/* 2. Center Area: Pinned Applications & Open Windows */}
        <div
          className={`dock-apps ${isMagnifying ? "is-magnifying" : ""}`}
          onMouseMove={handleDockMouseMove}
          onMouseLeave={handleDockMouseLeave}
        >
          {/* A. Pinned Apps Group */}
          <div className="dock-pinned-group">
            {pinnedItems.map(({ pinned, window }) => {
              const visual = getPinnedVisual(pinned);
              const isRunning = Boolean(window);
              const isActive = Boolean(window?.is_active);
              const isLaunching = launchingAppIds.has(pinned.id);
              const magnifyScale = isMagnifyActive ? (magnifyScales[pinned.id] ?? 1) : 1;

              return (
                <button
                  key={pinned.id}
                  ref={(el) => {
                    if (el) iconRefs.current.set(pinned.id, el);
                    else iconRefs.current.delete(pinned.id);
                  }}
                  className={`running-app-icon-btn ${isRunning ? "app-running" : "app-idle"} ${
                    isActive ? "app-active" : ""
                  } ${isLaunching ? "app-launching" : ""}`}
                  onClick={() => {
                    if (window) {
                      handleActivateWindow(window.id);
                    } else {
                      handleLaunchApp(pinned.id, pinned.command);
                    }
                  }}
                  onContextMenu={(e) =>
                    openContextMenu(e, {
                      appId: pinned.id,
                      appName: pinned.name,
                      command: pinned.command,
                      windowId: window?.id,
                      isPinned: true,
                      isRunning,
                    })
                  }
                  title={
                    window
                      ? `${pinned.name} • ${window.title} (Đang chạy - Nhấn để chuyển)`
                      : `${pinned.name} (Đã ghim - Nhấn để mở)`
                  }
                  style={{
                    width: `${btnSize}px`,
                    height: `${btnSize}px`,
                    ["--magnify-scale" as string]: magnifyScale,
                    color: visual.color,
                    background: isActive
                      ? visual.bg
                      : isRunning
                      ? "rgba(255, 255, 255, 0.08)"
                      : "rgba(255, 255, 255, 0.03)",
                    borderColor: isActive
                      ? visual.border
                      : isRunning
                      ? "rgba(255, 255, 255, 0.12)"
                      : "rgba(255, 255, 255, 0.05)",
                    opacity: isRunning ? 1 : 0.78,
                    ["--launch-border" as string]: visual.border,
                    ["--launch-glow" as string]: visual.bg,
                  }}
                >
                  <span
                    className={`app-icon-glyph ${
                      isLaunching && config.bouncingLaunch !== false ? "glyph-bouncing" : ""
                    }`}
                  >
                    {visual.icon}
                  </span>

                  {/* Dynamic Floor Shadow / Glow beneath bouncing icon */}
                  {isLaunching && config.dynamicShadow !== false && (
                    <span
                      className="dock-launch-shadow"
                      style={{
                        ["--shadow-color" as string]: visual.color,
                      }}
                    />
                  )}

                  {/* Running Indicator Dot */}
                  {isRunning && (
                    <span
                      className={`running-dot ${isActive ? "dot-active" : "dot-inactive"}`}
                      style={{
                        background: isActive ? visual.color : "rgba(255, 255, 255, 0.55)",
                        boxShadow: isActive ? `0 0 8px ${visual.color}` : "none",
                      }}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* B. Subtle Divider between Pinned Apps and Unpinned Running Apps */}
          {unpinnedWindows.length > 0 && activePinned.length > 0 && (
            <div className="dock-apps-separator" title="Ứng dụng đang chạy khác" />
          )}

          {/* C. Unpinned Running Apps */}
          {unpinnedWindows.length > 0 && (
            <div className="dock-unpinned-group">
              {unpinnedWindows.map((win) => {
                const visual = getAppVisual(win.class_name);
                const magnifyScale = isMagnifyActive ? (magnifyScales[win.id] ?? 1) : 1;

                return (
                  <button
                    key={win.id}
                    ref={(el) => {
                      if (el) iconRefs.current.set(win.id, el);
                      else iconRefs.current.delete(win.id);
                    }}
                    className={`running-app-icon-btn ${win.is_active ? "app-active" : ""}`}
                    onClick={() => handleActivateWindow(win.id)}
                    onContextMenu={(e) =>
                      openContextMenu(e, {
                        appName: win.class_name,
                        command: win.class_name.toLowerCase(),
                        windowId: win.id,
                        isPinned: false,
                        isRunning: true,
                      })
                    }
                    title={`${win.class_name} • ${win.title} (Đang chạy)`}
                    style={{
                      width: `${btnSize}px`,
                      height: `${btnSize}px`,
                      ["--magnify-scale" as string]: magnifyScale,
                      color: visual.color,
                      background: win.is_active ? visual.bg : "rgba(255, 255, 255, 0.05)",
                      borderColor: win.is_active ? visual.border : "rgba(255, 255, 255, 0.08)",
                    }}
                  >
                    <span className="app-icon-glyph">{visual.icon}</span>
                    <span
                      className={`running-dot ${win.is_active ? "dot-active" : "dot-inactive"}`}
                      style={{
                        background: win.is_active ? visual.color : "rgba(255, 255, 255, 0.5)",
                        boxShadow: win.is_active ? `0 0 8px ${visual.color}` : "none",
                      }}
                    />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 3. Right Area: Live Stats, Wallpaper Shuffle, Clock */}
        <div className="dock-right">
          {config.showStats && <div className="dock-divider" />}

          {/* Live System Stats */}
          {config.showStats && stats && (
            <div className="taskbar-section stats-section">
              <div className="stat-pill" title={`CPU Usage: ${stats.cpu_usage}%`}>
                <Cpu size={14} className="stat-icon cpu-icon" />
                <div className="stat-bar-mini">
                  <div
                    className="stat-bar-fill"
                    style={{
                      width: `${Math.min(stats.cpu_usage, 100)}%`,
                      background: stats.cpu_usage > 75 ? "#ef4444" : config.accentColor,
                    }}
                  />
                </div>
                <span className="stat-text">{stats.cpu_usage.toFixed(0)}%</span>
              </div>

              <div
                className="stat-pill"
                title={`RAM: ${(stats.ram_used_mb / 1024).toFixed(1)}GB / ${(
                  stats.ram_total_mb / 1024
                ).toFixed(1)}GB (${stats.ram_percent}%)`}
              >
                <HardDrive size={14} className="stat-icon ram-icon" />
                <div className="stat-bar-mini">
                  <div
                    className="stat-bar-fill"
                    style={{
                      width: `${Math.min(stats.ram_percent, 100)}%`,
                      background: stats.ram_percent > 85 ? "#ef4444" : "#a855f7",
                    }}
                  />
                </div>
                <span className="stat-text">{stats.ram_percent.toFixed(0)}%</span>
              </div>
            </div>
          )}

          {/* Wallpaper quick shuffle */}
          {config.showShuffle && (
            <button
              className="dock-action-btn"
              onClick={handleShuffle}
              title="Đổi ảnh nền ngẫu nhiên ngay lập tức"
            >
              <Shuffle size={14} />
            </button>
          )}

          {/* Clock & Date */}
          {config.showClock && (
            <div className="taskbar-section clock-section">
              <span className="clock-time">{time}</span>
              <span className="clock-date">{date}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
