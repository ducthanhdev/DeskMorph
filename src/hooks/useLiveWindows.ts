import { useMemo, useState } from "react";
import { invoke } from "../ipc";
import type { DockContextMenuState, OpenWindow } from "../types";
import { errorMessage, useConfig } from "../config/store";
import { groupWindows } from "../windowGroups";
import { usePolling } from "./usePolling";
import { usePopupActive } from "./usePopupActive";

export function useLiveWindows(menu: DockContextMenuState) {
  const [windows, setWindows] = useState(menu.windows || []);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const active = usePopupActive(menu.popupGeneration);
  const { config, ready } = useConfig();
  const classes = useMemo(() => new Set(menu.windows?.map((window) => window.class_name.toLowerCase())), [menu]);
  usePolling(async (signal) => {
    try {
      const all = await invoke<OpenWindow[]>("get_open_windows");
      if (signal.aborted) return;
      const grouped = groupWindows(all, (config.pinnedApps || []).filter((pin) => pin.enabled !== false));
      const pinned = menu.isPinned ? grouped.pinnedItems.find((item) => item.pinned.id === menu.appId) : undefined;
      setWindows(menu.isPinned ? pinned?.windows || [] : grouped.unpinnedGroups.flat().filter((window) => classes.has(window.class_name.toLowerCase())));
      setRefreshError(null);
    } catch (error) { if (!signal.aborted) setRefreshError(errorMessage(error)); }
  }, 1500, active && ready && (Boolean(menu.isPinned) || classes.size > 0));
  return { windows, refreshError, active };
}
