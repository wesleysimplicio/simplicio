//! Typed argument construction for Runtime-owned usage and cost projections.
//! The Desktop passes filters to the packaged Runtime; it never reads the ledger itself.

use serde_json::Value;
use std::path::{Path, PathBuf};

const MAX_QUERY_BYTES: usize = 16 * 1024;
const MAX_LABEL_BYTES: usize = 256;
const MAX_EPOCH: u64 = 4_102_444_800;

fn repo_path(value: &str) -> Result<PathBuf, String> {
    if value.is_empty() || value.len() > 4096 || !Path::new(value).is_absolute() {
        return Err("projection_query_invalid".into());
    }
    let canonical = PathBuf::from(value)
        .canonicalize()
        .map_err(|_| "projection_query_invalid".to_string())?;
    if !canonical.is_dir() {
        return Err("projection_query_invalid".into());
    }
    Ok(canonical)
}

fn label(value: &Value) -> Result<(), String> {
    let value = value.as_str().ok_or("projection_query_invalid")?;
    if value.is_empty()
        || value.len() > MAX_LABEL_BYTES
        || !value.bytes().all(|byte| (0x20..=0x7e).contains(&byte))
    {
        return Err("projection_query_invalid".into());
    }
    Ok(())
}

fn validate_query(query: &Value) -> Result<(), String> {
    let object = query.as_object().ok_or("projection_query_invalid")?;
    const ALLOWED: &[&str] = &[
        "from_epoch",
        "to_epoch",
        "provider",
        "model",
        "host",
        "project_id",
        "session_id",
    ];
    if object.keys().any(|key| !ALLOWED.contains(&key.as_str())) {
        return Err("projection_query_invalid".into());
    }
    for key in ["provider", "model", "host", "project_id", "session_id"] {
        if let Some(value) = object.get(key) {
            label(value)?;
        }
    }
    let from = object
        .get("from_epoch")
        .map(|value| {
            value
                .as_u64()
                .filter(|epoch| *epoch <= MAX_EPOCH)
                .ok_or("projection_query_invalid")
        })
        .transpose()?;
    let to = object
        .get("to_epoch")
        .map(|value| {
            value
                .as_u64()
                .filter(|epoch| *epoch <= MAX_EPOCH)
                .ok_or("projection_query_invalid")
        })
        .transpose()?;
    if let (Some(from), Some(to)) = (from, to) {
        if from >= to {
            return Err("projection_query_invalid".into());
        }
    }
    Ok(())
}

pub fn query_args(
    command: &str,
    query: &Value,
    selected_repo: Option<&str>,
    default_repo: &Path,
) -> Result<Vec<String>, String> {
    if !matches!(command, "desktop-unified-usage" | "desktop-cost-projection") {
        return Err("projection_query_invalid".into());
    }
    validate_query(query)?;
    let repo = selected_repo
        .map(repo_path)
        .transpose()?
        .unwrap_or_else(|| default_repo.to_path_buf());
    let repo = repo_path(&repo.to_string_lossy())?;
    let query_json = serde_json::to_string(query).map_err(|_| "projection_query_invalid")?;
    if query_json.len() > MAX_QUERY_BYTES {
        return Err("projection_query_invalid".into());
    }
    Ok(vec![
        command.into(),
        "--repo".into(),
        repo.to_string_lossy().into_owned(),
        "--query-json".into(),
        query_json,
        "--json".into(),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn builds_bounded_runtime_args_for_both_projections() {
        let repo = std::env::temp_dir().canonicalize().unwrap();
        let args = query_args(
            "desktop-cost-projection",
            &json!({"provider":"openai"}),
            None,
            &repo,
        )
        .unwrap();
        assert_eq!(args[0], "desktop-cost-projection");
        assert_eq!(args[1], "--repo");
        assert_eq!(args[3], "--query-json");
        assert_eq!(args[5], "--json");
        let args = query_args("desktop-unified-usage", &json!({}), None, &repo).unwrap();
        assert_eq!(args[0], "desktop-unified-usage");
    }

    #[test]
    fn rejects_unknown_keys_bad_labels_and_invalid_ranges() {
        let repo = std::env::temp_dir().canonicalize().unwrap();
        assert!(query_args(
            "desktop-cost-projection",
            &json!({"repo":"/private"}),
            None,
            &repo
        )
        .is_err());
        assert!(query_args(
            "desktop-cost-projection",
            &json!({"provider":"não"}),
            None,
            &repo
        )
        .is_err());
        assert!(query_args(
            "desktop-cost-projection",
            &json!({"from_epoch":2,"to_epoch":1}),
            None,
            &repo
        )
        .is_err());
        assert!(query_args("unknown", &json!({}), None, &repo).is_err());
    }
}
