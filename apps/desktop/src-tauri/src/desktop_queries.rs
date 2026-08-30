//! Typed, bounded Desktop queries over the installed Runtime. No SQL or config writer lives here.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
const PERIODS: &[&str] = &["today", "7d", "1m", "3m", "6m", "12m", "custom"];
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

fn query_string<'a>(request: &'a Value, key: &str, max: usize) -> Result<Option<&'a str>, String> {
    match request.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value))
            if !value.trim().is_empty()
                && value.len() <= max
                && !value.contains('\0')
                && !value.trim().starts_with('-') =>
        {
            Ok(Some(value.trim()))
        }
        _ => Err("token_query_invalid".into()),
    }
}

pub fn token_query_args(request: &Value, default_repo: &Path) -> Result<Vec<String>, String> {
    let fields = request.as_object().ok_or("token_query_invalid")?;
    if fields.keys().any(|key| {
        ![
            "repoPath",
            "sessionId",
            "fromEpoch",
            "toEpoch",
            "timezoneOffsetSeconds",
        ]
        .contains(&key.as_str())
    }) {
        return Err("token_query_invalid".into());
    }
    let offset = request
        .get("timezoneOffsetSeconds")
        .and_then(Value::as_i64)
        .ok_or("token_query_invalid")?;
    if !(-86_400..=86_400).contains(&offset) {
        return Err("token_query_invalid".into());
    }
    let repo = query_string(request, "repoPath", 4096)?
        .map(PathBuf::from)
        .unwrap_or_else(|| default_repo.to_path_buf());
    if !repo.is_absolute() {
        return Err("token_query_invalid".into());
    }
    let repo = repo.canonicalize().map_err(|_| "token_query_invalid")?;
    if !repo.is_dir() {
        return Err("token_query_invalid".into());
    }
    let mut args = vec![
        "tokens".into(),
        "report".into(),
        "--json".into(),
        "--tz-offset-seconds".into(),
        offset.to_string(),
    ];
    if let Some(session) = query_string(request, "sessionId", 256)? {
        args.extend(["--session".into(), session.into()]);
    }
    match (request.get("fromEpoch"), request.get("toEpoch")) {
        (None, None) => {}
        (Some(from), Some(to)) => {
            let from = from
                .as_u64()
                .filter(|n| *n <= MAX_SAFE_INTEGER)
                .ok_or("token_query_invalid")?;
            let to = to
                .as_u64()
                .filter(|n| *n <= MAX_SAFE_INTEGER)
                .ok_or("token_query_invalid")?;
            if from >= to {
                return Err("token_query_invalid".into());
            }
            args.extend([
                "--from".into(),
                from.to_string(),
                "--to".into(),
                to.to_string(),
            ]);
        }
        _ => return Err("token_query_invalid".into()),
    }
    let db = repo.join(".simplicio/token-usage.sqlite3");
    // Runtime's report opens SQLite with initialization. Do not create an empty ledger on a read.
    let canonical_db = db.canonicalize().map_err(|_| "token_ledger_unavailable")?;
    if !canonical_db.starts_with(&repo) || !canonical_db.is_file() {
        return Err("token_ledger_unavailable".into());
    }
    args.extend(["--db".into(), canonical_db.to_string_lossy().into_owned()]);
    Ok(args)
}

fn number(value: &Value, key: &str) -> Result<u64, String> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .filter(|n| *n <= MAX_SAFE_INTEGER)
        .ok_or_else(|| "token_report_invalid".into())
}

