import { useEffect, useState, type FocusEvent, type RefObject } from "react";

/** DOM focus alone can survive native window blur; track both sources. */
export function useFocusWithin(root: RefObject<HTMLElement | null>) {
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    let frame: number | undefined;
    const refresh = () => setFocused(document.hasFocus() && !!root.current?.contains(document.activeElement));
    const focus = () => {
      refresh();
      // Native GTK/WebKit mapping can settle DOM focus after the window event.
      cancelAnimationFrame(frame ?? 0);
      frame = requestAnimationFrame(refresh);
    };
    const blur = () => { cancelAnimationFrame(frame ?? 0); setFocused(false); };
    refresh();
    window.addEventListener("focus", focus);
    window.addEventListener("blur", blur);
    return () => {
      cancelAnimationFrame(frame ?? 0);
      window.removeEventListener("focus", focus);
      window.removeEventListener("blur", blur);
    };
  }, [root]);
  return {
    focused,
    onFocusCapture: () => setFocused(true),
    onBlurCapture: (event: FocusEvent<HTMLElement>) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false);
    },
  };
}
