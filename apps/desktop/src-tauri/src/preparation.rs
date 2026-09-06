//! Bounded pre-login preparation observations. Planning never applies registration.
use serde_json::{json, Value};
use std::{fs, path::{Path, PathBuf}, process::Command, time::Duration};
use crate::runtime_process::{capture, CaptureLimits};

pub fn project(plan: &Value) -> Result<Value, String> {
    let invalid = || "preparation_plan_invalid".to_string();
    if plan["schema"] != "simplicio.mcp-register-plan/v1" || plan["status"] != "planned" || plan["dry_run"] != true { return Err(invalid()); }
    let writes = plan["writes"].as_array().filter(|v| v.len() <= 64).ok_or_else(invalid)?;
    if writes.iter().any(|w| w["kind"] != "replace" || !w["label"].is_string() || !w["path"].is_string()) { return Err(invalid()); }
    // Current/desired config bodies and paths may include secrets. Never project them.
    Ok(json!({"schema":"simplicio.desktop-preparation-plan/v1", "status":"planned", "configurationWrites":writes.len(), "effectsApplied":false, "memoryReady":false, "requiresApply":true}))
}

fn python_version(bytes: &[u8]) -> Option<String> {
    let text = std::str::from_utf8(bytes).ok()?.trim();
    let version = text.strip_prefix("Python ")?;
    let parts: Vec<_> = version.split('.').collect();
    if parts.len() != 3 || parts[0] != "3" || parts.iter().any(|p| p.is_empty() || p.len() > 3 || !p.bytes().all(|b| b.is_ascii_digit())) { return None; }
    Some(version.to_string())
}

pub fn python() -> Value {
    // Avoid the macOS /usr/bin/python3 developer-tools installer shim.
    for path in ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"] {
        if !Path::new(path).is_file() { continue; }
        let limits = CaptureLimits { deadline: Duration::from_secs(5), stdout_bytes: 1024, stderr_bytes: 1024 };
        if let Ok(output) = capture(Command::new(path).arg("--version"), limits) {
            if output.status.success() {
                if let Some(version) = python_version(&output.stdout).or_else(|| python_version(&output.stderr)) {
                    return json!({"status":"detected", "version":version, "dependenciesVerified":false});
                }
            }
        }
        return json!({"status":"unavailable", "dependenciesVerified":false});
    }
    json!({"status":"not_detected", "dependenciesVerified":false})
}

const RECEIPT_FILE: &str = "desktop-preparation-receipt.json";
const RECEIPT_MAX_BYTES: usize = 16 * 1024;

pub fn receipt_path(home: &Path) -> PathBuf {
    home.join(".simplicio").join(RECEIPT_FILE)
}

pub fn persist_receipt(home: &Path, value: &Value) -> Result<(), String> {
    if !is_ready_receipt(value) {
        return Err("preparation_result_invalid".to_string());
    }
    let bytes = serde_json::to_vec(value).map_err(|_| "preparation_receipt_invalid".to_string())?;
    if bytes.len() > RECEIPT_MAX_BYTES {
        return Err("preparation_receipt_too_large".to_string());
    }
    let dir = home.join(".simplicio");
    fs::create_dir_all(&dir).map_err(|_| "preparation_receipt_write_failed".to_string())?;
    let path = receipt_path(home);
    let temp = path.with_extension("json.tmp");
    fs::write(&temp, &bytes).map_err(|_| "preparation_receipt_write_failed".to_string())?;
    fs::rename(&temp, &path).map_err(|_| "preparation_receipt_write_failed".to_string())?;
    Ok(())
}

pub fn receipt_ready(home: &Path) -> bool {
    let path = receipt_path(home);
    let Ok(bytes) = fs::read(path) else { return false; };
    if bytes.len() > RECEIPT_MAX_BYTES { return false; }
    serde_json::from_slice::<Value>(&bytes).map(|value| is_ready_receipt(&value)).unwrap_or(false)
}

fn is_ready_receipt(value: &Value) -> bool {
    value["schema"] == "simplicio.desktop-preparation-result/v1"
        && value["status"] == "ready"
        && value["effectsApplied"] == true
        && value["runtimeDependencies"]["status"] == "ready"
        && value["runtimeDependencies"]["pythonRequired"] == false
        && value["memory"]["ready"] == true
        && value["redacted"] == true
        && value["clients"]["configured"].as_u64().is_some_and(|n| n <= 64)
        && value["clients"]["skipped"].as_u64().is_some_and(|n| n <= 64)
        && value["memory"]["items"].as_u64().is_some_and(|n| n >= 100)
        && value["memory"]["skills"].as_u64().is_some_and(|n| n >= 50)
        && value["memory"]["migrations"].as_u64().is_some_and(|n| (1..=64).contains(&n))
}

