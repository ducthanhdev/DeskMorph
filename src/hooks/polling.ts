type Task = (signal: AbortSignal) => Promise<void>;
export type PollingRequest = { current: Promise<void> | null };
type Visibility = Pick<Document, "hidden" | "addEventListener" | "removeEventListener">;

/** A single timer owner; a new effect waits for the previous native request. */
export function startPolling(
  getTask: () => Task,
  interval: number,
  inFlight: PollingRequest,
  visibility: Visibility = document,
) {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let running = false;
  const clearTimer = () => { if (timer !== undefined) clearTimeout(timer); timer = undefined; };
  const run = async () => {
    clearTimer();
    if (running || controller.signal.aborted || visibility.hidden) return;
    running = true;
    try {
      // An aborted effect cannot cancel an already dispatched native IPC call.
      // Await it instead of spawning retry timers or overlapping that request.
      if (inFlight.current) await inFlight.current.catch(() => {});
      if (controller.signal.aborted || visibility.hidden) return;
      const request = Promise.resolve().then(() => controller.signal.aborted ? undefined : getTask()(controller.signal));
      inFlight.current = request;
      try { await request; }
      finally { if (inFlight.current === request) inFlight.current = null; }
    } catch (error) {
      if (!controller.signal.aborted) console.error(error);
    } finally {
      running = false;
      if (!controller.signal.aborted && !visibility.hidden) timer = setTimeout(run, interval);
    }
  };
  const onVisibility = () => {
    clearTimer();
    if (!visibility.hidden) void run();
  };
  visibility.addEventListener("visibilitychange", onVisibility);
  void run();
  return () => {
    controller.abort();
    clearTimer();
    visibility.removeEventListener("visibilitychange", onVisibility);
  };
}
