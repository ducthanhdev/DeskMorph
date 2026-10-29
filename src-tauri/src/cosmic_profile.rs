//! Existing COSMIC config preflight and recoverable multi-file writes.
//! Not a filesystem transaction: the compositor can observe intermediate files.
use crate::cosmic_background::{config_key, replace_output_source, target_outputs};
use gio::prelude::*;
use std::{
    fs,
    io::Read,
    os::unix::fs::{MetadataExt, OpenOptionsExt},
    path::{Path, PathBuf},
};

const MAX_DOCUMENT: u64 = 64 * 1024;

#[derive(Clone)]
pub(super) struct Snapshot {
    path: PathBuf,
    pub original: String,
    etag: String,
    identity: Identity,
    parents: Vec<(PathBuf, u64, u64)>,
}
#[derive(Clone, PartialEq, Eq)]
struct Identity {
    device: u64,
    inode: u64,
    size: u64,
    owner: u32,
    group: u32,
    mode: u32,
    links: u64,
    modified: (i64, i64),
    changed: (i64, i64),
}
fn identity(metadata: &fs::Metadata) -> Identity {
    Identity {
        device: metadata.dev(),
        inode: metadata.ino(),
        size: metadata.len(),
        owner: metadata.uid(),
        group: metadata.gid(),
        mode: metadata.mode(),
        links: metadata.nlink(),
        modified: (metadata.mtime(), metadata.mtime_nsec()),
        changed: (metadata.ctime(), metadata.ctime_nsec()),
    }
}
struct WriteError {
    message: String,
    uncertain: bool,
}
fn check_parent(path: &Path) -> Result<Vec<(PathBuf, u64, u64)>, String> {
    if !path.is_absolute()
        || path
            .components()
            .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        return Err("COSMIC config path must be absolute without parent traversal".into());
    }
    let mut parents = Vec::new();
    for parent in path.ancestors().skip(1) {
        let metadata = fs::symlink_metadata(parent).map_err(|e| e.to_string())?;
        if !metadata.is_dir() {
            return Err("COSMIC config ancestor must be a real directory".into());
        }
        parents.push((parent.to_owned(), metadata.dev(), metadata.ino()));
    }
    let parent = fs::metadata(path.parent().ok_or("Missing COSMIC config parent")?)
        .map_err(|e| e.to_string())?;
    // SAFETY: geteuid has no arguments or memory ownership requirements.
    if parent.uid() != unsafe { libc::geteuid() } || parent.mode() & 0o002 != 0 {
        return Err(
            "COSMIC config parent must be owned by this user and not world-writable".into(),
        );
    }
    Ok(parents)
}
impl Snapshot {
    pub fn load(path: &Path) -> Result<Self, String> {
        let parents = check_parent(path)?;
        // O_NONBLOCK prevents a swapped FIFO from hanging before fstat.
        let file = fs::OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(path)
            .map_err(|e| e.to_string())?;
        let before = file.metadata().map_err(|e| e.to_string())?;
        if !before.is_file()
            || before.len() > MAX_DOCUMENT
            || before.nlink() != 1
            || before.uid() != unsafe { libc::geteuid() }
            || before.mode() & 0o002 != 0
        {
            return Err("COSMIC config must be an owned, unshared regular file at most 64 KiB, not world-writable".into());
        }
        let mut bytes = Vec::new();
        (&file)
            .take(MAX_DOCUMENT + 1)
            .read_to_end(&mut bytes)
            .map_err(|e| e.to_string())?;
        if bytes.len() as u64 > MAX_DOCUMENT {
            return Err("COSMIC config grew beyond 64 KiB".into());
        }
        let identity = identity(&before);
        let native = gio::File::for_path(path);
        let info = native
            .query_info(
                "etag::value",
                gio::FileQueryInfoFlags::NOFOLLOW_SYMLINKS,
                None::<&gio::Cancellable>,
            )
            .map_err(|e| e.to_string())?;
        let etag = info
            .attribute_string("etag::value")
            .ok_or("COSMIC config has no etag")?
            .to_string();
        if identity != self::identity(&file.metadata().map_err(|e| e.to_string())?)
            || identity != self::identity(&fs::symlink_metadata(path).map_err(|e| e.to_string())?)
            || parents != check_parent(path)?
        {
            return Err("COSMIC config changed during read".into());
        }
        Ok(Self {
            path: path.to_owned(),
            original: String::from_utf8(bytes).map_err(|e| e.to_string())?,
            etag,
            identity,
            parents,
        })
    }
    fn unchanged(&self) -> Result<(), String> {
        let fresh = Self::load(&self.path)?;
        if fresh.original != self.original
            || fresh.etag != self.etag
            || fresh.identity != self.identity
            || fresh.parents != self.parents
        {
            return Err(format!(
                "COSMIC config changed externally: {}",
                self.path.display()
            ));
        }
        Ok(())
    }
    fn write(&self, replacement: &str) -> Result<Receipt, WriteError> {
        self.unchanged().map_err(|message| WriteError {
            message,
            uncertain: false,
        })?;
        let token = gio::File::for_path(&self.path)
            .replace_contents(
                replacement.as_bytes(),
                Some(&self.etag),
                false,
                gio::FileCreateFlags::NONE,
                None::<&gio::Cancellable>,
            )
            .map_err(|e| WriteError {
                message: format!("COSMIC write outcome uncertain: {e}"),
                uncertain: true,
            })?;
        Ok(Receipt {
            before: self.clone(),
            after: replacement.to_owned(),
            token: token.map(|s| s.to_string()),
        })
    }
}
struct Receipt {
    before: Snapshot,
    after: String,
    token: Option<String>,
}
impl Receipt {
    fn current(&self) -> Result<Snapshot, String> {
        let fresh = Snapshot::load(&self.before.path)?;
        if self.token.as_deref() != Some(fresh.etag.as_str())
            || fresh.original != self.after
            || fresh.parents != self.before.parents
            || fresh.identity.owner != self.before.identity.owner
            || fresh.identity.group != self.before.identity.group
            || fresh.identity.mode != self.before.identity.mode
            || fresh.identity.links != self.before.identity.links
        {
            return Err(format!(
                "COSMIC post-write state cannot be verified: {}",
                self.before.path.display()
            ));
        }
        Ok(fresh)
    }
    fn restore(&self) -> Result<(), String> {
        // Never overwrite a newer external edit during recovery.
        let fresh = self.current()?;
        let recovery = fresh.write(&self.before.original).map_err(|e| e.message)?;
        recovery.current()?;
        Ok(())
    }
}

