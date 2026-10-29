//! COSMIC RON source editing and schema validation for the background adapter.
#[cfg(test)]
use crate::cosmic_profile::{commit, Snapshot};
use ron::value::RawValue;
use serde::{Deserialize, Serialize};
use std::{ops::Range, path::Path};

const MAX_DOCUMENT: usize = 64 * 1024;

#[derive(Deserialize)]
struct Background<'a> {
    output: String,
    #[serde(borrow)]
    source: &'a RawValue,
}
#[derive(Deserialize, Serialize)]
enum Source {
    Path(String),
    Color(Color),
}

#[derive(Deserialize, Serialize)]
enum Color {
    Single([f32; 3]),
    Gradient(Gradient),
}

#[derive(Deserialize, Serialize)]
struct Gradient {
    colors: Vec<[f32; 3]>,
    radius: f32,
}

// Schema of the installed cosmic-bg 1.11.0 (9520e16). Keep the permissive
// byte-preserving editor separate: the adapter must validate the consumer's
// complete schema before claiming a write can be consumed.
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Entry {
    output: String,
    source: Source,
    filter_by_theme: bool,
    rotation_frequency: u64,
    #[serde(default)]
    filter_method: FilterMethod,
    #[serde(default)]
    scaling_mode: ScalingMode,
    #[serde(default)]
    sampling_method: SamplingMethod,
}
#[derive(Deserialize, Serialize, Default)]
enum FilterMethod {
    Nearest,
    Linear,
    #[default]
    Lanczos,
}
#[derive(Deserialize, Serialize, Default)]
enum ScalingMode {
    Fit([f32; 3]),
    Stretch,
    #[default]
    Zoom,
}
#[derive(Deserialize, Serialize, Default)]
enum SamplingMethod {
    #[default]
    Alphanumeric,
    Random,
}

pub fn validate_entry(document: &str, output: &str) -> Result<(), String> {
    source_range(document, output)?;
    let _: Entry = ron::from_str(document).map_err(|e| e.to_string())?;
    Ok(())
}
pub fn entry_for_output(document: &str, output: &str) -> Result<String, String> {
    validate_entry(document, "all")?;
    let mut entry: Entry = ron::from_str(document).map_err(|e| e.to_string())?;
    entry.output = output.to_owned();
    ron::to_string(&entry).map_err(|e| e.to_string())
}
pub fn configured_source(document: &str, output: &str) -> Result<Option<String>, String> {
    validate_entry(document, output)?;
    Ok(source_range(document, output)?.1)
}
// Mirrors Entry::fallback in the verified cosmic-bg source, including theme,
// rotation and scaling defaults. Used when its system Entry cannot be parsed.
pub const FALLBACK: &str = r#"(output: "all", source: Path("/usr/share/backgrounds/cosmic/orion_nebula_nasa_heic0601a.jpg"), filter_by_theme: true, rotation_frequency: 3600, filter_method: Lanczos, scaling_mode: Zoom, sampling_method: Alphanumeric,)"#;

