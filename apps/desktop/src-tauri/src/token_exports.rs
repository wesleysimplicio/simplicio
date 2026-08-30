//! Export only reports already received from Runtime, never arbitrary WebView data or paths.
use crate::desktop_queries::project_token_report;
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::fs::OpenOptions;
use std::io::{ErrorKind, Write};
use std::path::Path;
use std::sync::{Arc, Mutex};

const MAX_REPORTS: usize = 8;
const MAX_EXPORT_BYTES: usize = 65_536;
const QUALIFICATION: &str = "Recorded usage, not verified billing or savings. Per-sample provenance and costs are not exposed by this Runtime report.";
const TOTALS: &[&str] = &[
    "sample_count",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "paid_remote_tokens",
    "total_tokens",
    "missing_usage_events",
    "receipt_count",
];

#[derive(Clone, Default)]
pub struct TokenReports(Arc<Mutex<VecDeque<Value>>>);

impl TokenReports {
    pub fn remember(&self, raw: Value) -> Result<Value, String> {
        let report = project_token_report(raw)?;
        let mut reports = self.0.lock().map_err(|_| "token_report_unavailable")?;
        reports.retain(|item| item["report_hash"] != report["report_hash"]);
        reports.push_back(report.clone());
        while reports.len() > MAX_REPORTS {
            reports.pop_front();
        }
        Ok(report)
    }

    /// `downloads` is resolved by the native OS path API, not an IPC argument.
    pub fn save(&self, report_hash: &str, format: &str, downloads: &Path) -> Result<Value, String> {
        if !matches!(format, "json" | "csv") {
            return Err("token_export_invalid_format".into());
        }
        let report = self
            .0
            .lock()
            .map_err(|_| "token_report_unavailable")?
            .iter()
            .find(|item| item["report_hash"].as_str() == Some(report_hash))
            .cloned()
            .ok_or("token_export_report_expired")?;
        let body = encode(&report, format)?;
        if !downloads.is_absolute() || !downloads.is_dir() {
            return Err("token_export_downloads_unavailable".into());
        }
        for suffix in 0..1000 {
            let filename = if suffix == 0 {
                format!("simplicio-token-usage.{format}")
            } else {
                format!("simplicio-token-usage ({suffix}).{format}")
            };
            let path = downloads.join(filename);
            let mut options = OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            let mut file = match options.open(&path) {
                Ok(file) => file,
                Err(error) if error.kind() == ErrorKind::AlreadyExists => continue,
                Err(error) => return Err(write_error(error.kind()).into()),
            };
            if let Err(error) = file.write_all(&body).and_then(|_| file.sync_all()) {
                drop(file);
                // This exact file was exclusively created by this export, never pre-existing data.
                let _ = std::fs::remove_file(&path);
                return Err(write_error(error.kind()).into());
            }
            return Ok(json!({
                "schema": "simplicio.desktop-token-export/v1", "format": format,
                "path": path.to_string_lossy(), "bytes": body.len(),
            }));
        }
        Err("token_export_names_exhausted".into())
    }
}

fn write_error(kind: ErrorKind) -> &'static str {
    match kind {
        ErrorKind::PermissionDenied => "token_export_permission_denied",
        ErrorKind::NotFound => "token_export_downloads_unavailable",
        _ => "token_export_write_failed",
    }
}

