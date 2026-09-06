use serde_json::{json, Map, Value};
use std::collections::BTreeSet;

const RESULT_SCHEMA: &str = "simplicio.host-plugin-command-result/v1";
const PLAN_SCHEMA: &str = "simplicio.host-plugin-plan-summary/v1";
const SNAPSHOT_SCHEMA: &str = "simplicio.host-plugin-snapshot/v1";
const RECEIPT_SCHEMA: &str = "simplicio.host-plugin-receipt/v1";
const CLI_SCHEMA: &str = "simplicio.host-plugin-cli/v1";
const HOSTS: &[&str] = &[
    "codex", "claude", "gemini", "copilot", "qwen", "hermes", "kilo", "opencode",
];
const MODES: &[&str] = &["manager", "portable", "hybrid"];
const DISPOSITIONS: &[&str] = &[
    "ready",
    "already_exact",
    "not_detected",
    "unknown",
    "blocked",
];
const PLAN_REASONS: &[&str] = &[
    "ready",
    "already_exact",
    "not_detected",
    "unknown",
    "blocked",
    "local_install_capability_unverified",
];
const OPERATIONS: &[&str] = &["apply", "reconcile"];
const RECEIPT_STATES: &[&str] = &[
    "prepared",
    "applying",
    "complete",
    "partial",
    "requires_reconcile",
];
const RESULT_STATUSES: &[&str] = &[
    "pending",
    "applying",
    "verified",
    "applied_unverified",
    "not_detected",
    "unknown",
    "failed",
    "drifted",
    "blocked",
];
const REASON_CODES: &[&str] = &[
    "awaiting_effect",
    "already_exact",
    "host_or_manager_not_detected",
    "state_unknown",
    "precondition_blocked",
    "effect_prepared",
    "manager_version_verified",
    "manager_readback_drifted",
    "manager_readback_unknown",
    "portable_tree_verified",
    "exact_readback",
    "portable_payload_not_exact",
    "manager_plugin_drifted",
    "local_install_capability_unverified",
    "effect_failed",
    "reconcile_committed",
    "reconcile_not_applied",
    "reconcile_partial",
    "reconcile_drifted",
    "reconcile_ambiguous",
    "no_action_required",
];
const FAILURE_CODES: &[&str] = &[
    "manager_unavailable",
    "manager_precondition_changed",
    "manager_effect_failed",
    "manager_readback_failed",
    "payload_changed",
    "portable_busy",
    "portable_precondition_changed",
    "portable_stage_failed",
    "portable_backup_failed",
    "portable_publish_failed",
    "portable_readback_failed",
    "receipt_persistence_failed",
    "internal_contract",
];
const VERIFICATIONS: &[&str] = &[
    "none",
    "manager_version",
    "installed_tree",
    "installed_tree_and_manager",
];
const RECONCILE: &[&str] = &[
    "committed",
    "not_applied",
    "partial",
    "drifted",
    "ambiguous",
    "not_applicable",
];

fn invalid() -> String {
    "host_plugin_contract_invalid".to_string()
}

fn object(value: &Value) -> Result<&Map<String, Value>, String> {
    value.as_object().ok_or_else(invalid)
}

fn closed<'a>(
    object: &'a Map<String, Value>,
    key: &str,
    values: &[&str],
) -> Result<&'a str, String> {
    object
        .get(key)
        .and_then(Value::as_str)
        .filter(|value| values.contains(value))
        .ok_or_else(invalid)
}

pub fn valid_digest(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || matches!(byte, b'a'..=b'f'))
}

fn digest<'a>(object: &'a Map<String, Value>, key: &str) -> Result<&'a str, String> {
    object
        .get(key)
        .and_then(Value::as_str)
        .filter(|value| valid_digest(value))
        .ok_or_else(invalid)
}

fn optional_digest<'a>(
    object: &'a Map<String, Value>,
    key: &str,
) -> Result<Option<&'a str>, String> {
    match object.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) if valid_digest(value) => Ok(Some(value)),
        _ => Err(invalid()),
    }
}

