use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

const STATUS_SCHEMA: &str = "simplicio.status/v1";
const SAVINGS_SCHEMA: &str = "simplicio.savings-report/v1";
const INSTALL_SCHEMA: &str = "simplicio.install-plan/v1";
const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;

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
    // Match auth_access's documented positive auth-status contract. The public
    // snapshot states do not document negative legacy auth-status payloads;
    // unknown, contradictory or error responses cannot imply a subscription denial.
    let auth_error = auth.get("error").is_some_and(|error| !error.is_null());
    let identity_active =
        !auth_error && auth.pointer("/identity/status").and_then(Value::as_str) == Some("active");
    let access_active = identity_active
        && auth.pointer("/entitlement/status").and_then(Value::as_str) == Some("active")
        && auth.pointer("/entitlement/active").and_then(Value::as_bool) == Some(true);
    let access_state = if access_active { "active" } else { "unknown" };

    let runtime_version = status
        .pointer("/compiled_runtime/binary_version")
        .and_then(Value::as_str)
        .unwrap_or("");
    let runtime_state = if runtime_version.is_empty() {
        "degraded"
    } else {
        "healthy"
    };
    let saved_events = savings_count(&savings["runtime_saved_total"]["events"])?;
    let saved_tokens = savings_count(&savings["runtime_saved_total"]["saved_tokens"])?;
    if saved_events == 0 && saved_tokens != 0 {
        return Err("legacy_savings_invalid".into());
    }
    // Share integrity, promotability, proof and counter validation with the
    // context report. A nonzero event count alone is not a valid ledger.
    let savings_ledger_status = if crate::context_report::project(savings.clone()).is_ok() {
        "valid"
    } else {
        "unavailable"
    };
    let provider_hit_rate = status.pointer("/cache/hit_rate").and_then(Value::as_f64);
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
            "entitlementKnown": access_active,
            "reasonCode": match access_state {
                "active" => "legacy_runtime_active",
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
            // This required compatibility field retains the known raw counter.
            // savings-report/v1 is all-history, with no monthly bounds. Every
            // legacy consumer must keep it hidden behind unavailable proof;
            // the separate context report presents qualified historical totals.
            "monthTokens": saved_tokens,
            "monthPercent": 0,
            "estimatedUsd": Value::Null,
            "proofKind": "unavailable",
            "ledgerStatus": savings_ledger_status,
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

fn savings_count(value: &Value) -> Result<u64, String> {
    value
        .as_u64()
        .filter(|count| *count <= MAX_SAFE_INTEGER)
        .ok_or_else(|| "legacy_savings_invalid".into())
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

    fn measured_savings() -> Value {
        // Aggregate-only fixture using the public context_report contract.
        json!({
            "schema": SAVINGS_SCHEMA,
            "ledger": {
                "status": "valid", "hash_chain_valid": true, "promotable": true,
                "corrupt_lines": 0, "total_events": 12
            },
            "runtime_saved_total": { "events": 12, "saved_tokens": 350 },
            "llm_spend_total": { "events": 0 },
            "without_simplicio": { "paid_tokens": 1000 },
            "with_simplicio": { "paid_tokens": 650 },
            "baseline_kind": "measured", "confidence": "measured",
            "proof_breakdown": { "measured": 12 },
            "tokenizer_policy": {
                "by_tokenizer_id": { "n/a-not-required": 12 },
                "unlabeled_estimated_events_flagged": 0
            }
        })
    }

    fn savings_summary(input: &Value) -> Value {
        let (auth, status, _, install) = fixtures();
        build_legacy_snapshot(&auth, &status, input, &install).unwrap()["savings"].clone()
    }

    #[test]
    fn preserves_historical_totals_without_inventing_monthly_proof() {
        for (kind, breakdown) in [
            ("measured", json!({ "measured": 12 })),
            ("estimated", json!({ "estimated": 12 })),
            ("replayed", json!({ "replayed": 12 })),
            ("mixed", json!({ "measured": 9, "estimated": 3 })),
        ] {
            let mut input = measured_savings();
            input["baseline_kind"] = json!(kind);
            input["proof_breakdown"] = breakdown;
            let summary = savings_summary(&input);
            assert_eq!(
                summary["proofKind"], "unavailable",
                "promoted {kind} history"
            );
            assert_eq!(summary["ledgerStatus"], "valid");
            assert_eq!(summary["monthTokens"], 350);
            assert_eq!(summary["eventCount"], 12);
        }
    }

    #[test]
    fn invalid_integrity_or_unpromotable_ledger_never_becomes_measured_or_zero() {
        for (key, replacement) in [
            ("status", json!("invalid")),
            ("hash_chain_valid", json!(false)),
            ("promotable", json!(false)),
            ("corrupt_lines", json!(1)),
            ("total_events", json!(13)),
        ] {
            let mut input = measured_savings();
            input["ledger"][key] = replacement;
            let summary = savings_summary(&input);
            assert_eq!(summary["proofKind"], "unavailable", "accepted {key}");
            assert_eq!(summary["ledgerStatus"], "unavailable");
            assert_eq!(summary["monthTokens"], 350);
            assert_eq!(summary["eventCount"], 12);
        }
    }

    #[test]
    fn absent_evidence_is_unavailable_even_with_nonzero_counters() {
        for key in [
            "ledger",
            "proof_breakdown",
            "tokenizer_policy",
            "llm_spend_total",
        ] {
            let mut input = measured_savings();
            input.as_object_mut().unwrap().remove(key);
            let summary = savings_summary(&input);
            assert_eq!(summary["proofKind"], "unavailable", "accepted {key}");
            assert_eq!(summary["ledgerStatus"], "unavailable");
            assert_eq!(summary["monthTokens"], 350);
            assert_eq!(summary["eventCount"], 12);
        }
        let summary = savings_summary(&json!({
            "schema": SAVINGS_SCHEMA,
            "runtime_saved_total": { "events": 12, "saved_tokens": 350 }
        }));
        assert_eq!(summary["proofKind"], "unavailable");
        assert_eq!(summary["ledgerStatus"], "unavailable");
        assert_eq!(summary["monthTokens"], 350);
    }

    #[test]
    fn unknown_or_benchmark_proof_and_missing_qualifiers_stay_unavailable() {
        for (key, replacement) in [
            ("baseline_kind", Value::Null),
            ("baseline_kind", json!("future-kind")),
            ("baseline_kind", json!("benchmark")),
            ("confidence", Value::Null),
            ("confidence", json!("future-confidence")),
            ("proof_breakdown", json!({ "future-proof": 12 })),
            ("proof_breakdown", json!({ "benchmark-fixture": 12 })),
        ] {
            let mut input = measured_savings();
            input[key] = replacement;
            let summary = savings_summary(&input);
            assert_eq!(summary["proofKind"], "unavailable", "accepted {key}");
            assert_eq!(summary["ledgerStatus"], "valid");
            assert_eq!(summary["monthTokens"], 350);
        }
    }

    #[test]
    fn heuristic_unlabeled_or_conflicting_proof_does_not_claim_measured_savings() {
        for (key, replacement) in [
            ("baseline_kind", json!("estimated")),
            ("proof_breakdown", json!({ "measured": 9, "estimated": 3 })),
            (
                "tokenizer_policy",
                json!({
                    "by_tokenizer_id": { "heuristic:chars-div-4": 12 },
                    "unlabeled_estimated_events_flagged": 0
                }),
            ),
            (
                "tokenizer_policy",
                json!({
                    "by_tokenizer_id": { "n/a-not-required": 11 },
                    "unlabeled_estimated_events_flagged": 1
                }),
            ),
        ] {
            let mut input = measured_savings();
            input[key] = replacement;
            let summary = savings_summary(&input);
            assert_eq!(summary["proofKind"], "unavailable");
            assert_eq!(summary["ledgerStatus"], "valid");
            assert_eq!(summary["monthTokens"], 350);
        }
    }

    #[test]
    fn gross_net_divergence_and_mixed_llm_spend_do_not_become_unqualified_savings() {
        for paid_tokens in [900, 1100] {
            let mut input = measured_savings();
            input["with_simplicio"]["paid_tokens"] = json!(paid_tokens);
            let summary = savings_summary(&input);
            assert_eq!(summary["proofKind"], "unavailable");
            assert_eq!(summary["ledgerStatus"], "valid");
            assert_eq!(summary["monthTokens"], 350);
        }
        let mut input = measured_savings();
        input["runtime_saved_total"]["events"] = json!(10);
        input["llm_spend_total"]["events"] = json!(2);
        let summary = savings_summary(&input);
        assert_eq!(summary["proofKind"], "unavailable");
        assert_eq!(summary["monthTokens"], 350);
        assert_eq!(summary["eventCount"], 10);
    }

    #[test]
    fn missing_invalid_or_unsafe_counters_fail_instead_of_becoming_zero() {
        let (auth, status, _, install) = fixtures();
        for key in ["events", "saved_tokens"] {
            let mut missing = measured_savings();
            missing["runtime_saved_total"]
                .as_object_mut()
                .unwrap()
                .remove(key);
            assert!(build_legacy_snapshot(&auth, &status, &missing, &install).is_err());
            for replacement in [
                Value::Null,
                json!(-1),
                json!(1.5),
                json!("12"),
                json!(9_007_199_254_740_992_u64),
            ] {
                let mut input = measured_savings();
                input["runtime_saved_total"][key] = replacement;
                assert!(build_legacy_snapshot(&auth, &status, &input, &install).is_err());
            }
        }
        let mut contradictory = measured_savings();
        contradictory["runtime_saved_total"]["events"] = json!(0);
        assert!(build_legacy_snapshot(&auth, &status, &contradictory, &install).is_err());
        let (_, _, empty, _) = fixtures();
        let summary = savings_summary(&empty);
        assert_eq!(summary["monthTokens"], 0);
        assert_eq!(summary["eventCount"], 0);
        assert_eq!(summary["proofKind"], "unavailable");
    }

    #[test]
    fn unknown_or_undocumented_auth_states_are_never_subscription_decisions() {
        let (auth, status, savings, install) = fixtures();
        for state in [
            "unknown",
            "error",
            "unavailable",
            "",
            "ACTIVE",
            "active ",
            "revoked",
            "expired",
            "signed_out",
            "inactive",
            "denied",
        ] {
            for flag in [false, true] {
                let mut input = auth.clone();
                input["entitlement"]["status"] = json!(state);
                input["entitlement"]["active"] = json!(flag);
                let snapshot = build_legacy_snapshot(&input, &status, &savings, &install).unwrap();
                assert_eq!(snapshot["access"]["state"], "unknown");
                assert_eq!(snapshot["access"]["identityKnown"], true);
                assert_eq!(snapshot["access"]["entitlementKnown"], false);
            }
            let mut input = auth.clone();
            input["identity"]["status"] = json!(state);
            let snapshot = build_legacy_snapshot(&input, &status, &savings, &install).unwrap();
            assert_eq!(snapshot["access"]["state"], "unknown");
            assert_eq!(snapshot["access"]["identityKnown"], false);
            assert_eq!(snapshot["access"]["entitlementKnown"], false);
        }
    }

    #[test]
    fn contradictory_missing_or_malformed_auth_never_opens_active_access() {
        let (auth, status, savings, install) = fixtures();
        for key in ["identity", "entitlement"] {
            let mut input = auth.clone();
            input.as_object_mut().unwrap().remove(key);
            let snapshot = build_legacy_snapshot(&input, &status, &savings, &install).unwrap();
            assert_eq!(snapshot["access"]["state"], "unknown");
            assert_eq!(snapshot["access"]["entitlementKnown"], false);
        }
        for (pointer, replacement) in [
            ("/entitlement/active", json!(false)),
            ("/entitlement/active", json!("true")),
            ("/entitlement/active", Value::Null),
            ("/entitlement/status", Value::Null),
            ("/identity/status", Value::Null),
        ] {
            let mut input = auth.clone();
            *input.pointer_mut(pointer).unwrap() = replacement;
            let snapshot = build_legacy_snapshot(&input, &status, &savings, &install).unwrap();
            assert_eq!(snapshot["access"]["state"], "unknown");
            assert_eq!(snapshot["access"]["entitlementKnown"], false);
        }
        let mut input = auth.clone();
        input["error"] = json!({ "message": "test-only diagnostic sentinel" });
        let snapshot = build_legacy_snapshot(&input, &status, &savings, &install).unwrap();
        assert_eq!(snapshot["access"]["state"], "unknown");
        assert_eq!(snapshot["access"]["identityKnown"], false);
        assert_eq!(snapshot["access"]["entitlementKnown"], false);
        assert!(!snapshot
            .to_string()
            .contains("test-only diagnostic sentinel"));
        input["error"] = Value::Null;
        let snapshot = build_legacy_snapshot(&input, &status, &savings, &install).unwrap();
        assert_eq!(snapshot["access"]["state"], "active");
        assert_eq!(snapshot["access"]["identityKnown"], true);
        assert_eq!(snapshot["access"]["entitlementKnown"], true);
    }
}