pub(super) fn commit(writes: Vec<(Snapshot, String)>, controls: &[Snapshot]) -> Result<(), String> {
    commit_with(writes, controls, |_| Ok(()))
}
fn commit_with(
    writes: Vec<(Snapshot, String)>,
    controls: &[Snapshot],
    mut before_step: impl FnMut(usize) -> Result<(), String>,
) -> Result<(), String> {
    // Parse and prepare all replacements before entering here. No writes on a
    // failed preflight, including stale mode/output-list snapshots.
    for snapshot in controls.iter().chain(writes.iter().map(|(s, _)| s)) {
        snapshot.unchanged()?;
    }
    let mut receipts = Vec::<Receipt>::new();
    let mut uncertain = false;
    let result: Result<(), String> = (|| {
        for (index, (snapshot, replacement)) in writes.iter().enumerate() {
            before_step(index)?;
            for control in controls {
                control.unchanged()?;
            }
            let receipt = snapshot.write(replacement).map_err(|error| {
                uncertain = error.uncertain;
                error.message
            })?;
            receipts.push(receipt);
            receipts.last().unwrap().current()?;
        }
        before_step(writes.len())?;
        for control in controls {
            control.unchanged()?;
        }
        for receipt in &receipts {
            receipt.current()?;
        }
        Ok(())
    })();
    if let Err(error) = result {
        let mut failures = Vec::new();
        for receipt in receipts.iter().rev() {
            if let Err(error) = receipt.restore() {
                failures.push(error);
            }
        }
        return Err(if failures.is_empty() && !uncertain {
            format!(
                "{error}; rollback verified for {} written file(s)",
                receipts.len()
            )
        } else {
            format!(
                "{error}; partial COSMIC state, rollback could not be verified: {}",
                if failures.is_empty() {
                    "write error leaves current file outcome unknown".into()
                } else {
                    failures.join("; ")
                }
            )
        });
    }
    Ok(())
}

