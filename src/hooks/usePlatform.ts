import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "../ipc";
import { errorMessage } from "../config/store";
export interface PlatformInfo {
  session: string; desktop: string; windowManagement: boolean; wallpaper: boolean;
  forceQuit: boolean;
  dockPlacement: boolean; autoHide: boolean;
  unavailableReasons: Partial<Record<"dockPlacement" | "autoHide" | "windowEnumeration" | "windowActivation" | "windowClose" | "forceQuit" | "wallpaper" | "workspaces", string>>;
  windows: { enumerate: boolean; activate: boolean; close: boolean };
  workspaces: boolean; reasons: string[];
  monitors: { primary: boolean; name: string; x: number; y: number; width: number; height: number; scale: number }[];
}
export function usePlatform() {
  const [platform, setPlatform] = useState<PlatformInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let disposed = false;
    let stop: (() => void) | undefined;
    let loading = false;
    let pending = false;
    const load = async () => {
      if (disposed) return;
      if (loading) { pending = true; return; }
      loading = true;
      try {
        const value = await invoke<PlatformInfo>("get_platform_info");
        if (!disposed) { setPlatform(value); setError(null); }
      } catch (e) { if (!disposed) { setPlatform(null); setError(errorMessage(e)); } }
      finally {
        loading = false;
        if (pending && !disposed) { pending = false; void load(); }
      }
    };
    void load();
    listen("deskmorph:platform-changed", load).then((unlisten) => { if (disposed) unlisten(); else stop = unlisten; }).catch((e) => {
      const isBrowser = typeof window !== "undefined" && !("__TAURI_INTERNALS__" in window);
      if (!disposed && !isBrowser) setError(errorMessage(e));
    });
    return () => { disposed = true; stop?.(); };
  }, [reload]);
  const refresh = () => {
    setReload((value) => value + 1);
    // The local reload also recovers a listener that failed to register.
    // Native broadcast lets other WebViews re-probe without polling.
    void invoke("refresh_platform_info").catch(console.error);
  };
  return { platform, error, refresh };
}
