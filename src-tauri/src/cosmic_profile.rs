//! COSMIC user/default config resolution and recoverable multi-file writes.
//! Not a filesystem transaction: the compositor can observe intermediate files.
use crate::cosmic_background::{
    config_key, configured_source, entry_for_output, replace_output_source, target_outputs,
    validate_entry, FALLBACK,
};
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
    identity: Option<Identity>,
    user_owned: bool,
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
fn check_parent(
    path: &Path,
    owned: bool,
    allow_missing: bool,
) -> Result<Vec<(PathBuf, u64, u64)>, String> {
    if !path.is_absolute()
        || path
            .components()
            .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        return Err("COSMIC config path must be absolute without parent traversal".into());
    }
    let mut parents = Vec::new();
    for parent in path.ancestors().skip(1) {
        let metadata = match fs::symlink_metadata(parent) {
            Ok(metadata) => metadata,
            Err(error) if allow_missing && error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => return Err(error.to_string()),
        };
        if !metadata.is_dir() {
            return Err("COSMIC config ancestor must be a real directory".into());
        }
        parents.push((parent.to_owned(), metadata.dev(), metadata.ino()));
    }
    let nearest = parents.first().ok_or("Missing COSMIC config parent")?;
    let parent = fs::metadata(&nearest.0).map_err(|e| e.to_string())?;
    // SAFETY: geteuid has no arguments or memory ownership requirements.
    if (owned && parent.uid() != unsafe { libc::geteuid() }) || parent.mode() & 0o002 != 0 {
        return Err(
            "COSMIC config parent must be owned by this user and not world-writable".into(),
        );
    }
    Ok(parents)
}
impl Snapshot {
    pub fn load(path: &Path) -> Result<Self, String> {
        Self::load_kind(path, true)
    }
    fn load_kind(path: &Path, user_owned: bool) -> Result<Self, String> {
        let parents = check_parent(path, user_owned, false)?;
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
            || (user_owned && before.uid() != unsafe { libc::geteuid() })
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
            || parents != check_parent(path, user_owned, false)?
        {
            return Err("COSMIC config changed during read".into());
        }
        Ok(Self {
            path: path.to_owned(),
            original: String::from_utf8(bytes).map_err(|e| e.to_string())?,
            etag,
            identity: Some(identity),
            user_owned,
            parents,
        })
    }
    fn absent(path: &Path, original: String) -> Result<Self, String> {
        Self::absent_kind(path, original, true)
    }
    fn absent_kind(path: &Path, original: String, user_owned: bool) -> Result<Self, String> {
        match fs::symlink_metadata(path) {
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => (),
            _ => {
                return Err(format!(
                    "COSMIC config appeared or is inaccessible: {}",
                    path.display()
                ))
            }
        }
        Ok(Self {
            path: path.to_owned(),
            original,
            etag: String::new(),
            identity: None,
            user_owned,
            parents: check_parent(path, user_owned, true)?,
        })
    }
    fn parents_match(&self, fresh: &Snapshot) -> bool {
        self.parents
            .iter()
            .all(|parent| fresh.parents.contains(parent))
    }
    fn unchanged(&self) -> Result<(), String> {
        if self.identity.is_none() {
            let fresh = Self::absent_kind(&self.path, self.original.clone(), self.user_owned)?;
            if !self.parents_match(&fresh) {
                return Err("COSMIC config ancestor changed".into());
            }
            return Ok(());
        }
        let fresh = Self::load_kind(&self.path, self.user_owned)?;
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
    fn create(&self, replacement: &str) -> Result<Receipt, WriteError> {
        use std::io::Write;
        let failure = |message: String, uncertain| WriteError { message, uncertain };
        // Create missing parents one at a time; inspect existing directories
        // instead of following symlinks through create_dir_all.
        let mut missing = Vec::new();
        for parent in self.path.ancestors().skip(1) {
            match fs::symlink_metadata(parent) {
                Ok(_) => break,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => missing.push(parent),
                Err(error) => return Err(failure(error.to_string(), false)),
            }
        }
        for parent in missing.into_iter().rev() {
            use std::os::unix::fs::DirBuilderExt;
            match fs::DirBuilder::new().mode(0o700).create(parent) {
                Ok(()) => (),
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => (),
                Err(error) => return Err(failure(error.to_string(), false)),
            }
            check_parent(&parent.join("preflight"), true, false).map_err(|e| failure(e, false))?;
        }
        self.unchanged().map_err(|e| failure(e, false))?;
        let parent = self.path.parent().unwrap();
        let temp = parent.join(format!(
            ".deskmorph-{}-{}.tmp",
            std::process::id(),
            rand::random::<u64>()
        ));
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW)
            .open(&temp)
            .map_err(|e| failure(e.to_string(), false))?;
        let result = (|| {
            file.write_all(replacement.as_bytes())
                .map_err(|e| failure(e.to_string(), false))?;
            file.sync_all().map_err(|e| failure(e.to_string(), false))?;
            self.unchanged().map_err(|e| failure(e, false))?;
            // Same-directory hard-link publication is atomic and cannot replace
            // any destination, even when another writer creates it after check.
            fs::hard_link(&temp, &self.path).map_err(|e| failure(e.to_string(), false))?;
            fs::remove_file(&temp).map_err(|e| failure(e.to_string(), true))?;
            let fresh = Self::load(&self.path).map_err(|e| failure(e, true))?;
            if fresh.original != replacement {
                return Err(failure("COSMIC newly created config changed".into(), true));
            }
            Ok(Receipt {
                before: self.clone(),
                after: replacement.to_owned(),
                token: Some(fresh.etag),
            })
        })();
        let _ = fs::remove_file(&temp);
        result
    }
    fn write(&self, replacement: &str) -> Result<Receipt, WriteError> {
        self.unchanged().map_err(|message| WriteError {
            message,
            uncertain: false,
        })?;
        if self.identity.is_none() {
            return self.create(replacement);
        }
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
        let metadata_match = match (&self.before.identity, &fresh.identity) {
            (Some(before), Some(after)) => {
                before.owner == after.owner
                    && before.group == after.group
                    && before.mode == after.mode
                    && before.links == after.links
            }
            (None, Some(after)) => {
                after.owner == unsafe { libc::geteuid() } && after.mode & 0o777 == 0o600
            }
            _ => false,
        };
        if self.token.as_deref() != Some(fresh.etag.as_str())
            || fresh.original != self.after
            || !self.before.parents_match(&fresh)
            || !metadata_match
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
        if self.before.identity.is_none() {
            fresh.unchanged()?;
            fs::remove_file(&fresh.path).map_err(|e| e.to_string())?;
            self.before.unchanged()?;
            return Ok(());
        }
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
    refresh: Option<Snapshot>,
}
impl Plan {
    /// Only existing user config is handled here. Defaults/creation are separate
    /// work; missing or invalid entries fail before any write.
    #[cfg(test)]
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
            validate_entry(&snapshot.original, &output)?;
            entries.push((output, snapshot));
        }
        Ok(Self {
            controls,
            entries,
            refresh: None,
        })
    }
    /// Resolve user overrides, then the selected XDG system directory, then
    /// cosmic-bg's built-in fallback. Never fall back over an invalid user file.
    pub fn load_with_defaults(directory: &Path, system: Option<&Path>) -> Result<Self, String> {
        fn resolve(
            directory: &Path,
            system: Option<&Path>,
            key: &str,
            fallback: &str,
            validate: impl Fn(&str) -> Result<(), String>,
            controls: &mut Vec<Snapshot>,
        ) -> Result<Snapshot, String> {
            let path = directory.join(key);
            match fs::symlink_metadata(&path) {
                Ok(_) => {
                    let local = Snapshot::load(&path)?;
                    validate(&local.original)?;
                    return Ok(local);
                }
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => (),
                Err(error) => return Err(error.to_string()),
            }
            let mut text = fallback.to_owned();
            if let Some(system) = system {
                let source = system.join(key);
                match fs::symlink_metadata(&source) {
                    Ok(_) => {
                        let snapshot = Snapshot::load_kind(&source, false)?;
                        if validate(&snapshot.original).is_ok() {
                            text = snapshot.original.clone();
                        }
                        controls.push(snapshot);
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                        controls.push(Snapshot::absent_kind(&source, String::new(), false)?);
                    }
                    Err(error) => return Err(error.to_string()),
                }
            }
            validate(&text)?;
            Snapshot::absent(&path, text)
        }
        let mut controls = Vec::new();
        let same = resolve(
            directory,
            system,
            "same-on-all",
            "true",
            |s| {
                ron::from_str::<bool>(s)
                    .map(|_| ())
                    .map_err(|e| e.to_string())
            },
            &mut controls,
        )?;
        let enabled: bool = ron::from_str(&same.original).map_err(|e| e.to_string())?;
        let mut backgrounds = None;
        let mut list_snapshot = None;
        if !enabled {
            let list = resolve(
                directory,
                system,
                "backgrounds",
                "[]",
                |s| target_outputs("false", Some(s)).map(|_| ()),
                &mut controls,
            )?;
            backgrounds = Some(list.original.clone());
            list_snapshot = Some(list);
        }
        let outputs = target_outputs(&same.original, backgrounds.as_deref())?;
        controls.push(same);
        let all = resolve(
            directory,
            system,
            "all",
            FALLBACK,
            |s| validate_entry(s, "all"),
            &mut controls,
        )?;
        let mut entries = Vec::new();
        for output in outputs.iter().skip(1) {
            let fallback = entry_for_output(&all.original, output)?;
            let entry = resolve(
                directory,
                system,
                &config_key(output),
                &fallback,
                |s| validate_entry(s, output),
                &mut controls,
            )?;
            entries.push((output.clone(), entry));
        }
        let refresh = if entries.iter().any(|(_, entry)| entry.identity.is_none()) {
            // cosmic-bg ignores new output.* keys absent from its loaded map.
            // Re-publish the unchanged list last so it reloads the new entries.
            list_snapshot.take()
        } else {
            None
        };
        if let Some(list) = list_snapshot {
            controls.push(list);
        }
        entries.insert(0, ("all".into(), all));
        Ok(Self {
            controls,
            entries,
            refresh,
        })
    }
    pub fn current(&self) -> Result<String, String> {
        let mut common = None;
        for (output, entry) in &self.entries {
            let source = configured_source(&entry.original, output)?;
            if let Some(previous) = &common {
                if previous != &source {
                    return Ok(String::new());
                }
            } else {
                common = Some(source);
            }
        }
        Ok(common.flatten().unwrap_or_default())
    }
    pub fn writable(&self) -> Result<(), String> {
        use std::os::unix::ffi::OsStrExt;
        for snapshot in self
            .entries
            .iter()
            .map(|(_, snapshot)| snapshot)
            .chain(self.refresh.iter())
        {
            let parent = &snapshot.parents[0].0;
            for path in std::iter::once(parent.as_path())
                .chain(snapshot.identity.as_ref().map(|_| snapshot.path.as_path()))
            {
                let path = std::ffi::CString::new(path.as_os_str().as_bytes())
                    .map_err(|e| e.to_string())?;
                // SAFETY: CString lives through syscall; no output pointer.
                if unsafe {
                    libc::faccessat(libc::AT_FDCWD, path.as_ptr(), libc::W_OK, libc::AT_EACCESS)
                } != 0
                {
                    return Err("COSMIC wallpaper config is read-only".into());
                }
            }
        }
        Ok(())
    }
    pub fn apply(self, image: &Path) -> Result<(), String> {
        let mut writes = self
            .entries
            .into_iter()
            .map(|(output, snapshot)| {
                replace_output_source(&snapshot.original, &output, image)
                    .map(|replacement| (snapshot, replacement))
            })
            .collect::<Result<Vec<_>, _>>()?;
        if let Some(list) = self.refresh {
            let text = list.original.clone();
            writes.push((list, text));
        }
        commit(writes, &self.controls)
    }
}

