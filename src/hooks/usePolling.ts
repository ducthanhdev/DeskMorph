import { useEffect, useRef } from "react";
import { startPolling } from "./polling";

/** One request per hook, including StrictMode remounts and enabled-state changes. */
export function usePolling(task: (signal: AbortSignal) => Promise<void>, interval: number, enabled = true) {
  const taskRef = useRef(task);
  const inFlight = useRef<Promise<void> | null>(null);
  taskRef.current = task;
  useEffect(() => {
    if (!enabled) return;
    return startPolling(() => taskRef.current, interval, inFlight);
  }, [interval, enabled]);
}
