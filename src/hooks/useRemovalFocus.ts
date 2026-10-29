import { useLayoutEffect, useRef, type FocusEvent } from "react";

/** Recover only when our focused remove button disappears during a list update. */
export function useRemovalFocus() {
  const root = useRef<HTMLDivElement>(null);
  const fallback = useRef<HTMLInputElement>(null);
  const origin = useRef<{ element: HTMLElement; index: number } | null>(null);
  const buttons = () => Array.from(root.current?.querySelectorAll<HTMLButtonElement>("button[data-remove-focus]:not(:disabled)") || []);
  const onFocusCapture = (event: FocusEvent<HTMLDivElement>) => {
    const index = buttons().findIndex(button => button === (event.target as HTMLElement));
    origin.current = index < 0 ? null : { element: event.target as HTMLElement, index };
  };
  useLayoutEffect(() => {
    const previous = origin.current;
    if (!previous || previous.element.isConnected || !root.current?.isConnected) return;
    origin.current = null;
    // Never take focus back from another control while an async mutation finishes.
    if (document.activeElement !== document.body) return;
    const remaining = buttons();
    (remaining[Math.min(previous.index, remaining.length - 1)] || fallback.current)?.focus();
  });
  return { root, fallback, onFocusCapture };
}
