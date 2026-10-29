import resources from "./messages.json";
export const messages = resources;
export type MessageKey = keyof typeof messages.vi;
export type Language = keyof typeof messages;
export function translate(language: Language, key: MessageKey): string { return messages[language][key]; }

export function formatCount(language: Language, kind: "window" | "app", count: number): string {
  const plural = new Intl.PluralRules(language).select(count) === "one" ? "One" : "Other";
  return translate(language, `${kind}${plural}`).replace("{count}", new Intl.NumberFormat(language).format(count));
}

/** Resolve a stored UI message again after language changes; user data passes through. */
export function translateStoredText(language: Language, value: string): string {
  for (const catalog of Object.values(messages)) {
    const key = (Object.keys(catalog) as MessageKey[]).find(key => catalog[key] === value);
    if (key) return translate(language, key);
  }
  return value;
}