fn bounded_version(value: Option<&Value>) -> Result<&str, String> {
    value
        .and_then(Value::as_str)
        .filter(|value| {
            !value.is_empty()
                && value.len() <= 64
                && value.bytes().all(|byte| {
                    byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'+' | b'_' | b'-')
                })
        })
        .ok_or_else(invalid)
}

fn component_versions(value: Option<&Value>) -> Result<(), String> {
    let versions = value
        .and_then(Value::as_object)
        .filter(|versions| versions.len() <= 32)
        .ok_or_else(invalid)?;
    for (component, version) in versions {
        if component.is_empty()
            || component.len() > 64
            || !component
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
        {
            return Err(invalid());
        }
        bounded_version(Some(version))?;
    }
    Ok(())
}

fn command_payload<'a>(value: &'a Value, result: &str, field: &str) -> Result<&'a Value, String> {
    let envelope = object(value)?;
    if envelope.get("schema").and_then(Value::as_str) != Some(RESULT_SCHEMA)
        || envelope.get("result").and_then(Value::as_str) != Some(result)
    {
        return Err(invalid());
    }
    envelope.get(field).ok_or_else(invalid)
}

pub fn project_plan(value: Value) -> Result<Value, String> {
    let plan = object(command_payload(&value, "plan", "plan")?)?;
    if plan.get("schema").and_then(Value::as_str) != Some(PLAN_SCHEMA) {
        return Err(invalid());
    }
    component_versions(plan.get("component_versions"))?;
    let selection = plan
        .get("selection")
        .and_then(Value::as_object)
        .filter(|selection| {
            selection.len() == 1 && selection.get("scope").and_then(Value::as_str) == Some("all")
        })
        .ok_or_else(invalid)?;
    let hosts = plan
        .get("hosts")
        .and_then(Value::as_array)
        .filter(|hosts| hosts.len() == HOSTS.len())
        .ok_or_else(invalid)?;
    let mut seen = BTreeSet::new();
    let mut projected = Vec::with_capacity(HOSTS.len());
    for host in hosts {
        let host = object(host)?;
        let id = closed(host, "host", HOSTS)?;
        if !seen.insert(id) {
            return Err(invalid());
        }
        projected.push(json!({
            "host": id,
            "mode": closed(host, "mode", MODES)?,
            "disposition": closed(host, "disposition", DISPOSITIONS)?,
            "reason_code": closed(host, "reason_code", PLAN_REASONS)?,
        }));
    }
    if seen.len() != HOSTS.len() {
        return Err(invalid());
    }
    Ok(json!({
        "schema": RESULT_SCHEMA,
        "result": "plan",
        "plan": {
            "schema": PLAN_SCHEMA,
            "plan_digest": digest(plan, "plan_digest")?,
            "selection": selection,
            "manifest_digest": digest(plan, "manifest_digest")?,
            "plugin_version": bounded_version(plan.get("plugin_version"))?,
            "hosts": projected,
        }
    }))
}

