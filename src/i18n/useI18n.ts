import { displayPinName } from "./pinNames";
import type { PinnedApp } from "../types";
import { useConfig } from "../config/store";
import { formatCount, translate, translateStoredText, type MessageKey } from "./messages";
export function useI18n() {
  const { config } = useConfig();
  return { text: (value: string) => translateStoredText(config.language, value), pinName: (pin: PinnedApp) => displayPinName(config.language, pin), language: config.language, locale: config.language === "vi" ? "vi-VN" : "en-US", count: (kind: "window" | "app", count: number) => formatCount(config.language, kind, count), t: (key: MessageKey) => translate(config.language, key) };
}
