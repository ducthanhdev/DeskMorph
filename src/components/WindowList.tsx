import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AppWindow, X } from "lucide-react";
import type { DockContextMenuState, OpenWindow } from "../types";
import { useI18n } from "../i18n/useI18n";
import { errorMessage } from "../config/store";
import { usePlatform } from "../hooks/usePlatform";

export function WindowList({ menu }: { menu: DockContextMenuState }) {
  const { t, count } = useI18n();
  const { platform } = usePlatform();
  const [windows, setWindows] = useState(menu.windows || []);
  const [error, setError] = useState("");
  const [closing, setClosing] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState(menu.windows?.find((w) => w.is_active)?.id || menu.windows?.[0]?.id);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const classes = new Set(menu.windows?.map((w) => w.class_name.toLowerCase()));

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const all = await invoke<OpenWindow[]>("get_open_windows");
        if (disposed) return;
        const remaining = all.filter((w) => classes.has(w.class_name.toLowerCase()));
        setWindows(remaining);
        setSelectedId((id) => remaining.some((w) => w.id === id) ? id : remaining[0]?.id);
        if (!remaining.length) { await invoke("hide_dock_context_menu"); return; }
      } catch (err) { if (!disposed) setError(`${t("refreshWindowsError")}: ${errorMessage(err)}`); }
      if (!disposed) timer = setTimeout(refresh, 1500);
    };
    timer = setTimeout(refresh, 1500);
    return () => { disposed = true; clearTimeout(timer); };
  }, [menu]);
  useEffect(() => { if (selectedId) buttons.current.get(selectedId)?.focus(); }, [selectedId]);

  const activate = async (id: string) => {
    if (!platform?.windows.activate) return;
    try {
      await invoke("activate_window", { windowId: id });
      await invoke("hide_dock_context_menu");
    } catch (err) { setError(`${t("activateWindowError")}: ${errorMessage(err)}`); }
  };
  const close = async (id: string) => {
    if (!platform?.windows.close) return;
    setClosing(id); setError("");
    try { await invoke("close_window", { xid: id }); }
    catch (err) { setError(`${t("closeWindowError")}: ${errorMessage(err)}`); }
    finally { setClosing(null); }
  };
  return <section className="window-list" aria-label={`${t("windows")} ${menu.appName}`}
    onKeyDown={(e) => {
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
    <header><strong>{menu.appName}</strong><span>{count("window", windows.length)}</span></header>
    <div className="window-list-items">
      {windows.map((w) => <div key={w.id} className={`window-list-row ${w.is_active ? "is-active" : ""}`}>
        <button className="window-list-select" ref={(el) => { if (el) buttons.current.set(w.id, el); else buttons.current.delete(w.id); }}
          tabIndex={selectedId === w.id ? 0 : -1} aria-disabled={!platform?.windows.activate} onFocus={() => setSelectedId(w.id)} onClick={() => void activate(w.id)} title={platform?.windows.activate ? w.title : t("activateUnavailable")}>
          <AppWindow size={18} /><span>{w.title || w.class_name}{w.is_active && <small>{t("running")}</small>}</span>
        </button>
        <button className="window-list-close" disabled={closing === w.id || !platform?.windows.close} onClick={() => void close(w.id)} aria-label={`${t("close")} ${w.title}`} title={platform?.windows.close ? t("close") : t("closeUnavailable")}><X size={16} /></button>
      </div>)}
    </div>
    {error && <p role="alert">{error}</p>}
    {platform && !platform.windows.activate && <p>{t("activateUnavailable")}</p>}
    {platform && !platform.windows.close && <p>{t("closeUnavailable")}</p>}
  </section>;
}
