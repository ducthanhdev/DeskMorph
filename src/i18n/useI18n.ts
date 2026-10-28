import { useConfig } from "../config/store";
import { formatCount, translate, type MessageKey } from "./messages";
export function useI18n() {
  const { config } = useConfig();
  return { language: config.language, locale: config.language === "vi" ? "vi-VN" : "en-US", count: (kind: "window" | "app", count: number) => formatCount(config.language, kind, count), t: (key: MessageKey) => translate(config.language, key) };
}
