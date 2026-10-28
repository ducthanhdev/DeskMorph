import defaults from "./config/defaults.json";

export interface SystemStats {
  cpu_usage: number;
  ram_used_mb: number;
  ram_total_mb: number;
  ram_percent: number;
}



export interface OpenWindow {
  id: string;
  class_name: string;
  title: string;
  is_active: boolean;
}

export interface PinnedApp {
  id: string;
  name: string;
  command: string;
  desktopId?: string;
  matchClasses: string[];
  iconType: "chrome" | "terminal" | "code" | "files" | "settings" | "browser" | "custom";
  color?: string;
  enabled?: boolean;
}

export interface AppearancePreset {
  id: string;
  name: string;
  appearance: import("./dockAppearance").Appearance;
}

export interface TaskbarConfig {
  launcherShortcut: string | null;
  wallpaperScheduleEnabled: boolean;
  wallpaperIntervalMinutes: number;
  wallpaperFolders: string[];
  wallpaperRecursive: boolean;
  wallpaperFavorites: string[];
  language: "vi" | "en";
  clock24: boolean;
  clockSeconds: boolean;
  presets: AppearancePreset[];
  monitor: string | null;
  iconSize: number;
  iconSpacing: number;
  reduceMotion: boolean;
  keepDockOnClose: boolean;
  enabled: boolean;
  position: "top" | "bottom";
  height?: number;
  autoHide?: boolean;
  opacity: number;
  borderRadius: number;
  showBattery: boolean;
  showNetwork: boolean;
  showSystem: boolean;
  showAudio: boolean;
  showClock: boolean;
  showStats: boolean;
  showShuffle: boolean;
  showApps: boolean;
  accentColor: string;
  pinnedApps?: PinnedApp[];
  bouncingLaunch?: boolean;
  dynamicShadow?: boolean;
  magnification?: boolean;
  maxMagnificationScale?: number;
}

export const DEFAULT_CONFIG = defaults as TaskbarConfig;
export const DEFAULT_PINNED_APPS = DEFAULT_CONFIG.pinnedApps!;

export interface DockContextMenuState {
  mode?: "windows" | "launcher" | "audio" | "system";
  popupGeneration?: number;
  desktopId?: string;
  matchClasses?: string[];
  iconPath?: string | null;
  pinIndex?: number;
  pinCount?: number;
  windows?: OpenWindow[];
  appId?: string;
  appName: string;
  command?: string;
  windowId?: string;
  isPinned: boolean;
  isRunning: boolean;
  anchorX: number;
}

export interface InstalledApp {
  id: string;
  name: string;
  genericName: string;
  keywords: string[];
  executable: string;
  matchClasses: string[];
  iconPath: string | null;
  actions: { id: string; name: string }[];
}

export type PopupVisibility = { generation: number; visible: boolean };
