import { describeError } from "./i18n/errors";
import { ErrorText } from "./components/ErrorText";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { usePopupFocus } from "./hooks/usePopupFocus";
import { invoke } from "./ipc";
import { listen } from "@tauri-apps/api/event";
import { ArrowLeft, ArrowRight, Flame, Pin, PinOff, Plus, X } from "lucide-react";
import { useConfig, errorMessage } from "./config/store";
import { capabilityReason } from "./capabilities";
import { usePlatform } from "./hooks/usePlatform";
import { useInstalledApps } from "./hooks/useInstalledApps";
import { useI18n } from "./i18n/useI18n";
import { SystemPopup } from "./components/SystemPopup";
import { AudioPopup } from "./components/AudioPopup";
import { AppLauncher } from "./components/AppLauncher";
import { WindowList } from "./components/WindowList";
import { AppIcon } from "./components/AppIcon";
import { useAsyncLifetime } from "./hooks/useAsyncLifetime";
import { desktopIsMissing } from "./appSearch";
import { useLiveWindows } from "./hooks/useLiveWindows";
import type { DockContextMenuState, PinnedApp } from "./types";

function ContextActions({ menu }: { menu: DockContextMenuState }) {
  const lifetime = useAsyncLifetime();
  const { platform, error: platformError } = usePlatform();
  const { t, pinName, language } = useI18n();
  const { config, mutatePin, error: configError } = useConfig();
  const { apps, loading, error: catalogueError } = useInstalledApps();
  const installed = apps.find((app) => app.id === menu.desktopId);
  const missing = desktopIsMissing(menu.desktopId, installed, { loading, error: catalogueError });
  const { windows, refreshError, active } = useLiveWindows(menu);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmKill, setConfirmKill] = useState(false);
  const feedbackId = useId();
  const warningId = useId();
  const announcedError = useRef<string | null>(null);
  useEffect(() => {
    if (!error) { announcedError.current = null; return; }
    if (!active || menu.popupGeneration == null || lifetime.capture().aborted) return;
    const summary = describeError(language, error).summary;
    const key = `${menu.popupGeneration}:${summary}`;
    if (announcedError.current === key) return;
    announcedError.current = key;
    // WebKitGTK's AT-SPI backend can expose the text without emitting its
    // live-region event. Use the owned native window's standard ATK signal.
    // The backend rejects stale generations/blurred windows; DOM feedback and
    // source focus remain available even when this API is unsupported.
    void invoke("announce_accessibility", { message: summary, generation: menu.popupGeneration }).catch(() => {});
  }, [active, error, language, lifetime, menu.popupGeneration]);
  const root = useRef<HTMLElement>(null);
  const changing = useRef(false);
  const forceButton = useRef<HTMLButtonElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const returnToForce = useRef(false);
  const focus = usePopupFocus(root, active, busy, () =>
    (returnToForce.current ? forceButton.current : null) ?? root.current?.querySelector<HTMLButtonElement>("button:not(:disabled)") ?? null);
  useLayoutEffect(() => {
    const restore = returnToForce.current;
    if (!confirmKill) returnToForce.current = false;
    if (!document.hasFocus()) return;
    if (confirmKill && document.activeElement === forceButton.current) cancelButton.current?.focus();
    if (!confirmKill && restore) {
      if (document.activeElement === document.body) forceButton.current?.focus();
    }
  }, [confirmKill]);
  const pinIndex = config.pinnedApps?.findIndex((pin) => pin.id === menu.appId) ?? -1;
  const pinned = config.pinnedApps?.find(pin => pin.id === menu.appId);
  const appName = pinned ? pinName(pinned) : menu.appName;
  const hide = () => invoke("hide_dock_context_menu", { generation: menu.popupGeneration });
  useEffect(() => { root.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus(); }, []);
  const perform = async (task: () => Promise<unknown>, close = true) => {
    if (changing.current) return;
    changing.current = true;
    announcedError.current = null;
    const signal = lifetime.capture();
    setBusy(true); setError(null);
    try { const result = await task(); if (close && result !== false && !signal.aborted) await hide(); }
    catch (e) { if (!signal.aborted) setError(errorMessage(e)); }
    finally { changing.current = false; if (!signal.aborted) setBusy(false); }
  };
  const togglePin = async () => {
    const id = menu.appId || menu.desktopId;
    if (!id) { setError(t("identifyApp")); return; }
    const pin: PinnedApp = {
      id, desktopId: menu.desktopId, name: menu.appName,
      command: menu.desktopId ? `desktop:${menu.desktopId}` : menu.command || id,
      matchClasses: menu.matchClasses || [id], iconType: "custom", enabled: true,
    };
    await perform(() => mutatePin(menu.isPinned ? "remove" : "add", id, pin));
  };
  return <section ref={root} {...focus} className="context-actions" aria-label={`${t("details")} ${appName}`} onContextMenu={(e) => e.preventDefault()}
    onKeyDown={(e) => {
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const buttons = Array.from(root.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") || []);
      const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
      const next = e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1 : (index + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next]?.focus();
    }}>
    <header><AppIcon path={menu.iconPath} /><strong>{appName}</strong></header>
    {!platform?.windows.enumerate && <p role="status">{capabilityReason(platform, "windowEnumeration", t, platformError)}</p>}
    {missing && <p role="status">{t("unavailable")}</p>}
    {catalogueError && <p role="alert"><ErrorText error={catalogueError} /></p>}
    <div id={`${feedbackId}-region`} role="alert" aria-live="assertive" aria-atomic="true">
      {(error || configError || refreshError) && <p><ErrorText error={error || configError || refreshError!} summaryId={feedbackId} /></p>}
    </div>
    {(menu.command || installed) && <button aria-describedby={error ? feedbackId : undefined} disabled={busy || missing} onClick={() => void perform(() => menu.command ? invoke("spawn_app", { execCmd: menu.command }) : invoke("launch_installed_app", { id: installed!.id, action: null }))}><Plus size={16} /> {t("newLaunch")}</button>}
    <button disabled={busy || (!menu.isPinned && !menu.desktopId)} onClick={() => void togglePin()}>{menu.isPinned ? <PinOff size={16} /> : <Pin size={16} />}{menu.isPinned ? t("unpin") : t("pin")}</button>
    {menu.isPinned && pinIndex >= 0 && <div className="context-reorder">
      <button disabled={busy || pinIndex === 0} onClick={() => void perform(() => mutatePin("move", menu.appId!, undefined, pinIndex - 1))}><ArrowLeft size={14} /> {t("moveLeft")}</button>
      <button disabled={busy || pinIndex === (config.pinnedApps?.length || 0) - 1} onClick={() => void perform(() => mutatePin("move", menu.appId!, undefined, pinIndex + 1))}>{t("moveRight")} <ArrowRight size={14} /></button>
    </div>}
    {installed?.actions.map((action) => <button key={action.id} disabled={busy} onClick={() => void perform(() => invoke("launch_installed_app", { id: installed.id, action: action.id }))}><Plus size={16} />{action.name}</button>)}
    {Boolean(windows.length) && <div className="context-window-items" aria-label={t("windows")}>
      {windows.map((window) => <div key={window.id} className={`context-window-row ${window.is_active ? "is-active" : ""}`}>
        <button disabled={busy || !platform?.windows.activate} title={platform?.windows.activate ? window.title : capabilityReason(platform, "windowActivation", t, platformError)} onClick={() => { if (platform?.windows.activate) void perform(() => invoke("activate_window", { windowId: window.id })); }}>{window.title}</button>
        <button disabled={busy || !platform?.windows.close} title={platform?.windows.close ? t("close") : capabilityReason(platform, "windowClose", t, platformError)} aria-label={`${t("close")} ${window.title}`} onClick={() => { if (platform?.windows.close) void perform(() => invoke("close_window", { xid: window.id })); }}><X size={14} /></button>
      </div>)}
    </div>}
    {menu.windowId && windows.some((window) => window.id === menu.windowId) && <>
      <button ref={forceButton} className="context-danger" title={platform?.forceQuit ? undefined : capabilityReason(platform, "forceQuit", t, platformError)} disabled={busy || !platform?.forceQuit} onClick={() => setConfirmKill(true)}><Flame size={16} /> {t("forceQuit")}</button>
      {confirmKill && <div className="context-confirm" role="alertdialog" aria-label={t("forceQuit")} aria-describedby={warningId}>
        <p id={warningId}>{t("forceWarning")}</p>
        <button ref={cancelButton} aria-describedby={warningId} disabled={busy} onClick={() => { returnToForce.current = document.hasFocus() && document.activeElement === cancelButton.current; setConfirmKill(false); }}>{t("cancel")}</button>
        <button className="context-danger" aria-describedby={warningId} disabled={busy || !platform?.forceQuit} onClick={() => { if (platform?.forceQuit) void perform(() => invoke("force_kill_window", { xid: menu.windowId })); }}>{t("forceConfirm")}</button>
      </div>}
    </>}
  </section>;
}

export const DockContextMenuStandalone = () => {
  const [menu, setMenu] = useState<DockContextMenuState | null>(null);
  useEffect(() => {
    let disposed = false;
    let stop: (() => void) | undefined;
    listen<DockContextMenuState>("deskmorph:context-menu-data", (event) => { if (!disposed) setMenu(event.payload); })
      .then((unlisten) => {
        if (disposed) unlisten();
        else { stop = unlisten; void invoke("launcher_surface_ready").catch(console.error); }
      }).catch(console.error);
    // Native coordinator owns Escape and focus loss, using the active generation.
    return () => { disposed = true; stop?.(); };
  }, []);
  if (!menu) return null;
  if (menu.mode === "system") return <SystemPopup key={menu.popupGeneration} generation={menu.popupGeneration} />;
  if (menu.mode === "audio") return <AudioPopup key={menu.popupGeneration} generation={menu.popupGeneration} />;
  if (menu.mode === "launcher") return <AppLauncher key={menu.popupGeneration} generation={menu.popupGeneration} />;
  if (menu.mode === "windows") return <WindowList key={menu.popupGeneration} menu={menu} />;
  return <ContextActions key={menu.popupGeneration} menu={menu} />;
};