fn encode(report: &Value, format: &str) -> Result<Vec<u8>, String> {
    let report = project_token_report(report.clone())?;
    let body = if format == "json" {
        serde_json::to_vec_pretty(&json!({"report": report, "qualification": QUALIFICATION}))
            .map_err(|_| "token_export_write_failed")?
    } else {
        // No user-controlled session text, paths, raw samples or spreadsheet formulas in CSV.
        let mut csv = format!("window,from_epoch,to_epoch,{},timezone_offset_seconds,session_scope,report_hash,qualification\n", TOTALS.join(","));
        for period in report["periods"].as_array().ok_or("token_report_invalid")? {
            let mut columns = vec![
                period["window"]
                    .as_str()
                    .ok_or("token_report_invalid")?
                    .into(),
                period["from_epoch"].to_string(),
                period["to_epoch"].to_string(),
            ];
            columns.extend(TOTALS.iter().map(|key| period["totals"][*key].to_string()));
            columns.push(report["timezone_offset_seconds"].to_string());
            columns.push(
                if report["session_id"].is_null() {
                    "all_sessions"
                } else {
                    "filtered_session"
                }
                .into(),
            );
            columns.push(
                report["report_hash"]
                    .as_str()
                    .ok_or("token_report_invalid")?
                    .into(),
            );
            columns.push("recorded_usage_not_verified_billing_or_savings".into());
            csv.push_str(&columns.join(","));
            csv.push('\n');
        }
        csv.into_bytes()
    };
    if body.len() > MAX_EXPORT_BYTES {
        return Err("token_report_invalid".into());
    }
    Ok(body)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn report(index: u64) -> Value {
        json!({"schema":"workspace.token-analytics-report/v1","generated_by":"sqlite_ledger","now_epoch":100,
            "session_id":"=PRIVATE_FORMULA()","timezone_offset_seconds":-10800,"report_hash":format!("sha256:{index:064x}"),
            "raw_prompts":"private prompt", "path":"/private/project",
            "periods":[{"window":"today","from_epoch":0,"to_epoch":101,"totals":{
                "sample_count":1,"input_tokens":10,"cached_input_tokens":2,"output_tokens":3,"reasoning_tokens":1,
                "paid_remote_tokens":14,"total_tokens":14,"missing_usage_events":0,"receipt_count":1}}]})
    }

    struct Downloads(PathBuf);
    impl Downloads {
        fn new() -> Self {
            let nonce = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "simplicio-token-export-{}-{nonce}",
                std::process::id()
            ));
            std::fs::create_dir(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for Downloads {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn native_exports_are_qualified_runtime_aggregates_not_webview_data() {
        let reports = TokenReports::default();
        let expected = reports.remember(report(1)).unwrap();
        let downloads = Downloads::new();
        for format in ["json", "csv"] {
            let receipt = reports
                .save(
                    expected["report_hash"].as_str().unwrap(),
                    format,
                    &downloads.0,
                )
                .unwrap();
            assert_eq!(receipt["schema"], "simplicio.desktop-token-export/v1");
            let path = Path::new(receipt["path"].as_str().unwrap());
            let bytes = std::fs::read(path).unwrap();
            assert_eq!(receipt["bytes"], bytes.len());
            let text = String::from_utf8(bytes).unwrap();
            assert!(!text.contains("private prompt") && !text.contains("/private/project"));
            if format == "json" {
                let exported: Value = serde_json::from_str(&text).unwrap();
                assert_eq!(exported["report"], expected);
                assert_eq!(exported["qualification"], QUALIFICATION);
            } else {
                assert!(text
                    .contains("today,0,101,1,10,2,3,1,14,14,0,1,-10800,filtered_session,sha256:"));
                assert!(text.contains("recorded_usage_not_verified_billing_or_savings"));
                assert!(!text.contains("PRIVATE_FORMULA"));
            }
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                assert_eq!(
                    std::fs::metadata(path).unwrap().permissions().mode() & 0o777,
                    0o600
                );
            }
        }
    }

    #[test]
    fn exports_do_not_overwrite_existing_files_or_accept_arbitrary_formats() {
        let reports = TokenReports::default();
        let expected = reports.remember(report(1)).unwrap();
        let hash = expected["report_hash"].as_str().unwrap();
        let downloads = Downloads::new();
        let existing = downloads.0.join("simplicio-token-usage.json");
        std::fs::write(&existing, b"keep existing data").unwrap();
        let receipt = reports.save(hash, "json", &downloads.0).unwrap();
        assert!(receipt["path"]
            .as_str()
            .unwrap()
            .ends_with("simplicio-token-usage (1).json"));
        assert_eq!(std::fs::read(&existing).unwrap(), b"keep existing data");
        assert_eq!(
            reports
                .save(hash, "../../unsafe", &downloads.0)
                .unwrap_err(),
            "token_export_invalid_format"
        );
        assert_eq!(
            reports
                .save(hash, "json", &downloads.0.join("absent"))
                .unwrap_err(),
            "token_export_downloads_unavailable"
        );
        assert!(!downloads.0.join("absent").exists());
        assert_eq!(
            write_error(ErrorKind::PermissionDenied),
            "token_export_permission_denied"
        );
    }

    #[test]
    fn only_recent_validated_native_reports_can_be_exported() {
        let reports = TokenReports::default();
        assert!(reports.remember(json!({"report_hash":"fake"})).is_err());
        let first = reports.remember(report(0)).unwrap();
        let downloads = Downloads::new();
        for index in 1..=MAX_REPORTS as u64 {
            reports.remember(report(index)).unwrap();
        }
        assert_eq!(reports.0.lock().unwrap().len(), MAX_REPORTS);
        assert_eq!(
            reports
                .save(first["report_hash"].as_str().unwrap(), "json", &downloads.0)
                .unwrap_err(),
            "token_export_report_expired"
        );
        assert_eq!(
            reports
                .save("forged-digest", "csv", &downloads.0)
                .unwrap_err(),
            "token_export_report_expired"
        );
        assert_eq!(std::fs::read_dir(&downloads.0).unwrap().count(), 0);
    }

    #[cfg(unix)]
    #[test]
    fn export_never_follows_a_preexisting_filename_symlink() {
        let reports = TokenReports::default();
        let expected = reports.remember(report(1)).unwrap();
        let downloads = Downloads::new();
        let target = downloads.0.join("protected.json");
        std::fs::write(&target, b"keep protected data").unwrap();
        std::os::unix::fs::symlink(&target, downloads.0.join("simplicio-token-usage.json"))
            .unwrap();
        let receipt = reports
            .save(
                expected["report_hash"].as_str().unwrap(),
                "json",
                &downloads.0,
            )
            .unwrap();
        assert!(receipt["path"]
            .as_str()
            .unwrap()
            .ends_with("simplicio-token-usage (1).json"));
        assert_eq!(std::fs::read(target).unwrap(), b"keep protected data");
    }
}
