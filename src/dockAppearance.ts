import type { CSSProperties } from "react";
import type { TaskbarConfig } from "./types";
export const APPEARANCE_KEYS = ["position", "height", "iconSize", "iconSpacing", "opacity", "borderRadius", "accentColor", "bouncingLaunch", "dynamicShadow", "magnification", "maxMagnificationScale", "reduceMotion"] as const;
export type Appearance = Pick<TaskbarConfig, typeof APPEARANCE_KEYS[number]>;
export function appearanceOf(config: TaskbarConfig): Appearance {
  return Object.fromEntries(APPEARANCE_KEYS.map((key) => [key, config[key]])) as Appearance;
}
export function dockMetrics(config: TaskbarConfig) {
  const height = config.height || 52;
  const iconSize = Math.max(24, Math.min(config.iconSize, height - 14));
  return { height, iconSize, maxScale: Math.min(config.maxMagnificationScale ?? 1.35, (height - 8) / iconSize) };
}
export function dockSurface(config: TaskbarConfig): CSSProperties {
  return {
    height: `${dockMetrics(config).height}px`, background: `rgba(13,17,28,${config.opacity})`,
    borderRadius: `${config.borderRadius}px`, borderColor: "rgba(255,255,255,.14)",
    ["--icon-spacing" as string]: `${config.iconSpacing}px`,
  };
}
export const BUILTIN_PRESETS = [
  { id: "nord", nameKey: "themeNord", appearance: { position: "bottom", height: 48, iconSize: 32, iconSpacing: 6, opacity: .8, borderRadius: 12, accentColor: "#88c0d0", bouncingLaunch: false, dynamicShadow: false, magnification: true, maxMagnificationScale: 1.2, reduceMotion: false } },
  { id: "neon", nameKey: "themeNeon", appearance: { position: "bottom", height: 64, iconSize: 42, iconSpacing: 10, opacity: .92, borderRadius: 20, accentColor: "#8b5cf6", bouncingLaunch: true, dynamicShadow: true, magnification: true, maxMagnificationScale: 1.35, reduceMotion: false } },
  { id: "pop", nameKey: "themePop", appearance: { position: "bottom", height: 52, iconSize: 36, iconSpacing: 8, opacity: .85, borderRadius: 16, accentColor: "#48b9c7", bouncingLaunch: true, dynamicShadow: true, magnification: true, maxMagnificationScale: 1.35, reduceMotion: false } },
] as const;