fn project_snapshot(value: &Value) -> Result<Value, String> {
    let snapshot = object(value)?;
    if snapshot.get("schema").and_then(Value::as_str) != Some(SNAPSHOT_SCHEMA)
        || snapshot.get("receipt_schema").and_then(Value::as_str) != Some(RECEIPT_SCHEMA)
        || !snapshot
            .get("attempt_id")
            .and_then(Value::as_str)
            .is_some_and(|value| !value.is_empty() && value.len() <= 128)
        || !snapshot
            .get("revision")
            .and_then(Value::as_u64)
            .is_some_and(|value| value > 0)
    {
        return Err(invalid());
    }
    digest(snapshot, "manifest_digest")?;
    optional_digest(snapshot, "observed_plan_digest")?;
    optional_digest(snapshot, "prior_receipt_digest")?;
    let hosts = snapshot
        .get("hosts")
        .and_then(Value::as_array)
        .filter(|hosts| hosts.len() <= HOSTS.len())
        .ok_or_else(invalid)?;
    let mut seen = BTreeSet::new();
    let mut projected = Vec::with_capacity(hosts.len());
    for host in hosts {
        let host = object(host)?;
        let id = closed(host, "host", HOSTS)?;
        if !seen.insert(id) {
            return Err(invalid());
        }
        let failure_code = match host.get("failure_code") {
            None | Some(Value::Null) => None,
            _ => Some(closed(host, "failure_code", FAILURE_CODES)?),
        };
        let reconcile = match host.get("reconcile") {
            None | Some(Value::Null) => None,
            _ => Some(closed(host, "reconcile", RECONCILE)?),
        };
        projected.push(json!({
            "host": id,
            "status": closed(host, "status", RESULT_STATUSES)?,
            "reason_code": closed(host, "reason_code", REASON_CODES)?,
            "failure_code": failure_code,
            "verification": closed(host, "verification", VERIFICATIONS)?,
            "reconcile": reconcile,
        }));
    }
    let state = closed(snapshot, "state", RECEIPT_STATES)?;
    let durable_id = optional_digest(snapshot, "durable_id")?;
    if matches!(state, "partial" | "requires_reconcile") && durable_id.is_none() {
        return Err(invalid());
    }
    Ok(json!({
        "schema": SNAPSHOT_SCHEMA,
        "receipt_digest": digest(snapshot, "receipt_digest")?,
        "operation": closed(snapshot, "operation", OPERATIONS)?,
        "state": state,
        "durable_id": durable_id,
        "plan_digest": digest(snapshot, "plan_digest")?,
        "hosts": projected,
    }))
}

pub fn project_operation(value: Value, expected_operation: &str) -> Result<Value, String> {
    let snapshot = project_snapshot(command_payload(&value, "receipt", "snapshot")?)?;
    if snapshot.get("operation").and_then(Value::as_str) != Some(expected_operation)
        || !matches!(
            snapshot.get("state").and_then(Value::as_str),
            Some("complete" | "partial" | "requires_reconcile")
        )
    {
        return Err(invalid());
    }
    Ok(json!({ "schema": RESULT_SCHEMA, "result": "receipt", "snapshot": snapshot }))
}

