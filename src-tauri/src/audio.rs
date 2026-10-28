//! PulseAudio protocol (including PipeWire's PulseAudio service), without shell expansion.
use serde::Serialize;
use serde_json::Value;
use std::{io::Read, process::{Command, Stdio}, sync::{Arc, Mutex, atomic::{AtomicBool, Ordering}}, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, Manager};

#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Sink { pub name: String, pub description: String, pub volume: u32, pub muted: bool }
#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot { pub default_sink: String, pub sinks: Vec<Sink> }
#[derive(Clone, Debug, Serialize)]
pub struct AudioError { pub code: &'static str, pub message: String }
fn error(code: &'static str, message: impl ToString) -> AudioError { AudioError { code, message: message.to_string() } }
#[derive(Default)]
pub struct AudioState { stop: Arc<AtomicBool>, mutation: Arc<Mutex<()>>, worker: Mutex<Option<std::thread::JoinHandle<()>>> }

// Bound commands in time and output size; drain both pipes while the child is running.
fn pactl(args: &[&str]) -> Result<Vec<u8>, AudioError> {
    let mut child = Command::new("pactl").args(args).env("LC_ALL", "C").stdin(Stdio::null())
        .stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()
        .map_err(|e| error(if e.kind() == std::io::ErrorKind::NotFound { "audio_tool_missing" } else { "audio_spawn" }, e))?;
    let mut stdout = child.stdout.take().unwrap(); let mut stderr = child.stderr.take().unwrap();
    let out = std::thread::spawn(move || { let mut bytes = Vec::new(); let result = (&mut stdout).take(4 * 1024 * 1024 + 1).read_to_end(&mut bytes); (result, bytes) });
    let err = std::thread::spawn(move || { let mut bytes = Vec::new(); let _ = (&mut stderr).take(65537).read_to_end(&mut bytes); bytes });
    let deadline = Instant::now() + Duration::from_secs(4);
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(20)),
            Ok(None) => { let _ = child.kill(); let _ = child.wait(); break Err(error("audio_timeout", "Audio service timed out")); }
            Err(e) => { let _ = child.kill(); let _ = child.wait(); break Err(error("audio_wait", e)); }
        }
    };
    let (read, bytes) = out.join().map_err(|_| error("audio_read", "Output worker failed"))?;
    let stderr = err.join().unwrap_or_default();
    if !status?.success() { return Err(error("audio_service", String::from_utf8_lossy(&stderr).chars().take(512).collect::<String>())); }
    read.map_err(|e| error("audio_read", e))?;
    if bytes.len() > 4 * 1024 * 1024 { return Err(error("audio_output_limit", "Audio response too large")); }
    Ok(bytes)
}
fn parse_snapshot(info: &[u8], sinks: &[u8]) -> Result<Snapshot, AudioError> {
    let info: Value = serde_json::from_slice(info).map_err(|e| error("audio_response", e))?;
    let list: Value = serde_json::from_slice(sinks).map_err(|e| error("audio_response", e))?;
    let default_sink = info["default_sink_name"].as_str().ok_or_else(|| error("audio_response", "Missing default sink"))?.to_owned();
    let mut sinks = Vec::new();
    for item in list.as_array().ok_or_else(|| error("audio_response", "Invalid sink list"))? {
        let name = item["name"].as_str().filter(|s| !s.is_empty()).ok_or_else(|| error("audio_response", "Missing sink name"))?;
        let channels = item["volume"].as_object().filter(|v| !v.is_empty()).ok_or_else(|| error("audio_response", "Missing channel volumes"))?;
        let mut sum = 0.0;
        for channel in channels.values() { sum += channel["value"].as_u64().ok_or_else(|| error("audio_response", "Invalid channel volume"))? as f64 / 65536.0 * 100.0; }
        sinks.push(Sink { name: name.into(), description: item["description"].as_str().unwrap_or(name).into(), volume: (sum / channels.len() as f64).round() as u32,
            muted: item["mute"].as_bool().ok_or_else(|| error("audio_response", "Missing mute state"))? });
    }
    Ok(Snapshot { default_sink, sinks })
}
pub fn snapshot() -> Result<Snapshot, AudioError> {
    parse_snapshot(&pactl(&["--format=json", "info"])?, &pactl(&["--format=json", "list", "sinks"])?)
}
fn mutate(sink: &str, operation: &str, value: Option<u32>, muted: Option<bool>) -> Result<Snapshot, AudioError> {
    match operation {
        "volume" if value.is_some_and(|value| value <= 100) => (),
        "mute" if muted.is_some() => (),
        "default" => (),
        "volume" => return Err(error("audio_volume_range", "Volume must be 0–100")),
        "mute" => return Err(error("audio_mute_value", "Missing mute state")),
        _ => return Err(error("audio_operation", "Unknown audio operation")),
    }
    // Never reinterpret a stale selection as the current default output.
    if !snapshot()?.sinks.iter().any(|s| s.name == sink) { return Err(error("audio_sink_missing", "Selected output is no longer available")); }
    match operation {
        "volume" => { let value = value.filter(|v| *v <= 100).ok_or_else(|| error("audio_volume_range", "Volume must be 0–100"))?; pactl(&["set-sink-volume", sink, &format!("{value}%")])?; }
        "mute" => { let muted = muted.ok_or_else(|| error("audio_mute_value", "Missing mute state"))?; pactl(&["set-sink-mute", sink, if muted { "1" } else { "0" }])?; }
        "default" => { pactl(&["set-default-sink", sink])?; }
        _ => return Err(error("audio_operation", "Unknown audio operation")),
    }
    snapshot()
}
#[tauri::command]
pub async fn get_audio_snapshot() -> Result<Snapshot, AudioError> {
    tauri::async_runtime::spawn_blocking(snapshot).await.map_err(|e| error("audio_worker", e))?
}
#[tauri::command]
pub async fn change_audio(app: AppHandle, sink: String, operation: String, value: Option<u32>, muted: Option<bool>) -> Result<Snapshot, AudioError> {
    let lock = app.state::<AudioState>().mutation.clone();
    tauri::async_runtime::spawn_blocking(move || { let _guard = lock.lock().map_err(|e| error("audio_lock", e))?; mutate(&sink, &operation, value, muted) }).await.map_err(|e| error("audio_worker", e))?
}

