//! Native, redacted exports of the Runtime-owned unified usage projection.
use serde_json::{json, Map, Value};
use std::fs::OpenOptions;
use std::io::{ErrorKind, Write};
use std::path::Path;

const MAX_EXPORT_BYTES: usize = 65_536;
const QUALIFICATION: &str =
    "Recorded usage, not verified billing or savings. The Runtime projection is exported as received.";
const QUERY_FIELDS: &[&str] = &[
    "from_epoch",
    "to_epoch",
    "provider",
    "model",
    "host",
    "project_id",
    "session_id",
];
const ROW_FIELDS: &[&str] = &[
    "provider",
    "model",
    "host",
    "project_id",
    "session_id",
    "execution",
    "input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reported_output_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "cost_usd",
    "provenance",
    "reasoning_semantics",
    "reasoning_semantics_provenance",
    "reasoning_semantics_reason",
    "event_count",
    "source_completeness",
    "incomplete_events",
    "missing_usage_events",
    "unpriced_events",
    "metric_provenance",
    "missing_metrics",
];
const TOTAL_FIELDS: &[&str] = &[
    "event_count",
    "input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reported_output_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "cost_usd",
];
const METADATA_FIELDS: &[&str] = &[
    "source",
    "generated_by",
    "generated_at_epoch",
    "report_digest",
    "revision",
    "pricing_version",
    "pricing_sources",
    "coverage",
    "redacted",
];
const COVERAGE_FIELDS: &[&str] = &[
    "status",
    "missing_usage_events",
    "unpriced_events",
    "providers",
    "reason",
];

fn object<'a>(value: &'a Value) -> Result<&'a Map<String, Value>, String> {
    value
        .as_object()
        .ok_or_else(|| "unified_usage_export_invalid".to_string())
}

fn copy_fields(source: &Map<String, Value>, fields: &[&str]) -> Map<String, Value> {
    fields
        .iter()
        .filter_map(|field| {
            source
                .get(*field)
                .map(|value| ((*field).to_string(), value.clone()))
        })
        .collect()
}

fn digest(value: &Value) -> Result<&str, String> {
    let value = value
        .as_str()
        .filter(|value| {
            value.len() == 71
                && value.starts_with("sha256:")
                && value[7..].bytes().all(|byte| byte.is_ascii_hexdigit())
        })
        .ok_or_else(|| "unified_usage_export_invalid".to_string())?;
    Ok(value)
}

/// Keep only the versioned, redacted Runtime contract before writing a file.
fn project(value: &Value, expected_digest: Option<&str>) -> Result<Value, String> {
    let root = object(value)?;
    if root.get("schema") != Some(&Value::String("simplicio.desktop-unified-usage/v1".into())) {
        return Err("unified_usage_export_invalid".into());
    }

    let metadata = object(root.get("metadata").ok_or("unified_usage_export_invalid")?)?;
    if metadata.get("source") != Some(&Value::String("runtime".into()))
        || metadata.get("generated_by") != Some(&Value::String("runtime_usage_ledger".into()))
        || metadata.get("redacted") != Some(&Value::Bool(true))
    {
        return Err("unified_usage_export_untrusted_source".into());
    }
    let report_digest = digest(
        metadata
            .get("report_digest")
            .ok_or("unified_usage_export_invalid")?,
    )?;
    if let Some(expected) = expected_digest {
        if expected != report_digest {
            return Err("unified_usage_report_changed".into());
        }
    }

    let query = object(root.get("query").ok_or("unified_usage_export_invalid")?)?;
    let rows = root
        .get("rows")
        .and_then(Value::as_array)
        .filter(|rows| rows.len() <= 512)
        .ok_or("unified_usage_export_invalid")?;
    let rows = rows
        .iter()
        .map(|row| Ok(Value::Object(copy_fields(object(row)?, ROW_FIELDS))))
        .collect::<Result<Vec<_>, String>>()?;
    let totals = copy_fields(
        object(root.get("totals").ok_or("unified_usage_export_invalid")?)?,
        TOTAL_FIELDS,
    );
    let metadata = {
        let mut metadata = copy_fields(metadata, METADATA_FIELDS);
        let coverage = object(
            metadata
                .get("coverage")
                .ok_or("unified_usage_export_invalid")?,
        )?;
        metadata.insert(
            "coverage".into(),
            Value::Object(copy_fields(coverage, COVERAGE_FIELDS)),
        );
        metadata
    };

    Ok(json!({
        "schema": "simplicio.desktop-unified-usage/v1",
        "generated_at_epoch": root.get("generated_at_epoch").cloned().ok_or("unified_usage_export_invalid")?,
        "query": Value::Object(copy_fields(query, QUERY_FIELDS)),
        "rows": rows,
        "totals": totals,
        "metadata": metadata,
    }))
}

fn csv_cell(value: &Value) -> String {
    let raw = match value {
        Value::Null => String::new(),
        Value::String(value) => value.clone(),
        _ => value.to_string(),
    };
    format!("\"{}\"", raw.replace('"', "\"\""))
}

fn csv_value(row: &Map<String, Value>, field: &str) -> String {
    csv_cell(row.get(field).unwrap_or(&Value::Null))
}

