import { useLayoutEffect, useRef, type FocusEvent, type RefObject } from "react";

/** Keep keyboard position across disabled requests and disappearing popup controls. */
export function usePopupFocus(root: RefObject<HTMLElement | null>, active: boolean, busy: boolean, fallback?: () => HTMLElement | null) {
  const origin = useRef<HTMLElement | null>(null);
  const recovering = useRef(false);
  const onFocusCapture = (event: FocusEvent<HTMLElement>) => {
    const target = event.target as HTMLElement;
    // Nested media controls own their request state and focus recovery.
    origin.current = target.closest("[data-popup-focus-scope]") === root.current ? target : null;
    recovering.current = false;
  };
  useLayoutEffect(() => {
    if (!active) { origin.current = null; recovering.current = false; return; }
    const previous = origin.current;
    if (!previous) return;
    const removed = !previous.isConnected;
    const disabled = previous.matches(":disabled");
    if (removed || disabled) recovering.current = true;
    if (!recovering.current || busy) return;
    origin.current = null; recovering.current = false;
    // Native blur and an explicit move to another control always win.
    if (!document.hasFocus() || document.activeElement !== document.body) return;
    const destination = removed || disabled
      ? fallback?.() ?? root.current?.closest(".audio-popup")?.querySelector<HTMLButtonElement>("header button:not(:disabled)")
      : previous;
    destination?.focus();
  });
  return { "data-popup-focus-scope": true, onFocusCapture };
}
