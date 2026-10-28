import { invoke as nativeInvoke, type InvokeArgs, type InvokeOptions } from "@tauri-apps/api/core";
import { normalizeCommandError } from "./commandError";
export async function invoke<T>(command: string, args?: InvokeArgs, options?: InvokeOptions): Promise<T> {
  try { return await nativeInvoke<T>(command, args, options); }
  catch (error) { throw normalizeCommandError(command, error); }
}