pub fn project_result(result: &Value, python: Value) -> Result<Value, String> {
    let invalid = || "preparation_result_invalid".to_string();
    if result["schema"] != "simplicio.mcp-register-result/v1"
        || result["status"] != "passed"
        || result["dry_run"] != false
    {
        return Err(invalid());
    }
    let writes = result["writes"].as_array().filter(|writes| writes.len() <= 64).ok_or_else(invalid)?;
    if writes.iter().any(|write| !write["label"].is_string()
        || !matches!(write["status"].as_str(), Some("done" | "skipped"))) {
        return Err(invalid());
    }
    let skipped = result["skipped"].as_array().filter(|items| items.len() <= 64).ok_or_else(invalid)?;
    if skipped.iter().any(|item| !item.is_string()) { return Err(invalid()); }
    let neural = result["neural"].as_object().ok_or_else(invalid)?;
    let neural_status = neural.get("status").and_then(Value::as_str).ok_or_else(invalid)?;
    let memory_items = neural.get("memory_items").and_then(Value::as_u64).ok_or_else(invalid)?;
    let skills = neural.get("skills_registry").and_then(Value::as_u64).ok_or_else(invalid)?;
    let migrations = neural.get("migration_ids").and_then(Value::as_array)
        .filter(|ids| !ids.is_empty() && ids.len() <= 64).ok_or_else(invalid)?;
    if !matches!(neural_status, "ready" | "already-ready")
        || neural.get("quick_check").and_then(Value::as_str) != Some("ok")
        || memory_items < 100 || skills < 50 || migrations.iter().any(|id| !id.is_string()) {
        return Err(invalid());
    }
    if !matches!(python.get("status").and_then(Value::as_str),
        Some("detected" | "unavailable" | "not_detected")) {
        return Err(invalid());
    }
    Ok(json!({
        "schema": "simplicio.desktop-preparation-result/v1", "status": "ready",
        "effectsApplied": true,
        "runtimeDependencies": {"status": "ready", "pythonRequired": false},
        "python": python,
        "memory": {"ready": true, "items": memory_items, "skills": skills, "migrations": migrations.len()},
        "clients": {"configured": writes.len(), "skipped": skipped.len()},
        "redacted": true
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn plan() -> Value { json!({"schema":"simplicio.mcp-register-plan/v1","status":"planned","dry_run":true,"writes":[{"kind":"replace","label":"codex","path":"/private/user/config","current":{"token":"SECRET"},"desired":{"token":"SECRET"}}]}) }
    #[test] fn never_projects_credentials_or_claims_application() {
        let value = project(&plan()).unwrap();
        assert_eq!(value["configurationWrites"],1);
        assert_eq!(value["effectsApplied"],false);
        assert_eq!(value["memoryReady"],false);
        assert!(!value.to_string().contains("SECRET"));
        assert!(!value.to_string().contains("/private"));
    }
    #[test] fn refuses_effect_receipts_and_unbounded_plans() {
        let mut value=plan(); value["dry_run"]=json!(false); assert!(project(&value).is_err());
        value=plan(); value["writes"]=json!(vec![value["writes"][0].clone();65]); assert!(project(&value).is_err());
        value=plan(); value["writes"][0]["kind"]=json!("delete"); assert!(project(&value).is_err());
    }
    #[test] fn projects_only_bounded_readiness_from_an_applied_result() {
        let result = json!({
            "schema":"simplicio.mcp-register-result/v1","status":"passed","dry_run":false,
            "writes":[{"label":"codex","status":"done"}],"skipped":["missing-host"],
            "neural":{"status":"already-ready","quick_check":"ok","memory_items":815,
                "skills_registry":557,"migration_ids":["001","002"]},
            "binary":"/private/user/simplicio","mcp_url_env":{"value":"secret"}
        });
        let projected = project_result(&result, json!({
            "status":"detected","version":"3.13.2","dependenciesVerified":false
        })).unwrap();
        assert_eq!(projected["memory"]["ready"], true);
        assert_eq!(projected["clients"]["configured"], 1);
        assert_eq!(projected["runtimeDependencies"]["pythonRequired"], false);
        assert!(!projected.to_string().contains("/private"));
        assert!(!projected.to_string().contains("secret"));
    }
    #[test] fn refuses_failed_or_incomplete_environment_results() {
        let mut result = json!({
            "schema":"simplicio.mcp-register-result/v1","status":"passed","dry_run":false,
            "writes":[],"skipped":[],
            "neural":{"status":"ready","quick_check":"ok","memory_items":815,
                "skills_registry":557,"migration_ids":["001"]}
        });
        let python = json!({"status":"not_detected","dependenciesVerified":false});
        assert!(project_result(&result, python.clone()).is_ok());
        result["neural"]["quick_check"] = json!("failed");
        assert!(project_result(&result, python.clone()).is_err());
        result["neural"]["quick_check"] = json!("ok");
        result["status"] = json!("failed");
        assert!(project_result(&result, python).is_err());
    }
    #[test] fn persists_and_rejects_preparation_receipts() {
        let home = std::env::temp_dir().join(format!("simplicio-preparation-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&home);
        let ready = json!({
            "schema":"simplicio.desktop-preparation-result/v1","status":"ready","effectsApplied":true,
            "runtimeDependencies":{"status":"ready","pythonRequired":false},
            "python":{"status":"not_detected","dependenciesVerified":false},
            "memory":{"ready":true,"items":815,"skills":557,"migrations":2},
            "clients":{"configured":1,"skipped":0},"redacted":true
        });
        persist_receipt(&home, &ready).unwrap();
        assert!(receipt_ready(&home));
        let path = receipt_path(&home);
        let stored = fs::read_to_string(path).unwrap();
        assert!(!stored.contains("secret"));
        fs::write(receipt_path(&home), b"{}").unwrap();
        assert!(!receipt_ready(&home));
        let _ = fs::remove_dir_all(home);
    }
    #[test] fn python_version_is_strict_and_bounded() {
        assert_eq!(python_version(b"Python 3.13.2\n"),Some("3.13.2".into()));
        for value in ["Python 2.7.18","Python 3.13.2 SECRET","Python 3.13","3.13.2"] { assert!(python_version(value.as_bytes()).is_none()); }
    }
}
