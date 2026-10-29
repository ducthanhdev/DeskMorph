import { ErrorText } from "./ErrorText";
import { useEffect, useRef, useState } from "react";
import { invoke } from "../ipc";
import { listen } from "@tauri-apps/api/event";
import { usePopupActive } from "../hooks/usePopupActive";
import { MediaControls } from "./MediaControls";
import { useI18n } from "../i18n/useI18n";

type Sink = { name: string; description: string; volume: number; muted: boolean };
type Snapshot = { defaultSink: string; sinks: Sink[] };
type AudioError = { code: string; message: string };
type AudioEvent = { Ok: Snapshot } | { Err: AudioError };

export function AudioPopup({ generation }: { generation?: number }) {
  const { t } = useI18n();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const visible = usePopupActive(generation);
  const [subscribed, setSubscribed] = useState(false);
  const active = useRef(false);
  active.current = visible;
  const pending = useRef(false);
  const changing = useRef(false);
  const queuedVolume = useRef<{ sink: string; value: number } | null>(null);
  const root = useRef<HTMLElement>(null);
  const current = snapshot?.sinks.find((sink) => sink.name === snapshot.defaultSink);
  const receive = (value: Snapshot) => { setSnapshot(value); setError(null); };
  const failure = (e: unknown) => { setError(typeof e === "object" && e && "code" in e ? String(e.code) : String(e)); };
  useEffect(() => {
    const stops: (() => void)[] = [];
    let disposed = false;
    const subscribe = async () => {
      const registrations = await Promise.allSettled([
        listen<AudioEvent>("deskmorph:audio", ({ payload }) => {
          if (disposed || !active.current || pending.current || changing.current) return;
          if ("Ok" in payload) receive(payload.Ok); else failure(payload.Err);
        }),
      ]);
      for (const registration of registrations) {
        if (registration.status === "fulfilled") { if (disposed) registration.value(); else stops.push(registration.value); }
        else if (!disposed) failure(registration.reason);
      }
      if (!disposed) setSubscribed(registrations.every((result) => result.status === "fulfilled"));
    };
    void subscribe().catch((e) => { if (!disposed) failure(e); });
    root.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => { disposed = true; active.current = false; clearTimeout(timer.current); stops.forEach((stop) => stop()); };
  }, []);
  useEffect(() => {
    if (!visible) { clearTimeout(timer.current); pending.current = false; queuedVolume.current = null; return; }
    if (!subscribed) return;
    let disposed = false;
    void invoke<Snapshot>("get_audio_snapshot")
      .then((value) => { if (!disposed && active.current) receive(value); })
      .catch((e) => { if (!disposed && active.current) failure(e); });
    return () => { disposed = true; };
  }, [visible, subscribed]);
  const change = async (sink: string, operation: string, value?: number, muted?: boolean) => {
    if (!active.current) return;
    if (changing.current) {
      if (operation === "volume" && value !== undefined) queuedVolume.current = { sink, value };
      return;
    }
    clearTimeout(timer.current); pending.current = false; changing.current = true; setBusy(true); setError(null);
    try { const result = await invoke<Snapshot>("change_audio", { sink, operation, value: value ?? null, muted: muted ?? null }); if (active.current) receive(result); }
    catch (e) { if (active.current) failure(e); }
    finally {
      changing.current = false;
      if (active.current) {
        const next = queuedVolume.current; queuedVolume.current = null;
        if (next) void change(next.sink, "volume", next.value);
        else { setBusy(false); if (!pending.current) setDraft(null); }
      }
    }
  };
  const refresh = async () => {
    if (!active.current || changing.current) return;
    try { const result = await invoke<Snapshot>("get_audio_snapshot"); if (active.current && !pending.current && !changing.current) receive(result); }
    catch (e) { if (active.current) failure(e); }
  };
  return <section className="audio-popup" ref={root} aria-label={t("audio")}>
    <header><h2>{t("audio")}</h2><button onClick={() => { if (generation !== undefined) void invoke("hide_dock_context_menu", { generation }).catch((e) => { if (active.current) setError(String(e)); }); }}>{t("close")}</button></header>
    {error && <div role="alert"><p>{t("audioUnavailable")} <ErrorText error={error} /></p><button onClick={() => void refresh()}>{t("retry")}</button></div>}
    {!snapshot && !error && <p role="status">{t("loading")}</p>}
    {snapshot && <>
      {snapshot.sinks.length === 0 && <p role="status">{t("audioEmpty")}</p>}
      <fieldset className="audio-outputs" disabled={busy || !snapshot.sinks.length}><legend>{t("audioOutput")}</legend>
        {snapshot.sinks.map((sink) => <label key={sink.name}><input type="radio" name="audio-output" checked={sink.name === snapshot.defaultSink} onChange={() => void change(sink.name, "default")} />{sink.description}</label>)}
      </fieldset>
      <p className="audio-help">{t("audioFuture")}</p>
      {current && <>
        <label className="audio-volume">{t("audioVolume")} <output>{draft ?? current.volume}%</output>
          <input type="range" aria-label={t("audioVolume")} min={0} max={100} value={draft ?? Math.min(100, current.volume)} aria-busy={busy} onChange={(e) => {
            const value = Number(e.target.value); setDraft(value); pending.current = true; clearTimeout(timer.current);
            timer.current = setTimeout(() => void change(current.name, "volume", value), 180);
          }} />
        </label>
        {current.volume > 100 && <p className="audio-help">{t("audioAmplified")}</p>}
        <label className="audio-mute"><input type="checkbox" checked={current.muted} disabled={busy} onChange={(e) => void change(current.name, "mute", undefined, e.target.checked)} />{t("audioMute")}</label>
      </>}
    </>}
    <MediaControls generation={generation} />
  </section>;
}
