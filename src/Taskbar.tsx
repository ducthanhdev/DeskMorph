import { ErrorText } from "./components/ErrorText";
import React, { useEffect, useLayoutEffect, useState, useRef } from "react";
import { invoke } from "./ipc";
import { useConfig } from "./config/store";
import { dockMetrics, dockSurface, dockAppStyle, magnificationScale } from "./dockAppearance";
import { useI18n } from "./i18n/useI18n";
import { desktopIdForPin, desktopIsMissing, installedForClass, installedForPin, launchCommandForPin } from "./appSearch";
import { useInstalledApps } from "./hooks/useInstalledApps";
import { SystemWidgets } from "./components/SystemWidgets";
import { DockAppTile, DockStats } from "./components/DockParts";
import { getPinnedVisual, getAppVisual } from "./dockVisuals";
import { useFocusWithin } from "./hooks/useFocusWithin";
import { useDockTooltip } from "./hooks/useDockTooltip";
import { usePlatform } from "./hooks/usePlatform";
import { usePolling } from "./hooks/usePolling";
import { useAsyncLifetime } from "./hooks/useAsyncLifetime";
import { useReducedMotion } from "./hooks/useReducedMotion";
import { useClock } from "./hooks/useClock";
import { formatClock } from "./dateTime";
import { capabilityReason } from "./capabilities";
import { groupWindows, matchesWindowClass } from "./windowGroups";
import { listen } from "@tauri-apps/api/event";
import {
  SystemStats,
  OpenWindow,
  InstalledApp,
  DEFAULT_PINNED_APPS,
} from "./types";
import {
  Volume2,
  Shuffle,
  Sparkles,
} from "lucide-react";

