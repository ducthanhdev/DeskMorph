import type { InstalledApp, PinnedApp } from "./types";

export function normalizeSearch(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase().trim();
}
export function searchApps(apps: InstalledApp[], query: string) {
  const normalized = normalizeSearch(query);
  const terms = normalized.split(/\s+/).filter(Boolean);
  return apps.map((app) => {
    const name = normalizeSearch(app.name);
    const text = normalizeSearch([app.name, app.genericName, app.id, ...app.keywords].join(" "));
    const rank = !terms.every((term) => text.includes(term)) ? -1 : !normalized ? 3 : name === normalized ? 0 : name.startsWith(normalized) ? 1 : name.includes(normalized) ? 2 : 3;
    return { app, rank };
  }).filter((item) => item.rank >= 0)
    .sort((a, b) => a.rank - b.rank || normalizeSearch(a.app.name).localeCompare(normalizeSearch(b.app.name)) || a.app.id.localeCompare(b.app.id))
    .map(({ app }) => app);
}
export function installedForPin(pin: PinnedApp, apps: InstalledApp[]) {
  if (pin.desktopId) return apps.find((app) => app.id === pin.desktopId);
  const command = pin.command.replace(/^desktop:/, "");
  const exact = apps.find((app) => app.id === command || app.executable.split("/").pop() === command);
  if (exact) return exact;
  const matches = apps.filter((app) => app.matchClasses.some((cls) => pin.matchClasses.some((hint) => cls.toLowerCase() === hint.toLowerCase())));
  return matches[0];
}
export function pinFromApp(app: InstalledApp): PinnedApp {
  return { id: app.id, desktopId: app.id, name: app.name, command: `desktop:${app.id}`, matchClasses: app.matchClasses, iconType: "custom", enabled: true };
}
