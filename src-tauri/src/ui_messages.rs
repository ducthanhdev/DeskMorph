//! App-owned native dialog labels share the frontend message catalogue.
use std::sync::OnceLock;
use serde_json::Value;

pub fn text(language: &str, key: &str) -> &'static str {
    static MESSAGES: OnceLock<Value> = OnceLock::new();
    let messages = MESSAGES.get_or_init(|| serde_json::from_str(include_str!("../../src/i18n/messages.json")).expect("bundled UI messages must be valid JSON"));
    messages[if language == "en" { "en" } else { "vi" }][key].as_str().expect("native UI key must exist")
}

#[cfg(test)]
mod tests {
    #[test]
    fn native_export_labels_exist_in_both_languages_and_fallback_is_vietnamese() {
        for language in ["vi", "en"] {
            for key in ["exportConfig", "cancel", "save"] {
                assert!(!super::text(language, key).is_empty());
            }
        }
        assert_eq!(super::text("en", "exportConfig"), "Export configuration");
        assert_eq!(super::text("vi", "exportConfig"), "Xuất cấu hình");
        assert_eq!(super::text("unknown", "cancel"), super::text("vi", "cancel"));
    }
}