fn encode(projection: &Value, format: &str) -> Result<Vec<u8>, String> {
    let body = if format == "json" {
        serde_json::to_vec_pretty(&json!({
            "projection": projection,
            "qualification": QUALIFICATION,
        }))
        .map_err(|_| "unified_usage_export_failed")?
    } else {
        let rows = projection
            .get("rows")
            .and_then(Value::as_array)
            .ok_or("unified_usage_export_invalid")?;
        let fields = [
            "provider",
            "model",
            "host",
            "project_id",
            "session_id",
            "execution",
            "input_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "reported_output_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
            "cost_usd",
            "provenance",
            "reasoning_semantics",
            "reasoning_semantics_provenance",
            "source_completeness",
            "incomplete_events",
            "missing_usage_events",
            "unpriced_events",
            "event_count",
        ];
        let mut csv = format!("{}\n", fields.join(","));
        for row in rows {
            let row = object(row)?;
            csv.push_str(
                &fields
                    .iter()
                    .map(|field| csv_value(row, field))
                    .collect::<Vec<_>>()
                    .join(","),
            );
            csv.push('\n');
        }
        csv.into_bytes()
    };
    if body.len() > MAX_EXPORT_BYTES {
        return Err("unified_usage_export_too_large".into());
    }
    Ok(body)
}

/// Save a fresh, redacted Runtime projection to an OS-selected Downloads path.
pub fn save(
    value: &Value,
    format: &str,
    expected_digest: Option<&str>,
    downloads: &Path,
) -> Result<Value, String> {
    if !matches!(format, "json" | "csv") {
        return Err("unified_usage_export_invalid_format".into());
    }
    if !downloads.is_absolute() || !downloads.is_dir() {
        return Err("unified_usage_export_downloads_unavailable".into());
    }
    let projection = project(value, expected_digest)?;
    let body = encode(&projection, format)?;
    for suffix in 0..1000 {
        let filename = if suffix == 0 {
            format!("simplicio-unified-usage.{format}")
        } else {
            format!("simplicio-unified-usage ({suffix}).{format}")
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
            let _ = std::fs::remove_file(&path);
            return Err(write_error(error.kind()).into());
        }
        return Ok(json!({
            "schema": "simplicio.desktop-unified-usage-export/v1",
            "format": format,
            "path": path.to_string_lossy(),
            "bytes": body.len(),
            "report_digest": projection["metadata"]["report_digest"],
        }));
    }
    Err("unified_usage_export_names_exhausted".into())
}

fn write_error(kind: ErrorKind) -> &'static str {
    match kind {
        ErrorKind::PermissionDenied => "unified_usage_export_permission_denied",
        ErrorKind::NotFound => "unified_usage_export_downloads_unavailable",
        _ => "unified_usage_export_failed",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn projection() -> Value {
        json!({
            "schema": "simplicio.desktop-unified-usage/v1",
            "generated_at_epoch": 1700000100,
            "query": {"provider":"openai","prompt":"private query"},
            "rows": [{
                "provider":"openai","model":"gpt-5","host":"codex",
                "input_tokens":100,"cache_read_tokens":20,"cache_write_tokens":5,
                "reported_output_tokens":40,"output_tokens":40,"reasoning_tokens":10,
                "total_tokens":150,"cost_usd":0.02,"provenance":"provider-reported",
                "prompt":"private row"
            }],
            "totals": {
                "event_count":1,"input_tokens":100,"cache_read_tokens":20,"cache_write_tokens":5,
                "reported_output_tokens":40,"output_tokens":40,"reasoning_tokens":10,
                "total_tokens":150,"cost_usd":0.02
            },
            "metadata": {
                "source":"runtime","generated_by":"runtime_usage_ledger","redacted":true,
                "generated_at_epoch":1700000100,
                "report_digest":"sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "revision":"sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                "coverage":{"status":"complete","missing_usage_events":0,"unpriced_events":0,"providers":["openai"],"reason":null},
                "pricing_version":null,"pricing_sources":[]
            }
        })
    }

    struct Downloads(PathBuf);
    impl Downloads {
        fn new() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "simplicio-unified-export-{}-{nonce}",
                std::process::id()
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for Downloads {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn exports_only_allowlisted_runtime_fields() {
        let downloads = Downloads::new();
        let receipt = save(
            &projection(),
            "json",
            Some("sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"),
            &downloads.0,
        )
        .unwrap();
        let body = fs::read_to_string(receipt["path"].as_str().unwrap()).unwrap();
        assert!(body.contains("gpt-5"));
        assert!(!body.contains("private query"));
        assert!(!body.contains("private row"));
        assert_eq!(
            receipt["schema"],
            "simplicio.desktop-unified-usage-export/v1"
        );
    }

    #[test]
    fn rejects_stale_projection_and_preserves_existing_file() {
        let downloads = Downloads::new();
        fs::write(downloads.0.join("simplicio-unified-usage.json"), b"keep").unwrap();
        let error = save(
            &projection(),
            "json",
            Some("sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"),
            &downloads.0,
        )
        .unwrap_err();
        assert_eq!(error, "unified_usage_report_changed");
        assert_eq!(
            fs::read(downloads.0.join("simplicio-unified-usage.json")).unwrap(),
            b"keep"
        );
    }

    #[test]
    fn rejects_invalid_format_without_touching_downloads() {
        let downloads = Downloads::new();
        assert_eq!(
            save(&projection(), "xml", None, &downloads.0).unwrap_err(),
            "unified_usage_export_invalid_format"
        );
        assert_eq!(fs::read_dir(&downloads.0).unwrap().count(), 0);
    }
}