pub fn validate_desktop_projection(value: Option<&Value>) -> Result<(), String> {
    let Some(value) = value else {
        return Ok(());
    };
    let projection = object(value)?;
    let allowed = BTreeSet::from([
        "schema",
        "available",
        "reconcileRequired",
        "pendingCount",
        "pendingTruncated",
        "state",
        "revision",
        "receiptDigest",
        "reconcileReceiptId",
        "planDigest",
        "hosts",
    ]);
    if projection.keys().any(|key| !allowed.contains(key.as_str()))
        || projection.get("schema").and_then(Value::as_str)
            != Some("simplicio.desktop-host-plugins/v1")
    {
        return Err(invalid());
    }
    let available = projection
        .get("available")
        .and_then(Value::as_bool)
        .ok_or_else(invalid)?;
    let reconcile_required = projection
        .get("reconcileRequired")
        .and_then(Value::as_bool)
        .ok_or_else(invalid)?;
    let pending_count = projection
        .get("pendingCount")
        .and_then(Value::as_u64)
        .ok_or_else(invalid)?;
    let pending_truncated = projection
        .get("pendingTruncated")
        .and_then(Value::as_bool)
        .ok_or_else(invalid)?;
    if reconcile_required != (pending_count > 0) || pending_truncated != (pending_count > 8) {
        return Err(invalid());
    }
    let hosts = projection
        .get("hosts")
        .and_then(Value::as_array)
        .filter(|hosts| hosts.len() <= HOSTS.len())
        .ok_or_else(invalid)?;
    let mut seen = BTreeSet::new();
    let host_allowed = BTreeSet::from([
        "host",
        "status",
        "reasonCode",
        "failureCode",
        "verification",
        "reconcile",
    ]);
    for host in hosts {
        let host = object(host)?;
        if host.keys().any(|key| !host_allowed.contains(key.as_str())) {
            return Err(invalid());
        }
        let id = closed(host, "host", HOSTS)?;
        if !seen.insert(id) {
            return Err(invalid());
        }
        closed(host, "status", RESULT_STATUSES)?;
        closed(host, "reasonCode", REASON_CODES)?;
        closed(host, "verification", VERIFICATIONS)?;
        if !matches!(host.get("failureCode"), None | Some(Value::Null)) {
            closed(host, "failureCode", FAILURE_CODES)?;
        }
        if !matches!(host.get("reconcile"), None | Some(Value::Null)) {
            closed(host, "reconcile", RECONCILE)?;
        }
    }
    let state = match projection.get("state") {
        None => None,
        Some(Value::String(state)) if RECEIPT_STATES.contains(&state.as_str()) => {
            Some(state.as_str())
        }
        _ => return Err(invalid()),
    };
    let revision = match projection.get("revision") {
        None => None,
        Some(value) => value.as_u64().filter(|revision| *revision > 0),
    };
    let receipt_digest = match projection.get("receiptDigest") {
        None => None,
        Some(Value::String(value)) if valid_digest(value) => Some(value.as_str()),
        _ => return Err(invalid()),
    };
    let plan_digest = match projection.get("planDigest") {
        None => None,
        Some(Value::String(value)) if valid_digest(value) => Some(value.as_str()),
        _ => return Err(invalid()),
    };
    let reconcile_receipt_id = match projection.get("reconcileReceiptId") {
        None => None,
        Some(Value::String(value)) if valid_digest(value) => Some(value.as_str()),
        _ => return Err(invalid()),
    };
    let snapshot_fields = [
        state.is_some(),
        revision.is_some(),
        receipt_digest.is_some(),
        plan_digest.is_some(),
    ];
    if snapshot_fields.iter().any(|present| *present)
        && snapshot_fields.iter().any(|present| !*present)
    {
        return Err(invalid());
    }
    if !available && (!hosts.is_empty() || snapshot_fields[0] || pending_count > 0) {
        return Err(invalid());
    }
    if state.is_none() && !hosts.is_empty() {
        return Err(invalid());
    }
    if reconcile_required != reconcile_receipt_id.is_some() {
        return Err(invalid());
    }
    Ok(())
}

