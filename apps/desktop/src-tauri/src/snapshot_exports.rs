//! Redacted snapshot exports to a native, fixed destination. No arbitrary bodies or paths over IPC.
use serde_json::{json, Value};
use std::fs::OpenOptions;
use std::io::{ErrorKind, Write};
use std::path::Path;

fn projection(snapshot: &Value, kind: &str, filters: &Value) -> Result<Value, String> {
    match kind {
        "diagnostic" => Ok(json!({
            "schema": "simplicio.desktop-diagnostic/v1",
            "generatedAt": snapshot["generatedAt"], "source": snapshot["source"],
            "access": { "state": snapshot["access"]["state"], "plan": snapshot["access"]["plan"], "reasonCode": snapshot["access"]["reasonCode"] },
            "runtime": { "state": snapshot["runtime"]["state"], "version": snapshot["runtime"]["version"], "transport": snapshot["runtime"]["transport"] },
            "savings": { "proofKind": snapshot["savings"]["proofKind"], "ledgerStatus": snapshot["savings"]["ledgerStatus"], "eventCount": snapshot["savings"]["eventCount"] },
            "providers": snapshot["providers"].as_array().map(|items| items.iter().take(32).map(|item| json!({
                "id": item["id"], "state": item["state"], "reasonCode": item["reasonCode"]
            })).collect::<Vec<_>>()).unwrap_or_default(),
            "redaction": {
                "credentials": snapshot["redaction"]["credentials"].as_bool().unwrap_or(false),
                "prompts": snapshot["redaction"]["prompts"].as_bool().unwrap_or(false),
            },
        })),
        "activity" => {
            let status = filters["status"].as_str().unwrap_or("all");
            let provider = filters["provider"].as_str().unwrap_or("all");
            let search = filters["search"].as_str().unwrap_or("");
            if !matches!(status, "all" | "verified" | "running" | "attention")
                || provider.len() > 256
                || search.len() > 120
            {
                return Err("snapshot_export_invalid".into());
            }
            let search = search.to_lowercase();
            let items = snapshot["activity"].as_array().map(|items| items.iter().take(5)
                .filter(|item| status == "all" || item["status"].as_str() == Some(status))
                .filter(|item| provider == "all" || item["provider"].as_str() == Some(provider))
                .filter(|item| search.is_empty() || ["id", "title", "detail", "provider", "status"].iter().any(|field| item[*field].as_str().unwrap_or("").to_lowercase().contains(&search)))
                .map(|item| json!({
                    "id": item["id"], "title": item["title"], "provider": item["provider"],
                    "savedTokens": item["savedTokens"], "occurredAt": item["occurredAt"], "status": item["status"],
                })).collect::<Vec<_>>()).unwrap_or_default();
            Ok(json!({ "schema": "simplicio.activity-export/v1", "items": items }))
        }
        _ => Err("snapshot_export_invalid".into()),
    }
}

