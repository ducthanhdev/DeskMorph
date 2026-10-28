import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { PopupVisibility } from "../types";
import { watchPopupVisibility } from "./popupVisibility";

/** Subscribe before querying so a hide during listener registration is observed. */
export function usePopupActive(generation?: number) {
  const [active, setActive] = useState(false);
  useEffect(() => {
    setActive(false);
    if (generation === undefined) return;
    return watchPopupVisibility(
      (receive) => listen<PopupVisibility>("deskmorph:context-visibility-generation", ({ payload }) => {
        if (payload.generation === generation) receive(payload.visible);
      }),
      () => invoke<boolean>("is_context_popup_active", { generation }),
      setActive,
      console.error,
    );
  }, [generation]);
  return active;
}
