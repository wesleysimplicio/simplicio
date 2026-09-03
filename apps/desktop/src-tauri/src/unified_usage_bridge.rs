use serde_json::Value;
use std::path::{Path, PathBuf};

const MAX_QUERY_BYTES: usize = 16 * 1024;
const QUERY_FIELDS: [&str; 7] = [
    "from_epoch",
    "to_epoch",
    "provider",
    "model",
    "host",
    "project_id",
    "session_id",
];

fn invalid() -> String {
    "unified_usage_query_invalid".to_string()
}

/// Convert the renderer request into the bounded Runtime CLI invocation.
///
/// Values are forwarded verbatim after structural validation. The Desktop does
/// not calculate totals, provenance, coverage, pricing or projection digests.
pub fn query_args(
    query: &Value,
    repo_path: Option<&str>,
    default_repo: &Path,
) -> Result<Vec<String>, String> {
    let fields = query.as_object().ok_or_else(invalid)?;
    if fields
        .keys()
        .any(|key| !QUERY_FIELDS.contains(&key.as_str()))
    {
        return Err(invalid());
    }

    let repo = match repo_path.map(str::trim).filter(|value| !value.is_empty()) {
        Some(path) => PathBuf::from(path),
        None => default_repo.to_path_buf(),
    };
    let repo = repo.canonicalize().map_err(|_| invalid())?;
    if !repo.is_dir() {
        return Err(invalid());
    }

    let encoded = serde_json::to_string(query).map_err(|_| invalid())?;
    if encoded.len() > MAX_QUERY_BYTES {
        return Err(invalid());
    }

    Ok(vec![
        "desktop-unified-usage".to_string(),
        "--repo".to_string(),
        repo.to_string_lossy().into_owned(),
        "--query-json".to_string(),
        encoded,
        "--json".to_string(),
    ])
}

#[cfg(test)]
mod tests {
    use super::query_args;
    use serde_json::json;
    use std::path::Path;

    #[test]
    fn forwards_the_runtime_query_without_calculating_renderer_totals() {
        let query = json!({
            "from_epoch": 100,
            "to_epoch": 200,
            "provider": "openai",
            "model": "gpt-5",
            "host": "codex",
            "project_id": "project-redacted",
            "session_id": "session-redacted"
        });

        let args = query_args(&query, None, Path::new(".")).expect("valid query");
        assert_eq!(args[0], "desktop-unified-usage");
        assert_eq!(args[1], "--repo");
        assert_eq!(args[3], "--query-json");
        assert_eq!(
            serde_json::from_str::<serde_json::Value>(&args[4]).expect("query JSON"),
            query
        );
        assert_eq!(args[5], "--json");
    }

    #[test]
    fn rejects_renderer_attempts_to_send_usage_or_sensitive_fields() {
        for query in [
            json!({"total_tokens": 0}),
            json!({"prompt": "secret"}),
            json!({"argv": ["--token", "secret"]}),
        ] {
            assert_eq!(
                query_args(&query, None, Path::new(".")).unwrap_err(),
                "unified_usage_query_invalid"
            );
        }
    }
}
