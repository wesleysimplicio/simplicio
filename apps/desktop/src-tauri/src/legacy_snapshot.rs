use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

const STATUS_SCHEMA: &str = "simplicio.status/v1";
const SAVINGS_SCHEMA: &str = "simplicio.savings-report/v1";
const INSTALL_SCHEMA: &str = "simplicio.install-plan/v1";

pub fn build_legacy_snapshot(
    auth: &Value,
    status: &Value,
    savings: &Value,
    install: &Value,
) -> Result<Value, String> {
    if auth.get("ok").and_then(Value::as_bool) != Some(true)
        || status.get("schema").and_then(Value::as_str) != Some(STATUS_SCHEMA)
        || savings.get("schema").and_then(Value::as_str) != Some(SAVINGS_SCHEMA)
        || install.get("schema").and_then(Value::as_str) != Some(INSTALL_SCHEMA)
    {
        return Err("Contrato legado do Runtime incompatível".to_string());
    }

    let generated_at = format!(
        "unix:{}",
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| "Relógio local inválido".to_string())?
            .as_secs()
    );
    let identity_active = auth
        .pointer("/identity/status")
        .and_then(Value::as_str)
        == Some("active");
    let entitlement_status = auth
        .pointer("/entitlement/status")
        .and_then(Value::as_str);
    let entitlement_active = auth
        .pointer("/entitlement/active")
        .and_then(Value::as_bool)
        == Some(true);
    let access_state = if !identity_active {
        "signed_out"
    } else if entitlement_status.is_none() {
        "unknown"
    } else if entitlement_active {
        "active"
    } else {
        "inactive"
    };

    let runtime_version = status
        .pointer("/compiled_runtime/binary_version")
        .and_then(Value::as_str)
        .unwrap_or("");
    let runtime_state = if runtime_version.is_empty() {
        "degraded"
    } else {
        "healthy"
    };
    let saved_events = savings
        .pointer("/runtime_saved_total/events")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let saved_tokens = savings
        .pointer("/runtime_saved_total/saved_tokens")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let provider_hit_rate = status
        .pointer("/cache/hit_rate")
        .and_then(Value::as_f64);
    let decision_runs = status
        .pointer("/cache/runs_with_decision")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let map_ready = status
        .pointer("/evidence/index_ready")
        .and_then(Value::as_bool)
        .unwrap_or(false);

    let mut snapshot = json!({
        "schema": "simplicio.desktop-snapshot/v1",
        "generatedAt": generated_at,
        "source": "runtime",
        "access": {
            "state": access_state,
            "identityKnown": identity_active,
            "entitlementKnown": entitlement_status.is_some(),
            "reasonCode": match access_state {
                "active" => "legacy_runtime_active",
                "inactive" => "legacy_runtime_entitlement_inactive",
                "signed_out" => "legacy_runtime_signed_out",
                _ => "legacy_runtime_entitlement_unknown",
            },
            "checkedAt": generated_at,
            "expiresAt": auth.pointer("/token/expires_at").and_then(Value::as_str),
            "displayName": auth.pointer("/user/name").and_then(Value::as_str),
            "email": auth.pointer("/user/email").and_then(Value::as_str),
            "plan": auth.pointer("/entitlement/plan").and_then(Value::as_str),
        },
        "runtime": {
            "state": runtime_state,
            "version": runtime_version,
            "transport": "daemon",
            "lastReceiptAt": Value::Null,
            "deterministic": {
                "ready": runtime_state == "healthy",
                "cpuFirst": true,
                "mapper": "canonical",
                "mapCache": "generation_scoped",
                "hookContext": "receipt_only",
            },
            "optionalFast": {
                "required": false,
                "hookInjected": false,
                "status": "not_required",
            },
        },
        "savings": {
            "monthTokens": saved_tokens,
            "monthPercent": 0,
            "estimatedUsd": Value::Null,
            "proofKind": if saved_events > 0 { "measured" } else { "unavailable" },
            "ledgerStatus": if saved_events > 0 { "valid" } else { "unavailable" },
            "eventCount": saved_events,
            "providerCache": {
                "status": if provider_hit_rate.is_some() { "mixed" } else { "unknown" },
                "hitPercent": provider_hit_rate.map(|rate| rate * 100.0),
                "proofKind": if provider_hit_rate.is_some() { "measured" } else { "unavailable" },
                "telemetrySource": if provider_hit_rate.is_some() { Some("simplicio.status/v1") } else { None },
            },
            "decisionCache": {
                "hitPercent": provider_hit_rate.map(|rate| rate * 100.0),
                "runs": decision_runs,
                "proofKind": if provider_hit_rate.is_some() { "measured" } else { "unavailable" },
                "hits": status.pointer("/cache/hits").and_then(Value::as_u64).unwrap_or(0),
            },
            "mapCache": {
                "status": if map_ready { "ready" } else { "unavailable" },
                "delivery": "receipt_only",
                "generation": Value::Null,
                "digest": Value::Null,
                "bytes": Value::Null,
                "fastInHooks": false,
            },
        },
        "providers": providers_from_install(install),
        "activity": [],
        "actions": [
            { "id": "login", "governed": true, "executed": false },
            { "id": "subscribe", "governed": true, "executed": false },
            { "id": "refresh_access", "governed": true, "executed": false },
            { "id": "repair_providers", "governed": true, "executed": false },
        ],
        "freshness": {
            "access": generated_at,
            "runtime": generated_at,
            "savings": generated_at,
            "providers": generated_at,
        },
        "redaction": {
            "personalPaths": true,
            "configurationBodies": true,
            "credentials": true,
            "prompts": true,
            "skillBodies": true,
            "rawLedgers": true,
        },
        "limits": {
            "maxBytes": 65536,
            "maxProviders": 32,
            "maxActivity": 5,
        },
    });

    let encoded = serde_json::to_vec(&snapshot)
        .map_err(|_| "Não foi possível calcular o digest do snapshot".to_string())?;
    let digest = Sha256::digest(encoded);
    snapshot["snapshotDigest"] = Value::String(format!("sha256:{digest:x}"));
    Ok(snapshot)
}

