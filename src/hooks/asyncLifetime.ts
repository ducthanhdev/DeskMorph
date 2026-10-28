/** Consumers can stop observing an IPC result without pretending to cancel it. */
export class AsyncLifetime {
  private controller = new AbortController();
  private frames = new Set<number>();
  constructor(
    private requestFrame: typeof requestAnimationFrame = (callback) => requestAnimationFrame(callback),
    private cancelFrame: typeof cancelAnimationFrame = (id) => cancelAnimationFrame(id),
  ) {}
  capture() { return this.controller.signal; }
  start() { this.stop(); this.controller = new AbortController(); }
  stop() {
    this.controller.abort();
    this.frames.forEach((id) => this.cancelFrame(id));
    this.frames.clear();
  }
  frame(signal: AbortSignal, callback: () => void) {
    if (signal.aborted) return;
    const id = this.requestFrame(() => {
      this.frames.delete(id);
      if (!signal.aborted) callback();
    });
    this.frames.add(id);
  }
}

/** close must address the opening generation; an old task cannot close a new popup. */
export async function completePopupAction(task: () => Promise<unknown>, close: () => Promise<boolean>, signal: AbortSignal) {
  if (signal.aborted) return false;
  const result = await task();
  if (signal.aborted || result === false) return false;
  return close();
}
