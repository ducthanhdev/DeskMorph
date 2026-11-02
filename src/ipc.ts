import { invoke as nativeInvoke, type InvokeArgs, type InvokeOptions } from "@tauri-apps/api/core";
import { normalizeCommandError } from "./commandError";

export async function invoke<T>(command: string, args?: InvokeArgs, options?: InvokeOptions): Promise<T> {
  const isBrowserDev = typeof window !== "undefined" && !("__TAURI_INTERNALS__" in window);
  if (isBrowserDev) {
    const handler = (window as unknown as { __BROWSER_INVOKE__?: (cmd: string, a?: unknown) => unknown }).__BROWSER_INVOKE__;
    if (handler) {
      try {
        const res = handler(command, args);
        if (res !== undefined) return res as T;
      } catch {}
    }
  }
  try { return await nativeInvoke<T>(command, { ...args, sourceDock: new URLSearchParams(window.location.search).get("dock") ?? undefined }, options); }
  catch (error) { throw normalizeCommandError(command, error); }
}