fn providers_from_install(install: &Value) -> Vec<Value> {
    install
        .pointer("/apply_preview/config_diffs")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .take(32)
        .filter_map(|item| {
            let id = item.get("label")?.as_str()?;
            let exists = item.get("exists").and_then(Value::as_bool).unwrap_or(false);
            let changed = item.get("changed").and_then(Value::as_bool).unwrap_or(false);
            let (name, kind, tier) = provider_identity(id);
            let state = if !exists {
                "not_installed"
            } else if changed {
                "needs_attention"
            } else {
                "registered"
            };
            Some(json!({
                "id": id,
                "name": name,
                "kind": kind,
                "protocol": "MCP",
                "tier": tier,
                "state": state,
                "detail": if changed {
                    "A configuração existe, mas diverge do Runtime gerenciado."
                } else if exists {
                    "Configuração encontrada; execute a verificação para confirmar o handshake."
                } else {
                    "Nenhuma configuração verificável foi encontrada."
                },
                "installState": if exists { "installed" } else { "absent" },
                "registrationState": if exists && !changed { "registered" } else { "unregistered" },
                "handshakeState": "unverified",
                "freshness": if changed { "stale" } else { "unknown" },
                "reasonCode": if changed { "runtime_path_drift" } else if exists { "handshake_unverified" } else { "not_installed" },
                "availableActions": if changed || exists { json!(["repair", "verify"]) } else { json!(["register"]) },
            }))
        })
        .collect()
}

fn provider_identity(id: &str) -> (&'static str, &'static str, &'static str) {
    match id {
        "claude-code" => ("Claude Code", "agent", "first_class"),
        "claude-desktop" => ("Claude Desktop", "agent", "compatible"),
        "codex" => ("Codex", "agent", "first_class"),
        "hermes" => ("Hermes Agent", "agent", "compatible"),
        "gemini" => ("Gemini", "agent", "compatible"),
        "opencode" => ("OpenCode", "editor", "compatible"),
        "trae" => ("Trae", "editor", "compatible"),
        "vscode" => ("Visual Studio Code", "editor", "compatible"),
        _ => ("Provider", "editor", "compatible"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixtures() -> (Value, Value, Value, Value) {
        (
            json!({
                "ok": true,
                "identity": { "status": "active" },
                "entitlement": { "status": "active", "active": true, "plan": "annual" },
                "token": { "expires_at": "2026-09-01" },
                "user": { "name": "Wesley", "email": "user@example.com" }
            }),
            json!({
                "schema": STATUS_SCHEMA,
                "compiled_runtime": { "binary_version": "3.8.35" },
                "cache": { "hit_rate": Value::Null, "runs_with_decision": 0, "hits": 0 },
                "evidence": { "index_ready": false }
            }),
            json!({
                "schema": SAVINGS_SCHEMA,
                "runtime_saved_total": { "events": 0, "saved_tokens": 0 }
            }),
            json!({
                "schema": INSTALL_SCHEMA,
                "apply_preview": { "config_diffs": [
                    { "label": "codex", "exists": true, "changed": false },
                    { "label": "vscode", "exists": true, "changed": true }
                ]}
            }),
        )
    }

    #[test]
    fn builds_a_bounded_active_snapshot_without_inventing_handshakes() {
        let (auth, status, savings, install) = fixtures();
        let snapshot = build_legacy_snapshot(&auth, &status, &savings, &install).unwrap();
        assert_eq!(snapshot["access"]["state"], "active");
        assert_eq!(snapshot["runtime"]["version"], "3.8.35");
        assert_eq!(snapshot["providers"][0]["state"], "registered");
        assert_eq!(snapshot["providers"][1]["state"], "needs_attention");
        assert!(snapshot["providers"]
            .as_array()
            .unwrap()
            .iter()
            .all(|provider| provider["state"] != "connected"));
        assert!(snapshot["snapshotDigest"]
            .as_str()
            .unwrap()
            .starts_with("sha256:"));
    }

    #[test]
    fn rejects_unrecognized_legacy_contracts() {
        let (auth, mut status, savings, install) = fixtures();
        status["schema"] = json!("unexpected");
        assert!(build_legacy_snapshot(&auth, &status, &savings, &install).is_err());
    }
}
