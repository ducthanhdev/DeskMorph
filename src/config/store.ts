import { invoke } from "../ipc";
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

export { errorMessage } from "../commandError";
import { CommandError, errorMessage } from "../commandError";
let retryInFlight = false;
let retryOperation: (() => Promise<boolean>) | null = null;
function setState(next: State) { state = next; listeners.forEach((fn) => fn()); }
function accept(snapshot: ConfigSnapshot) {
  if (snapshot.revision >= state.revision) setState({ ...snapshot, ready: true, error: state.error });
}
function report(error: unknown, retry?: () => Promise<boolean>) {
  // A persisted mutation must reapply the native state, never replay a toggle/move/import.
  retryOperation = error instanceof CommandError && error.context.persisted === true
    ? () => perform(() => invoke<ConfigSnapshot>("retry_config_apply")) : error instanceof CommandError && error.code === "config_conflict" ? null : retry ?? null;
  setState({ ...state, error: errorMessage(error) });
}
async function perform(operation: (expectedRevision?: number) => Promise<ConfigSnapshot>, expectedRevision?: number): Promise<boolean> {
  const baseRevision = expectedRevision ?? state.revision;
  try {
    const snapshot = await operation(expectedRevision);
    retryOperation = null; accept(snapshot); setState({ ...state, error: null }); return true;
  } catch (error) { report(error, () => perform(operation, baseRevision)); return false; }
}
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
      if (!disposed) { accept(snapshot); if (!retryOperation) setState({ ...state, error: null }); }
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
  if (!state.ready) { report(new CommandError("config_not_ready", "Configuration is still loading", "patch_config")); return false; }
  return perform((expectedRevision) => invoke<ConfigSnapshot>("patch_config", { patch, expectedRevision }));
}
export async function mutatePin(action: "add" | "remove" | "toggleEnabled" | "move" | "setClasses", id: string, pin?: PinnedApp | Pick<PinnedApp, "matchClasses">, target?: number) {
  if (!state.ready) { report(new CommandError("config_not_ready", "Configuration is still loading", "mutate_pin")); return false; }
  return perform((expectedRevision) => invoke<ConfigSnapshot>("mutate_pin", { action, id, pin: pin ?? null, target: target ?? null, expectedRevision }));
}
export async function replaceConfigDocument(document: unknown, expectedRevision: number) {
  return perform(() => invoke<ConfigSnapshot>("replace_config_document", { document, expectedRevision }));
}
export function useConfig() {
  const snapshot = useSyncExternalStore(subscribe, () => state);
  return { ...snapshot, updateConfig, mutatePin, replaceConfigDocument, retry: () => { if (retryOperation) { if (!retryInFlight) { retryInFlight = true; void retryOperation().finally(() => { retryInFlight = false; }); } } else { disconnect?.(); disconnect = connect(); } } };
}
