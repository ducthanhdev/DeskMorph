import { useCallback, useEffect, useState } from "react";
import { invoke } from "../ipc";
import { listen } from "@tauri-apps/api/event";
import { errorMessage } from "../config/store";
import type { InstalledApp } from "../types";

export function useInstalledApps() {
  const [apps, setApps] = useState<InstalledApp[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const refresh = useCallback(() => setRefreshIndex((i) => i + 1), []);
  useEffect(() => {
    let disposed = false;
    let stop: (() => void) | undefined;
    let loadingRequest = false;
    let pending = false;
    const load = async (force = false) => {
      if (loadingRequest) { pending = true; return; }
      loadingRequest = true;
      try {
        const result = await invoke<InstalledApp[]>("get_installed_apps", { refresh: force });
        if (!disposed) { setApps(result); setError(null); }
      } catch (e) { if (!disposed) setError(errorMessage(e)); }
      finally {
        loadingRequest = false;
        if (!disposed) {
          setLoading(false);
          if (pending) { pending = false; void load(); }
        }
      }
    };
    setLoading(true);
    void load(refreshIndex > 0);
    listen("deskmorph:apps-changed", () => { if (!disposed) void load(); })
      .then((unlisten) => { if (disposed) unlisten(); else stop = unlisten; }).catch((e) => { if (!disposed) setError(errorMessage(e)); });
    return () => { disposed = true; stop?.(); };
  }, [refreshIndex]);
  return { apps, loading, error, refresh };
}