pub fn save(
    snapshot: &Value,
    kind: &str,
    filters: &Value,
    downloads: &Path,
) -> Result<Value, String> {
    let value = projection(snapshot, kind, filters)?;
    let body = serde_json::to_vec_pretty(&value).map_err(|_| "snapshot_export_failed")?;
    if body.len() > 65_536 || !downloads.is_absolute() || !downloads.is_dir() {
        return Err("snapshot_export_unavailable".into());
    }
    for suffix in 0..1000 {
        let filename = if suffix == 0 {
            format!("simplicio-{kind}.json")
        } else {
            format!("simplicio-{kind} ({suffix}).json")
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
            Err(_) => return Err("snapshot_export_failed".into()),
        };
        if file.write_all(&body).and_then(|_| file.sync_all()).is_err() {
            drop(file);
            // Only remove the exact incomplete file exclusively created by this export.
            let _ = std::fs::remove_file(&path);
            return Err("snapshot_export_failed".into());
        }
        return Ok(
            json!({ "schema": "simplicio.desktop-snapshot-export/v1", "kind": kind, "path": path.to_string_lossy(), "bytes": body.len() }),
        );
    }
    Err("snapshot_export_failed".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot() -> Value {
        json!({
            "generatedAt": "2026-08-30", "source": "runtime",
            "access": {"state":"active","email":"private@example.com","token":"SECRET","plan":"annual"},
            "runtime":{"state":"healthy","version":"3.8.39","transport":"sidecar","path":"/private/path"},
            "providers":[{"id":"codex","state":"registered","credentials":"SECRET"}],
            "activity":[{"id":"1","title":"Receipt","provider":"codex","detail":"PRIVATE PROMPT","status":"verified"},{"id":"2","provider":"other","status":"attention"}],
            "redaction":{"credentials":true,"prompts":true}
        })
    }

    #[test]
    fn exports_only_allowlisted_snapshot_fields_and_filters_receipts() {
        let diagnostic = projection(&snapshot(), "diagnostic", &Value::Null)
            .unwrap()
            .to_string();
        for private in [
            "private@example.com",
            "SECRET",
            "/private/path",
            "PRIVATE PROMPT",
        ] {
            assert!(!diagnostic.contains(private));
        }
        let activity = projection(
            &snapshot(),
            "activity",
            &json!({"status":"verified","provider":"codex"}),
        )
        .unwrap();
        assert_eq!(activity["items"].as_array().unwrap().len(), 1);
        assert!(activity["items"][0].get("detail").is_none());
        let searched = projection(
            &snapshot(),
            "activity",
            &json!({"status":"all","provider":"all","search":"private prompt"}),
        )
        .unwrap();
        assert_eq!(searched["items"].as_array().unwrap().len(), 1);
        assert_eq!(searched["items"][0]["id"], "1");
        assert!(projection(&snapshot(), "../arbitrary", &Value::Null).is_err());
        assert!(projection(&snapshot(), "activity", &json!({"status":"invalid"})).is_err());
    }

    #[test]
    fn diagnostic_redaction_exports_only_known_boolean_flags() {
        let mut snapshot = snapshot();
        snapshot["redaction"] = json!({
            "credentials": true,
            "prompts": true,
            "extra": "redaction-extra-sentinel",
            "debug": {"nested": [{"value": "redaction-nested-sentinel"}]},
        });
        let diagnostic = projection(&snapshot, "diagnostic", &Value::Null).unwrap();
        assert_eq!(
            diagnostic["redaction"],
            json!({"credentials": true, "prompts": true})
        );
        let body = diagnostic.to_string();
        assert!(!body.contains("redaction-extra-sentinel"));
        assert!(!body.contains("redaction-nested-sentinel"));
    }

    #[test]
    fn diagnostic_redaction_never_passes_through_non_boolean_flags() {
        let mut snapshot = snapshot();
        for redaction in [
            json!({
                "credentials": {"value": "redaction-flag-sentinel"},
                "prompts": "redaction-flag-sentinel",
            }),
            Value::Null,
        ] {
            snapshot["redaction"] = redaction;
            let diagnostic = projection(&snapshot, "diagnostic", &Value::Null).unwrap();
            assert_eq!(
                diagnostic["redaction"],
                json!({"credentials": false, "prompts": false})
            );
            assert!(!diagnostic.to_string().contains("redaction-flag-sentinel"));
        }
    }

    #[test]
    fn export_preserves_existing_files_and_returns_the_actual_native_path() {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let directory = std::env::temp_dir().join(format!(
            "simplicio-snapshot-export-{}-{nonce}",
            std::process::id()
        ));
        std::fs::create_dir(&directory).unwrap();
        let existing = directory.join("simplicio-diagnostic.json");
        std::fs::write(&existing, b"existing user data").unwrap();
        let receipt = save(&snapshot(), "diagnostic", &Value::Null, &directory).unwrap();
        let exported = Path::new(receipt["path"].as_str().unwrap());
        assert!(exported.ends_with("simplicio-diagnostic (1).json"));
        assert_eq!(std::fs::read(&existing).unwrap(), b"existing user data");
        assert_eq!(
            std::fs::read(exported).unwrap().len(),
            receipt["bytes"].as_u64().unwrap() as usize
        );
        std::fs::remove_file(exported).unwrap();
        std::fs::remove_file(existing).unwrap();
        std::fs::remove_dir(directory).unwrap();
    }
}
