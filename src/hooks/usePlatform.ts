import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "../ipc";
import { errorMessage } from "../config/store";
export interface PlatformInfo {
  session: string; desktop: string; windowManagement: boolean; wallpaper: boolean;
  forceQuit: boolean;
  windows: { enumerate: boolean; activate: boolean; close: boolean };
  workspaces: boolean; reasons: string[];
  monitors: { name: string; x: number; y: number; width: number; height: number; scale: number }[];
}
export function usePlatform() {
  const [platform, setPlatform] = useState<PlatformInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
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
      } catch (e) { if (!disposed) setError(errorMessage(e)); }
      finally {
        loading = false;
        if (pending && !disposed) { pending = false; void load(); }
      }
    };
    void load();
    listen("deskmorph:platform-changed", load).then((unlisten) => { if (disposed) unlisten(); else stop = unlisten; }).catch((e) => { if (!disposed) setError(errorMessage(e)); });
    return () => { disposed = true; stop?.(); };
  }, []);
  return { platform, error };
}