pub struct Plan {
    controls: Vec<Snapshot>,
    entries: Vec<(String, Snapshot)>,
}
impl Plan {
    /// Only existing user config is handled here. Defaults/creation are separate
    /// work; missing or invalid entries fail before any write.
    pub fn load_existing(directory: &Path) -> Result<Self, String> {
        let same = Snapshot::load(&directory.join("same-on-all"))?;
        let mut controls = vec![same];
        let enabled: bool = ron::from_str(&controls[0].original).map_err(|e| e.to_string())?;
        if !enabled {
            controls.push(Snapshot::load(&directory.join("backgrounds"))?);
        }
        let outputs = target_outputs(
            &controls[0].original,
            controls.get(1).map(|s| s.original.as_str()),
        )?;
        let mut entries = Vec::new();
        for output in outputs {
            let snapshot = Snapshot::load(&directory.join(config_key(&output)))?;
            // Validate every target before returning a writable plan.
            replace_output_source(&snapshot.original, &output, Path::new("/preflight.png"))?;
            entries.push((output, snapshot));
        }
        Ok(Self { controls, entries })
    }
    pub fn apply(self, image: &Path) -> Result<(), String> {
        let writes = self
            .entries
            .into_iter()
            .map(|(output, snapshot)| {
                replace_output_source(&snapshot.original, &output, image)
                    .map(|replacement| (snapshot, replacement))
            })
            .collect::<Result<Vec<_>, _>>()?;
        commit(writes, &self.controls)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;
    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let root = std::env::temp_dir().join(format!(
                "deskmorph-cosmic-profile-{}-{}",
                std::process::id(),
                rand::random::<u64>()
            ));
            fs::create_dir(&root).unwrap();
            fs::set_permissions(&root, fs::Permissions::from_mode(0o700)).unwrap();
            for (key, value) in [
                ("same-on-all", "false"),
                ("backgrounds", "[\"DP-1\", \"HDMI-1\"]"),
            ] {
                fs::write(root.join(key), value).unwrap();
            }
            for output in ["all", "DP-1", "HDMI-1"] {
                fs::write(root.join(config_key(output)), format!("(output: {output:?}, source: Path(\"/old.png\"), filter_by_theme: true, rotation_frequency: 3600, scaling_mode: Zoom,)" )).unwrap();
                fs::set_permissions(
                    root.join(config_key(output)),
                    fs::Permissions::from_mode(0o600),
                )
                .unwrap();
            }
            Self(root)
        }
        fn load(&self) -> Plan {
            Plan::load_existing(&self.0).unwrap()
        }
        fn contents(&self) -> Vec<String> {
            ["all", "output.DP-1", "output.HDMI-1"]
                .iter()
                .map(|key| fs::read_to_string(self.0.join(key)).unwrap())
                .collect()
        }
        fn writes(plan: Plan) -> (Vec<(Snapshot, String)>, Vec<Snapshot>) {
            let writes = plan
                .entries
                .into_iter()
                .map(|(output, snapshot)| {
                    let replaced =
                        replace_output_source(&snapshot.original, &output, Path::new("/new.png"))
                            .unwrap();
                    (snapshot, replaced)
                })
                .collect();
            (writes, plan.controls)
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    #[test]
    fn existing_outputs_apply_and_preflight_errors_write_nothing() {
        let fixture = Fixture::new();
        let mode = fs::read(fixture.0.join("same-on-all")).unwrap();
        let outputs = fs::read(fixture.0.join("backgrounds")).unwrap();
        fixture.load().apply(Path::new("/new.png")).unwrap();
        assert!(fixture
            .contents()
            .iter()
            .all(|s| s.contains("Path(\"/new.png\")")));
        assert_eq!(fs::read(fixture.0.join("same-on-all")).unwrap(), mode);
        assert_eq!(fs::read(fixture.0.join("backgrounds")).unwrap(), outputs);
        let before = fixture.contents();
        fs::write(fixture.0.join("output.HDMI-1"), "invalid").unwrap();
        assert!(Plan::load_existing(&fixture.0).is_err());
        assert_eq!(&fixture.contents()[..2], &before[..2]);
        fs::remove_file(fixture.0.join("output.HDMI-1")).unwrap();
        assert!(Plan::load_existing(&fixture.0).is_err());
        assert_eq!(
            fs::read_to_string(fixture.0.join("all")).unwrap(),
            before[0]
        );
    }
    #[test]
    fn stale_plan_and_same_size_edit_are_preserved_before_any_write() {
        let fixture = Fixture::new();
        let plan = fixture.load();
        let before = fixture.contents();
        let external = before[2].replace("old.png", "ext.png");
        fs::write(fixture.0.join("output.HDMI-1"), &external).unwrap();
        assert!(plan.apply(Path::new("/new.png")).is_err());
        assert_eq!(&fixture.contents()[..2], &before[..2]);
        assert_eq!(fixture.contents()[2], external);
        let plan = fixture.load();
        fs::write(fixture.0.join("same-on-all"), "true").unwrap();
        assert!(plan.apply(Path::new("/new.png")).is_err());
        assert_eq!(&fixture.contents()[..2], &before[..2]);
    }
    #[test]
    fn mid_write_failure_restores_exact_bytes_and_permissions() {
        let fixture = Fixture::new();
        let before = fixture.contents();
        let (writes, controls) = Fixture::writes(fixture.load());
        let error = commit_with(writes, &controls, |index| {
            if index == 2 {
                Err("injected third write failure".into())
            } else {
                Ok(())
            }
        })
        .unwrap_err();
        assert!(
            error.contains("rollback verified for 2 written file(s)"),
            "{error}"
        );
        assert_eq!(fixture.contents(), before);
        for key in ["all", "output.DP-1", "output.HDMI-1"] {
            assert_eq!(
                fs::metadata(fixture.0.join(key))
                    .unwrap()
                    .permissions()
                    .mode()
                    & 0o777,
                0o600
            );
        }
    }
    #[test]
    fn real_permission_failure_reports_unverified_partial_state() {
        let fixture = Fixture::new();
        for key in ["output.DP-1", "output.HDMI-1"] {
            fs::set_permissions(fixture.0.join(key), fs::Permissions::from_mode(0o400)).unwrap();
        }
        let before = fixture.contents();
        let (writes, controls) = Fixture::writes(fixture.load());
        let result = commit_with(writes, &controls, |index| {
            if index == 1 {
                assert!(fixture.contents()[0].contains("Path(\"/new.png\")"));
                fs::set_permissions(&fixture.0, fs::Permissions::from_mode(0o500)).unwrap();
            }
            Ok(())
        });
        // Always restore the lab directory permission before assertions/cleanup.
        fs::set_permissions(&fixture.0, fs::Permissions::from_mode(0o700)).unwrap();
        let error = result.unwrap_err();
        assert!(
            error.contains("write outcome uncertain") && error.contains("partial COSMIC state"),
            "{error}"
        );
        // GIO may restore the first writable file in-place even when it cannot
        // create a temp file. Never promote that into a verified full rollback
        // for the failed second write whose outcome token was not returned.
        assert_eq!(&fixture.contents()[1..], &before[1..]);
    }
    #[test]
    fn rollback_preserves_newer_external_write_and_reports_partial_state() {
        let fixture = Fixture::new();
        let before = fixture.contents();
        let (writes, controls) = Fixture::writes(fixture.load());
        let external = before[0].replace("old.png", "external.png");
        let error = commit_with(writes, &controls, |index| {
            if index == 2 {
                fs::write(fixture.0.join("all"), &external).unwrap();
                Err("injected failure after external edit".into())
            } else {
                Ok(())
            }
        })
        .unwrap_err();
        assert!(error.contains("partial COSMIC state"), "{error}");
        assert_eq!(fixture.contents()[0], external);
        assert_eq!(&fixture.contents()[1..], &before[1..]);
    }
    #[test]
    fn post_write_control_conflict_restores_entries_without_overwriting_control() {
        let fixture = Fixture::new();
        let before = fixture.contents();
        let (writes, controls) = Fixture::writes(fixture.load());
        let count = writes.len();
        let error = commit_with(writes, &controls, |index| {
            if index == count {
                fs::write(fixture.0.join("backgrounds"), "[]").unwrap();
            }
            Ok(())
        })
        .unwrap_err();
        assert!(
            error.contains("rollback verified for 3 written file(s)"),
            "{error}"
        );
        assert_eq!(fixture.contents(), before);
        assert_eq!(
            fs::read_to_string(fixture.0.join("backgrounds")).unwrap(),
            "[]"
        );
    }
    #[test]
    fn directory_substitution_and_fifo_are_rejected_without_mutation() {
        let fixture = Fixture::new();
        let before = fixture.contents();
        let plan = fixture.load();
        let original_directory = fixture.0.with_extension("moved");
        fs::rename(&fixture.0, &original_directory).unwrap();
        fs::create_dir(&fixture.0).unwrap();
        fs::set_permissions(&fixture.0, fs::Permissions::from_mode(0o700)).unwrap();
        for entry in fs::read_dir(&original_directory).unwrap() {
            let entry = entry.unwrap();
            fs::rename(entry.path(), fixture.0.join(entry.file_name())).unwrap();
        }
        assert!(plan.apply(Path::new("/new.png")).is_err());
        assert_eq!(fixture.contents(), before);
        for entry in fs::read_dir(&fixture.0).unwrap() {
            let entry = entry.unwrap();
            fs::rename(entry.path(), original_directory.join(entry.file_name())).unwrap();
        }
        fs::remove_dir(&fixture.0).unwrap();
        fs::rename(original_directory, &fixture.0).unwrap();
        let fifo = fixture.0.join("fifo");
        let c_path = std::ffi::CString::new(fifo.as_os_str().as_encoded_bytes()).unwrap();
        // SAFETY: valid NUL-terminated owned path, mode has no pointer arguments.
        assert_eq!(unsafe { libc::mkfifo(c_path.as_ptr(), 0o600) }, 0);
        assert!(Snapshot::load(&fifo).is_err());
    }
    #[test]
    fn rejects_symlinks_hardlinks_oversize_and_insecure_permissions() {
        let fixture = Fixture::new();
        let target = fixture.0.join("all");
        let link = fixture.0.join("symlink");
        std::os::unix::fs::symlink(&target, &link).unwrap();
        assert!(Snapshot::load(&link).is_err());
        let hard = fixture.0.join("hardlink");
        fs::hard_link(&target, &hard).unwrap();
        assert!(Snapshot::load(&target).is_err());
        fs::remove_file(&hard).unwrap();
        fs::set_permissions(&target, fs::Permissions::from_mode(0o666)).unwrap();
        assert!(Snapshot::load(&target).is_err());
        fs::set_permissions(&target, fs::Permissions::from_mode(0o600)).unwrap();
        fs::write(&target, vec![b' '; MAX_DOCUMENT as usize + 1]).unwrap();
        assert!(Snapshot::load(&target).is_err());
        let real = fixture.0.join("real");
        fs::create_dir(&real).unwrap();
        fs::write(real.join("all"), "anything").unwrap();
        let alias = fixture.0.join("alias");
        std::os::unix::fs::symlink(&real, &alias).unwrap();
        assert!(Snapshot::load(&alias.join("all")).is_err());
        fs::set_permissions(&fixture.0, fs::Permissions::from_mode(0o777)).unwrap();
        assert!(Snapshot::load(&fixture.0.join("same-on-all")).is_err());
    }
}
