import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useSyncExternalStore } from "react";
import { DEFAULT_CONFIG, type PinnedApp, type TaskbarConfig } from "../types";

export interface ConfigSnapshot {
  schemaVersion: number;
  revision: number;
  config: TaskbarConfig;
  warning: string | null;
}
interface State { config: TaskbarConfig; revision: number; ready: boolean; error: string | null; warning: string | null }
let state: State = { config: DEFAULT_CONFIG, revision: -1, ready: false, error: null, warning: null };
const listeners = new Set<() => void>();
let disconnect: (() => void) | undefined;

export function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) return String(error.message);
  return String(error);
}
function setState(next: State) { state = next; listeners.forEach((fn) => fn()); }
function accept(snapshot: ConfigSnapshot) {
  if (snapshot.revision >= state.revision) setState({ ...snapshot, ready: true, error: null });
}
function report(error: unknown) { setState({ ...state, error: errorMessage(error) }); }
function connect() {
  let disposed = false;
  let unlisten: (() => void) | undefined;
  const start = async () => {
    try {
      const stop = await listen<ConfigSnapshot>("deskmorph:config-snapshot", (event) => {
        if (!disposed) accept(event.payload);
      });
      if (disposed) { stop(); return; }
      unlisten = stop;
      let legacy: unknown = null;
      let raw: string | null = null;
      try {
        raw = localStorage.getItem("deskmorph_config");
        if (raw) legacy = JSON.parse(raw);
      } catch { legacy = raw; /* Native migration reports invalid JSON while retaining the original. */ }
      const snapshot = await invoke<ConfigSnapshot>("get_config", { legacy });
      if (!disposed) accept(snapshot);
    } catch (error) { if (!disposed) report(error); }
  };
  void start();
  return () => { disposed = true; unlisten?.(); };
}
function subscribe(fn: () => void) {
  listeners.add(fn);
  if (listeners.size === 1) disconnect = connect();
  return () => {
    listeners.delete(fn);
    if (!listeners.size) { disconnect?.(); disconnect = undefined; }
  };
}
async function updateConfig(patch: Partial<TaskbarConfig>) {
  if (!state.ready) { report("Cấu hình chưa tải xong; hãy thử lại"); return false; }
  try { accept(await invoke<ConfigSnapshot>("patch_config", { patch })); return true; }
  catch (error) { report(error); return false; }
}
export async function mutatePin(action: "add" | "remove" | "toggleEnabled" | "move", id: string, pin?: PinnedApp, target?: number) {
  if (!state.ready) { report("Cấu hình chưa tải xong; hãy thử lại"); return false; }
  try {
    accept(await invoke<ConfigSnapshot>("mutate_pin", { action, id, pin: pin ?? null, target: target ?? null }));
    return true;
  } catch (error) { report(error); return false; }
}
export async function replaceConfigDocument(document: unknown, expectedRevision: number) {
  try {
    accept(await invoke<ConfigSnapshot>("replace_config_document", { document, expectedRevision }));
    return true;
  } catch (error) { report(error); return false; }
}
export function useConfig() {
  const snapshot = useSyncExternalStore(subscribe, () => state);
  return { ...snapshot, updateConfig, mutatePin, replaceConfigDocument, retry: () => { disconnect?.(); disconnect = connect(); } };
}
