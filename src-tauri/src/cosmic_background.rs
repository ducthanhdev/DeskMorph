//! COSMIC RON edit primitive. Not enabled as a desktop adapter until integration
//! verifies per-output configuration, ownership and failure recovery.
use gio::prelude::*;
use ron::value::RawValue;
use serde::Deserialize;
use std::{ops::Range, path::Path};

const MAX_DOCUMENT: usize = 64 * 1024;

#[derive(Deserialize)]
struct Background<'a> {
    output: String,
    #[serde(borrow)]
    source: &'a RawValue,
}
#[derive(Deserialize)]
enum Source {
    Path(String),
}

fn source_range(document: &str) -> Result<(Range<usize>, String), String> {
    if document.len() > MAX_DOCUMENT {
        return Err("COSMIC background document exceeds 64 KiB".into());
    }
    let background: Background<'_> = ron::from_str(document).map_err(|e| e.to_string())?;
    if background.output != "all" {
        return Err("Per-output COSMIC background is not verified".into());
    }
    let Source::Path(path) = background
        .source
        .into_rust::<Source>()
        .map_err(|e| e.to_string())?;
    if path.contains('\0') || !Path::new(&path).is_absolute() {
        return Err("COSMIC image must have an absolute path".into());
    }
    let raw = background.source.get_ron();
    let start = (raw.as_ptr() as usize)
        .checked_sub(document.as_ptr() as usize)
        .ok_or("RON source is not borrowed from document")?;
    let end = start
        .checked_add(raw.len())
        .ok_or("RON source range overflow")?;
    if document.get(start..end) != Some(raw) {
        return Err("Invalid borrowed RON source range".into());
    }
    Ok((start..end, path))
}

pub fn replace_source(document: &str, path: &Path) -> Result<String, String> {
    let path = path
        .to_str()
        .filter(|value| path.is_absolute() && !value.contains('\0'))
        .ok_or("COSMIC image path must be absolute UTF-8")?;
    let (range, _) = source_range(document)?;
    let replacement = format!("Path({})", ron::to_string(path).map_err(|e| e.to_string())?);
    let mut result = document.to_owned();
    result.replace_range(range, &replacement);
    if source_range(&result)?.1 != path {
        return Err("COSMIC source replacement did not roundtrip".into());
    }
    Ok(result)
}

pub struct Document {
    file: gio::File,
    original: String,
    etag: String,
}

impl Document {
    pub fn load(path: &Path) -> Result<Self, String> {
        let metadata = std::fs::symlink_metadata(path).map_err(|e| e.to_string())?;
        if !metadata.is_file() || metadata.len() > MAX_DOCUMENT as u64 {
            return Err("COSMIC config must be a regular file at most 64 KiB".into());
        }
        let file = gio::File::for_path(path);
        let (bytes, etag) = file
            .load_contents(None::<&gio::Cancellable>)
            .map_err(|e| e.to_string())?;
        let original = String::from_utf8(bytes.to_vec()).map_err(|e| e.to_string())?;
        source_range(&original)?;
        let etag = etag
            .ok_or("COSMIC config has no concurrency token")?
            .to_string();
        Ok(Self {
            file,
            original,
            etag,
        })
    }
    pub fn source(&self) -> Result<String, String> {
        Ok(source_range(&self.original)?.1)
    }
    pub fn write_source(self, path: &Path) -> Result<(), String> {
        let replacement = replace_source(&self.original, path)?;
        self.file
            .replace_contents(
                replacement.as_bytes(),
                Some(&self.etag),
                false,
                gio::FileCreateFlags::NONE,
                None::<&gio::Cancellable>,
            )
            .map_err(|e| e.to_string())?;
        let (bytes, _) = self
            .file
            .load_contents(None::<&gio::Cancellable>)
            .map_err(|e| e.to_string())?;
        if bytes.as_slice() != replacement.as_bytes() {
            return Err("COSMIC config changed after replacement".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const ORIGINAL: &str = "(\n output: \"all\",\n // preserve this comment and unknown enum\n custom: Future(Some((nested: [1, 2]))),\n source: Path(\"/old.png\"),\n scaling_mode: Zoom,\n)";
    #[test]
    fn preserves_unknown_fields_comments_and_escaped_paths() {
        let path = Path::new("/ảnh có khoảng trắng/quote\"slash\\.png");
        let replaced = replace_source(ORIGINAL, path).unwrap();
        assert_eq!(source_range(&replaced).unwrap().1, path.to_str().unwrap());
        let (before, _) = source_range(ORIGINAL).unwrap();
        let (after, _) = source_range(&replaced).unwrap();
        assert_eq!(&ORIGINAL[..before.start], &replaced[..after.start]);
        assert_eq!(&ORIGINAL[before.end..], &replaced[after.end..]);
    }
    #[test]
    fn rejects_unsupported_ambiguous_or_invalid_config() {
        for document in [
            "(output: \"all\")",
            "(output: \"all\", source: Path(\"relative.png\"))",
            "(output: \"HDMI-A-1\", source: Path(\"/old.png\"))",
            "(output: \"all\", source: Directory(\"/images\"))",
            "(output: \"all\", source: Path(\"/a\"), source: Path(\"/b\"))",
            "(output: \"all\", source: Path(\"/a\"), broken: [)",
        ] {
            assert!(
                replace_source(document, Path::new("/new.png")).is_err(),
                "{document}"
            );
        }
        assert!(replace_source(ORIGINAL, Path::new("relative.png")).is_err());
        assert!(replace_source(ORIGINAL, Path::new("/invalid\0.png")).is_err());
        assert!(replace_source(
            "(output: \"all\", output: \"all\", source: Path(\"/a\"))",
            Path::new("/new.png")
        )
        .is_err());
        assert!(replace_source(&" ".repeat(MAX_DOCUMENT + 1), Path::new("/new.png")).is_err());
    }
    #[test]
    fn etag_conflict_preserves_external_config_and_normal_write_preserves_mode() {
        use std::os::unix::fs::PermissionsExt;
        let root = std::env::temp_dir().join(format!(
            "deskmorph-cosmic-{}-{}",
            std::process::id(),
            rand::random::<u64>()
        ));
        std::fs::create_dir(&root).unwrap();
        let path = root.join("all");
        std::fs::write(&path, ORIGINAL).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).unwrap();
        let document = Document::load(&path).unwrap();
        assert_eq!(document.source().unwrap(), "/old.png");
        let external = ORIGINAL.replace("/old.png", "/externally-edited-longer.png");
        std::fs::write(&path, &external).unwrap();
        assert!(document.write_source(Path::new("/new.png")).is_err());
        assert_eq!(std::fs::read_to_string(&path).unwrap(), external);
        Document::load(&path)
            .unwrap()
            .write_source(Path::new("/new.png"))
            .unwrap();
        assert_eq!(
            std::fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        let link = root.join("link");
        std::os::unix::fs::symlink(&path, &link).unwrap();
        assert!(Document::load(&link).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
