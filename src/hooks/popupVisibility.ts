type Stop = () => void;

/** Register first, query second; only events after query dispatch supersede it. */
export function watchPopupVisibility(
  register: (receive: (visible: boolean) => void) => Promise<Stop>,
  query: () => Promise<boolean>,
  receive: (visible: boolean) => void,
  failure: (error: unknown) => void,
): Stop {
  let disposed = false;
  let events = 0;
  let stop: Stop | undefined;
  void (async () => {
    const unlisten = await register((visible) => {
      if (disposed) return;
      events++;
      receive(visible);
    });
    if (disposed) { unlisten(); return; }
    stop = unlisten;
    const version = events;
    const visible = await query();
    if (!disposed && events === version) receive(visible);
  })().catch((error) => { if (!disposed) failure(error); });
  return () => {
    if (disposed) return;
    disposed = true;
    stop?.();
  };
}
