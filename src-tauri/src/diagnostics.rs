//! Opt-in debug command timing; never records arguments or window contents.
use std::{sync::atomic::{AtomicU64, Ordering}, time::{Instant, SystemTime, UNIX_EPOCH}};

static SEQUENCE: AtomicU64 = AtomicU64::new(1);
pub struct CommandTrace { name: &'static str, id: u64, started: Instant }
fn emit(name: &str, id: u64, phase: &str, elapsed_ms: Option<f64>) {
    let at = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
    eprintln!("deskmorph_command {}", serde_json::json!({"pid":std::process::id(),"command":name,"id":id,"phase":phase,"atUnixMs":at,"elapsedMs":elapsed_ms}));
}
pub fn command(name: &'static str) -> Option<CommandTrace> {
    if !cfg!(debug_assertions) || std::env::var("DESKMORPH_TRACE_COMMANDS").as_deref() != Ok("1") { return None; }
    let id = SEQUENCE.fetch_add(1, Ordering::Relaxed);
    emit(name, id, "start", None);
    Some(CommandTrace { name, id, started: Instant::now() })
}
impl Drop for CommandTrace {
    fn drop(&mut self) { emit(self.name, self.id, "end", Some(self.started.elapsed().as_secs_f64() * 1000.0)); }
}
