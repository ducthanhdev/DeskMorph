import type { OpenWindow, PinnedApp } from "./types";

export function groupWindows(openWindows: OpenWindow[], pinnedApps: PinnedApp[]) {
  const matched = new Set<string>();
  const pinnedItems = pinnedApps.map((pinned) => {
    const windows = openWindows.filter((w) => !matched.has(w.id) &&
      pinned.matchClasses.some((cls) => w.class_name.toLowerCase().includes(cls.toLowerCase())));
    windows.forEach((w) => matched.add(w.id));
    return { pinned, windows };
  });
  const groups = new Map<string, OpenWindow[]>();
  for (const window of openWindows) {
    if (matched.has(window.id)) continue;
    const key = window.class_name.toLowerCase();
    groups.set(key, [...(groups.get(key) || []), window]);
  }
  return { pinnedItems, unpinnedGroups: [...groups.values()] };
}
