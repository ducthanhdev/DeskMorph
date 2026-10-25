export interface SystemStats {
  cpu_usage: number;
  ram_used_mb: number;
  ram_total_mb: number;
  ram_percent: number;
}

export interface WallpaperInfo {
  path: string;
  filename: string;
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
  matchClasses: string[];
  iconType: "chrome" | "terminal" | "code" | "files" | "settings" | "browser" | "custom";
  color?: string;
  enabled?: boolean;
}

export interface TaskbarConfig {
  enabled: boolean;
  position: "top" | "bottom";
  height?: number;
  autoHide?: boolean;
  opacity: number;
  borderRadius: number;
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

export const DEFAULT_PINNED_APPS: PinnedApp[] = [
  {
    id: "chrome",
    name: "Google Chrome",
    command: "google-chrome",
    matchClasses: ["chrome", "google-chrome", "chromium"],
    iconType: "chrome",
    color: "#38bdf8",
    enabled: true,
  },
  {
    id: "code",
    name: "VS Code / IDE",
    command: "code",
    matchClasses: ["code", "cursor", "antigravity"],
    iconType: "code",
    color: "#818cf8",
    enabled: true,
  },
  {
    id: "terminal",
    name: "Terminal",
    command: "cosmic-term",
    matchClasses: ["cosmic-term", "terminal", "kitty", "alacritty", "console", "pty"],
    iconType: "terminal",
    color: "#34d399",
    enabled: true,
  },
  {
    id: "files",
    name: "Tệp tin (Files)",
    command: "cosmic-files",
    matchClasses: ["cosmic-files", "nautilus", "files", "thunar"],
    iconType: "files",
    color: "#fbbf24",
    enabled: true,
  },
  {
    id: "settings",
    name: "Cài đặt (Settings)",
    command: "cosmic-settings",
    matchClasses: ["cosmic-settings", "gnome-control-center", "settings", "preference"],
    iconType: "settings",
    color: "#94a3b8",
    enabled: true,
  },
];

export interface DockContextMenuState {
  appId?: string;
  appName: string;
  command?: string;
  windowId?: string;
  isPinned: boolean;
  isRunning: boolean;
  anchorX: number;
}
