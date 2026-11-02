import { AppWindow, Globe, Code2, Terminal, Folder, Settings, Sparkles } from "lucide-react";
import type { PinnedApp } from "./types";
export const getPinnedVisual = (app: PinnedApp) => {
    switch (app.iconType) {
      case "chrome":
      case "browser":
        return {
          icon: <Globe size={20} />,
          color: app.color || "#38bdf8",
          bg: "rgba(56, 189, 248, 0.18)",
          border: "rgba(56, 189, 248, 0.45)",
        };
      case "code":
        return {
          icon: <Code2 size={20} />,
          color: app.color || "#38bdf8",
          bg: "rgba(56, 189, 248, 0.2)",
          border: "rgba(56, 189, 248, 0.5)",
        };
      case "terminal":
        return {
          icon: <Terminal size={20} />,
          color: app.color || "#34d399",
          bg: "rgba(52, 211, 153, 0.18)",
          border: "rgba(52, 211, 153, 0.45)",
        };
      case "files":
        return {
          icon: <Folder size={20} />,
          color: app.color || "#fbbf24",
          bg: "rgba(251, 191, 36, 0.18)",
          border: "rgba(251, 191, 36, 0.45)",
        };
      case "settings":
        return {
          icon: <Settings size={20} />,
          color: app.color || "#94a3b8",
          bg: "rgba(148, 163, 184, 0.18)",
          border: "rgba(148, 163, 184, 0.45)",
        };
      default:
        return {
          icon: <AppWindow size={20} />,
          color: app.color || "#38bdf8",
          bg: "rgba(56, 189, 248, 0.18)",
          border: "rgba(56, 189, 248, 0.45)",
        };
    }
  };

export const getAppVisual = (className: string) => {
    const lower = className.toLowerCase();
    if (lower.includes("chrome") || lower.includes("chromium")) {
      return {
        icon: <Globe size={20} />,
        color: "#38bdf8",
        bg: "rgba(56, 189, 248, 0.18)",
        border: "rgba(56, 189, 248, 0.45)",
      };
    }
    if (lower.includes("firefox")) {
      return {
        icon: <Globe size={20} />,
        color: "#fb923c",
        bg: "rgba(251, 146, 60, 0.18)",
        border: "rgba(251, 146, 60, 0.45)",
      };
    }
    if (
      lower.includes("terminal") ||
      lower.includes("console") ||
      lower.includes("pty") ||
      lower.includes("kitty") ||
      lower.includes("alacritty")
    ) {
      return {
        icon: <Terminal size={20} />,
        color: "#34d399",
        bg: "rgba(52, 211, 153, 0.18)",
        border: "rgba(52, 211, 153, 0.45)",
      };
    }
    if (
      lower.includes("code") ||
      lower.includes("cursor") ||
      lower.includes("ide") ||
      lower.includes("antigravity")
    ) {
      return {
        icon: <Code2 size={20} />,
        color: "#38bdf8",
        bg: "rgba(56, 189, 248, 0.2)",
        border: "rgba(56, 189, 248, 0.5)",
      };
    }
    if (lower.includes("nautilus") || lower.includes("file") || lower.includes("thunar")) {
      return {
        icon: <Folder size={20} />,
        color: "#fbbf24",
        bg: "rgba(251, 191, 36, 0.18)",
        border: "rgba(251, 191, 36, 0.45)",
      };
    }
    if (lower.includes("setting") || lower.includes("preference")) {
      return {
        icon: <Settings size={20} />,
        color: "#94a3b8",
        bg: "rgba(148, 163, 184, 0.18)",
        border: "rgba(148, 163, 184, 0.45)",
      };
    }
    if (lower.includes("deskmorph")) {
      return {
        icon: <Sparkles size={20} />,
        color: "#48b9c7",
        bg: "rgba(72, 185, 199, 0.2)",
        border: "rgba(72, 185, 199, 0.5)",
      };
    }
    return {
      icon: <AppWindow size={20} />,
      color: "#38bdf8",
      bg: "rgba(56, 189, 248, 0.18)",
      border: "rgba(56, 189, 248, 0.45)",
    };
  };

