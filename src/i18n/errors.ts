import { messages, translate, type Language, type MessageKey } from "./messages";

const errors: Record<string, MessageKey> = {
  config_repaired: "configRepaired", config_recovered: "configRecovered", config_legacy_repaired: "configLegacyRepaired",
  config_legacy_unreadable: "configLegacyUnreadable", config_durability: "configDurability",
  config_not_ready: "configNotReady", config_conflict: "configConflict", config_write: "configWriteError",
  config_read: "configReadError", config_version: "configVersionError", invalid_config: "configInvalidError",
  config_document: "configInvalidError", config_export: "configExportError",
  shortcut_conflict: "shortcutConflict", shortcut_unsupported: "shortcutUnsupported",
  xprop_unavailable: "xpropMissing", window_backend_unsupported: "nativeWindowsUnavailable",
  window_activation_unsupported: "activateUnavailable", window_close_unsupported: "closeUnavailable",
  window_enumeration_unsupported: "enumerateUnavailable", wallpaper_read_only: "wallpaperReadOnly",
  wallpaper_adapter_unsupported: "wallpaperAdapterUnavailable", downloads_missing: "downloadsMissing",
  system_monitor_missing: "systemMonitorMissing", file_manager_missing: "fileManagerMissing",
  pin_class_conflict: "pinClassConflict", pin_identity_conflict: "pinIdentityConflict", pin_missing: "pinMissingError",
  app_missing: "unavailable", app_launch_failed: "launchError", set_wallpaper_failed: "wallpaperError",
  wallpaper_write_unverified: "wallpaperWriteUnverified",
  wallpaper_config_invalid: "wallpaperConfigInvalid",
  wallpaper_schema_unavailable: "wallpaperSchemaUnavailable", wallpaper_setting_unavailable: "wallpaperSchemaUnavailable",
  trash_unsupported: "trashUnavailable", x11_display_missing: "x11DisplayMissing",
};
const commands: Record<string, MessageKey> = {
  launch_app: "launchError", launch_installed_app: "launchError", spawn_app: "launchError",
  activate_window: "activateWindowError", close_window: "closeWindowError", get_open_windows: "refreshWindowsError",
  set_wallpaper: "wallpaperError", shuffle_wallpaper: "wallpaperError", open_system_location: "systemOpenError",
  get_audio_snapshot: "audioUnavailable", get_media_players: "mediaError",
};

/** Localize at render time so an error already on screen follows a language change. */
export function describeError(language: Language, raw: string, fallback: MessageKey = "operationFailed"): { summary: string; code?: string } {
  for (const catalog of Object.values(messages)) {
    const known = (Object.keys(catalog) as MessageKey[]).find(key => catalog[key] === raw);
    if (known) return { summary: translate(language, known) };
  }
  // Compatibility with warnings persisted by versions before stable warning codes.
  if (raw.startsWith(messages.vi.configDurability.split(";")[0] + ";")) return { summary: translate(language, "configDurability") };
  // Structured CommandError.toString(), legacy "code: message", or code-only audio errors.
  const code = /\[([a-z][a-z0-9_]+);\s*[a-z][a-z0-9_]*\]$/.exec(raw)?.[1]
    || /^(?:Error:\s*)?([a-z][a-z0-9]*_[a-z0-9_]+)(?::|$)/.exec(raw)?.[1];
  const command = /\[[a-z][a-z0-9_]+;\s*([a-z][a-z0-9_]*)\]$/.exec(raw)?.[1];
  return { summary: translate(language, code && errors[code] || command && commands[command] || fallback), code };
}
