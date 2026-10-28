import { CommandError } from "../commandError";
import { useEffect, useRef, useState } from "react";
import { invoke } from "../ipc";
import { useI18n } from "../i18n/useI18n";
import { usePolling } from "../hooks/usePolling";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { usePopupActive } from "../hooks/usePopupActive";
import type { SystemStats } from "../types";
import type { MessageKey } from "../i18n/messages";
const stateKeys: Record<string, MessageKey> = {
  charging: "batteryCharging", discharging: "batteryDischarging", charged: "batteryCharged", empty: "batteryEmpty", pendingCharge: "batteryPendingCharge", pendingDischarge: "batteryPendingDischarge",
  wifi: "networkWifi", wired: "networkWired", other: "networkOther", disconnected: "networkDisconnected", asleep: "networkAsleep", disconnecting: "networkDisconnecting", connecting: "networkConnecting", local: "networkLocal", site: "networkSite", global: "networkGlobal",
  none: "connectivityNone", portal: "connectivityPortal", limited: "connectivityLimited", full: "connectivityFull",
};
export function SystemPopup({ generation }: { generation?: number }) {
  const { t, locale } = useI18n();
  const visible = usePopupActive(generation);
  const active = useRef(false);
  active.current = visible;
  const { status, error: statusError } = useSystemStatus(visible);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const changing = useRef(false);
  const root = useRef<HTMLElement>(null);
  const describe = (key: string) => t(stateKeys[key] || "unknown");
  useEffect(() => {
    root.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => { active.current = false; };
  }, []);
  usePolling(async (signal) => {
    try { const value = await invoke<SystemStats>("get_system_stats"); if (!signal.aborted) { setStats(value); setStatsError(null); } }
    catch (e) { if (!signal.aborted) setStatsError(String(e)); }
  }, 2000, visible);
  const open = async (location: string) => {
    if (!active.current || changing.current) return;
    changing.current = true; setBusy(true); setError(null);
    try { await invoke("open_system_location", { location }); }
    catch (e) { if (active.current) setError(e instanceof CommandError && e.code === "downloads_missing" ? t("downloadsMissing") : `${t("systemOpenError")} (${String(e)})`); }
    finally { changing.current = false; if (active.current) setBusy(false); }
  };
  return <section className="audio-popup system-popup" ref={root} aria-label={t("systemTools")}>
    <header><h2>{t("systemTools")}</h2><button onClick={() => void invoke("hide_dock_context_menu")}>{t("close")}</button></header>
    {(error || statusError || statsError) && <p role="alert">{error || statusError || statsError}</p>}
    {!status && <p role="status">{t("loading")}</p>}
    {stats && <section aria-label={t("showStats")}><h3>{t("showStats")}</h3><p>CPU: {stats.cpu_usage.toFixed(1)}%</p><p>RAM: {new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(stats.ram_used_mb / 1024)} / {new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(stats.ram_total_mb / 1024)} GiB ({stats.ram_percent.toFixed(1)}%)</p><small>{t("statsInterval")}</small></section>}
    <section aria-label={t("battery")}><h3>{t("battery")}</h3>
      {status?.battery ? <><p>{Math.round(status.battery.percentage)}% • {describe(status.battery.state)}</p><p>{status.battery.remainingSeconds ? `${t("batteryEstimate")}: ${Math.ceil(status.battery.remainingSeconds / 60)} ${t("minutes")}` : t("batteryNoEstimate")}</p></> : <p>{status?.batteryError ? t("batteryUnavailable") : status ? t("batteryAbsent") : t("loading")}</p>}
    </section>
    <section aria-label={t("network")}><h3>{t("network")}</h3>
      {status?.network ? <><p>{describe(status.network.kind)} • {describe(status.network.state)}</p><p>{describe(status.network.connectivity)}</p><small>{t("networkProbeHelp")}</small></> : <p>{status?.networkError ? t("networkUnavailable") : t("loading")}</p>}
    </section>
    <div className="system-actions"><button disabled={busy || !status?.folderAvailable} onClick={() => void open("downloads")}>{t("downloads")}</button><button disabled={busy || !status?.trashAvailable} onClick={() => void open("trash")}>{t("trash")}</button><button disabled={busy || !status?.monitorId} onClick={() => void open("monitor")}>{t("systemMonitor")}</button></div>
    {status && !status.folderAvailable && <p>{t("fileManagerMissing")}</p>}
    {status && !status.trashAvailable && <p>{t("trashUnavailable")}</p>}
    {status && !status.monitorId && <p>{t("systemMonitorMissing")}</p>}
  </section>;
}
