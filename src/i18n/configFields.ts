import type { TaskbarConfig } from "../types";
import { translate, type Language, type MessageKey } from "./messages";

export const configFieldLabels = {
  launcherShortcut: "shortcutTitle", enabled: "enabled", position: "position", height: "height", autoHide: "autoHide",
  opacity: "opacity", borderRadius: "radius", showBattery: "batteryWidget", showNetwork: "networkWidget",
  showSystem: "systemToolsWidget", showAudio: "audio", showClock: "showClock", showStats: "showStats",
  showShuffle: "showShuffle", showApps: "showApps", accentColor: "accent", pinnedApps: "pinnedApps",
  bouncingLaunch: "bounce", dynamicShadow: "shadow", magnification: "magnify", maxMagnificationScale: "maxScale",
  iconSize: "iconSize", iconSpacing: "spacing", reduceMotion: "reduceMotion", monitor: "monitor",
  language: "language", clock24: "clock24", clockSeconds: "clockSeconds", presets: "savedPresets",
  keepDockOnClose: "keepDock", wallpaperScheduleEnabled: "schedule", wallpaperIntervalMinutes: "interval",
  wallpaperFolders: "savedFolders", wallpaperRecursive: "recursive", wallpaperFavorites: "savedFavorites",
} satisfies Record<keyof TaskbarConfig, MessageKey>;

export function configFieldLabel(language: Language, field: string): string {
  return Object.prototype.hasOwnProperty.call(configFieldLabels, field) ? translate(language, configFieldLabels[field as keyof TaskbarConfig]) : field;
}
export function configReviewValue(language: Language, field: string, value: unknown): string {
  if (typeof value === "boolean") return translate(language, value ? "on" : "off");
  if (value === null || value === undefined) return translate(language, "notSet");
  if (field === "position" && (value === "top" || value === "bottom")) return translate(language, value);
  if (field === "language") return value === "vi" ? "Tiếng Việt" : value === "en" ? "English" : String(value);
  if (typeof value === "number") return new Intl.NumberFormat(language).format(value);
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
