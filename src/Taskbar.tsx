import React, { useEffect, useLayoutEffect, useState, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useConfig } from "./config/store";
import { dockMetrics, dockSurface } from "./dockAppearance";
import { useI18n } from "./i18n/useI18n";
import { installedForPin } from "./appSearch";
import { useInstalledApps } from "./hooks/useInstalledApps";
import { SystemWidgets } from "./components/SystemWidgets";
import { AppIcon } from "./components/AppIcon";
import { useDockTooltip } from "./hooks/useDockTooltip";
import { usePlatform } from "./hooks/usePlatform";
import { usePolling } from "./hooks/usePolling";
import { useClock } from "./hooks/useClock";
import { groupWindows } from "./windowGroups";
import { listen } from "@tauri-apps/api/event";
import {
  SystemStats,
  OpenWindow,
  PinnedApp,
  DEFAULT_PINNED_APPS,
} from "./types";
import {
  Volume2,
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
  const { t, locale, count } = useI18n();
  const { apps: installedApps } = useInstalledApps();
  const { platform } = usePlatform();
  const [operationError, setOperationError] = useState<string | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const ramDescription = stats ? `RAM: ${(stats.ram_used_mb / 1024).toFixed(1)} GiB / ${(stats.ram_total_mb / 1024).toFixed(1)} GiB (${stats.ram_percent}%)` : undefined;
  const [openWindows, setOpenWindows] = useState<OpenWindow[]>([]);
  const appsRef = useRef<HTMLDivElement>(null);
  const [appsScroll, setAppsScroll] = useState({ overflow: false, back: false, forward: false });
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
  const [popupVisible, setPopupVisible] = useState(false);
  const iconRefs = useRef<Map<string, HTMLElement>>(new Map());
  const rafId = useRef<number | null>(null);

  const { config, ready, error: configError, mutatePin } = useConfig();
  const now = useClock(ready && config.enabled && config.showClock);
  const outsideSince = useRef<number | null>(null);
  // Native resize can remove the edge trigger without a DOM mouseleave, or
  // synthesize an enter at stale coordinates. Reconcile with global X11
  // coordinates only while auto-hide is enabled; this starts no child process.
  usePolling(async (signal) => {
    const inside = await invoke<boolean>("is_pointer_over_dock");
    if (signal.aborted) return;
    if (inside) { outsideSince.current = null; setIsHovered(true); }
    else {
      outsideSince.current ??= performance.now();
      if (performance.now() - outsideSince.current >= 500) setIsHovered(false);
    }
  }, 250, ready && config.enabled && config.autoHide && platform?.session === "x11" && !popupVisible);
  const time = now.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", second: config.clockSeconds ? "2-digit" : undefined, hour12: !config.clock24 });
  const date = now.toLocaleDateString(locale, { weekday: "short", month: "short", day: "numeric" });
  const dockRef = useRef<HTMLDivElement>(null);
  const pointerDrag = useRef<{ id: string; pointerId: number; x: number; y: number; started: boolean; cancelled: boolean } | null>(null);
  const movingPin = useRef(false);
  const suppressClickUntil = useRef(0);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  useEffect(() => {
    const cancel = (event?: KeyboardEvent) => {
      if (event && event.key !== "Escape") return;
      if (!pointerDrag.current) return;
      pointerDrag.current.cancelled = true;
      suppressClickUntil.current = Infinity;
      setDraggingId(null); setDropTargetId(null);
      event?.preventDefault();
    };
    const onBlur = () => cancel();
    window.addEventListener("keydown", cancel);
    window.addEventListener("blur", onBlur);
    return () => { window.removeEventListener("keydown", cancel); window.removeEventListener("blur", onBlur); };
  }, []);
  const [systemReducedMotion, setSystemReducedMotion] = useState(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  const reducedMotion = config.reduceMotion || systemReducedMotion;
  const tooltip = useDockTooltip(popupVisible || Boolean(draggingId));
  useEffect(() => {
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => setSystemReducedMotion(query.matches);
    query.addEventListener("change", changed);
    return () => query.removeEventListener("change", changed);
  }, []);

  const keepVisibleBriefly = (durationMs = 7000) => {
    setPreviewVisible(true);
    if (previewTimer.current) {
      clearTimeout(previewTimer.current);
    }
    previewTimer.current = setTimeout(() => {
      setPreviewVisible(false);
    }, durationMs);
  };

  useEffect(() => {
    keepVisibleBriefly(7000);
    let disposed = false;
    let unlisten: (() => void) | undefined;
    let unlistenPopup: (() => void) | undefined;
    listen<boolean>("deskmorph:popup-visible", (event) => {
      if (!disposed) setPopupVisible(event.payload);
    }).then((stop) => { if (disposed) stop(); else unlistenPopup = stop; }).catch(console.error);
    listen<boolean>("deskmorph:context-menu-visibility", (event) => {
      if (disposed) return;
      setContextMenuVisible(Boolean(event.payload));
      if (event.payload) {
        setIsMagnifying(false);
        setMagnifyScales({});
      }
    }).then((stop) => { if (disposed) stop(); else unlisten = stop; }).catch(console.error);
    return () => {
      disposed = true;
      unlisten?.();
      unlistenPopup?.();
      if (hideTimer.current) clearTimeout(hideTimer.current);
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

  usePolling(async (signal) => {
    try {
      const wins = await invoke<OpenWindow[]>("get_open_windows");
      if (!signal.aborted) { setOpenWindows(wins); setOperationError(null); }
    } catch (e) { if (!signal.aborted) setOperationError(String(e)); }
  }, 1500, ready && config.enabled && config.showApps && Boolean(platform?.windowManagement));
  usePolling(async (signal) => {
    const res = await invoke<SystemStats>("get_system_stats");
    if (!signal.aborted) setStats(res);
  }, 2000, ready && config.enabled && config.showStats);


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

  const { height: currentHeight, iconSize: btnSize, maxScale, hitWidth, hitHeight } = dockMetrics(config);
  const isHidden = Boolean(config.autoHide && !isHovered && !previewVisible && !contextMenuVisible && !popupVisible);

  // Sync window physical size when hidden state changes
  useEffect(() => {
    if (!ready || !config.enabled) return;
    invoke("set_taskbar_autohide_state", {
      hidden: isHidden,
      height: currentHeight,
      position: config.position,
    }).catch(console.error);
  }, [isHidden, currentHeight, config.position, ready, config.enabled]);

  // Context Menu Management
  const openContextMenu = async (
    e: React.MouseEvent,
    item: {
      appId?: string;
      appName: string;
      command?: string;
      windowId?: string;
      desktopId?: string;
      windows?: OpenWindow[];
      matchClasses?: string[];
      iconPath?: string | null;
      pinIndex?: number;
      pinCount?: number;
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
      setContextMenuVisible(false);
      console.error("Failed to show dock context menu", err);
    }
  };

  // Magnification Engine: Cosine Wave Algorithm
  const isMagnifyActive = config.magnification !== false && !reducedMotion && !contextMenuVisible && !popupVisible && !draggingId;

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

      const nextScales: Record<string, number> = {};

      iconRefs.current.forEach((el, id) => {
        if (!el) return;
        const rect = el.getBoundingClientRect();
        // The button stays fixed; only its decorative visual layer is scaled.
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

  const shuffleBusy = useRef(false);
  const handleShuffle = async () => {
    if (shuffleBusy.current) return;
    shuffleBusy.current = true;
    try { await invoke("shuffle_wallpaper"); setOperationError(null); }
    catch (error) { setOperationError(String(error)); }
    finally { shuffleBusy.current = false; }
  };

  const handleActivateWindow = async (id: string) => {
    try {
      await invoke("activate_window", { windowId: id });
    } catch (err) {
      setOperationError(String(err));
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
      setOperationError(String(err));
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


  const launcherSize = Math.max(28, btnSize - 2);

  // Group windows into Pinned vs Unpinned Running Apps
  const pinnedList = config.pinnedApps || DEFAULT_PINNED_APPS;
  const activePinned = pinnedList.filter((app) => app.enabled !== false);
  const { pinnedItems, unpinnedGroups } = groupWindows(openWindows, activePinned);

  useLayoutEffect(() => {
    const area = appsRef.current;
    if (!area || !config.showApps) return;
    const update = () => {
      const max = area.scrollWidth - area.clientWidth;
      // Compare against the whole viewport so the arrows cannot keep themselves
      // visible merely by consuming the space that would otherwise fit the apps.
      const next = { overflow: area.scrollWidth > (area.parentElement?.clientWidth ?? area.clientWidth) + 1, back: area.scrollLeft > 1, forward: area.scrollLeft < max - 1 };
      setAppsScroll((previous) => previous.overflow === next.overflow && previous.back === next.back && previous.forward === next.forward ? previous : next);
    };
    const observer = new ResizeObserver(update);
    [area, ...Array.from(area.children)].forEach((element) => observer.observe(element));
    area.addEventListener("scroll", update, { passive: true });
    update();
    return () => { observer.disconnect(); area.removeEventListener("scroll", update); };
  }, [config.showApps, pinnedItems.length, unpinnedGroups.length]);

  const scrollApps = (direction: number) => appsRef.current?.scrollBy({ left: direction * Math.max(100, appsRef.current.clientWidth * .8), behavior: reducedMotion ? "instant" : "smooth" });

  useLayoutEffect(() => {
    if (!ready || !config.enabled || !dockRef.current) return;
    const root = dockRef.current;
    let timer: ReturnType<typeof setTimeout>;
    let lastWidth = 0;
    const elements = [".dock-left", ".dock-right", ".dock-pinned-group", ".dock-unpinned-group", ".dock-apps-separator"]
      .flatMap((selector) => Array.from(root.querySelectorAll<HTMLElement>(selector)));
    const measure = () => {
      const width = Math.ceil(elements.reduce((sum, el) => sum + el.offsetWidth, 0) + 76 + (unpinnedGroups.length && activePinned.length ? 16 : 0));
      if (width === lastWidth) return;
      lastWidth = width;
      clearTimeout(timer);
      timer = setTimeout(() => void invoke("set_dock_content_width", { width }).catch(console.error), 80);
    };
    const observer = new ResizeObserver(measure);
    elements.forEach((el) => observer.observe(el));
    measure();
    return () => { clearTimeout(timer); observer.disconnect(); };
  }, [ready, config.enabled, config.iconSize, config.iconSpacing, config.height, config.showApps, config.showAudio, config.showBattery, config.showNetwork, config.showSystem, config.showClock, config.showStats, config.showShuffle, pinnedItems.length, unpinnedGroups.length]);

  const movePin = async (id: string, target: number) => {
    if (movingPin.current || pinnedList.findIndex((pin) => pin.id === id) === target) return;
    movingPin.current = true;
    try {
      if (await mutatePin("move", id, undefined, target)) requestAnimationFrame(() => iconRefs.current.get(id)?.focus());
    } finally { movingPin.current = false; }
  };

  const pinAt = (x: number, y: number) => document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-pin-id]")?.dataset.pinId;
  const finishPinDrag = (event: React.PointerEvent<HTMLButtonElement>, cancelled = false) => {
    const drag = pointerDrag.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    pointerDrag.current = null;
    setDraggingId(null); setDropTargetId(null);
    if (!drag.started && !drag.cancelled && !cancelled) return;
    event.preventDefault();
    suppressClickUntil.current = Date.now() + 350;
    if (cancelled || drag.cancelled) return;
    const targetId = pinAt(event.clientX, event.clientY);
    const target = pinnedList.findIndex((pin) => pin.id === targetId);
    if (target >= 0 && targetId !== drag.id) void movePin(drag.id, target);
  };

  const selectWindows = async (e: React.MouseEvent, windows: OpenWindow[], appName: string) => {
    if (windows.length === 1) {
      await handleActivateWindow(windows[0].id);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    setContextMenuVisible(true);
    setIsMagnifying(false);
    setMagnifyScales({});
    try {
      await invoke("show_dock_context_menu", {
        iconCenterX: Math.round(rect.left + rect.width / 2),
        menuData: { mode: "windows", appName, windows },
      });
    } catch (err) {
      setContextMenuVisible(false);
      console.error("Failed to show window list", err);
    }
  };

  return (
    <div
      className="taskbar-wrapper"
      onContextMenu={(e) => e.preventDefault()}
    >
      {operationError && <div className="app-status" role="alert">{operationError}</div>}
      {configError && <div className="app-status" role="alert">{configError}</div>}
      {/* Hit test trigger area at the edge when hidden */}
      {isHidden && (
        <div
          className="dock-edge-trigger"
          onMouseEnter={() => {
            handleMouseEnter();
            // Revealing moves the native window away from the screen edge.
            // The removed trigger cannot deliver mouseleave. Give the pointer
            // time to reach the Dock; entering its surface cancels this timer.
            handleMouseLeave();
          }}
          style={{
            [config.position === "top" ? "top" : "bottom"]: 0,
          }}
        />
      )}


      <div
        {...tooltip}
        ref={dockRef}
        className={`taskbar-container ${reducedMotion ? "reduce-motion" : ""} ${isHidden ? "dock-autohidden" : ""}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onContextMenu={(e) => e.preventDefault()}
        style={{
          ...dockSurface(config),
          transform: isHidden
            ? config.position === "top"
              ? "translateY(-120%)"
              : "translateY(120%)"
            : "translateY(0)",
          transition: reducedMotion ? "none" : "transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease, background 0.3s ease",
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
          <button
            type="button"
            aria-label={t("searchApps")}
            onClick={() => void invoke("show_app_launcher").catch(console.error)}
            className="dock-launcher-btn"
            data-dock-tooltip={t("searchApps")}
            onContextMenu={(e) => e.preventDefault()}
            style={{
              width: `${launcherSize}px`,
              height: `${launcherSize}px`,
              background: `linear-gradient(135deg, ${config.accentColor}, #8b5cf6)`,
            }}
          >
            <Sparkles size={Math.round(launcherSize * 0.48)} color="#0c1017" />
          </button>
          <div className="dock-divider" />
        </div>

        {/* 2. Center Area: Pinned Applications & Open Windows */}
        <div className="dock-apps-viewport" style={{ display: config.showApps ? undefined : "none" }}>
          {appsScroll.overflow && <button className="dock-scroll-btn" aria-label={t("scrollAppsLeft")} data-dock-tooltip={t("scrollAppsLeft")} aria-controls="dock-apps" disabled={!appsScroll.back} onClick={() => scrollApps(-1)}><span aria-hidden="true">‹</span></button>}
        <div
          ref={appsRef}
          id="dock-apps"
          style={{ display: config.showApps ? undefined : "none" }}
          className={`dock-apps ${isMagnifying ? "is-magnifying" : ""}`}
          onMouseMove={handleDockMouseMove}
          onMouseLeave={handleDockMouseLeave}
        >
          {/* A. Pinned Apps Group */}
          <div className="dock-pinned-group">
            {pinnedItems.map(({ pinned, windows }) => {
              const visual = getPinnedVisual(pinned);
              const installed = installedForPin(pinned, installedApps);
              const window = windows.find((w) => w.is_active) || windows[0];
              const isRunning = windows.length > 0;
              const isActive = windows.some((w) => w.is_active);
              const isLaunching = launchingAppIds.has(pinned.id);
              const magnifyScale = isMagnifyActive ? (magnifyScales[pinned.id] ?? 1) : 1;

              return (
                <button
                  aria-label={`${pinned.name} • ${count("window", windows.length)}`}
                  aria-keyshortcuts="Control+Shift+ArrowLeft Control+Shift+ArrowRight"
                  key={pinned.id}
                  data-pin-id={pinned.id}
                  draggable={false}
                  onDragStart={(event) => event.preventDefault()}
                  onPointerDown={(event) => {
                    if (event.button !== 0 || !event.isPrimary || movingPin.current || pointerDrag.current) return;
                    pointerDrag.current = { id: pinned.id, pointerId: event.pointerId, x: event.clientX, y: event.clientY, started: false, cancelled: false };
                    event.currentTarget.setPointerCapture(event.pointerId);
                  }}
                  onPointerMove={(event) => {
                    const drag = pointerDrag.current;
                    if (!drag || drag.pointerId !== event.pointerId || drag.cancelled) return;
                    if (!drag.started && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) >= 8) {
                      drag.started = true;
                      suppressClickUntil.current = Infinity;
                      setDraggingId(drag.id); setIsMagnifying(false); setMagnifyScales({});
                    }
                    if (drag.started) {
                      event.preventDefault();
                      const targetId = pinAt(event.clientX, event.clientY);
                      setDropTargetId(targetId && targetId !== drag.id ? targetId : null);
                    }
                  }}
                  onPointerUp={(event) => finishPinDrag(event)}
                  onPointerCancel={(event) => finishPinDrag(event, true)}
                  onLostPointerCapture={(event) => finishPinDrag(event, true)}
                  onKeyDown={(e) => {
                    if (e.ctrlKey && e.shiftKey && ["ArrowLeft", "ArrowRight"].includes(e.key)) {
                      e.preventDefault();
                      const index = pinnedList.findIndex((app) => app.id === pinned.id);
                      void movePin(pinned.id, Math.max(0, Math.min(pinnedList.length - 1, index + (e.key === "ArrowLeft" ? -1 : 1))));
                    }
                  }}
                  onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); void handleLaunchApp(pinned.id, installed ? `desktop:${installed.id}` : pinned.command); } }}
                  ref={(el) => {
                    if (el) iconRefs.current.set(pinned.id, el);
                    else iconRefs.current.delete(pinned.id);
                  }}
                  className={`running-app-icon-btn ${isRunning ? "app-running" : "app-idle"} ${
                    isActive ? "app-active" : ""
                  } ${isLaunching ? "app-launching" : ""} ${draggingId === pinned.id ? "is-dragging" : ""} ${dropTargetId === pinned.id ? "is-drop-target" : ""}`}
                  onClick={(e) => {
                    if (Date.now() < suppressClickUntil.current) return;
                    if (window) {
                      void selectWindows(e, windows, pinned.name);
                    } else {
                      handleLaunchApp(pinned.id, installed ? `desktop:${installed.id}` : pinned.command);
                    }
                  }}
                  onContextMenu={(e) =>
                    openContextMenu(e, {
                      desktopId: installed?.id || pinned.desktopId,
                      windows,
                      matchClasses: pinned.matchClasses,
                      iconPath: installed?.iconPath,
                      pinIndex: pinnedList.findIndex((app) => app.id === pinned.id),
                      pinCount: pinnedList.length,
                      appId: pinned.id,
                      appName: pinned.name,
                      command: installed ? `desktop:${installed.id}` : pinned.command,
                      windowId: window?.id,
                      isPinned: true,
                      isRunning,
                    })
                  }
                  data-dock-tooltip={
                    window
                      ? `${pinned.name} • ${count("window", windows.length)} • ${t("selectWindow")}`
                      : `${pinned.name} (Đã ghim - Nhấn để mở)`
                  }
                  style={{
                    width: `${hitWidth}px`,
                    height: `${hitHeight}px`,
                    ["--magnify-scale" as string]: magnifyScale,
                    color: visual.color,
                    ["--icon-background" as string]: isActive
                      ? visual.bg
                      : isRunning
                      ? "rgba(255, 255, 255, 0.08)"
                      : "rgba(255, 255, 255, 0.03)",
                    ["--icon-border" as string]: isActive
                      ? visual.border
                      : isRunning
                      ? "rgba(255, 255, 255, 0.12)"
                      : "rgba(255, 255, 255, 0.05)",
                    opacity: isRunning ? 1 : 0.78,
                    ["--launch-border" as string]: visual.border,
                    ["--launch-glow" as string]: visual.bg,
                  }}
                >
                  <span className="app-icon-tile">
                  <span className="app-icon-visual"><span
                    className={`app-icon-glyph ${
                      isLaunching && config.bouncingLaunch !== false && !reducedMotion ? "glyph-bouncing" : ""
                    }`}
                  >
                    {installed?.iconPath ? <AppIcon path={installed.iconPath} size={Math.round(btnSize * .68)} /> : visual.icon}
                  </span></span>

                  {/* Dynamic Floor Shadow / Glow beneath bouncing icon */}
                  {isLaunching && config.dynamicShadow !== false && !reducedMotion && (
                    <span
                      className="dock-launch-shadow"
                      style={{
                        ["--shadow-color" as string]: visual.color,
                      }}
                    />
                  )}

                  {windows.length > 1 && <span className="dock-window-count" aria-hidden="true">{windows.length > 9 ? "9+" : windows.length}</span>}
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
                  </span>
                </button>
              );
            })}
          </div>

          {/* B. Subtle Divider between Pinned Apps and Unpinned Running Apps */}
          {unpinnedGroups.length > 0 && activePinned.length > 0 && (
            <div className="dock-apps-separator" aria-hidden="true" />
          )}

          {/* C. Unpinned Running Apps */}
          {unpinnedGroups.length > 0 && (
            <div className="dock-unpinned-group">
              {unpinnedGroups.map((windows) => {
                const win = windows.find((w) => w.is_active) || windows[0];
                const groupId = win.class_name.toLowerCase();
                const isActive = windows.some((w) => w.is_active);
                const visual = getAppVisual(win.class_name);
                const installed = installedApps.find((app) => app.matchClasses.includes(win.class_name.toLowerCase()));
                const magnifyScale = isMagnifyActive ? (magnifyScales[groupId] ?? 1) : 1;

                return (
                  <button
                    aria-label={`${win.class_name} • ${count("window", windows.length)}`}
                    key={groupId}
                    ref={(el) => {
                      if (el) iconRefs.current.set(groupId, el);
                      else iconRefs.current.delete(groupId);
                    }}
                    className={`running-app-icon-btn ${isActive ? "app-active" : ""}`}
                    onClick={(e) => void selectWindows(e, windows, win.class_name)}
                    onAuxClick={(e) => { if (e.button === 1 && installed) { e.preventDefault(); void handleLaunchApp(installed.id, `desktop:${installed.id}`); } }}
                    onContextMenu={(e) =>
                      openContextMenu(e, {
                        desktopId: installed?.id,
                        windows,
                        matchClasses: installed?.matchClasses || [win.class_name],
                        iconPath: installed?.iconPath,
                        appName: installed?.name || win.class_name,
                        command: installed ? `desktop:${installed.id}` : undefined,
                        windowId: win.id,
                        isPinned: false,
                        isRunning: true,
                      })
                    }
                    data-dock-tooltip={`${win.class_name} • ${count("window", windows.length)} • ${t("selectWindow")}`}
                    style={{
                      width: `${hitWidth}px`,
                      height: `${hitHeight}px`,
                      ["--magnify-scale" as string]: magnifyScale,
                      color: visual.color,
                      ["--icon-background" as string]: isActive ? visual.bg : "rgba(255, 255, 255, 0.05)",
                      ["--icon-border" as string]: isActive ? visual.border : "rgba(255, 255, 255, 0.08)",
                    }}
                  >
                    <span className="app-icon-tile">
                    <span className="app-icon-visual"><span className="app-icon-glyph">{installed?.iconPath ? <AppIcon path={installed.iconPath} size={Math.round(btnSize * .68)} /> : visual.icon}</span></span>
                    {windows.length > 1 && <span className="dock-window-count" aria-hidden="true">{windows.length > 9 ? "9+" : windows.length}</span>}
                    <span
                      className={`running-dot ${isActive ? "dot-active" : "dot-inactive"}`}
                      style={{
                        background: isActive ? visual.color : "rgba(255, 255, 255, 0.5)",
                        boxShadow: isActive ? `0 0 8px ${visual.color}` : "none",
                      }}
                    />
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

          {appsScroll.overflow && <button className="dock-scroll-btn" aria-label={t("scrollAppsRight")} data-dock-tooltip={t("scrollAppsRight")} aria-controls="dock-apps" disabled={!appsScroll.forward} onClick={() => scrollApps(1)}><span aria-hidden="true">›</span></button>}
        </div>
        {/* 3. Right Area: Live Stats, Wallpaper Shuffle, Clock */}
        <div className="dock-right">
          {config.showStats && <div className="dock-divider" />}

          {/* Live System Stats */}
          {config.showStats && stats && (
            <div className="taskbar-section stats-section">
              <div className="stat-pill" role="img" aria-label={`CPU: ${stats.cpu_usage}%`} data-dock-tooltip={`CPU: ${stats.cpu_usage}%`}>
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
                role="img" aria-label={ramDescription}
                data-dock-tooltip={ramDescription}
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
              disabled={!platform?.wallpaper}
              aria-label={t("shuffle")}
              data-dock-tooltip={platform?.wallpaper ? t("shuffle") : t("unsupported")}
            >
              <Shuffle size={14} />
            </button>
          )}

          {config.showAudio && <button className="dock-action-btn" aria-label={t("audio")} data-dock-tooltip={t("audio")} onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            void invoke("show_dock_context_menu", { iconCenterX: Math.round(rect.left + rect.width / 2), menuData: { mode: "audio", appName: t("audio") } }).catch((error) => setOperationError(String(error)));
          }}><Volume2 size={16} /></button>}

          <SystemWidgets onError={setOperationError} />

          {/* Clock & Date */}
          {config.showClock && (
            <button
              type="button"
              aria-label={t("calendar")}
              className="taskbar-section clock-section interactive-widget"
              onClick={async (e) => {
                e.stopPropagation();
                const rect = e.currentTarget.getBoundingClientRect();
                const anchorX = Math.round(rect.left + rect.width / 2);
                const anchorY = Math.round(rect.top);
                try {
                  await invoke("toggle_calendar_flyout", { anchorX, anchorY });
                } catch (err) {
                  console.error("Failed to toggle calendar flyout", err);
                }
              }}
              data-dock-tooltip={t("calendar")}
            >
              <span className="clock-time">{time}</span>
              <span className="clock-date">{date}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
