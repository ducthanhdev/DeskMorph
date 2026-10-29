import type { PlatformInfo } from "./hooks/usePlatform";
import type { MessageKey } from "./i18n/messages";
export type PlatformFeature = keyof PlatformInfo["unavailableReasons"];
const reasonKeys: Record<string, MessageKey> = {
  window_backend_unsupported: "nativeWindowsUnavailable", x11_display_missing: "x11DisplayMissing",
  xprop_unavailable: "xpropMissing", window_enumeration_unsupported: "enumerateUnavailable",
  window_activation_unsupported: "activateUnavailable", window_close_unsupported: "closeUnavailable",
  xkill_unavailable: "forceUnavailable", wallpaper_adapter_unsupported: "wallpaperAdapterUnavailable",
  wallpaper_schema_unavailable: "wallpaperSchemaUnavailable", wallpaper_setting_unavailable: "wallpaperSchemaUnavailable",
  wallpaper_config_invalid: "wallpaperConfigInvalid",
  wallpaper_read_only: "wallpaperReadOnly", dock_placement_unverified: "dockPlacementUnavailable",
  dock_autohide_unverified: "autoHideUnavailable", workspaces_not_implemented: "workspacesDevelopment",
};
export function capabilityReason(platform: PlatformInfo | null, feature: PlatformFeature,
  t: (key: MessageKey) => string, error?: string | null): string {
  if (error) return t("capabilityProbeFailed");
  if (!platform) return t("loading");
  const code = platform.unavailableReasons?.[feature];
  return t(code && reasonKeys[code] || "capabilityProbeFailed");
}
