//! GTK resolves themes; only bounded raster copies are exposed to WebViews.
use gio::prelude::*;
use gtk::gdk_pixbuf::Pixbuf;
use gtk::prelude::*;
use std::{
    collections::{hash_map::DefaultHasher, HashSet, VecDeque},
    fs,
    hash::{Hash, Hasher},
    path::{Path, PathBuf},
    time::UNIX_EPOCH,
};

const SIDE: i32 = 64;
const SOURCE_BYTES: u64 = 2 * 1024 * 1024;
const SOURCE_PIXELS: i64 = 16_000_000;
const CACHE_FILES: usize = 512;
const PNG_BYTES: u64 = 32 * 1024;

pub(crate) struct IconCache {
    root: PathBuf,
    files: VecDeque<PathBuf>,
    used: HashSet<PathBuf>,
}
fn managed(path: &Path) -> bool {
    path.file_name()
        .and_then(|n| n.to_str())
        .is_some_and(|name| {
            name.len() == 20
                && name.ends_with(".png")
                && name.as_bytes()[..16].iter().all(|b| b.is_ascii_hexdigit())
        })
}
fn temporary_owner(path: &Path) -> Option<u32> {
    let name = path.file_name()?.to_str()?.strip_suffix(".tmp")?;
    let (key, owner) = name.split_once('.')?;
    if key.len() != 16 || !key.bytes().all(|b| b.is_ascii_hexdigit()) {
        return None;
    }
    owner.parse().ok()
}
impl IconCache {
    pub(crate) fn new(root: PathBuf) -> std::io::Result<Self> {
        fs::create_dir_all(&root)?;
        let mut files: Vec<_> = fs::read_dir(&root)?
            .filter_map(|entry| {
                let path = entry.ok()?.path();
                let metadata = fs::symlink_metadata(&path).ok()?;
                if metadata.is_file() {
                    if let Some(owner) = temporary_owner(&path) {
                        if !Path::new("/proc").join(owner.to_string()).exists() {
                            let _ = fs::remove_file(&path);
                        }
                        return None;
                    }
                    if managed(&path) && metadata.len() > PNG_BYTES {
                        let _ = fs::remove_file(&path);
                        return None;
                    }
                }
                if !managed(&path) || !metadata.is_file() {
                    return None;
                }
                Some((metadata.modified().unwrap_or(UNIX_EPOCH), path))
            })
            .collect();
        files.sort_by(|a, b| a.cmp(b));
        let mut cache = Self {
            root,
            files: files.into_iter().map(|(_, path)| path).collect(),
            used: HashSet::new(),
        };
        while cache.files.len() > CACHE_FILES {
            let path = cache.files.pop_front().unwrap();
            fs::remove_file(path)?;
        }
        Ok(cache)
    }
    pub(crate) fn resolve(
        &mut self,
        icon: &gio::Icon,
        theme: Option<&gtk::IconTheme>,
    ) -> Option<String> {
        let source = if let Some(file) = icon.downcast_ref::<gio::FileIcon>() {
            file.file().path()?
        } else {
            theme?
                .lookup_by_gicon(icon, SIDE, gtk::IconLookupFlags::FORCE_SIZE)?
                .filename()?
        };
        self.rasterize(&source)
            .map(|path| path.to_string_lossy().into_owned())
    }
    fn rasterize(&mut self, source: &Path) -> Option<PathBuf> {
        if !source.is_absolute() {
            return None;
        }
        let source = fs::canonicalize(source).ok()?;
        let metadata = fs::metadata(&source).ok()?;
        if !metadata.is_file() || metadata.len() > SOURCE_BYTES {
            return None;
        }
        let mut key = DefaultHasher::new();
        source.hash(&mut key);
        metadata.len().hash(&mut key);
        metadata
            .modified()
            .ok()?
            .duration_since(UNIX_EPOCH)
            .ok()?
            .as_nanos()
            .hash(&mut key);
        // Distinguish a replacement even if its caller preserved the mtime/size.
        use std::os::unix::fs::MetadataExt;
        metadata.ctime().hash(&mut key);
        metadata.ctime_nsec().hash(&mut key);
        let target = self.root.join(format!("{:016x}.png", key.finish()));
        if self.used.contains(&target) {
            return Some(target);
        }
        if self.used.len() >= CACHE_FILES {
            return None;
        }
        let valid_cached = fs::symlink_metadata(&target)
            .ok()
            .is_some_and(|m| m.is_file() && m.len() <= PNG_BYTES)
            && Pixbuf::file_info(&target).is_some_and(|(format, w, h)| {
                format.name().as_deref() == Some("png") && w > 0 && h > 0 && w <= SIDE && h <= SIDE
            });
        if valid_cached {
            self.used.insert(target.clone());
            return Some(target);
        }
        let (_, width, height) = Pixbuf::file_info(&source)?;
        if width <= 0 || height <= 0 || i64::from(width) * i64::from(height) > SOURCE_PIXELS {
            return None;
        }
        let image = Pixbuf::from_file_at_scale(&source, SIDE, SIDE, true).ok()?;
        if image.width() > SIDE || image.height() > SIDE {
            return None;
        }
        if !self.files.contains(&target) {
            while self.files.len() >= CACHE_FILES {
                let index = self
                    .files
                    .iter()
                    .position(|path| !self.used.contains(path))?;
                let path = self.files.remove(index)?;
                fs::remove_file(path).ok()?;
            }
        }
        let temporary = target.with_extension(format!("{}.tmp", std::process::id()));
        // The cache is owned by this app; never follow an existing temporary file.
        let reservation = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .ok()?;
        drop(reservation);
        let result = image
            .savev(&temporary, "png", &[])
            .ok()
            .filter(|_| fs::metadata(&temporary).is_ok_and(|m| m.len() <= PNG_BYTES))
            .and_then(|_| fs::rename(&temporary, &target).ok());
        if result.is_none() {
            let _ = fs::remove_file(&temporary);
            return None;
        }
        if !self.files.contains(&target) {
            self.files.push_back(target.clone());
        }
        self.used.insert(target.clone());
        Some(target)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn root() -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "deskmorph-icons-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&root).unwrap();
        root
    }
    fn svg(path: &Path, color: &str, width: i32, height: i32) {
        fs::write(path, format!(r#"<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><path fill="{color}" d="M0 0h{width}v{height}H0z"/></svg>"#)).unwrap();
    }
    #[test]
    fn raster_icons_bound_dimensions_invalidate_changes_and_reject_bad_sources() {
        let root = root();
        let cache = root.join("cache");
        fs::create_dir_all(&cache).unwrap();
        let orphan = cache.join("0000000000000000.4294967295.tmp");
        fs::write(&orphan, "partial").unwrap();
        let oversized = cache.join("0000000000000001.png");
        fs::File::create(&oversized)
            .unwrap()
            .set_len(PNG_BYTES + 1)
            .unwrap();
        let mut icons = IconCache::new(cache.clone()).unwrap();
        assert!(!orphan.exists() && !oversized.exists());
        let source = root.join("icon.svg");
        svg(&source, "#ff00ff", 256, 128);
        let first = icons.rasterize(&source).unwrap();
        let image = Pixbuf::from_file(&first).unwrap();
        assert_eq!((image.width(), image.height()), (64, 32));
        assert_eq!(icons.rasterize(&source), Some(first.clone()));
        svg(&source, "#00ff00", 128, 256);
        let changed = icons.rasterize(&source).unwrap();
        assert_ne!(first, changed);
        let image = Pixbuf::from_file(&changed).unwrap();
        assert_eq!((image.width(), image.height()), (32, 64));
        let png = root.join("source.png");
        image.savev(&png, "png", &[]).unwrap();
        assert!(icons.rasterize(&png).is_some());
        let bad = root.join("bad.png");
        fs::write(&bad, "broken").unwrap();
        assert!(icons.rasterize(&bad).is_none());
        let huge = root.join("huge.svg");
        svg(&huge, "red", 100_000, 100_000);
        assert!(icons.rasterize(&huge).is_none());
        fs::File::create(&bad)
            .unwrap()
            .set_len(SOURCE_BYTES + 1)
            .unwrap();
        assert!(icons.rasterize(&bad).is_none());
        assert!(icons.rasterize(Path::new("relative.png")).is_none());
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn cache_never_evicts_this_catalogue_icons_and_stays_bounded_across_refreshes() {
        let root = root();
        let cache = root.join("cache");
        let mut icons = IconCache::new(cache.clone()).unwrap();
        let mut first = None;
        for index in 0..CACHE_FILES {
            let source = root.join(format!("{index}.svg"));
            svg(&source, "blue", 16, 16);
            let target = icons.rasterize(&source).unwrap();
            if index == 0 {
                first = Some(target);
            }
        }
        let extra = root.join("extra.svg");
        svg(&extra, "red", 16, 16);
        assert!(icons.rasterize(&extra).is_none());
        assert!(first.unwrap().exists());
        drop(icons);
        let mut icons = IconCache::new(cache.clone()).unwrap();
        assert!(icons.rasterize(&extra).is_some());
        let files: Vec<_> = fs::read_dir(&cache)
            .unwrap()
            .map(|entry| entry.unwrap())
            .collect();
        assert_eq!(files.len(), CACHE_FILES);
        assert!(files
            .iter()
            .all(|entry| entry.metadata().unwrap().len() <= PNG_BYTES));
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    #[ignore = "requires native GTK display; run outside sandbox with --include-ignored"]
    fn theme_inheritance_hicolor_absolute_icons_and_theme_switch() {
        let root = root();
        for (name, parent) in [
            ("DeskMorphChild", "DeskMorphParent,hicolor"),
            ("DeskMorphParent", "hicolor"),
            ("DeskMorphOther", "hicolor"),
            ("hicolor", ""),
        ] {
            let directory = root.join(name);
            fs::create_dir_all(directory.join("64x64/apps")).unwrap();
            fs::write(directory.join("index.theme"), format!("[Icon Theme]\nName={name}\nInherits={parent}\nDirectories=64x64/apps\n[64x64/apps]\nSize=64\nType=Fixed\nContext=Applications\n")).unwrap();
        }
        svg(
            &root.join("DeskMorphParent/64x64/apps/deskmorph-inherited.svg"),
            "#ff00ff",
            64,
            64,
        );
        svg(
            &root.join("hicolor/64x64/apps/deskmorph-fallback.svg"),
            "#00ff00",
            64,
            64,
        );
        svg(
            &root.join("DeskMorphOther/64x64/apps/deskmorph-inherited.svg"),
            "#0000ff",
            64,
            64,
        );
        // GTK belongs to a fresh process/thread; don't mutate the user's theme.
        let output = std::process::Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "application_icons::tests::theme_child",
                "--nocapture",
            ])
            .env("DESKMORPH_ICON_THEME_FIXTURE", &root)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn theme_child() {
        let Some(root) = std::env::var_os("DESKMORPH_ICON_THEME_FIXTURE").map(PathBuf::from) else {
            return;
        };
        gtk::init().unwrap();
        let theme = gtk::IconTheme::new();
        theme.prepend_search_path(&root);
        theme.set_custom_theme(Some("DeskMorphChild"));
        let mut icons = IconCache::new(root.join("cache")).unwrap();
        let inherited = gio::ThemedIcon::new("deskmorph-inherited");
        let first = icons.resolve(inherited.upcast_ref(), Some(&theme)).unwrap();
        assert!(icons
            .resolve(
                gio::ThemedIcon::new("deskmorph-fallback").upcast_ref(),
                Some(&theme)
            )
            .is_some());
        assert!(icons
            .resolve(
                gio::ThemedIcon::new("deskmorph-does-not-exist").upcast_ref(),
                Some(&theme)
            )
            .is_none());
        let file = gio::FileIcon::new(&gio::File::for_path(
            root.join("hicolor/64x64/apps/deskmorph-fallback.svg"),
        ));
        assert!(icons.resolve(file.upcast_ref(), None).is_some());
        theme.set_custom_theme(Some("DeskMorphOther"));
        let changed = icons.resolve(inherited.upcast_ref(), Some(&theme)).unwrap();
        assert_ne!(first, changed);
        assert_ne!(
            Pixbuf::from_file(first).unwrap().pixel_bytes(),
            Pixbuf::from_file(changed).unwrap().pixel_bytes()
        );
    }
}
