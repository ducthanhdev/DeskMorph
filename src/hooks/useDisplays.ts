import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "../ipc";
import { errorMessage, normalizeCommandError } from "../commandError";
import type { DisplayState } from "../displays/types";

/** Subscribe before initial read; sequence prevents delayed reads replacing newer events. */
export function useDisplays() {
  const [state, setState] = useState<DisplayState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let disposed = false;
    let latest: DisplayState | null = null;
    let loading = false, pending = false;
    let received = 0;
    const stops: (() => void)[] = [];
    const accept = (next: DisplayState) => {
      if (disposed || latest && next.epoch === latest.epoch && next.sequence < latest.sequence) return;
      latest = next; setState(next); setError(null);
    };
    const load = async () => {
      if (disposed) return;
      if (loading) { pending = true; return; }
      loading = true;
      const generationBefore = received;
      try {
        const next = await invoke<DisplayState>("get_display_state");
        // A process epoch cannot change within this WebView. If a newer epoch
        // arrived while reading, keep that event rather than reviving an old one.
        if (received === generationBefore || latest && next.epoch === latest.epoch && next.sequence > latest.sequence) accept(next);
      } catch (failure) {
        if (!disposed && received === generationBefore) { setState(null); setError(errorMessage(failure)); }
      } finally {
        loading = false;
        if (pending && !disposed) { pending = false; void load(); }
      }
    };
    const subscribe = async () => {
      try {
        for (const [event, callback] of [
          ["deskmorph:display-state", (event: { payload: DisplayState }) => { received++; accept(event.payload); }],
          ["deskmorph:display-read-error", (event: { payload: { code: string; message: string } }) => {
            received++;
            if (!disposed) { setState(null); setError(normalizeCommandError("get_display_state", event.payload).toString()); }
          }],
        ] as const) {
          // Payload type differs between the two subscriptions.
          const stop = await listen(event, callback as (event: { payload: unknown }) => void);
          if (disposed) { stop(); return; }
          stops.push(stop);
        }
        await load();
      } catch (failure) {
        if (!disposed) { setState(null); setError(errorMessage(failure)); }
      }
    };
    void subscribe();
    return () => { disposed = true; stops.forEach(stop => stop()); };
  }, [revision]);
  return { state, error, refresh: () => setRevision(value => value + 1) };
}