pub fn project_token_report(value: Value) -> Result<Value, String> {
    if value["schema"] != "workspace.token-analytics-report/v1"
        || value["generated_by"] != "sqlite_ledger"
    {
        return Err("token_report_invalid".into());
    }
    let digest = value["report_hash"]
        .as_str()
        .ok_or("token_report_invalid")?;
    if digest.len() != 71
        || !digest.starts_with("sha256:")
        || !digest[7..].bytes().all(|b| b.is_ascii_hexdigit())
    {
        return Err("token_report_invalid".into());
    }
    let offset = value["timezone_offset_seconds"]
        .as_i64()
        .filter(|n| (-86_400..=86_400).contains(n))
        .ok_or("token_report_invalid")?;
    let session = match &value["session_id"] {
        Value::Null => Value::Null,
        Value::String(id) if id.len() <= 256 => json!(id),
        _ => return Err("token_report_invalid".into()),
    };
    let raw_periods = value["periods"]
        .as_array()
        .filter(|rows| !rows.is_empty() && rows.len() <= 7)
        .ok_or("token_report_invalid")?;
    let mut periods = Vec::new();
    let mut seen = std::collections::BTreeSet::new();
    for period in raw_periods {
        let window = period["window"]
            .as_str()
            .filter(|window| PERIODS.contains(window))
            .ok_or("token_report_invalid")?;
        if !seen.insert(window) {
            return Err("token_report_invalid".into());
        }
        let from = number(period, "from_epoch")?;
        let to = number(period, "to_epoch")?;
        if from >= to {
            return Err("token_report_invalid".into());
        }
        let mut totals = serde_json::Map::new();
        for key in TOTALS {
            totals.insert((*key).into(), json!(number(&period["totals"], key)?));
        }
        let n = |key: &str| totals[key].as_u64().unwrap_or_default();
        if n("cached_input_tokens") > n("input_tokens")
            || n("missing_usage_events") > n("sample_count")
            || n("receipt_count") > n("sample_count")
            || n("total_tokens") != n("input_tokens") + n("output_tokens") + n("reasoning_tokens")
        {
            return Err("token_report_invalid".into());
        }
        periods.push(json!({"window":window,"from_epoch":from,"to_epoch":to,"totals":totals}));
    }
    Ok(
        json!({"schema":"workspace.token-analytics-report/v1","now_epoch":number(&value,"now_epoch")?,
        "session_id":session,"timezone_offset_seconds":offset,"periods":periods,"generated_by":"sqlite_ledger","report_hash":digest}),
    )
}

pub fn project_install_plan(plan: Value) -> Result<Value, String> {
    if plan["schema"] != "simplicio.install-plan/v1" || plan["dry_run"] != true {
        return Err("integration_plan_invalid".into());
    }
    let raw = plan
        .pointer("/apply_preview/config_diffs")
        .and_then(Value::as_array)
        .filter(|rows| rows.len() <= 64)
        .ok_or("integration_plan_invalid")?;
    let mut changes = Vec::new();
    for row in raw {
        let label = row["label"]
            .as_str()
            .filter(|s| {
                !s.is_empty()
                    && s.len() <= 128
                    && s.chars()
                        .all(|c| c.is_ascii_alphanumeric() || "._-".contains(c))
            })
            .ok_or("integration_plan_invalid")?;
        let changed = row["changed"].as_bool().ok_or("integration_plan_invalid")?;
        let exists = row["exists"].as_bool().ok_or("integration_plan_invalid")?;
        changes.push(json!({"label":label,"changed":changed,"exists":exists}));
    }
    // Bind confirmation to the exact proposed config changes without sending their bodies to the UI.
    let bytes = serde_json::to_vec(&json!({"preview":plan["apply_preview"],"configs":plan["generated_configs"],"binary":plan["binary"]})).map_err(|_| "integration_plan_invalid")?;
    let digest = format!("sha256:{:x}", Sha256::digest(bytes));
    Ok(
        json!({"schema":"simplicio.desktop-integration-plan/v1","source":"runtime","planDigest":digest,"changes":changes}),
    )
}

