import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { ArrowLeft, ArrowRight, Flame, Pin, PinOff, Plus, X } from "lucide-react";
import { useConfig, errorMessage } from "./config/store";
import { usePlatform } from "./hooks/usePlatform";
import { useInstalledApps } from "./hooks/useInstalledApps";
import { useI18n } from "./i18n/useI18n";
import { SystemPopup } from "./components/SystemPopup";
import { AudioPopup } from "./components/AudioPopup";
import { AppLauncher } from "./components/AppLauncher";
import { WindowList } from "./components/WindowList";
import { AppIcon } from "./components/AppIcon";
import { useAsyncLifetime } from "./hooks/useAsyncLifetime";
import { useLiveWindows } from "./hooks/useLiveWindows";
import type { DockContextMenuState, PinnedApp } from "./types";

function ContextActions({ menu }: { menu: DockContextMenuState }) {
  const lifetime = useAsyncLifetime();
  const { platform } = usePlatform();
  const { t } = useI18n();
  const { config, mutatePin, error: configError } = useConfig();
  const { apps } = useInstalledApps();
  const installed = apps.find((app) => app.id === menu.desktopId);
  const { windows, refreshError } = useLiveWindows(menu);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmKill, setConfirmKill] = useState(false);
  const root = useRef<HTMLElement>(null);
  const pinIndex = config.pinnedApps?.findIndex((pin) => pin.id === menu.appId) ?? -1;
  const hide = () => invoke("hide_dock_context_menu", { generation: menu.popupGeneration });
  useEffect(() => { root.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus(); }, []);
  const perform = async (task: () => Promise<unknown>, close = true) => {
    if (busy) return;
    const signal = lifetime.capture();
    setBusy(true); setError(null);
    try { const result = await task(); if (close && result !== false && !signal.aborted) await hide(); }
    catch (e) { if (!signal.aborted) setError(errorMessage(e)); }
    finally { if (!signal.aborted) setBusy(false); }
  };
  const togglePin = async () => {
    const id = menu.appId || menu.desktopId;
    if (!id) { setError(t("identifyApp")); return; }
    const pin: PinnedApp = {
      id, desktopId: menu.desktopId, name: menu.appName,
      command: menu.desktopId ? `desktop:${menu.desktopId}` : menu.command || id,
      matchClasses: menu.matchClasses || [id], iconType: "custom", enabled: true,
    };
    const signal = lifetime.capture();
    if (await mutatePin(menu.isPinned ? "remove" : "add", id, pin) && !signal.aborted) await hide();
  };
  return <section ref={root} className="context-actions" aria-label={`${t("details")} ${menu.appName}`} onContextMenu={(e) => e.preventDefault()}
    onKeyDown={(e) => {
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const buttons = Array.from(root.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") || []);
      const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
      const next = e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1 : (index + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next]?.focus();
    }}>
    <header><AppIcon path={menu.iconPath} /><strong>{menu.appName}</strong></header>
    {(error || configError || refreshError) && <p role="alert">{error || configError || `${t("refreshWindowsError")}: ${refreshError}`}</p>}
    {(menu.command || installed) && <button disabled={busy} onClick={() => void perform(() => installed ? invoke("launch_installed_app", { id: installed.id, action: null }) : invoke("spawn_app", { execCmd: menu.command }))}><Plus size={16} /> {t("newLaunch")}</button>}
    <button disabled={busy || (!menu.isPinned && !menu.desktopId)} onClick={() => void togglePin()}>{menu.isPinned ? <PinOff size={16} /> : <Pin size={16} />}{menu.isPinned ? t("unpin") : t("pin")}</button>
    {menu.isPinned && pinIndex >= 0 && <div className="context-reorder">
      <button disabled={busy || pinIndex === 0} onClick={() => void perform(() => mutatePin("move", menu.appId!, undefined, pinIndex - 1))}><ArrowLeft size={14} /> {t("moveLeft")}</button>
      <button disabled={busy || pinIndex === (config.pinnedApps?.length || 0) - 1} onClick={() => void perform(() => mutatePin("move", menu.appId!, undefined, pinIndex + 1))}>{t("moveRight")} <ArrowRight size={14} /></button>
    </div>}
    {installed?.actions.map((action) => <button key={action.id} disabled={busy} onClick={() => void perform(() => invoke("launch_installed_app", { id: installed.id, action: action.id }))}><Plus size={16} />{action.name}</button>)}
    {Boolean(windows.length) && <div className="context-window-items" aria-label={t("windows")}>
      {windows.map((window) => <div key={window.id} className={`context-window-row ${window.is_active ? "is-active" : ""}`}>
        <button disabled={busy || !platform?.windows.activate} title={platform?.windows.activate ? window.title : t("activateUnavailable")} onClick={() => void perform(() => invoke("activate_window", { windowId: window.id }))}>{window.title}</button>
        <button disabled={busy || !platform?.windows.close} title={platform?.windows.close ? t("close") : t("closeUnavailable")} aria-label={`${t("close")} ${window.title}`} onClick={() => void perform(() => invoke("close_window", { xid: window.id }))}><X size={14} /></button>
      </div>)}
    </div>}
    {menu.windowId && windows.some((window) => window.id === menu.windowId) && <>
      <button className="context-danger" title={platform?.forceQuit ? undefined : t("forceUnavailable")} disabled={busy || !platform?.forceQuit} onClick={() => setConfirmKill(true)}><Flame size={16} /> {t("forceQuit")}</button>
      {confirmKill && <div className="context-confirm" role="alert">
        <p>{t("forceWarning")}</p>
        <button disabled={busy} onClick={() => setConfirmKill(false)}>{t("cancel")}</button>
        <button className="context-danger" disabled={busy} onClick={() => void perform(() => invoke("force_kill_window", { xid: menu.windowId }))}>{t("forceConfirm")}</button>
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
      .then((unlisten) => { if (disposed) unlisten(); else stop = unlisten; }).catch(console.error);
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") void invoke("hide_dock_context_menu").catch(console.error); };
    // Native coordinator handles focus loss; duplicating it in DOM blur races with popup replacement.
    window.addEventListener("keydown", onKey);
    return () => { disposed = true; stop?.(); window.removeEventListener("keydown", onKey); };
  }, []);
  if (!menu) return null;
  if (menu.mode === "system") return <SystemPopup key={menu.popupGeneration} generation={menu.popupGeneration} />;
  if (menu.mode === "audio") return <AudioPopup key={menu.popupGeneration} generation={menu.popupGeneration} />;
  if (menu.mode === "launcher") return <AppLauncher key={menu.popupGeneration} generation={menu.popupGeneration} />;
  if (menu.mode === "windows") return <WindowList key={menu.popupGeneration} menu={menu} />;
  return <ContextActions key={menu.popupGeneration} menu={menu} />;
};
