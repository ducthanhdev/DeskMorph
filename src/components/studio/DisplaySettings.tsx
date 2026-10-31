import { useState } from "react";
import { invoke } from "../../ipc";
import { errorMessage } from "../../commandError";
import { useDisplays } from "../../hooks/useDisplays";
import { useI18n } from "../../i18n/useI18n";
import { ErrorText } from "../ErrorText";
import { Card } from "./Controls";
import { useAsyncLifetime } from "../../hooks/useAsyncLifetime";

export function DisplaySettings() {
  const { state, error, refresh } = useDisplays();
  const { t, language } = useI18n();
  const lifetime = useAsyncLifetime();
  const [openError, setOpenError] = useState("");
  const [opening, setOpening] = useState(false);
  const format = (value: number) => new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(value);
  const active = state?.logicalMonitors ?? [];
  return <Card title={t("displaysTab")}>
    <p className="settings-help">{t("displayPrimaryHelp")}</p>
    <div className="display-actions">
      <button type="button" onClick={refresh}>{t("displayRefresh")}</button>
      <button type="button" disabled={opening} onClick={async () => {
        const signal = lifetime.capture();
        setOpening(true); setOpenError("");
        try { await invoke("open_display_settings"); }
        catch (failure) { if (!signal.aborted) setOpenError(errorMessage(failure)); }
        finally { if (!signal.aborted) setOpening(false); }
      }}>{t("displayOpenSettings")}</button>
    </div>
    {openError && <p role="alert"><ErrorText error={openError} /></p>}
    {error ? <p role="alert"><ErrorText error={error} /></p> : !state ? <p role="status">{t("loading")}</p> : <>
      <p role="status"><ErrorText error={state.capabilities.reason} /></p>
      {state.capabilities.canRead && <>
        {active.length === 1 && <p className="settings-help">{t("displaySingle")}</p>}
        {active.length === 0 && <p role="status">{t("displayNoneActive")}</p>}
        <ul className="display-list" aria-label={t("displayList")}>
          {active.map(group => <li key={group.id} className="display-item">
            <h3>{group.name}</h3>
            <p><strong>{group.primary ? t("displayPrimary") : t("displaySecondary")}</strong>{group.connectors.length > 1 && ` · ${t("displayMirror")}`}</p>
            <p>{group.connectors.join(" + ")} · {format(group.scale * 100)}% · {t("displayCoordinates")} ({group.x}, {group.y})</p>
            {state.physicalMonitors.filter(monitor => monitor.logicalId === group.id).map(monitor => <p key={monitor.connector}>
              {monitor.connector}: {monitor.width} × {monitor.height} · {monitor.refreshHz === null ? "—" : format(monitor.refreshHz)} Hz
            </p>)}
            <button type="button" disabled aria-label={`${group.name}: ${group.primary ? t("displayAlreadyPrimary") : t("displaySetPrimary")}`}>
              {group.primary ? t("displayAlreadyPrimary") : t("displaySetPrimary")}
            </button>
          </li>)}
          {state.physicalMonitors.filter(monitor => !monitor.active).map(monitor => <li key={monitor.connector} className="display-item">
            <h3>{monitor.name}</h3><p>{monitor.connector} · {t("displayInactive")}</p>
          </li>)}
        </ul>
      </>}
    </>}
  </Card>;
}
