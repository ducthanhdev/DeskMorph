import defaults from "../config/defaults.json";
import type { PinnedApp } from "../types";
import { translate, type Language } from "./messages";

/** Display-only translation of unchanged bundled labels; never rewrite saved/user names. */
export function displayPinName(language: Language, pin: PinnedApp): string {
  const bundled = defaults.pinnedApps.find(item => item.id === pin.id);
  if (pin.desktopId || !bundled || pin.name !== bundled.name || pin.command !== bundled.command || pin.iconType !== bundled.iconType) return pin.name;
  if (pin.id === "files") return translate(language, "defaultFiles");
  if (pin.id === "settings") return translate(language, "defaultSettings");
  return pin.name;
}
