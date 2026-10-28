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
  const glyphSize = Math.round(iconSize * .68);
  // Leave four pixels of scroll padding on either side, including bounce squash.
  const maxScale = Math.min(config.maxMagnificationScale ?? 1.35, (height - 8) / iconSize, (iconSize + 8) / (glyphSize * 1.06));
  // Centered groups leave border + scroll padding above and below their glyphs.
  // Keep the stretched, magnified bounce within that vertical viewport.
  const bounceDistance = Math.min(9, Math.max(0, (height / 2 - 5) / maxScale - glyphSize * .52));
  const hitWidth = Math.max(iconSize, Math.ceil(glyphSize * maxScale * 1.06));
  const hitHeight = height - 10;
  return { height, iconSize, glyphSize, maxScale, bounceDistance, hitWidth, hitHeight };
}
export function dockSurface(config: TaskbarConfig): CSSProperties {
  const metrics = dockMetrics(config);
  return {
    height: `${metrics.height}px`, background: `rgba(13,17,28,${config.opacity})`,
    borderRadius: `${config.borderRadius}px`, borderColor: "rgba(255,255,255,.14)",
    ["--icon-spacing" as string]: `${config.iconSpacing}px`,
    ["--glyph-size" as string]: `${metrics.glyphSize}px`,
    ["--icon-size" as string]: `${metrics.iconSize}px`,
    ["--bounce-distance" as string]: `${metrics.bounceDistance}px`,
    ["--stats-direction" as string]: metrics.height < 47 ? "row" : "column",
  };
}
export const BUILTIN_PRESETS = [
  { id: "nord", nameKey: "themeNord", appearance: { position: "bottom", height: 48, iconSize: 32, iconSpacing: 6, opacity: .8, borderRadius: 12, accentColor: "#88c0d0", bouncingLaunch: false, dynamicShadow: false, magnification: true, maxMagnificationScale: 1.2, reduceMotion: false } },
  { id: "neon", nameKey: "themeNeon", appearance: { position: "bottom", height: 64, iconSize: 42, iconSpacing: 10, opacity: .92, borderRadius: 20, accentColor: "#8b5cf6", bouncingLaunch: true, dynamicShadow: true, magnification: true, maxMagnificationScale: 1.35, reduceMotion: false } },
  { id: "pop", nameKey: "themePop", appearance: { position: "bottom", height: 52, iconSize: 36, iconSpacing: 8, opacity: .85, borderRadius: 16, accentColor: "#48b9c7", bouncingLaunch: true, dynamicShadow: true, magnification: true, maxMagnificationScale: 1.35, reduceMotion: false } },
] as const;
