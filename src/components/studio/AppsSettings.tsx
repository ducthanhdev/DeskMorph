import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useConfig, errorMessage } from "../../config/store";
import { useInstalledApps } from "../../hooks/useInstalledApps";
import { installedForPin, pinFromApp, searchApps } from "../../appSearch";
import { useI18n } from "../../i18n/useI18n";
import { AppIcon } from "../AppIcon";
import { Card } from "./Controls";
export function AppsSettings() {
  const { config, mutatePin } = useConfig();
  const { apps, loading, error, refresh } = useInstalledApps();
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [operationError, setOperationError] = useState("");
  return <>
    <Card title={t("pinnedApps")}>
      {config.pinnedApps?.map((pin, index) => {
        const app = installedForPin(pin, apps);
        return <div className="studio-app-row" key={pin.id}><AppIcon path={app?.iconPath} size={28} /><span><strong>{pin.name}</strong>{pin.desktopId && !loading && !error && !app && <small>{t("unavailable")}</small>}</span>
          <input type="checkbox" aria-label={`${t("pin")} ${pin.name}`} checked={pin.enabled !== false} onChange={() => void mutatePin("toggleEnabled", pin.id)} />
          <button aria-label={`${t("moveLeft")} ${pin.name}`} disabled={index === 0} onClick={() => void mutatePin("move", pin.id, undefined, index - 1)}>←</button>
          <button aria-label={`${t("moveRight")} ${pin.name}`} disabled={index === config.pinnedApps!.length - 1} onClick={() => void mutatePin("move", pin.id, undefined, index + 1)}>→</button>
          <button aria-label={`${t("unpin")} ${pin.name}`} onClick={() => void mutatePin("remove", pin.id)}>{t("unpin")}</button>
        </div>;
      })}
    </Card>
    <Card title={t("appsTab")}>
      <div className="settings-inline"><input aria-label={t("searchApps")} placeholder={t("searchApps")} value={query} onChange={(e) => setQuery(e.target.value)} /><button className="studio-button" onClick={refresh}>{t("refresh")}</button></div>
      {(error || operationError) && <p role="alert">{error || operationError}</p>}{loading && <p role="status">{t("scanningApps")}</p>}
      {!loading && !error && !searchApps(apps, query).length && <p role="status">{t("noApps")}</p>}
      <div className="studio-app-list">{searchApps(apps, query).slice(0, 60).map((app) => {
        const existing = config.pinnedApps?.find((pin) => installedForPin(pin, apps)?.id === app.id);
        const pinned = existing && existing.enabled !== false;
        return <div className="studio-app-row" key={app.id}><AppIcon path={app.iconPath} size={28} /><span><strong>{app.name}</strong><small>{app.genericName || app.id}</small></span>
          <button onClick={async () => { try { await invoke("launch_installed_app", { id: app.id, action: null }); setOperationError(""); } catch (e) { setOperationError(errorMessage(e)); } }}>{t("open")}</button>
          <button aria-label={`${pinned ? t("unpin") : t("pin")} ${app.name}`} onClick={() => void mutatePin(pinned ? "remove" : "add", existing?.id || app.id, existing || pinFromApp(app))}>{pinned ? t("unpin") : t("pin")}</button>
        </div>;
      })}</div>
    </Card>
  </>;
}
