import { invoke } from "@tauri-apps/api/core";
import { Battery, BatteryCharging, Wifi, Network, Activity } from "lucide-react";
import { useConfig } from "../config/store";
import { useI18n } from "../i18n/useI18n";
import { useSystemStatus } from "../hooks/useSystemStatus";
export function SystemWidgets({ preview = false, onError }: { preview?: boolean; onError?: (error: string) => void }) {
  const { config, ready } = useConfig();
  const { t } = useI18n();
  const { status } = useSystemStatus(ready && config.enabled && (config.showBattery || config.showNetwork));
  const open = (event: React.MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    void invoke("show_dock_context_menu", { iconCenterX: Math.round(rect.left + rect.width / 2), menuData: { mode: "system", appName: t("systemTools") } }).catch((e) => onError?.(String(e)));
  };
  const button = (name: string, children: React.ReactNode) => preview ? <span className="dock-action-btn system-widget-button" title={name}>{children}</span> : <button className="dock-action-btn system-widget-button" aria-label={name} data-dock-tooltip={name} onClick={open}>{children}</button>;
  return <>
    {config.showBattery && status?.battery && button(`${t("battery")} ${Math.round(status.battery.percentage)}%`, <>{status.battery.state === "charging" ? <BatteryCharging size={16} /> : <Battery size={16} />}<small>{Math.round(status.battery.percentage)}%</small></>)}
    {config.showBattery && status?.batteryError && button(t("batteryUnavailable"), <Battery size={16} />)}
    {config.showNetwork && status?.network && button(status.network.state === "disconnected" || status.network.state === "asleep" ? t("networkDisconnected") : t("network"), status.network.kind === "wifi" ? <Wifi size={16} /> : <Network size={16} />)}
    {config.showNetwork && status?.networkError && button(t("networkUnavailable"), <Network size={16} />)}
    {config.showSystem && button(t("systemTools"), <Activity size={16} />)}
  </>;
}
