import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { usePolling } from "./usePolling";
export type SystemStatus = {
  battery: { percentage: number; state: string; remainingSeconds: number | null } | null;
  batteryError: string | null;
  network: { kind: string; state: string; connectivity: string } | null;
  networkError: string | null;
  monitorId: string | null;
  folderAvailable: boolean;
  trashAvailable: boolean;
};
export function useSystemStatus(enabled = true) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  usePolling(async (signal) => {
    try { const value = await invoke<SystemStatus>("get_system_status"); if (!signal.aborted) { setStatus(value); setError(null); } }
    catch (e) { if (!signal.aborted) setError(String(e)); }
  }, 5000, enabled);
  return { status, error };
}
