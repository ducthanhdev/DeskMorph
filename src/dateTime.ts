import type { TaskbarConfig } from "./types";

type ClockPreferences = Pick<TaskbarConfig, "clock24" | "clockSeconds">;

/** An explicit cycle keeps midnight at 00 in 24-hour mode in every locale. */
export function formatClock(date: Date | number, locale: string, config: ClockPreferences): string {
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit", minute: "2-digit",
    second: config.clockSeconds ? "2-digit" : undefined,
    hourCycle: config.clock24 ? "h23" : "h12",
  }).format(date);
}

export function formatClockDateTime(date: Date | number, locale: string, config: ClockPreferences): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short", timeStyle: config.clockSeconds ? "medium" : "short",
    hourCycle: config.clock24 ? "h23" : "h12",
  }).format(date);
}
