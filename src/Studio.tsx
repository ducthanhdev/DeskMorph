import { ErrorText } from "./components/ErrorText";
import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { appearanceOf, type Appearance } from "./dockAppearance";
import { useConfig } from "./config/store";
import { useAsyncLifetime } from "./hooks/useAsyncLifetime";
import { usePlatform } from "./hooks/usePlatform";
import { useI18n } from "./i18n/useI18n";
import { DockSettings } from "./components/studio/DockSettings";
import { AppsSettings } from "./components/studio/AppsSettings";
import { AppearanceSettings } from "./components/studio/AppearanceSettings";
import { SystemSettings } from "./components/studio/SystemSettings";
import { WallpaperSettings } from "./components/studio/WallpaperSettings";
import { DockPreview } from "./components/studio/DockPreview";

const tabs = ["dock", "apps", "appearance", "wallpaper", "system"] as const;
type Tab = typeof tabs[number];
export function Studio() {
  const lifetime = useAsyncLifetime();
  const [activeTab, setActiveTab] = useState<Tab>("dock");
  const { config, ready, error, warning, retry, updateConfig } = useConfig();
  const { platform, error: platformError, refresh: refreshPlatform } = usePlatform();
  const { t } = useI18n();
  const [originalAppearance, setOriginalAppearance] = useState<Appearance | null>(null);
  const [restoring, setRestoring] = useState(false);
  useEffect(() => { if (ready) setOriginalAppearance(value => value || appearanceOf(config)); }, [ready, config]);
  const appearanceChanged = originalAppearance && JSON.stringify(appearanceOf(config)) !== JSON.stringify(originalAppearance);
  return <div className={`studio-app ${config.reduceMotion ? "reduce-motion" : ""}`}>
    <header className="studio-header"><div className="header-brand"><div className="logo-box"><Sparkles size={24} /></div><div><h1 className="brand-title">DeskMorph</h1><p className="brand-subtitle">{t("subtitle")}</p></div></div></header>
    {error && <div className="app-status" role="alert"><ErrorText error={error} /> <button onClick={retry}>{t("retry")}</button></div>}
    {warning && <div className="app-status" role="status">{warning.split("\n").filter(Boolean).map((line, index) => <div key={index}><ErrorText error={line} kind="warning" /></div>)}</div>}
    {platformError && <div className="app-status" role="alert"><ErrorText error={platformError} /> <button onClick={refreshPlatform}>{t("retry")}</button></div>}
    {platform?.reasons.map((reason) => <div className="app-status" role="status" key={reason}><ErrorText error={reason} /></div>)}
    {!ready ? <p className="app-status" role="status">{t("loading")}</p> : <div className="studio-body">
      <nav className="studio-nav" aria-label="Studio">{tabs.map((tab) => <button key={tab} className={`nav-btn ${activeTab === tab ? "active" : ""}`} aria-current={activeTab === tab ? "page" : undefined} onClick={() => setActiveTab(tab)}>{t(`${tab}Tab`)}</button>)}</nav>
      <main className="studio-content" key={activeTab}>
        {(activeTab === "dock" || activeTab === "appearance") && <><DockPreview /><button className="studio-button appearance-restore" disabled={!appearanceChanged || restoring} onClick={async () => {
          if (!originalAppearance || restoring) return;
          const signal = lifetime.capture();
          setRestoring(true); try { await updateConfig(originalAppearance); } finally { if (!signal.aborted) setRestoring(false); }
        }}>{t("restoreAppearance")}</button></>}
        {activeTab === "dock" && <DockSettings />}
        {activeTab === "apps" && <AppsSettings />}
        {activeTab === "appearance" && <AppearanceSettings />}
        {activeTab === "wallpaper" && <WallpaperSettings />}
        {activeTab === "system" && <SystemSettings />}
      </main>
    </div>}
  </div>;
}