/// Exit zero alone is not evidence of installation: a plan also exits successfully.
pub fn validate_install_receipt(receipt: &Value) -> Result<(), String> {
    if receipt["schema"] != "simplicio.install-apply/v1" || receipt["status"] != "applied" {
        return Err("integration_install_unconfirmed".into());
    }
    let actions = receipt["actions"]
        .as_array()
        .filter(|rows| !rows.is_empty() && rows.len() <= 128)
        .ok_or("integration_install_unconfirmed")?;
    let mut seen = std::collections::BTreeSet::new();
    for action in actions {
        let name = action["name"]
            .as_str()
            .filter(|name| !name.is_empty() && name.len() <= 160)
            .ok_or("integration_install_unconfirmed")?;
        if !seen.insert(name) || !matches!(action["status"].as_str(), Some("done" | "skipped")) {
            return Err("integration_install_unconfirmed".into());
        }
    }
    if !seen.contains("binary-copy")
        || !actions
            .iter()
            .any(|action| action["name"] == "install-manifest" && action["status"] == "done")
    {
        return Err("integration_install_unconfirmed".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn report() -> Value {
        json!({"schema":"workspace.token-analytics-report/v1","generated_by":"sqlite_ledger","now_epoch":100,
            "session_id":null,"timezone_offset_seconds":0,"report_hash":format!("sha256:{}","a".repeat(64)),
            "periods":[{"window":"today","from_epoch":0,"to_epoch":101,"totals":{
                "sample_count":1,"input_tokens":10,"cached_input_tokens":2,"output_tokens":3,"reasoning_tokens":1,
                "paid_remote_tokens":14,"total_tokens":14,"missing_usage_events":0,"receipt_count":1}}]})
    }

    #[test]
    fn token_projection_keeps_only_the_canonical_bounded_report() {
        let mut raw = report();
        raw["raw_prompts"] = json!("secret");
        let projected = project_token_report(raw).unwrap();
        assert!(projected.get("raw_prompts").is_none());
        assert_eq!(projected["periods"][0]["totals"]["total_tokens"], 14);
    }

    #[test]
    fn invalid_counts_and_schema_fail_closed() {
        let mut raw = report();
        raw["periods"][0]["totals"]["cached_input_tokens"] = json!(11);
        assert!(project_token_report(raw).is_err());
        let mut raw = report();
        raw["schema"] = json!("other");
        assert!(project_token_report(raw).is_err());
        let mut raw = report();
        raw["periods"][0]["totals"]["total_tokens"] = json!(99);
        assert!(project_token_report(raw).is_err());
    }

    #[test]
    fn token_query_rejects_unknown_keys_before_filesystem_access() {
        assert_eq!(
            token_query_args(&json!({"command":"delete"}), Path::new("/absent")).unwrap_err(),
            "token_query_invalid"
        );
        assert_eq!(
            token_query_args(
                &json!({"timezoneOffsetSeconds":0,"repoPath":"relative"}),
                Path::new("/absent")
            )
            .unwrap_err(),
            "token_query_invalid"
        );
    }

    struct TestProject(PathBuf);

    impl TestProject {
        fn new() -> Self {
            let nonce = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "simplicio desktop query {} {nonce}",
                std::process::id()
            ));
            std::fs::create_dir(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for TestProject {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn token_query_never_creates_a_ledger_and_keeps_values_in_individual_arguments() {
        let project = TestProject::new();
        let query = json!({"timezoneOffsetSeconds":-10800,"sessionId":"session with spaces","fromEpoch":10,"toEpoch":20});
        assert_eq!(
            token_query_args(&query, &project.0).unwrap_err(),
            "token_ledger_unavailable"
        );
        assert!(!project.0.join(".simplicio").exists());
        std::fs::create_dir(project.0.join(".simplicio")).unwrap();
        let db = project.0.join(".simplicio/token-usage.sqlite3");
        std::fs::write(&db, []).unwrap();
        assert_eq!(
            token_query_args(&query, &project.0).unwrap(),
            vec![
                "tokens",
                "report",
                "--json",
                "--tz-offset-seconds",
                "-10800",
                "--session",
                "session with spaces",
                "--from",
                "10",
                "--to",
                "20",
                "--db",
                db.canonicalize().unwrap().to_str().unwrap(),
            ]
        );
        for invalid in [
            json!({"timezoneOffsetSeconds":0,"sessionId":" --help"}),
            json!({"timezoneOffsetSeconds":0,"fromEpoch":20,"toEpoch":10}),
            json!({"timezoneOffsetSeconds":0,"fromEpoch":10}),
            json!({"timezoneOffsetSeconds":86401}),
        ] {
            assert_eq!(
                token_query_args(&invalid, &project.0).unwrap_err(),
                "token_query_invalid"
            );
        }
    }

    #[cfg(unix)]
    #[test]
    fn token_query_rejects_a_ledger_symlink_outside_the_selected_project() {
        let project = TestProject::new();
        let outside = TestProject::new();
        let external_db = outside.0.join("ledger.sqlite3");
        std::fs::write(&external_db, []).unwrap();
        std::fs::create_dir(project.0.join(".simplicio")).unwrap();
        std::os::unix::fs::symlink(
            external_db,
            project.0.join(".simplicio/token-usage.sqlite3"),
        )
        .unwrap();
        assert_eq!(
            token_query_args(&json!({"timezoneOffsetSeconds":0}), &project.0).unwrap_err(),
            "token_ledger_unavailable"
        );
    }

    #[test]
    #[ignore = "requires SIMPLICIO_TEST_RUNTIME_BIN pointing to a verified native Runtime"]
    fn signed_runtime_token_report_smoke() {
        let binary =
            std::env::var_os("SIMPLICIO_TEST_RUNTIME_BIN").expect("explicit Runtime path required");
        let project = TestProject::new();
        let db = project.0.join(".simplicio/token-usage.sqlite3");
        let input = project.0.join("synthetic-sample.json");
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        for (id, session, tokens) in [
            ("desktop-smoke-1", "desktop smoke session", 100),
            ("desktop-smoke-2", "another session", 900),
        ] {
            let sample = json!({"schema":"workspace.token-analytics/v1","sample_id":id,"receipt_ref":id,
                "session_id":session,"occurred_at_epoch":now-1,"input_tokens":tokens,"cached_input_tokens":20,
                "output_tokens":30,"reasoning_tokens":7,"paid_remote_tokens":tokens+37,"provenance":"measured"});
            std::fs::write(&input, serde_json::to_vec(&sample).unwrap()).unwrap();
            let output = std::process::Command::new(&binary)
                .args(["tokens", "record", "--input"])
                .arg(&input)
                .arg("--db")
                .arg(&db)
                .current_dir(&project.0)
                .env("SIMPLICIO_DESKTOP_BRIDGE", "1")
                .output()
                .unwrap();
            assert!(
                output.status.success(),
                "synthetic record failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
        let args = token_query_args(
            &json!({"timezoneOffsetSeconds":-10800,"sessionId":"desktop smoke session",
            "fromEpoch":now-60,"toEpoch":now+1}),
            &project.0,
        )
        .unwrap();
        let output = std::process::Command::new(&binary)
            .args(args)
            .current_dir(&project.0)
            .env("SIMPLICIO_DESKTOP_BRIDGE", "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "report failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let report = project_token_report(serde_json::from_slice(&output.stdout).unwrap()).unwrap();
        assert_eq!(report["timezone_offset_seconds"], -10800);
        assert_eq!(report["session_id"], "desktop smoke session");
        let periods = report["periods"].as_array().unwrap();
        assert_eq!(periods.len(), 7);
        let custom = periods
            .iter()
            .find(|period| period["window"] == "custom")
            .unwrap();
        assert_eq!(custom["totals"]["sample_count"], 1);
        assert_eq!(custom["totals"]["total_tokens"], 137);
    }

    #[test]
    fn only_a_completed_install_receipt_can_report_success() {
        let receipt = json!({"schema":"simplicio.install-apply/v1","status":"applied","actions":[
            {"name":"binary-copy","status":"skipped"},
            {"name":"assistant-config:codex","status":"done"},
            {"name":"path-registration","status":"skipped"},
            {"name":"install-manifest","status":"done"},
        ]});
        assert!(validate_install_receipt(&receipt).is_ok());
        let mut partial = receipt.clone();
        partial["status"] = json!("partial");
        assert!(validate_install_receipt(&partial).is_err());
        let mut failed = receipt.clone();
        failed["actions"][1]["status"] = json!("failed");
        assert!(validate_install_receipt(&failed).is_err());
        let mut missing = receipt;
        missing["actions"] = json!([]);
        assert!(validate_install_receipt(&missing).is_err());
        assert!(validate_install_receipt(
            &json!({"schema":"simplicio.install-plan/v1","status":"planned"})
        )
        .is_err());
    }

    #[test]
    fn installation_plan_is_redacted_and_digest_changes_with_payload() {
        let mut plan = json!({"schema":"simplicio.install-plan/v1","dry_run":true,"apply_preview":{"config_diffs":[{"label":"codex","changed":true,"exists":true,"path":"/private/user/config","diff":"secret"}]}});
        let projected = project_install_plan(plan.clone()).unwrap();
        assert!(!projected.to_string().contains("secret"));
        assert!(!projected.to_string().contains("/private"));
        plan["apply_preview"]["config_diffs"][0]["diff"] = json!("new proposal");
        assert_ne!(
            projected["planDigest"],
            project_install_plan(plan).unwrap()["planDigest"]
        );
    }
}