// Subscribe only while the audio popup is visible. EOF/service failure reconnects with backoff.
// Reader threads terminate when their owned child is killed on hide or shutdown.
fn is_audio_event(line: &str) -> bool { line.contains(" on sink #") || line.contains(" on server #") }
pub fn start(app: &AppHandle) {
    let handle = app.clone(); let stop = app.state::<AudioState>().stop.clone();
    let worker = std::thread::spawn(move || {
        let app = handle;
        while !stop.load(Ordering::Relaxed) {
            if !crate::popup::is_audio_active(&app) { std::thread::sleep(Duration::from_millis(100)); continue; }
            let result = Command::new("pactl").arg("subscribe").env("LC_ALL", "C").stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::null()).spawn();
            if let Ok(mut child) = result {
                let stdout = child.stdout.take().unwrap();
                let (tx, rx) = std::sync::mpsc::sync_channel(32);
                let reader = std::thread::spawn(move || {
                    use std::io::{BufRead, BufReader};
                    for line in BufReader::new(stdout).lines() {
                        match line { Ok(line) if is_audio_event(&line) => { let _ = tx.try_send(()); }, Ok(_) => (), Err(_) => break }
                    }
                });
                let mut pending = Some(Instant::now());
                while !stop.load(Ordering::Relaxed) && crate::popup::is_audio_active(&app) {
                    match rx.recv_timeout(Duration::from_millis(100)) {
                        Ok(()) => { if pending.is_none() { pending = Some(Instant::now() + Duration::from_millis(150)); } },
                        Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
                        Err(_) => (),
                    }
                    if pending.is_some_and(|at| Instant::now() >= at) {
                        let result = snapshot(); let _ = app.emit("deskmorph:audio", &result); pending = None;
                    }
                }
                let _ = child.kill(); let _ = child.wait(); let _ = reader.join();
            }
            if crate::popup::is_audio_active(&app) { let _ = app.emit("deskmorph:audio", &snapshot()); }
            for _ in 0..20 { if stop.load(Ordering::Relaxed) || !crate::popup::is_audio_active(&app) { break; } std::thread::sleep(Duration::from_millis(100)); }
        }
    });
    *app.state::<AudioState>().worker.lock().unwrap() = Some(worker);
}
pub fn stop(app: &AppHandle) {
    let state = app.state::<AudioState>();
    state.stop.store(true, Ordering::Relaxed);
    let worker = state.worker.lock().ok().and_then(|mut worker| worker.take());
    if let Some(worker) = worker { let _ = worker.join(); }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn subscription_filters_actual_pactl_event_format() {
        assert!(is_audio_event("Event 'change' on sink #42"));
        assert!(is_audio_event("Event 'change' on server #4294967295"));
        assert!(is_audio_event("Event 'remove' on sink #42"));
        assert!(!is_audio_event("Event 'change' on sink-input #99"));
    }
    #[test]
    fn unsafe_or_invalid_writes_are_rejected_before_contacting_the_service() {
        assert_eq!(mutate("", "volume", Some(101), None).unwrap_err().code, "audio_volume_range");
        assert_eq!(mutate("", "volume", None, None).unwrap_err().code, "audio_volume_range");
        assert_eq!(mutate("", "mute", None, None).unwrap_err().code, "audio_mute_value");
        assert_eq!(mutate("", "unknown", None, None).unwrap_err().code, "audio_operation");
    }
    #[test]
    fn maps_channels_without_clamping_existing_amplification() {
        let parsed = parse_snapshot(br#"{"default_sink_name":"analog"}"#, br#"[{"name":"analog","description":"Speakers","mute":true,"volume":{"left":{"value":65536},"right":{"value":131072}}}]"#).unwrap();
        assert_eq!(parsed.sinks[0].volume, 150); assert!(parsed.sinks[0].muted);
        assert_eq!(parsed.default_sink, "analog");
        assert!(parse_snapshot(b"{}", b"[]").is_err());
        assert!(parse_snapshot(br#"{"default_sink_name":"gone"}"#, br#"[{"name":"bad","volume":{},"mute":false}]"#).is_err());
        assert!(parse_snapshot(br#"{"default_sink_name":"gone"}"#, b"[]").unwrap().sinks.is_empty());
    }
}
