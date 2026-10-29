import { useEffect, useRef, useState } from "react";
import { invoke } from "../ipc";
import { X } from "lucide-react";
import type { DockContextMenuState } from "../types";
import { useI18n } from "../i18n/useI18n";
import { errorMessage } from "../config/store";
import { capabilityReason } from "../capabilities";
import { usePlatform } from "../hooks/usePlatform";
import { useAsyncLifetime } from "../hooks/useAsyncLifetime";
import { AppIcon } from "./AppIcon";
import { useInstalledApps } from "../hooks/useInstalledApps";
import { installedForClass } from "../appSearch";
import { useLiveWindows } from "../hooks/useLiveWindows";

export function WindowList({ menu }: { menu: DockContextMenuState }) {
  const lifetime = useAsyncLifetime();
  const { apps } = useInstalledApps();
  const installed = menu.desktopId ? apps.find((app) => app.id === menu.desktopId) : installedForClass(menu.windows?.[0]?.class_name || "", apps);
  const iconPath = installed?.iconPath;
  const { t, count } = useI18n();
  const { platform, error: platformError } = usePlatform();
  const { windows, refreshError, active } = useLiveWindows(menu);
  const [error, setError] = useState("");
  const [closing, setClosing] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState(menu.windows?.find((w) => w.is_active)?.id || menu.windows?.[0]?.id);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const previousWindows = useRef(windows);
  const hide = () => invoke("hide_dock_context_menu", { generation: menu.popupGeneration });

  useEffect(() => {
    const previous = previousWindows.current;
    setSelectedId((id) => {
      if (windows.some((window) => window.id === id)) return id;
      const index = Math.max(0, previous.findIndex((window) => window.id === id));
      return windows[Math.min(index, windows.length - 1)]?.id;
    });
    previousWindows.current = windows;
    if (active && !windows.length) void hide().catch((err) => setError(errorMessage(err)));
  }, [windows, active]);
  useEffect(() => {
    const focusSelected = () => {
      if (active && selectedId && document.hasFocus()) buttons.current.get(selectedId)?.focus();
    };
    focusSelected();
    // Native GTK mapping can grant WebKit focus after the React effect ran.
    window.addEventListener("focus", focusSelected);
    return () => window.removeEventListener("focus", focusSelected);
  }, [selectedId, active]);

  const activate = async (id: string) => {
    if (!platform?.windows.activate) return;
    const signal = lifetime.capture();
    try {
      await invoke("activate_window", { windowId: id });
      if (!signal.aborted) await hide();
    } catch (err) { if (!signal.aborted) setError(`${t("activateWindowError")}: ${errorMessage(err)}`); }
  };
  const close = async (id: string) => {
    if (!platform?.windows.close) return;
    const signal = lifetime.capture();
    setClosing(id); setError("");
    try { await invoke("close_window", { xid: id }); }
    catch (err) { if (!signal.aborted) setError(`${t("closeWindowError")}: ${errorMessage(err)}`); }
    finally { if (!signal.aborted) setClosing(null); }
  };
  return <section className="window-list" aria-label={`${t("windows")} ${menu.appName}`}
    onKeyDown={(e) => {
      if (!windows.length) return;
      const index = Math.max(0, windows.findIndex((w) => w.id === selectedId));
      let next: number;
      switch (e.key) {
        case "ArrowDown": next = (index + 1) % windows.length; break;
        case "ArrowUp": next = (index - 1 + windows.length) % windows.length; break;
        case "Home": next = 0; break;
        case "End": next = windows.length - 1; break;
        default: return;
      }
      e.preventDefault();
      setSelectedId(windows[next]?.id);
    }}>
    <header><AppIcon path={iconPath} size={20} /><strong>{menu.appName}</strong><span>{platform?.windows.enumerate ? count("window", windows.length) : t("windowStatusUnavailable")}</span></header>
    <div className="window-list-items">
      {windows.map((w) => <div key={w.id} className={`window-list-row ${w.is_active ? "is-active" : ""}`}>
        <button className="window-list-select" ref={(el) => { if (el) buttons.current.set(w.id, el); else buttons.current.delete(w.id); }}
          tabIndex={selectedId === w.id ? 0 : -1} aria-disabled={!platform?.windows.activate} onFocus={() => setSelectedId(w.id)} onClick={() => void activate(w.id)} title={platform?.windows.activate ? w.title : capabilityReason(platform, "windowActivation", t, platformError)}>
          <AppIcon path={iconPath} size={18} /><span>{w.title || w.class_name}{w.is_active && <small>{t("running")}</small>}</span>
        </button>
        <button className="window-list-close" disabled={closing === w.id || !platform?.windows.close} onClick={() => void close(w.id)} aria-label={`${t("close")} ${w.title}`} title={platform?.windows.close ? t("close") : capabilityReason(platform, "windowClose", t, platformError)}><X size={16} /></button>
      </div>)}
    </div>
    {(error || refreshError) && <p role="alert">{error || `${t("refreshWindowsError")}: ${refreshError}`}</p>}
    {!platform?.windows.enumerate && <p role="status">{capabilityReason(platform, "windowEnumeration", t, platformError)}</p>}
    {platform && !platform.windows.activate && <p>{capabilityReason(platform, "windowActivation", t, platformError)}</p>}
    {platform && !platform.windows.close && <p>{capabilityReason(platform, "windowClose", t, platformError)}</p>}
  </section>;
}