const PROFILE: &str = "cosmic/com.system76.CosmicBackground/v1";
pub fn from_environment() -> Result<Plan, String> {
    let absolute = |name: &str| {
        std::env::var_os(name)
            .map(PathBuf::from)
            .filter(|p| p.is_absolute())
    };
    let home = absolute("HOME");
    let config = absolute("XDG_CONFIG_HOME")
        .or_else(|| home.as_ref().map(|p| p.join(".config")))
        .ok_or("COSMIC config home is unavailable")?;
    let data_home =
        absolute("XDG_DATA_HOME").or_else(|| home.as_ref().map(|p| p.join(".local/share")));
    let data_dirs = std::env::var_os("XDG_DATA_DIRS")
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "/usr/local/share:/usr/share".into());
    let system = data_home
        .into_iter()
        .chain(std::env::split_paths(&data_dirs).filter(|p| p.is_absolute()))
        .map(|p| p.join(PROFILE))
        .find(|p| p.is_dir());
    Plan::load_with_defaults(&config.join(PROFILE), system.as_deref())
        .map_err(|error| format!("wallpaper_config_invalid: {error}"))
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
    fn defaults_probe_does_not_write_and_apply_creates_only_missing_entry() {
        let fixture = Fixture::new();
        let directory = fixture
            .0
            .join("new-config/cosmic/com.system76.CosmicBackground/v1");
        let system = fixture.0.join("system");
        fs::create_dir(&system).unwrap();
        let default = FALLBACK.replace("3600", "73").replace("Lanczos", "Nearest");
        fs::write(system.join("all"), &default).unwrap();
        let plan = Plan::load_with_defaults(&directory, Some(&system)).unwrap();
        plan.writable().unwrap();
        assert!(!directory.exists());
        assert!(plan.current().unwrap().contains("orion_nebula"));
        plan.apply(Path::new("/new.png")).unwrap();
        let actual = fs::read_to_string(directory.join("all")).unwrap();
        assert_eq!(
            actual,
            replace_output_source(&default, "all", Path::new("/new.png")).unwrap()
        );
        assert_eq!(
            fs::metadata(directory.join("all")).unwrap().mode() & 0o777,
            0o600
        );
        assert!(!directory.join("same-on-all").exists());
        assert_eq!(fs::read_to_string(system.join("all")).unwrap(), default);
        assert_eq!(fs::read_dir(&directory).unwrap().count(), 1);
    }
    #[test]
    fn invalid_system_default_uses_builtin_but_invalid_user_config_is_preserved() {
        let fixture = Fixture::new();
        let directory = fixture.0.join("new-config");
        let system = fixture.0.join("system");
        fs::create_dir(&system).unwrap();
        fs::write(system.join("all"), FALLBACK.replace("true", "#true")).unwrap();
        Plan::load_with_defaults(&directory, Some(&system))
            .unwrap()
            .apply(Path::new("/new.png"))
            .unwrap();
        assert_eq!(
            fs::read_to_string(directory.join("all")).unwrap(),
            replace_source_for_test()
        );
        fs::write(directory.join("all"), "invalid local override").unwrap();
        assert!(Plan::load_with_defaults(&directory, Some(&system)).is_err());
        assert_eq!(
            fs::read_to_string(directory.join("all")).unwrap(),
            "invalid local override"
        );
        fn replace_source_for_test() -> String {
            replace_output_source(FALLBACK, "all", Path::new("/new.png")).unwrap()
        }
    }
    #[test]
    fn absent_output_entries_are_created_with_output_identity_and_list_refresh() {
        let fixture = Fixture::new();
        for key in ["all", "output.DP-1", "output.HDMI-1"] {
            fs::remove_file(fixture.0.join(key)).unwrap();
        }
        let before_list = fs::read(fixture.0.join("backgrounds")).unwrap();
        let plan = Plan::load_with_defaults(&fixture.0, None).unwrap();
        assert!(plan.refresh.is_some());
        plan.apply(Path::new("/new.png")).unwrap();
        for output in ["all", "DP-1", "HDMI-1"] {
            let document = fs::read_to_string(fixture.0.join(config_key(output))).unwrap();
            assert_eq!(
                configured_source(&document, output).unwrap().as_deref(),
                Some("/new.png")
            );
        }
        assert_eq!(
            fs::read(fixture.0.join("backgrounds")).unwrap(),
            before_list
        );
        assert_eq!(
            fs::read_to_string(fixture.0.join("same-on-all")).unwrap(),
            "false"
        );
    }
    #[test]
    fn creation_conflict_and_failed_creation_rollback_preserve_external_data() {
        let fixture = Fixture::new();
        let path = fixture.0.join("new-entry");
        let absent = Snapshot::absent(&path, "virtual default".into()).unwrap();
        fs::write(&path, "new external file").unwrap();
        assert!(commit(vec![(absent, "replacement".into())], &[]).is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), "new external file");
        fs::remove_file(&path).unwrap();
        let absent = Snapshot::absent(&path, "virtual default".into()).unwrap();
        let error = commit_with(vec![(absent, "replacement".into())], &[], |index| {
            if index == 1 {
                Err("post-create failure".into())
            } else {
                Ok(())
            }
        })
        .unwrap_err();
        assert!(error.contains("rollback verified"), "{error}");
        assert!(!path.exists());
        let absent = Snapshot::absent(&path, "virtual default".into()).unwrap();
        let error = commit_with(vec![(absent, "replacement".into())], &[], |index| {
            if index == 1 {
                fs::write(&path, "new external file").unwrap();
                Err("post-create external edit".into())
            } else {
                Ok(())
            }
        })
        .unwrap_err();
        assert!(error.contains("partial COSMIC state"), "{error}");
        assert_eq!(fs::read_to_string(&path).unwrap(), "new external file");
        assert!(!fs::read_dir(&fixture.0).unwrap().any(|e| e
            .unwrap()
            .file_name()
            .to_string_lossy()
            .starts_with(".deskmorph-")));
    }
    #[test]
    fn default_change_and_read_only_probe_fail_without_overwriting() {
        let fixture = Fixture::new();
        let system = fixture.0.join("system");
        fs::create_dir(&system).unwrap();
        let directory = fixture.0.join("new-config");
        let plan = Plan::load_with_defaults(&directory, Some(&system)).unwrap();
        fs::write(system.join("all"), FALLBACK).unwrap();
        assert!(plan.apply(Path::new("/new.png")).is_err());
        assert!(!directory.exists());
        let plan = fixture.load();
        fs::set_permissions(fixture.0.join("all"), fs::Permissions::from_mode(0o400)).unwrap();
        assert!(plan.writable().is_err());
        assert!(fixture.contents().iter().all(|s| s.contains("/old.png")));
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
