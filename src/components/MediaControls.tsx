import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { usePopupActive } from "../hooks/usePopupActive";
import { useI18n } from "../i18n/useI18n";
type Player = { name: string; owner: string; identity: string; title: string; artists: string[]; artUrl: string; status: string; canPlay: boolean; canPause: boolean; canNext: boolean; canPrevious: boolean };
export function MediaControls({ generation }: { generation?: number }) {
  const { t } = useI18n();
  const [players, setPlayers] = useState<Player[]>([]);
  const [selection, setSelection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [artwork, setArtwork] = useState<string | null>(null);
  const [artworkError, setArtworkError] = useState(false);
  const [busy, setBusy] = useState(false);
  const visible = usePopupActive(generation);
  const [subscribed, setSubscribed] = useState(false);
  const active = useRef(false);
  active.current = visible;
  const changing = useRef(false);
  const player = players.find((player) => `${player.name}:${player.owner}` === selection) ?? players[0];
  useEffect(() => {
    let disposed = false; setArtwork(null); setArtworkError(false);
    if (player?.artUrl && active.current) {
      void invoke<string | null>("get_media_artwork", { name: player.name, expectedOwner: player.owner })
        .then((data) => { if (!disposed && active.current) setArtwork(data); })
        .catch(() => { if (!disposed && active.current) setArtworkError(true); });
    }
    return () => { disposed = true; };
  }, [player?.name, player?.owner, player?.artUrl]);
  const refresh = async (signal?: AbortSignal) => {
    try { const values = await invoke<Player[]>("get_media_players"); if (active.current && !signal?.aborted) { setPlayers(values); setError(null); } }
    catch (e) { if (active.current && !signal?.aborted) setError(String(e)); }
  };
  useEffect(() => {
    let disposed = false; const stops: (() => void)[] = [];
    const start = async () => {
      const results = await Promise.allSettled([
        listen<{ Ok: Player[] } | { Err: string }>("deskmorph:media", ({ payload }) => {
          if (disposed || !active.current) return;
          if ("Ok" in payload) { setPlayers(payload.Ok); setError(null); } else setError(payload.Err);
        }),
      ]);
      for (const result of results) { if (result.status === "fulfilled") { if (disposed) result.value(); else stops.push(result.value); } else if (!disposed) setError(String(result.reason)); }
      if (!disposed) setSubscribed(results.every((result) => result.status === "fulfilled"));
    };
    void start();
    return () => { disposed = true; active.current = false; stops.forEach((stop) => stop()); };
  }, []);
  useEffect(() => {
    if (!visible || !subscribed) return;
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [visible, subscribed]);
  const control = async (action: string) => {
    if (!player || changing.current || !active.current) return;
    changing.current = true; setBusy(true); setError(null);
    try { await invoke("control_media", { name: player.name, expectedOwner: player.owner, action }); await refresh(); }
    catch (e) { if (active.current) setError(String(e)); }
    finally { changing.current = false; if (active.current) setBusy(false); }
  };
  return <section className="media-controls" aria-label={t("media")}>
    <h3>{t("media")}</h3>
    {error && <p role="alert">{t("mediaError")} ({error}) <button onClick={() => void refresh()}>{t("retry")}</button></p>}
    {!player && !error && <p role="status">{t("mediaEmpty")}</p>}
    {players.length > 1 && <fieldset disabled={busy}><legend>{t("mediaPlayer")}</legend>{players.map((item) => <label key={`${item.name}:${item.owner}`}><input type="radio" name="media-player" checked={item.name === player?.name && item.owner === player?.owner} onChange={() => setSelection(`${item.name}:${item.owner}`)} />{item.identity || item.name}</label>)}</fieldset>}
    {player && <>
      {artwork && <img className="media-artwork" src={artwork} alt={t("mediaArtwork")} onError={() => { setArtwork(null); setArtworkError(true); }} />}
      {artworkError && <p>{t("mediaArtworkError")}</p>}
      <strong>{player.title || t("unknown")}</strong>
      <p>{player.artists.join(", ") || player.identity}</p>
      <p role="status">{player.status === "Playing" ? t("mediaPlaying") : player.status === "Paused" ? t("mediaPaused") : t("mediaStopped")}</p>
      <div className="media-buttons">
        <button disabled={busy || !player.canPrevious} onClick={() => void control("Previous")}>{t("mediaPrevious")}</button>
        <button disabled={busy || (player.status === "Playing" ? !player.canPause : !player.canPlay)} onClick={() => void control(player.status === "Playing" ? "Pause" : "Play")}>{player.status === "Playing" ? t("mediaPause") : t("mediaPlay")}</button>
        <button disabled={busy || !player.canNext} onClick={() => void control("Next")}>{t("mediaNext")}</button>
      </div>
    </>}
  </section>;
}
