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
/** Explicit desktop identities never fall through to unrelated executable/WM_CLASS hints. */
export function desktopIdForPin(pin: PinnedApp): string | undefined {
  if (pin.desktopId !== undefined) return pin.desktopId;
  const command = pin.command.trim();
  if (command.startsWith("desktop:")) return command.slice("desktop:".length);
  if (command.endsWith(".desktop") && !/[\s/]/.test(command)) return command;
  return undefined;
}
export function launchCommandForPin(pin: PinnedApp): string {
  const desktopId = desktopIdForPin(pin);
  return desktopId !== undefined ? `desktop:${desktopId}` : pin.command;
}
export function installedForPin(pin: PinnedApp, apps: InstalledApp[]) {
  const desktopId = desktopIdForPin(pin);
  if (desktopId !== undefined) return apps.find((app) => app.id === desktopId);
  const command = pin.command.trim();
  const exact = apps.filter((app) => app.executable === command || (!command.includes("/") && app.executable.split("/").pop() === command));
  if (exact.length) return exact.length === 1 ? exact[0] : undefined;
  const matches = apps.filter((app) => app.matchClasses.some((cls) => pin.matchClasses.some((hint) => cls.toLowerCase() === hint.toLowerCase())));
  return matches.length === 1 ? matches[0] : undefined;
}
export function pinFromApp(app: InstalledApp): PinnedApp {
  return { id: app.id, desktopId: app.id, name: app.name, command: `desktop:${app.id}`, matchClasses: app.matchClasses, iconType: "custom", enabled: true };
}

/** Absence is meaningful only after a successful catalogue read. */
export function desktopIsMissing(id: string | undefined, app: InstalledApp | undefined, status: { loading: boolean; error: string | null }): boolean {
  return id !== undefined && !app && !status.loading && !status.error;
}

/** Native class hints must identify one catalogue app before borrowing its icon. */
export function installedForClass(className: string, apps: InstalledApp[]) {
  const key = className.toLowerCase();
  const exact = apps.filter((app) => app.id.replace(/\.desktop$/, "").toLowerCase() === key);
  if (exact.length) return exact.length === 1 ? exact[0] : undefined;
  const matches = apps.filter((app) => app.matchClasses.some((hint) => hint.toLowerCase() === key));
  return matches.length === 1 ? matches[0] : undefined;
}
