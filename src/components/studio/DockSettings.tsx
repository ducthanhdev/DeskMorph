import { useState } from "react";
import { invoke } from "../../ipc";
import { ErrorText } from "../ErrorText";
import { useConfig, errorMessage } from "../../config/store";
import { usePlatform } from "../../hooks/usePlatform";
import { useI18n } from "../../i18n/useI18n";
import { Card, Range, Toggle } from "./Controls";
import { capabilityReason } from "../../capabilities";
export function DockSettings() {
  const { config, updateConfig } = useConfig();
  const { platform, error: platformError } = usePlatform();
  const { t } = useI18n();
  const [focusError, setFocusError] = useState("");
  return <>
    <Card title={t("dockTab")}>
      <Toggle label={t("enabled")} value={config.enabled} onChange={(enabled) => updateConfig({ enabled })} />
      <button type="button" disabled={!config.enabled || !platform?.dockPlacement} onClick={() => {
        setFocusError("");
        void invoke("focus_dock").catch(error => setFocusError(errorMessage(error)));
      }}>{t("focusDock")}</button>
      <p className="settings-help">{t("focusDockHelp")}</p>
      {focusError && <p role="alert"><ErrorText error={focusError} /></p>}
      <label className="settings-field">{t("position")}<select aria-label={t("position")} disabled={!platform?.dockPlacement} value={config.position} onChange={(e) => void updateConfig({ position: e.target.value as "top" | "bottom" })}><option value="bottom">{t("bottom")}</option><option value="top">{t("top")}</option></select></label>
      <label className="settings-field">{t("monitor")}<select aria-label={t("monitor")} disabled={!platform?.dockPlacement} value={config.monitor || ""} onChange={(e) => void updateConfig({ monitor: e.target.value || null })}>
        <option value="">{t("primary")}</option>{platform?.monitors.map((m) => <option key={`${m.name}:${m.x}:${m.y}`} value={m.name}>{m.name} • {m.width}×{m.height}</option>)}
        {config.monitor && !platform?.monitors.some((m) => m.name === config.monitor) && <option value={config.monitor}>{config.monitor} ({t("disconnected")})</option>}
      </select></label>
      {!platform?.dockPlacement && <p role="status">{capabilityReason(platform, "dockPlacement", t, platformError)}</p>}
      <Range label={t("height")} min={40} max={90} value={config.height || 52} onChange={(height) => updateConfig({ height })} />
      <Range label={t("iconSize")} min={24} max={56} value={config.iconSize} onChange={(iconSize) => updateConfig({ iconSize })} />
      <Range label={t("spacing")} min={0} max={24} value={config.iconSpacing} onChange={(iconSpacing) => updateConfig({ iconSpacing })} />
      <Toggle label={t("autoHide")} help={platform?.autoHide ? t("autoHideHelp") : capabilityReason(platform, "autoHide", t, platformError)} disabled={!platform?.autoHide} value={Boolean(config.autoHide)} onChange={(autoHide) => updateConfig({ autoHide })} />
      {config.autoHide && !platform?.autoHide && <p role="status">{t("autoHideInactive")}</p>}
      <p className="settings-help">{t("dockHelp")}</p>
    </Card>
    <Card title={t("details")}>
      {([['showApps','showApps'],['showBattery','batteryWidget'],['showNetwork','networkWidget'],['showSystem','systemToolsWidget'],['showAudio','audio'],['showClock','showClock'],['showStats','showStats'],['showShuffle','showShuffle']] as const).map(([field,label]) => <Toggle key={field} label={t(label)} value={config[field]} onChange={(value) => updateConfig({ [field]: value })} />)}
      <Toggle label={t("clock24")} value={config.clock24} onChange={(clock24) => updateConfig({ clock24 })} />
      <Toggle label={t("clockSeconds")} value={config.clockSeconds} onChange={(clockSeconds) => updateConfig({ clockSeconds })} />
    </Card>
  </>;
}
