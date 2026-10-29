//! Share one short-lived desktop snapshot across Dock, preview and popups.
//! Actions still validate their target against the live adapter, bypassing this cache.
use super::{OpenWindow, WindowError};
use std::{sync::Mutex, time::{Duration, Instant}};

const MAX_AGE: Duration = Duration::from_secs(1);

#[derive(Default)]
pub struct WindowSnapshots(Mutex<Option<(Instant, Vec<OpenWindow>)>>);

impl WindowSnapshots {
    pub fn get(&self) -> Result<Vec<OpenWindow>, WindowError> {
        self.get_with(|| {
            let _trace = crate::diagnostics::command("sample_open_windows");
            super::backend()?.list()
        })
    }

    fn get_with(&self, load: impl FnOnce() -> Result<Vec<OpenWindow>, WindowError>) -> Result<Vec<OpenWindow>, WindowError> {
        let mut snapshot = self.0.lock().map_err(|_| WindowError::new("window_snapshot_unavailable", "Window snapshot lock is poisoned", "none", "list", None))?;
        let now = Instant::now();
        if let Some((at, windows)) = &*snapshot {
            if now.duration_since(*at) < MAX_AGE { return Ok(windows.clone()); }
        }
        // Never fall back to an old success after a failed refresh.
        *snapshot = None;
        let windows = load()?;
        *snapshot = Some((now, windows.clone()));
        Ok(windows)
    }

    pub fn invalidate(&self) {
        // Invalidation also recovers an empty cache after a loader panic.
        *self.0.lock().unwrap_or_else(|error| error.into_inner()) = None;
        self.0.clear_poison();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Barrier, atomic::{AtomicUsize, Ordering}};

    fn window(title: &str) -> OpenWindow {
        OpenWindow { id: "0x12".to_string().into(), class_name: "Fixture".into(), title: title.into(), is_active: false }
    }

    #[test]
    fn simultaneous_consumers_share_one_snapshot_and_get_independent_results() {
        let cache = Arc::new(WindowSnapshots::default());
        let calls = Arc::new(AtomicUsize::new(0));
        let ready = Arc::new(Barrier::new(8));
        let handles: Vec<_> = (0..8).map(|_| {
            let (cache, calls, ready) = (cache.clone(), calls.clone(), ready.clone());
            std::thread::spawn(move || {
                ready.wait();
                cache.get_with(|| { calls.fetch_add(1, Ordering::SeqCst); Ok(vec![window("Original")]) }).unwrap()
            })
        }).collect();
        for handle in handles {
            let mut result = handle.join().unwrap();
            assert_eq!(result[0].title, "Original");
            result[0].title = "Consumer mutation".into();
        }
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        assert_eq!(cache.get_with(|| panic!("Fresh cache must be reused")).unwrap()[0].title, "Original");
    }

    #[test]
    fn expired_snapshot_failure_is_not_cached_and_retry_recovers() {
        let cache = WindowSnapshots(Mutex::new(Some((Instant::now() - MAX_AGE, vec![window("Stale")]))));
        let error = cache.get_with(|| Err(WindowError::new("xprop_failed", "fixture failure", "x11", "list", None))).unwrap_err();
        assert_eq!(error.code, "xprop_failed");
        assert!(cache.0.lock().unwrap().is_none());
        let fresh = cache.get_with(|| Ok(vec![window("Restored")])).unwrap();
        assert_eq!(fresh[0].title, "Restored");
    }

    #[test]
    fn explicit_invalidation_reloads_before_expiry_and_preserves_empty_success() {
        let cache = WindowSnapshots::default();
        cache.get_with(|| Ok(vec![window("Before action")])).unwrap();
        cache.invalidate();
        assert!(cache.get_with(|| Ok(Vec::new())).unwrap().is_empty());
        assert!(cache.get_with(|| panic!("Empty success remains cacheable")).unwrap().is_empty());
    }
}