pub fn cli_error_code(value: &Value) -> Option<&str> {
    let value = value.as_object()?;
    (value.get("schema")?.as_str()? == CLI_SCHEMA && value.get("status")?.as_str()? == "error")
        .then(|| value.get("error_code")?.as_str())?
        .filter(|code| {
            code.len() <= 96
                && code.as_bytes().first().is_some_and(u8::is_ascii_lowercase)
                && code
                    .bytes()
                    .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'_')
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot(state: &str) -> Value {
        json!({
            "schema": SNAPSHOT_SCHEMA,
            "receipt_schema": "simplicio.host-plugin-receipt/v1",
            "receipt_digest": format!("sha256:{}", "a".repeat(64)),
            "operation": "apply",
            "state": state,
            "attempt_id": "private-attempt",
            "revision": 1,
            "durable_id": format!("sha256:{}", "b".repeat(64)),
            "plan_digest": format!("sha256:{}", "c".repeat(64)),
            "manifest_digest": format!("sha256:{}", "d".repeat(64)),
            "hosts": [{
                "host": "codex", "status": "applied_unverified", "reason_code": "manager_readback_unknown",
                "failure_code": null, "verification": "none", "reconcile": null,
                "backup_id": "/private/backup", "raw_stdout": "secret"
            }]
        })
    }

    fn plan() -> Value {
        let hosts = HOSTS
            .iter()
            .enumerate()
            .map(|(index, host)| {
                json!({
                    "host": host,
                    "mode": if index >= 6 { "portable" } else { "manager" },
                    "disposition": "ready",
                    "reason_code": "ready",
                    "config_path": "/private/user",
                    "raw_stdout": "secret"
                })
            })
            .collect::<Vec<_>>();
        json!({
            "schema": RESULT_SCHEMA,
            "result": "plan",
            "plan": {
                "schema": PLAN_SCHEMA,
                "plan_digest": format!("sha256:{}", "a".repeat(64)),
                "selection": { "scope": "all" },
                "manifest_digest": format!("sha256:{}", "b".repeat(64)),
                "plugin_version": "3.8.41",
                "component_versions": { "runtime": "3.8.41", "plugin": "3.8.41" },
                "hosts": hosts
            }
        })
    }

    #[test]
    fn bundled_runtime_host_matrix_is_accepted() {
        let value = serde_json::from_str(include_str!("../../src/runtime-host-plugin-plan.fixture.json")).unwrap();
        let result = project_plan(value).unwrap();
        let hosts = result["plan"]["hosts"].as_array().unwrap();
        assert!(hosts.iter().any(|h| h["host"] == "kilo"));
        assert!(hosts.iter().any(|h| h["host"] == "opencode"));
        assert_eq!(hosts.len(), 8);
    }

    #[test]
    fn plan_projection_requires_all_hosts_and_drops_paths_and_component_details() {
        let projected = project_plan(plan()).unwrap();
        assert_eq!(projected["plan"]["hosts"].as_array().unwrap().len(), 8);
        let encoded = serde_json::to_string(&projected).unwrap();
        assert!(!encoded.contains("private"));
        assert!(!encoded.contains("secret"));
        assert!(!encoded.contains("component_versions"));
        let mut invalid = plan();
        invalid["plan"]
            .as_object_mut()
            .unwrap()
            .remove("component_versions");
        assert!(project_plan(invalid).is_err());
    }

    #[test]
    fn operation_projection_drops_raw_receipt_paths_and_streams() {
        let value = json!({
            "schema": RESULT_SCHEMA, "result": "receipt",
            "receipt": { "backup_id": "/private/backup", "stdout": "secret" },
            "snapshot": snapshot("complete")
        });
        let projected = project_operation(value, "apply").unwrap();
        let encoded = serde_json::to_string(&projected).unwrap();
        assert!(!encoded.contains("private"));
        assert!(!encoded.contains("secret"));
        assert!(!encoded.contains("backup"));
        assert_eq!(
            projected["snapshot"]["hosts"][0]["status"],
            "applied_unverified"
        );
    }

    #[test]
    fn operation_projection_rejects_mismatched_or_non_terminal_receipts() {
        let apply = json!({
            "schema": RESULT_SCHEMA, "result": "receipt", "receipt": {}, "snapshot": snapshot("complete")
        });
        assert!(project_operation(apply, "reconcile").is_err());
        let pending = json!({
            "schema": RESULT_SCHEMA, "result": "receipt", "receipt": {}, "snapshot": snapshot("applying")
        });
        assert!(project_operation(pending, "apply").is_err());
    }

    #[test]
    fn desktop_projection_is_bounded_and_rejects_private_fields() {
        let projection = json!({
            "schema": "simplicio.desktop-host-plugins/v1",
            "available": true,
            "reconcileRequired": true,
            "reconcileReceiptId": format!("sha256:{}", "e".repeat(64)),
            "pendingCount": 9,
            "pendingTruncated": true,
            "state": "partial",
            "revision": 2,
            "receiptDigest": format!("sha256:{}", "a".repeat(64)),
            "planDigest": format!("sha256:{}", "c".repeat(64)),
            "hosts": [{
                "host": "codex", "status": "failed", "reasonCode": "effect_failed",
                "failureCode": "manager_effect_failed", "verification": "none", "reconcile": "ambiguous"
            }]
        });
        assert!(validate_desktop_projection(Some(&projection)).is_ok());
        let mut private = projection;
        private["configPath"] = json!("/private/user");
        assert!(validate_desktop_projection(Some(&private)).is_err());
    }

    #[test]
    fn closed_cli_error_never_reflects_arbitrary_output() {
        assert_eq!(
            cli_error_code(
                &json!({ "schema": CLI_SCHEMA, "status": "error", "error_code": "plan_precondition_changed" })
            ),
            Some("plan_precondition_changed")
        );
        assert_eq!(
            cli_error_code(
                &json!({ "schema": CLI_SCHEMA, "status": "error", "error_code": "/private secret" })
            ),
            None
        );
    }
}