export const Taskbar: React.FC = () => {
  const lifetime = useAsyncLifetime();
  const { t, locale, count, pinName } = useI18n();
  const { apps: installedApps, loading: appsLoading, error: appsError } = useInstalledApps();
  const { platform, error: platformError } = usePlatform();
  const [windowsError, setWindowsError] = useState<string | null>(null);
  const [retryAction, setRetryAction] = useState<(() => void) | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
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

  const { config, ready, error: configError, mutatePin, retry: configRetry } = useConfig();
  const dockRef = useRef<HTMLDivElement>(null);
  const keyboardFocus = useFocusWithin(dockRef);
  const autoHideEnabled = Boolean(config.autoHide && platform?.autoHide);
  const isHidden = Boolean(autoHideEnabled && !keyboardFocus.focused && !isHovered && !previewVisible && !contextMenuVisible && !popupVisible && !operationError && !configError && !windowsError);
  const now = useClock(ready && config.enabled && config.showClock && !isHidden);
  const outsideSince = useRef<number | null>(null);
  // Native resize can remove the edge trigger without a DOM mouseleave, or
  // synthesize an enter at stale coordinates. Reconcile with global X11
  // coordinates only while auto-hide is enabled; this starts no child process.
  usePolling(async (signal) => {
    const inside = await invoke<boolean>("is_pointer_over_dock");
    if (signal.aborted) return;
    if (inside) {
      outsideSince.current = null;
      if (hideTimer.current) { clearTimeout(hideTimer.current); hideTimer.current = null; }
      setIsHovered(true);
    }
    else {
      outsideSince.current ??= performance.now();
      if (performance.now() - outsideSince.current >= 500) setIsHovered(false);
    }
  }, 250, ready && config.enabled && autoHideEnabled && !popupVisible);
  const time = formatClock(now, locale, config);
  const date = now.toLocaleDateString(locale, { weekday: "short", month: "short", day: "numeric" });
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
  const reducedMotion = useReducedMotion(config.reduceMotion);
  const tooltip = useDockTooltip(popupVisible || Boolean(draggingId));

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
      if (!signal.aborted) { setOpenWindows(wins); setWindowsError(null); }
    } catch (e) { if (!signal.aborted) setWindowsError(String(e)); }
  }, 1500, ready && config.enabled && !isHidden && config.showApps && Boolean(platform?.windowManagement));
  usePolling(async (signal) => {
    const res = await invoke<SystemStats>("get_system_stats");
    if (!signal.aborted) setStats(res);
  }, 2000, ready && config.enabled && !isHidden && config.showStats);


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
            matchesWindowClass(app.matchClasses, w.class_name)
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

  const { height: currentHeight, iconSize: btnSize, maxScale } = dockMetrics(config);

  // Sync window physical size when hidden state changes
  useEffect(() => {
    if (!ready || !config.enabled || !platform?.autoHide) return;
    invoke("set_taskbar_autohide_state", {
      hidden: isHidden,
      height: currentHeight,
      position: config.position,
    }).catch(console.error);
  }, [isHidden, currentHeight, config.position, ready, config.enabled, platform?.autoHide]);

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
    const signal = lifetime.capture();

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
      if (!signal.aborted) setContextMenuVisible(false);
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
      const nextScales: Record<string, number> = {};
      iconRefs.current.forEach((el, id) => {
        const rect = el.getBoundingClientRect();
        nextScales[id] = magnificationScale(Math.abs(rect.left + rect.width / 2 - mouseViewportX), maxScale);
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
    outsideSince.current = null;
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
    setIsHovered(true);
    if (autoHideEnabled) {
      invoke("set_taskbar_autohide_state", {
        hidden: false,
        height: currentHeight,
        position: config.position,
      }).catch(console.error);
    }
  };

  const handleMouseLeave = () => {
    if (autoHideEnabled) {
      if (hideTimer.current) clearTimeout(hideTimer.current);
      hideTimer.current = setTimeout(() => {
        hideTimer.current = null;
        setIsHovered(false);
      }, 500);
    }
  };

  const shuffleBusy = useRef(false);
  const handleShuffle = async () => {
    if (shuffleBusy.current || !platform?.wallpaper) return;
    shuffleBusy.current = true; setOperationError(null); setRetryAction(null);
    const signal = lifetime.capture();
    try { await invoke("shuffle_wallpaper"); if (!signal.aborted) setOperationError(null); }
    catch (error) { if (!signal.aborted) { setOperationError(String(error)); setRetryAction(() => () => { void handleShuffle(); }); } }
    finally { shuffleBusy.current = false; }
  };

  const handleActivateWindow = async (id: string) => {
    if (!platform?.windows.activate) { setOperationError(capabilityReason(platform, "windowActivation", t, platformError)); return; }
    setRetryAction(null); setOperationError(null);
    const signal = lifetime.capture();
    try {
      await invoke("activate_window", { windowId: id });
    } catch (err) {
      if (!signal.aborted) setOperationError(String(err));
      console.error("Failed to activate window", err);
    }
  };

  const handleLaunchApp = async (appId: string, cmd: string) => {
    const signal = lifetime.capture();
    setOperationError(null); setRetryAction(null);
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
      if (signal.aborted) return;
      setOperationError(String(err));
      setRetryAction(() => () => { void handleLaunchApp(appId, cmd); });
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



  const launcherSize = Math.max(28, btnSize - 2);

  // Group windows into Pinned vs Unpinned Running Apps
  const pinnedList = config.pinnedApps || DEFAULT_PINNED_APPS;
  const activePinned = pinnedList.filter((app) => app.enabled !== false);
  const { pinnedItems, unpinnedGroups } = groupWindows(platform?.windows.enumerate ? openWindows : [], activePinned);

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
    if (!ready || !config.enabled || !platform?.dockPlacement || !dockRef.current) return;
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
  }, [ready, config.enabled, platform?.dockPlacement, config.iconSize, config.iconSpacing, config.height, config.showApps, config.showAudio, config.showBattery, config.showNetwork, config.showSystem, config.showClock, config.showStats, config.showShuffle, pinnedItems.length, unpinnedGroups.length]);

  const movePin = async (id: string, target: number) => {
    if (movingPin.current || pinnedList.findIndex((pin) => pin.id === id) === target) return;
    movingPin.current = true;
    const signal = lifetime.capture();
    try {
      if (await mutatePin("move", id, undefined, target)) lifetime.frame(signal, () => {
        if (!document.hidden && !dockRef.current?.classList.contains("dock-autohidden")) iconRefs.current.get(id)?.focus();
      });
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

  const selectWindows = async (e: React.MouseEvent, windows: OpenWindow[], appName: string, appId?: string, installed?: InstalledApp) => {
    const signal = lifetime.capture();
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
        menuData: { mode: "windows", appName, windows, appId, desktopId: installed?.id, iconPath: installed?.iconPath, isPinned: Boolean(appId) },
      });
    } catch (err) {
      if (!signal.aborted) setContextMenuVisible(false);
      console.error("Failed to show window list", err);
    }
  };

  return (
    <div
      className="taskbar-wrapper"
      onContextMenu={(e) => e.preventDefault()}
    >
      {windowsError && !operationError && !configError && <div className="app-status" role="alert"><span className="dock-error-message"><ErrorText error={windowsError} /></span><button onClick={() => setWindowsError(null)}>{t("close")}</button></div>}
      {operationError && <div className="app-status" role="alert"><span className="dock-error-message"><ErrorText error={operationError} /></span> {retryAction && <button onClick={retryAction}>{t("retry")}</button>} <button onClick={() => { setOperationError(null); setRetryAction(null); }}>{t("close")}</button></div>}
      {configError && !operationError && <div className="app-status" role="alert"><span className="dock-error-message"><ErrorText error={configError} /></span><button onClick={configRetry}>{t("retry")}</button></div>}
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
        onFocusCapture={(event) => { tooltip.onFocusCapture(event); keyboardFocus.onFocusCapture(); }}
        onBlurCapture={(event) => { tooltip.onBlurCapture(); keyboardFocus.onBlurCapture(event); }}
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
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              void invoke("show_app_launcher", { iconCenterX: Math.round(rect.left + rect.width / 2) }).catch(console.error);
            }}
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
              const missing = desktopIsMissing(desktopIdForPin(pinned), installed, { loading: appsLoading, error: appsError });
              const launchPinned = () => {
                if (missing) { setOperationError(t("unavailable")); setRetryAction(null); }
                else void handleLaunchApp(pinned.id, launchCommandForPin(pinned));
              };
              const window = windows.find((w) => w.is_active) || windows[0];
              const isRunning = windows.length > 0;
              const isActive = windows.some((w) => w.is_active);
              const isLaunching = launchingAppIds.has(pinned.id);
              const magnifyScale = isMagnifyActive ? (magnifyScales[pinned.id] ?? 1) : 1;

              return (
                <button
                  aria-label={`${pinName(pinned)} • ${platform?.windows.enumerate ? count("window", windows.length) : t("windowStatusUnavailable")}${missing ? ` • ${t("unavailable")}` : ""}`}
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
                  onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); launchPinned(); } }}
                  ref={(el) => {
                    if (el) iconRefs.current.set(pinned.id, el);
                    else iconRefs.current.delete(pinned.id);
                  }}
                  className={`running-app-icon-btn ${isRunning ? "app-running" : "app-idle"} ${missing ? "app-unavailable" : ""} ${
                    isActive ? "app-active" : ""
                  } ${isLaunching ? "app-launching" : ""} ${draggingId === pinned.id ? "is-dragging" : ""} ${dropTargetId === pinned.id ? "is-drop-target" : ""}`}
                  onClick={(e) => {
                    if (Date.now() < suppressClickUntil.current) return;
                    if (window) {
                      void selectWindows(e, windows, pinName(pinned), pinned.id, installed);
                    } else {
                      launchPinned();
                    }
                  }}
                  onContextMenu={(e) =>
                    openContextMenu(e, {
                      desktopId: desktopIdForPin(pinned) ?? installed?.id,
                      windows,
                      matchClasses: pinned.matchClasses,
                      iconPath: installed?.iconPath,
                      pinIndex: pinnedList.findIndex((app) => app.id === pinned.id),
                      pinCount: pinnedList.length,
                      appId: pinned.id,
                      appName: pinName(pinned),
                      command: launchCommandForPin(pinned),
                      windowId: window?.id,
                      isPinned: true,
                      isRunning,
                    })
                  }
                  data-dock-tooltip={
                    missing ? `${pinName(pinned)} • ${t("unavailable")}` : window
                      ? `${pinName(pinned)} • ${count("window", windows.length)} • ${t("selectWindow")}`
                      : `${pinName(pinned)} • ${platform?.windows.enumerate ? t("open") : t("windowStatusUnavailable")}`
                  }
                  style={dockAppStyle(config, visual, true, isRunning, isActive, magnifyScale)}
                >
                  <DockAppTile visual={visual} iconPath={installed?.iconPath} glyphSize={Math.round(btnSize * .68)}
                    running={isRunning} active={isActive} count={windows.length} missing={missing}
                    bouncing={isLaunching && config.bouncingLaunch !== false && !reducedMotion}
                    shadow={isLaunching && config.dynamicShadow !== false && !reducedMotion} />
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
                const installed = installedForClass(win.class_name, installedApps);
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
                    onClick={(e) => void selectWindows(e, windows, win.class_name, undefined, installed)}
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
                    style={dockAppStyle(config, visual, false, true, isActive, magnifyScale)}
                  >
                    <DockAppTile visual={visual} iconPath={installed?.iconPath} glyphSize={Math.round(btnSize * .68)}
                      running active={isActive} count={windows.length} />
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
          {config.showStats && <DockStats stats={stats} accentColor={config.accentColor} />}

          {/* Wallpaper quick shuffle */}
          {config.showShuffle && (
            <button
              className="dock-action-btn"
              onClick={handleShuffle}
              disabled={!platform?.wallpaper}
              aria-label={t("shuffle")}
              data-dock-tooltip={platform?.wallpaper ? t("shuffle") : capabilityReason(platform, "wallpaper", t, platformError)}
            >
              <Shuffle size={14} />
            </button>
          )}

          {config.showAudio && <button className="dock-action-btn" aria-label={t("audio")} data-dock-tooltip={t("audio")} onClick={(e) => {
            const signal = lifetime.capture();
            const rect = e.currentTarget.getBoundingClientRect();
            void invoke("show_dock_context_menu", { iconCenterX: Math.round(rect.left + rect.width / 2), menuData: { mode: "audio", appName: t("audio") } }).catch((error) => { if (!signal.aborted) setOperationError(String(error)); });
          }}><Volume2 size={16} /></button>}

          <SystemWidgets enabled={!isHidden} onError={setOperationError} />

          {/* Clock & Date */}
          {config.showClock && (
            <button
              type="button"
              aria-label={t("calendar")}
              aria-describedby="dock-clock-time dock-clock-date"
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
              <span id="dock-clock-time" className="clock-time">{time}</span>
              <span id="dock-clock-date" className="clock-date">{date}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