fn source_range(
    document: &str,
    expected_output: &str,
) -> Result<(Range<usize>, Option<String>), String> {
    if document.len() > MAX_DOCUMENT {
        return Err("COSMIC background document exceeds 64 KiB".into());
    }
    let background: Background<'_> = ron::from_str(document).map_err(|e| e.to_string())?;
    if background.output != expected_output {
        return Err("COSMIC output does not match its config key".into());
    }
    let source = background
        .source
        .into_rust::<Source>()
        .map_err(|e| e.to_string())?;
    let path = match source {
        Source::Path(path) => {
            if path.contains('\0') || !Path::new(&path).is_absolute() {
                return Err("COSMIC source must have an absolute path".into());
            }
            Some(path)
        }
        Source::Color(color) => {
            // Accept the installed COSMIC color schema, but reject non-finite
            // floats rather than treating a malformed source as a valid image.
            let valid = match color {
                Color::Single(rgb) => rgb.iter().all(|v| v.is_finite()),
                Color::Gradient(gradient) => {
                    gradient.radius.is_finite()
                        && gradient.colors.iter().flatten().all(|v| v.is_finite())
                }
            };
            if !valid {
                return Err("COSMIC color contains non-finite values".into());
            }
            None
        }
    };
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

#[cfg(test)]
pub fn replace_source(document: &str, path: &Path) -> Result<String, String> {
    replace_output_source(document, "all", path)
}

pub fn replace_output_source(document: &str, output: &str, path: &Path) -> Result<String, String> {
    let path = path
        .to_str()
        .filter(|value| path.is_absolute() && !value.contains('\0'))
        .ok_or("COSMIC image path must be absolute UTF-8")?;
    let (range, _) = source_range(document, output)?;
    let replacement = format!("Path({})", ron::to_string(path).map_err(|e| e.to_string())?);
    let mut result = document.to_owned();
    result.replace_range(range, &replacement);
    if source_range(&result, output)?.1.as_deref() != Some(path) {
        return Err("COSMIC source replacement did not roundtrip".into());
    }
    Ok(result)
}

/// Resolve the existing COSMIC entries affected by the application's global
/// wallpaper action. Include `all` so a later connected output uses the same
/// image, while retaining the user's same-on-all setting and output list.
/// This is planning only: callers must load/validate every target before writes.
pub fn target_outputs(same_on_all: &str, backgrounds: Option<&str>) -> Result<Vec<String>, String> {
    if same_on_all.len() > MAX_DOCUMENT {
        return Err("COSMIC same-on-all document exceeds 64 KiB".into());
    }
    let same: bool = ron::from_str(same_on_all).map_err(|e| e.to_string())?;
    let mut outputs = vec!["all".to_owned()];
    if same {
        return Ok(outputs);
    }
    let backgrounds = backgrounds.ok_or("COSMIC per-output list is missing")?;
    if backgrounds.len() > MAX_DOCUMENT {
        return Err("COSMIC output list exceeds 64 KiB".into());
    }
    let names: Vec<String> = ron::from_str(backgrounds).map_err(|e| e.to_string())?;
    if names.len() > 64 {
        return Err("COSMIC output list exceeds 64 entries".into());
    }
    let mut seen = std::collections::HashSet::new();
    for name in names {
        if name.is_empty()
            || name == "all"
            || name.len() > 255
            || name
                .chars()
                .any(|c| c == '/' || c == '\\' || c.is_control())
        {
            return Err("Invalid COSMIC output name".into());
        }
        if !seen.insert(name.clone()) {
            return Err("Duplicate COSMIC output name".into());
        }
        outputs.push(name);
    }
    Ok(outputs)
}

pub fn config_key(output: &str) -> String {
    if output == "all" {
        "all".into()
    } else {
        format!("output.{output}")
    }
}

#[cfg(test)]
pub struct Document {
    snapshot: Snapshot,
    output: String,
}
#[cfg(test)]
impl Document {
    pub fn load(path: &Path) -> Result<Self, String> {
        Self::load_output(path, "all")
    }
    pub fn load_output(path: &Path, output: &str) -> Result<Self, String> {
        let snapshot = Snapshot::load(path)?;
        source_range(&snapshot.original, output)?;
        Ok(Self {
            snapshot,
            output: output.to_owned(),
        })
    }
    pub fn source(&self) -> Result<Option<String>, String> {
        Ok(source_range(&self.snapshot.original, &self.output)?.1)
    }
    pub fn write_source(self, path: &Path) -> Result<(), String> {
        let replacement = replace_output_source(&self.snapshot.original, &self.output, path)?;
        commit(vec![(self.snapshot, replacement)], &[])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const ORIGINAL: &str = "(\n output: \"all\",\n // preserve this comment and unknown enum\n custom: Future(Some((nested: [1, 2]))),\n source: Path(\"/old.png\"),\n scaling_mode: Zoom,\n)";
    #[test]
    fn adapter_requires_complete_known_consumer_schema() {
        validate_entry(FALLBACK, "all").unwrap();
        for document in [
            FALLBACK.replace("filter_by_theme: true,", ""),
            FALLBACK.replace("rotation_frequency: 3600", "rotation_frequency: -1"),
            FALLBACK.replace("Lanczos", "FutureFilter"),
            FALLBACK.replace("filter_by_theme: true", "filter_by_theme: #true"),
            FALLBACK.replace(
                "sampling_method: Alphanumeric,",
                "sampling_method: Alphanumeric, future: Something,",
            ),
        ] {
            assert!(validate_entry(&document, "all").is_err(), "{document}");
        }
        let per_output = entry_for_output(FALLBACK, "DP-1").unwrap();
        validate_entry(&per_output, "DP-1").unwrap();
        assert!(validate_entry(&per_output, "all").is_err());
    }
    #[test]
    fn preserves_unknown_fields_comments_and_escaped_paths() {
        let path = Path::new("/ảnh có khoảng trắng/quote\"slash\\.png");
        let replaced = replace_source(ORIGINAL, path).unwrap();
        assert_eq!(
            source_range(&replaced, "all").unwrap().1.as_deref(),
            path.to_str()
        );
        let (before, _) = source_range(ORIGINAL, "all").unwrap();
        let (after, _) = source_range(&replaced, "all").unwrap();
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
    fn per_output_and_color_sources_preserve_other_settings() {
        for source in [
            "Color(Single((0.1, 0.2, 0.3)))",
            "Color(Gradient((colors: [(0.1, 0.2, 0.3), (1.0, 0.0, 0.5)], radius: 0.5)))",
            "Path(\"/image directory\")",
        ] {
            let document = format!("(output: \"WINIT-0\", source: {source}, filter_by_theme: true, rotation_frequency: 3600, filter_method: Lanczos, scaling_mode: Fit((0.0, 0.0, 0.0)), sampling_method: Alphanumeric,)");
            let replaced =
                replace_output_source(&document, "WINIT-0", Path::new("/new image.png")).unwrap();
            assert_eq!(
                source_range(&replaced, "WINIT-0").unwrap().1.as_deref(),
                Some("/new image.png")
            );
            let (before, _) = source_range(&document, "WINIT-0").unwrap();
            let (after, _) = source_range(&replaced, "WINIT-0").unwrap();
            assert_eq!(&document[..before.start], &replaced[..after.start]);
            assert_eq!(&document[before.end..], &replaced[after.end..]);
            assert!(replace_output_source(&document, "HDMI-A-1", Path::new("/new.png")).is_err());
        }
        assert!(replace_source(
            "(output: \"all\", source: Color(Single((NaN, 0.0, 0.0))))",
            Path::new("/new.png")
        )
        .is_err());
    }
    #[test]
    fn global_action_plans_existing_outputs_without_changing_mode_or_list() {
        assert_eq!(target_outputs("true", None).unwrap(), ["all"]);
        assert_eq!(
            target_outputs("true", Some("invalid inactive list")).unwrap(),
            ["all"]
        );
        assert_eq!(
            target_outputs("false", Some("[\"WINIT-0\", \"HDMI-A-1\"]")).unwrap(),
            ["all", "WINIT-0", "HDMI-A-1"]
        );
        assert_eq!(target_outputs("false", Some("[]")).unwrap(), ["all"]);
        assert_eq!(config_key("WINIT-0"), "output.WINIT-0");
        for (same, list) in [
            ("false", None),
            ("bad", None),
            ("false", Some("[\"../../all\"]")),
            ("false", Some("[\"all\"]")),
            ("false", Some("[\"\"]")),
            ("false", Some("[\"DP-1\",\"DP-1\"]")),
        ] {
            assert!(target_outputs(same, list).is_err());
        }
        let names: Vec<_> = (0..65).map(|i| format!("DP-{i}")).collect();
        assert!(target_outputs("false", Some(&ron::to_string(&names).unwrap())).is_err());
    }
    #[test]
    #[ignore = "requires owned COSMIC compositor lab; invoked by wayland_lab.py --cosmic-test"]
    fn native_lab_edit() {
        let root = std::path::PathBuf::from(
            std::env::var_os("DESKMORPH_COMPOSITOR_LAB").expect("lab marker required"),
        );
        assert!(
            root.is_absolute()
                && root.parent() == Some(Path::new("/tmp"))
                && root
                    .file_name()
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .starts_with("deskmorph-wayland-lab-")
        );
        assert_eq!(
            std::env::var_os("XDG_CONFIG_HOME").unwrap(),
            root.join("config")
        );
        assert_eq!(
            std::env::var_os("XDG_STATE_HOME").unwrap(),
            root.join("state")
        );
        let output = std::env::var("DESKMORPH_COSMIC_EDIT_OUTPUT").unwrap();
        assert!(output == "all" || output == "WINIT-0" || output == "batch");
        let image = root.join("blue.png");
        assert!(image.is_file());
        if output == "batch" {
            let directory = root.join("config/cosmic/com.system76.CosmicBackground/v1");
            crate::cosmic_profile::Plan::load_existing(&directory)
                .unwrap()
                .apply(&image)
                .unwrap();
            for name in ["all", "WINIT-0"] {
                assert_eq!(
                    Document::load_output(&directory.join(config_key(name)), name)
                        .unwrap()
                        .source()
                        .unwrap()
                        .as_deref(),
                    image.to_str()
                );
            }
            return;
        }
        let path = root
            .join("config/cosmic/com.system76.CosmicBackground/v1")
            .join(config_key(&output));
        let document = Document::load_output(&path, &output).unwrap();
        let original = document.snapshot.original.clone();
        let expected = replace_output_source(&original, &output, &image).unwrap();
        document.write_source(&image).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), expected);
        assert_eq!(
            Document::load_output(&path, &output)
                .unwrap()
                .source()
                .unwrap()
                .as_deref(),
            image.to_str()
        );
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
        assert_eq!(document.source().unwrap().as_deref(), Some("/old.png"));
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
