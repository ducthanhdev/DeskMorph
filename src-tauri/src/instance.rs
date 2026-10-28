//! Linux single-instance forwarding, isolated by XDG config directory.
use std::{
    fs::{self, File, OpenOptions},
    hash::{Hash, Hasher},
    io::{Read, Write},
    os::{
        fd::AsRawFd,
        unix::{
            fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
            net::{UnixListener, UnixStream},
        },
    },
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::Duration,
};
use tauri::{AppHandle, Manager};
extern "C" {
    fn flock(fd: i32, operation: i32) -> i32;
    fn geteuid() -> u32;
}
pub struct InstanceGuard {
    _lock: File,
    listener: UnixListener,
    path: PathBuf,
    shutdown: Arc<AtomicBool>,
    worker: std::sync::Mutex<Option<std::thread::JoinHandle<()>>>,
}

fn read_request(stream: &mut UnixStream) -> Result<(), String> {
    let deadline = std::time::Instant::now() + Duration::from_millis(500);
    let mut request = Vec::new();
    loop {
        let remaining = deadline
            .checked_duration_since(std::time::Instant::now())
            .ok_or("instance_request_timeout")?;
        stream
            .set_read_timeout(Some(remaining))
            .map_err(|e| e.to_string())?;
        let mut chunk = [0; 17];
        match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(n) => {
                request.extend_from_slice(&chunk[..n]);
                if request.len() > 16 {
                    return Err("instance_request_invalid".into());
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(e) => return Err(format!("instance_request_read: {e}")),
        }
    }
    if request == b"studio" {
        Ok(())
    } else {
        Err("instance_request_invalid".into())
    }
}
impl InstanceGuard {
    /// None means a running instance accepted the request.
    pub fn acquire(key: &str) -> Result<Option<Self>, String> {
        let uid = unsafe { geteuid() };
        let root = std::env::var_os("XDG_RUNTIME_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir)
            .join(format!("deskmorph-{uid}"));
        Self::acquire_in(key, root, uid)
    }
    fn acquire_in(key: &str, root: PathBuf, uid: u32) -> Result<Option<Self>, String> {
        match fs::create_dir(&root) {
            Ok(()) => fs::set_permissions(&root, fs::Permissions::from_mode(0o700))
                .map_err(|e| e.to_string())?,
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
            Err(e) => return Err(e.to_string()),
        }
        let metadata = fs::symlink_metadata(&root).map_err(|e| e.to_string())?;
        if !metadata.is_dir() || metadata.uid() != uid || metadata.permissions().mode() & 0o077 != 0
        {
            return Err(
                "Thư mục instance không thuộc người dùng hoặc quyền truy cập không phù hợp".into(),
            );
        }
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        key.hash(&mut hasher);
        let name = format!("{:x}", hasher.finish());
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .mode(0o600)
            .open(root.join(format!("{name}.lock")))
            .map_err(|e| e.to_string())?;
        let path = root.join(format!("{name}.sock"));
        if unsafe { flock(lock.as_raw_fd(), 2 | 4) } != 0 {
            let error = std::io::Error::last_os_error();
            if error.kind() != std::io::ErrorKind::WouldBlock {
                return Err(error.to_string());
            }
            for _ in 0..30 {
                if let Ok(mut stream) = UnixStream::connect(&path) {
                    stream
                        .set_write_timeout(Some(Duration::from_secs(1)))
                        .map_err(|e| e.to_string())?;
                    stream.write_all(b"studio").map_err(|e| e.to_string())?;
                    stream
                        .shutdown(std::net::Shutdown::Write)
                        .map_err(|e| e.to_string())?;
                    stream
                        .set_read_timeout(Some(Duration::from_secs(5)))
                        .map_err(|e| e.to_string())?;
                    let mut response = String::new();
                    stream
                        .take(1024)
                        .read_to_string(&mut response)
                        .map_err(|e| format!("instance_response: {e}"))?;
                    if response != "ok" {
                        return Err(format!(
                            "instance_forward_failed: {}",
                            if response.is_empty() {
                                "Phiên đang chạy chưa xác nhận mở Studio"
                            } else {
                                &response
                            }
                        ));
                    }
                    return Ok(None);
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            return Err("Phiên DeskMorph hiện tại chưa nhận được yêu cầu mở Studio".into());
        }
        match fs::remove_file(&path) {
            Ok(()) => (),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(e) => return Err(e.to_string()),
        }
        let listener = UnixListener::bind(&path).map_err(|e| e.to_string())?;
        listener.set_nonblocking(true).map_err(|e| e.to_string())?;
        Ok(Some(Self {
            _lock: lock,
            listener,
            path,
            shutdown: Arc::new(AtomicBool::new(false)),
            worker: std::sync::Mutex::new(None),
        }))
    }
    pub fn start(self, app: AppHandle) -> Result<Self, String> {
        let shutdown = self.shutdown.clone();
        self.start_with(move || {
            let (tx, rx) = std::sync::mpsc::sync_channel(1);
            let handle = app.clone();
            let stopping = shutdown.clone();
            app.run_on_main_thread(move || {
                let result = (|| {
                    if stopping.load(Ordering::Relaxed) {
                        return Err("instance_stopping".into());
                    }
                    let window = handle
                        .get_webview_window("main")
                        .ok_or("instance_window_missing")?;
                    window.show().map_err(|e| e.to_string())?;
                    window.unminimize().map_err(|e| e.to_string())?;
                    window.set_focus().map_err(|e| e.to_string())
                })();
                let _ = tx.send(result);
            })
            .map_err(|e| e.to_string())?;
            rx.recv_timeout(Duration::from_secs(1))
                .map_err(|e| format!("instance_dispatch: {e}"))?
        })
    }
    fn start_with(
        self,
        open_studio: impl Fn() -> Result<(), String> + Send + 'static,
    ) -> Result<Self, String> {
        let listener = self.listener.try_clone().map_err(|e| e.to_string())?;
        let shutdown = self.shutdown.clone();
        let worker = std::thread::Builder::new()
            .name("deskmorph-instance".into())
            .spawn(move || {
                while !shutdown.load(Ordering::Relaxed) {
                    match listener.accept() {
                        Ok((mut stream, _)) => {
                            let result = read_request(&mut stream).and_then(|_| {
                                if shutdown.load(Ordering::Relaxed) {
                                    Err("instance_stopping".into())
                                } else {
                                    open_studio()
                                }
                            });
                            let response = match result {
                                Ok(()) => "ok".into(),
                                Err(error) => format!("error: {error}"),
                            };
                            let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
                            let _ = stream.write_all(response.as_bytes());
                        }
                        Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                            std::thread::sleep(Duration::from_millis(100))
                        }
                        Err(_) => break,
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        *self.worker.lock().unwrap_or_else(|e| e.into_inner()) = Some(worker);
        Ok(self)
    }
    pub fn stop(&self) {
        self.shutdown.store(true, Ordering::Relaxed);
        if let Some(worker) = self.worker.lock().unwrap_or_else(|e| e.into_inner()).take() {
            let _ = worker.join();
        }
    }
}
impl Drop for InstanceGuard {
    fn drop(&mut self) {
        self.stop();
        let _ = fs::remove_file(&self.path);
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore = "requires native Unix socket access; run cargo test -- --include-ignored outside sandbox"]
    fn second_instance_forwards_without_acquiring_lock_and_stale_socket_recovers() {
        let key = format!("test-instance-{}", std::process::id());
        let root =
            std::env::temp_dir().join(format!("deskmorph-instance-test-{}", std::process::id()));
        let acquire = || InstanceGuard::acquire_in(&key, root.clone(), unsafe { geteuid() });
        let opened = Arc::new(std::sync::atomic::AtomicUsize::new(0));
        let count = opened.clone();
        let first = acquire()
            .unwrap()
            .unwrap()
            .start_with(move || {
                count.fetch_add(1, Ordering::SeqCst);
                Ok(())
            })
            .unwrap();
        assert!(acquire().unwrap().is_none());
        assert_eq!(opened.load(Ordering::SeqCst), 1);
        let mut stream = UnixStream::connect(&first.path).unwrap();
        stream.write_all(b"stu").unwrap();
        std::thread::sleep(Duration::from_millis(10));
        stream.write_all(b"dio").unwrap();
        stream.shutdown(std::net::Shutdown::Write).unwrap();
        let mut response = String::new();
        stream.read_to_string(&mut response).unwrap();
        assert_eq!(response, "ok");
        assert_eq!(opened.load(Ordering::SeqCst), 2);
        for bytes in [b"stu".as_slice(), b"studio-unrecognized", b"".as_slice()] {
            let mut stream = UnixStream::connect(&first.path).unwrap();
            stream.write_all(bytes).unwrap();
            stream.shutdown(std::net::Shutdown::Write).unwrap();
            let mut response = String::new();
            let read = stream.read_to_string(&mut response);
            assert!(
                response.starts_with("error:")
                    || read.is_err_and(|e| e.kind() == std::io::ErrorKind::ConnectionReset)
            );
        }
        assert_eq!(opened.load(Ordering::SeqCst), 2);
        let path = first.path.clone();
        drop(first);
        assert!(!path.exists());
        let second = acquire()
            .unwrap()
            .unwrap()
            .start_with(|| Err("fixture window error".into()))
            .unwrap();
        assert!(second.path.exists());
        assert!(acquire().err().unwrap().contains("fixture window error"));
        // A connected client that never finishes its request cannot retain the
        // listener worker indefinitely or dispatch a callback after shutdown.
        let _stalled = UnixStream::connect(&second.path).unwrap();
        std::thread::sleep(Duration::from_millis(110));
        let before = std::time::Instant::now();
        drop(second);
        assert!(before.elapsed() < Duration::from_secs(2));
        let _ = fs::remove_dir_all(root);
    }
}
