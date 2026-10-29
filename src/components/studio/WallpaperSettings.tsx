import { ErrorText } from "../ErrorText";
import { usePopupFocus } from "../../hooks/usePopupFocus";
import { useRemovalFocus } from "../../hooks/useRemovalFocus";
import { useEffect, useRef, useState } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { invoke } from "../../ipc";
import { useConfig, errorMessage } from "../../config/store";
import { usePlatform } from "../../hooks/usePlatform";
import { usePolling } from "../../hooks/usePolling";
import { useI18n } from "../../i18n/useI18n";
import { Card, Toggle } from "./Controls";
import { formatClock, formatClockDateTime } from "../../dateTime";
import { capabilityReason } from "../../capabilities";
interface Image { path: string; filename: string; folder: string; format: string }
interface Scan { images: Image[]; issues: { path: string; message: string }[]; limited: boolean }
interface ScheduleStatus { enabled: boolean; running: boolean; nextRunUnixMs: number | null; lastRunUnixMs: number | null; lastPath: string | null; lastError: string | null }
interface Thumbnail { path: string; thumbnail: string | null; error: string | null }
const PAGE_SIZE = 24;
export function WallpaperSettings() {
  const { config, updateConfig } = useConfig();
  const { t, locale, text } = useI18n();
  const { platform, error: platformError } = usePlatform();
  const removalFocus = useRemovalFocus();
  const libraryFocus = useRemovalFocus("button[data-library-focus]:not(:disabled)", true, "button[data-library-page]:not(:disabled)");
  const [folder, setFolder] = useState("");
  const [scan, setScan] = useState<Scan>({ images: [], issues: [], limited: false });
  const [current, setCurrent] = useState("");
  const [schedule, setSchedule] = useState<ScheduleStatus | null>(null);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState("");
  const [libraryError, setLibraryError] = useState("");
  const [pollError, setPollError] = useState("");
  const [failedApply, setFailedApply] = useState<{ path?: string } | null>(null);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [filterFolder, setFilterFolder] = useState("");
  const [format, setFormat] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [thumbnails, setThumbnails] = useState<Record<string, Thumbnail>>({});
  const mounted = useRef(false);
  const applyLock = useRef(false);
  const actionRoot = useRef<HTMLDivElement>(null);
  const actionFocus = usePopupFocus(actionRoot, true, applying, () => libraryFocus.fallback.current);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const roots = JSON.stringify(config.wallpaperFolders);
  useEffect(() => {
    let disposed = false;
    const requestId = crypto.randomUUID();
    setLoading(true); setLibraryError("");
    invoke<Scan>("scan_wallpapers", { requestId }).then((result) => {
      if (!disposed) { setScan(result); setPage(0); setThumbnails({}); }
    }).catch((e) => { if (!disposed) setLibraryError(errorMessage(e)); })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; void invoke("cancel_wallpaper_scan", { requestId }).catch(console.error); };
  }, [roots, config.wallpaperRecursive, refresh]);
  usePolling(async (signal) => {
    try { const path = await invoke<string>("get_current_wallpaper"); if (!signal.aborted) { setCurrent(path); setPollError(""); } }
    catch (e) { if (!signal.aborted) setPollError(errorMessage(e)); }
  }, 3000, Boolean(platform?.wallpaper));
  usePolling(async (signal) => {
    try { const status = await invoke<ScheduleStatus>("get_wallpaper_schedule_status"); if (!signal.aborted) setSchedule(status); }
    catch (e) { if (!signal.aborted) setPollError(errorMessage(e)); }
  }, 2000, Boolean(platform?.wallpaper));
  const favorites = new Set(config.wallpaperFavorites);
  const filtered = scan.images.filter((image) => (!query || image.filename.toLocaleLowerCase().includes(query.toLocaleLowerCase())) && (!filterFolder || image.folder === filterFolder) && (!format || image.format === format) && (!favoritesOnly || favorites.has(image.path)));
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const visible = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const visiblePaths = JSON.stringify(visible.map((image) => image.path));
  useEffect(() => {
    let disposed = false;
    const paths: string[] = JSON.parse(visiblePaths);
    if (!paths.length || loading) return;
    invoke<Thumbnail[]>("wallpaper_thumbnails", { paths }).then((result) => {
      if (!disposed) setThumbnails(Object.fromEntries(result.map((item) => [item.path, item])));
    }).catch((e) => { if (!disposed) setLibraryError(errorMessage(e)); });
    return () => { disposed = true; };
  }, [visiblePaths, loading, refresh]);
  const apply = async (path?: string) => {
    if (!platform?.wallpaper || applyLock.current) return;
    applyLock.current = true; setApplying(true); setStatus(""); setError(""); setFailedApply(null);
    try {
      let applied = path;
      if (path) { if (!await invoke<boolean>("set_wallpaper", { path })) throw new Error(t("wallpaperError")); }
      else applied = await invoke<string>("shuffle_wallpaper");
      if (mounted.current) { setCurrent(applied || ""); setStatus(t("wallpaperApplied")); setError(""); }
    } catch (e) { if (mounted.current) { setError(errorMessage(e)); setFailedApply({ path }); } }
    finally { applyLock.current = false; if (mounted.current) setApplying(false); }
  };
  return <div {...actionFocus} ref={(element) => { removalFocus.root.current = element; actionRoot.current = element; }}
    onFocusCapture={(event) => { removalFocus.onFocusCapture(event); actionFocus.onFocusCapture(event); }}><Card title={t("wallpaperTab")}>
    <p className="settings-help">{t("wallpaperHelp")}</p>
    {!platform?.wallpaper && <p role="status">{capabilityReason(platform, "wallpaper", t, platformError)}</p>}
    <form className="settings-inline" onSubmit={async (e) => {
      e.preventDefault(); const path = folder.trim();
      if (!path.startsWith("/")) { setError(t("absoluteFolder")); return; }
      if (await updateConfig({ wallpaperFolders: [...new Set([...config.wallpaperFolders, path])] })) setFolder("");
    }}><input ref={removalFocus.fallback} aria-label={t("folder")} placeholder={t("folder")} value={folder} onChange={(e) => setFolder(e.target.value)} /><button className="studio-button" type="submit">{t("addFolder")}</button></form>
    {!config.wallpaperFolders.length && <p className="settings-help">{t("defaultFolders")}</p>}
    {config.wallpaperFolders.map((path) => <div className="settings-inline" key={path}><code className="wallpaper-folder-path">{path}</code><button data-remove-focus aria-label={`${t("remove")} ${path}`} onClick={() => void updateConfig({ wallpaperFolders: config.wallpaperFolders.filter((item) => item !== path) })}>{t("remove")}</button></div>)}
    <Toggle label={t("recursive")} help={t("recursiveHelp")} value={config.wallpaperRecursive} onChange={(wallpaperRecursive) => updateConfig({ wallpaperRecursive })} />
    <div className="settings-inline"><button onClick={() => setRefresh((value) => value + 1)}>{t("scan")}</button><button disabled={!platform?.wallpaper || applying || !scan.images.length} onClick={() => void apply()}>{t("shuffleNow")}</button></div>
    <section className="wallpaper-schedule" aria-label={t("schedule")}>
      <Toggle label={t("schedule")} help={t("scheduleHelp")} disabled={!platform?.wallpaper} value={config.wallpaperScheduleEnabled} onChange={(wallpaperScheduleEnabled) => updateConfig({ wallpaperScheduleEnabled })} />
      <label className="settings-field">{t("interval")}<select aria-label={t("interval")} value={config.wallpaperIntervalMinutes} onChange={(e) => void updateConfig({ wallpaperIntervalMinutes: Number(e.target.value) })}>{[...new Set([1, 5, 15, 30, 60, config.wallpaperIntervalMinutes])].sort((a,b) => a-b).map((minutes) => <option key={minutes} value={minutes}>{minutes} {t("minutes")}</option>)}</select></label>
      {config.wallpaperScheduleEnabled && schedule?.nextRunUnixMs && <p className="settings-help" role="status">{t("nextWallpaper")}: {formatClock(schedule.nextRunUnixMs, locale, config)}</p>}
      {schedule?.running && <p role="status">{t("changingWallpaper")}</p>}
      {schedule?.lastRunUnixMs && <p className="settings-help">{t("lastWallpaperAttempt")}: {formatClockDateTime(schedule.lastRunUnixMs, locale, config)}</p>}
      {schedule?.lastError && <p role="alert">{t("scheduleError")}: <ErrorText error={schedule.lastError} /></p>}
    </section>
    {current && <p className="settings-help">{t("currentWallpaper")}: <span className="wallpaper-folder-path">{current}</span></p>}
    <div ref={libraryFocus.root} onFocusCapture={libraryFocus.onFocusCapture}>
    <div className="wallpaper-filters">
      <input ref={libraryFocus.fallback} aria-label={t("searchWallpapers")} placeholder={t("searchWallpapers")} value={query} onChange={(e) => { setQuery(e.target.value); setPage(0); }} />
      <select aria-label={t("filterFolder")} value={filterFolder} onChange={(e) => { setFilterFolder(e.target.value); setPage(0); }}><option value="">{t("allFolders")}</option>{[...new Set(scan.images.map((image) => image.folder))].sort().map((path) => <option key={path} value={path}>{path}</option>)}</select>
      <select aria-label={t("format")} value={format} onChange={(e) => { setFormat(e.target.value); setPage(0); }}><option value="">{t("allFormats")}</option>{[...new Set(scan.images.map((image) => image.format))].sort().map((value) => <option key={value} value={value}>{value.toUpperCase()}</option>)}</select>
      <Toggle label={t("favoritesOnly")} value={favoritesOnly} onChange={(value) => { setFavoritesOnly(value); setPage(0); }} />
    </div>
    {libraryError && <p role="alert"><ErrorText error={libraryError} /> <button onClick={() => setRefresh((value) => value + 1)}>{t("retry")}</button></p>}
    {pollError && <p role="alert"><ErrorText error={pollError} /></p>}
    {error && <p role="alert"><ErrorText error={error} /> {failedApply && <button disabled={applying} onClick={() => void apply(failedApply.path)}>{t("retry")}</button>}</p>}{status && <p role="status">{text(status)}</p>}
    {scan.limited && <p role="status">{t("scanLimited")}</p>}
    {scan.issues.length > 0 && <details className="wallpaper-issues" onToggle={(event) => setIssuesOpen(event.currentTarget.open)}><summary role="button" aria-expanded={issuesOpen}>{t("scanIssues")} ({scan.issues.length})</summary><ul>{scan.issues.map((issue, i) => <li key={i}><code>{issue.path}</code>: {issue.message}</li>)}</ul></details>}
    {loading ? <p role="status">{t("loading")}</p> : !filtered.length ? <p role="status">{t("noWallpapers")}</p> : <>
      <p className="settings-help" role="status" aria-atomic="true">{filtered.length} • {t("page")} {currentPage + 1}/{pages}</p>
      <div className="wallpaper-grid">{visible.map((image) => <article key={image.path} className={`wallpaper-library-card ${current === image.path ? "is-current" : ""}`}>
        <button className="wallpaper-apply" aria-label={`${t("apply")} ${image.filename}`} aria-pressed={current === image.path} disabled={!platform?.wallpaper || applying} onClick={() => void apply(image.path)}>
          {thumbnails[image.path]?.thumbnail ? <img className="wallpaper-thumb-img" loading="lazy" src={convertFileSrc(thumbnails[image.path].thumbnail!)} alt="" onError={() => setThumbnails((previous) => ({ ...previous, [image.path]: { path: image.path, thumbnail: null, error: "unavailable" } }))} /> : <div className="wallpaper-thumb-placeholder">{thumbnails[image.path]?.error ? t("thumbnailError") : t("loading")}</div>}
          <span className="wallpaper-name">{image.filename}</span>
        </button>
        <button data-popup-focus-scope data-library-focus className="wallpaper-favorite" aria-label={`${t("favorite")} ${image.filename}`} aria-pressed={favorites.has(image.path)} onClick={() => void updateConfig({ wallpaperFavorites: favorites.has(image.path) ? config.wallpaperFavorites.filter((path) => path !== image.path) : [...config.wallpaperFavorites, image.path] })}>{favorites.has(image.path) ? "★" : "☆"}</button>
      </article>)}</div>
      <div className="settings-inline"><button data-popup-focus-scope data-library-focus data-library-page disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>{t("previousPage")}</button><button data-popup-focus-scope data-library-focus data-library-page disabled={currentPage >= pages - 1} onClick={() => setPage(currentPage + 1)}>{t("nextPage")}</button></div>
    </>}
    </div>
  </Card></div>;
}
