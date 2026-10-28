import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { PopupVisibility } from "../types";

/** Subscribe before querying so a hide during listener registration is observed. */
export function usePopupActive(generation?: number) {
  const [active, setActive] = useState(false);
  useEffect(() => {
    let disposed = false;
    let changed = false;
    let stop: (() => void) | undefined;
    setActive(false);
    if (generation === undefined) return;
    void (async () => {
      const unlisten = await listen<PopupVisibility>("deskmorph:context-visibility-generation", ({ payload }) => {
        if (disposed || payload.generation !== generation) return;
        changed = true;
        setActive(payload.visible);
      });
      if (disposed) { unlisten(); return; }
      stop = unlisten;
      const current = await invoke<boolean>("is_context_popup_active", { generation });
      if (!disposed && !changed) setActive(current);
    })().catch((error) => { if (!disposed) console.error(error); });
    return () => { disposed = true; stop?.(); };
  }, [generation]);
  return active;
}
