import { useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { FocusEvent, PointerEvent } from "react";
export function useDockTooltip(disabled: boolean) {
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const revision = useRef(Date.now() * 100);
  const hide = () => {
    clearTimeout(timer.current);
    revision.current = Math.max(revision.current + 1, Date.now() * 100);
    void invoke("set_dock_tooltip", { revision: revision.current, text: null, anchor: null }).catch(console.error);
  };
  const show = (element: HTMLElement | null) => {
    hide();
    if (disabled || !element?.dataset.dockTooltip) return;
    const current = revision.current;
    timer.current = setTimeout(() => {
      if (!element.isConnected || current !== revision.current) return;
      const rect = element.getBoundingClientRect();
      void invoke("set_dock_tooltip", { revision: current, text: element.dataset.dockTooltip, anchor: Math.round(rect.left + rect.width / 2) }).catch(console.error);
    }, 500);
  };
  useEffect(() => { if (disabled) hide(); return hide; }, [disabled]);
  const target = (node: EventTarget | null) => node instanceof Element ? node.closest<HTMLElement>("[data-dock-tooltip]") : null;
  return {
    onPointerOver: (event: PointerEvent) => { const next = target(event.target); if (next !== target(event.relatedTarget)) show(next); },
    onPointerOut: (event: PointerEvent) => { if (target(event.target) !== target(event.relatedTarget)) hide(); },
    onFocusCapture: (event: FocusEvent) => show(target(event.target)),
    onBlurCapture: hide,
    onPointerDownCapture: hide,
  };
}
