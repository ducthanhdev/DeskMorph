import { useLayoutEffect, useRef, type FocusEvent } from "react";

/** Recover a removed list control, optionally including disabled pagination. */
export function useRemovalFocus(selector = "button[data-remove-focus]:not(:disabled)", recoverDisabled = false, disabledFallbackSelector?: string) {
  const root = useRef<HTMLDivElement>(null);
  const fallback = useRef<HTMLInputElement>(null);
  const origin = useRef<{ element: HTMLElement; index: number } | null>(null);
  const buttons = () => Array.from(root.current?.querySelectorAll<HTMLButtonElement>(selector) || []);
  const onFocusCapture = (event: FocusEvent<HTMLDivElement>) => {
    const index = buttons().findIndex(button => button === (event.target as HTMLElement));
    origin.current = index < 0 ? null : { element: event.target as HTMLElement, index };
  };
  useLayoutEffect(() => {
    const previous = origin.current;
    if (!previous || (previous.element.isConnected && !(recoverDisabled && previous.element.matches(":disabled"))) || !root.current?.isConnected) return;
    origin.current = null;
    // Never take focus back from another control while an async mutation finishes.
    if (recoverDisabled && !document.hasFocus()) return;
    if (document.activeElement !== document.body && !(recoverDisabled && document.activeElement === previous.element)) return;
    const remaining = buttons();
    const disabledDestination = recoverDisabled && previous.element.matches(":disabled") && disabledFallbackSelector
      ? root.current.querySelector<HTMLElement>(disabledFallbackSelector) : null;
    (disabledDestination || remaining[Math.min(previous.index, remaining.length - 1)] || fallback.current)?.focus();
  });
  return { root, fallback, onFocusCapture };
}
