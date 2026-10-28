import { useState } from "react";
import { usePolling } from "./usePolling";

/** Local clock updates use the same visibility/cleanup rules as other UI work. */
export function useClock(enabled: boolean) {
  const [now, setNow] = useState(() => new Date());
  usePolling(async (signal) => { if (!signal.aborted) setNow(new Date()); }, 1000, enabled);
  return now;
}
