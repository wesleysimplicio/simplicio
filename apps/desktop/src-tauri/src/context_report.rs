//! Allowlisted context-savings projection. The Runtime, not the Desktop, reads the ledger.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
const INVALID: &str = "context_report_invalid";

pub fn query_args(repo_path: Option<&str>, default_repo: &Path) -> Result<Vec<String>, String> {
    let input = repo_path.unwrap_or(default_repo.to_str().ok_or("context_query_invalid")?);
    let project =
        crate::local_projects::validate_project(input).map_err(|_| "context_query_invalid")?;
    let path = project["path"].as_str().ok_or("context_query_invalid")?;
    let repo = PathBuf::from(path);
    let ledger = repo.join(".simplicio/ledger/savings-events.jsonl");
    // A read must not initialize a ledger or follow a ledger symlink outside the selected folder.
    let resolved = ledger
        .canonicalize()
        .map_err(|_| "context_ledger_unavailable")?;
    if !resolved.is_file() || !resolved.starts_with(&repo) {
        return Err("context_ledger_unavailable".into());
    }
    Ok(vec![
        "savings".into(),
        "report".into(),
        "--repo".into(),
        path.into(),
        "--json".into(),
    ])
}

fn count(value: &Value) -> Result<u64, String> {
    value
        .as_u64()
        .filter(|n| *n <= MAX_SAFE_INTEGER)
        .ok_or_else(|| INVALID.into())
}

pub fn project(value: Value) -> Result<Value, String> {
    if value["schema"] != "simplicio.savings-report/v1" {
        return Err(INVALID.into());
    }
    if value["ledger"]["status"] != "valid"
        || value["ledger"]["hash_chain_valid"] != true
        || value["ledger"]["promotable"] != true
        || value["ledger"]["corrupt_lines"] != 0
    {
        return Err("context_ledger_invalid".into());
    }
    let ledger_events = count(&value["ledger"]["total_events"])?;
    if ledger_events == 0 {
        return Err("context_ledger_empty".into());
    }
    let context_events = count(&value["runtime_saved_total"]["events"])?;
    let spend_events = count(&value["llm_spend_total"]["events"])?;
    if context_events.checked_add(spend_events) != Some(ledger_events) {
        return Err(INVALID.into());
    }
    let saved = count(&value["runtime_saved_total"]["saved_tokens"])?;
    if context_events == 0 && saved != 0 {
        return Err(INVALID.into());
    }
    // Runtime's all-event totals also include llm_spend. They cannot be presented as a
    // context-only before/after comparison when those events are mixed into this ledger.
    let comparison = if spend_events == 0 {
        let baseline = count(&value["without_simplicio"]["paid_tokens"])?;
        let actual = count(&value["with_simplicio"]["paid_tokens"])?;
        Some((baseline, actual, baseline as i64 - actual as i64))
    } else {
        None
    };

    let mut proof = json!({"measured":0,"estimated":0,"replayed":0,"benchmark":0,"unavailable":0});
    let breakdown = value["proof_breakdown"].as_object().ok_or(INVALID)?;
    if breakdown.len() > 32 {
        return Err(INVALID.into());
    }
    let mut proof_count = 0_u64;
    for (kind, raw_count) in breakdown {
        let amount = count(raw_count)?;
        proof_count = proof_count
            .checked_add(amount)
            .filter(|n| *n <= ledger_events)
            .ok_or(INVALID)?;
        let key = match kind.as_str() {
            "measured" => "measured",
            "estimated" => "estimated",
            "replayed" => "replayed",
            "benchmark" | "benchmark-fixture" => "benchmark",
            _ => "unavailable",
        };
        proof[key] = json!(proof[key].as_u64().unwrap_or(0) + amount);
    }
    if proof_count != ledger_events {
        return Err(INVALID.into());
    }
    let tokenizers = value["tokenizer_policy"]["by_tokenizer_id"]
        .as_object()
        .ok_or(INVALID)?;
    if tokenizers.len() > 256 {
        return Err(INVALID.into());
    }
    let mut labeled = 0_u64;
    let mut heuristic = 0_u64;
    for (id, raw_count) in tokenizers {
        let amount = count(raw_count)?;
        labeled = labeled
            .checked_add(amount)
            .filter(|n| *n <= ledger_events)
            .ok_or(INVALID)?;
        if id.starts_with("heuristic:") {
            heuristic += amount;
        }
    }
    let unlabeled = count(&value["tokenizer_policy"]["unlabeled_estimated_events_flagged"])?;
    if labeled.checked_add(unlabeled) != Some(ledger_events) {
        return Err(INVALID.into());
    }
    let baseline_kind = match value["baseline_kind"].as_str() {
        Some(kind @ ("measured" | "estimated" | "replayed" | "benchmark" | "mixed")) => kind,
        Some("benchmark-fixture") => "benchmark",
        _ => "unavailable",
    };
    let confidence = match value["confidence"].as_str() {
        Some(level @ ("low" | "medium" | "high" | "measured")) => level,
        _ => "unavailable",
    };
    let mut report = json!({
        "schema":"simplicio.desktop-context-report/v1", "source":"runtime", "scope":"project_history",
        "eventCount":context_events, "ledgerEventCount":ledger_events, "llmSpendEventCount":spend_events,
        "savedTokens":saved,
        "baselineTokens":comparison.map(|v|v.0), "actualTokens":comparison.map(|v|v.1),
        "netTokens":comparison.map(|v|v.2),
        "baselineKind":baseline_kind, "confidence":confidence,
        "heuristicEventCount":heuristic, "unlabeledEstimateCount":unlabeled, "proof":proof,
    });
    let bytes = serde_json::to_vec(&report).map_err(|_| INVALID)?;
    report["reportHash"] = json!(format!("sha256:{:x}", Sha256::digest(bytes)));
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> Value {
        json!({
            "schema":"simplicio.savings-report/v1",
            "ledger":{"status":"valid","hash_chain_valid":true,"promotable":true,"corrupt_lines":0,"total_events":12},
            "runtime_saved_total":{"events":12,"saved_tokens":350}, "llm_spend_total":{"events":0},
            "without_simplicio":{"paid_tokens":1000}, "with_simplicio":{"paid_tokens":650},
            "baseline_kind":"mixed", "confidence":"low", "proof_breakdown":{"measured":9,"estimated":3},
            "tokenizer_policy":{"by_tokenizer_id":{"heuristic:chars-div-4":10,"n/a-not-required":1},"unlabeled_estimated_events_flagged":1},
            "records":[{"prompt":"private prompt","user":"private identity"}], "cost_totals":{"saved":999},
            "source_artifacts":["/private/ledger"]
        })
    }

    #[test]
    fn projects_only_bounded_metrics_without_records_costs_or_paths() {
        let report = project(fixture()).unwrap();
        assert_eq!(report["savedTokens"], 350);
        assert_eq!(report["netTokens"], 350);
        assert_eq!(report["heuristicEventCount"], 10);
        assert_eq!(report["unlabeledEstimateCount"], 1);
        let body = report.to_string();
        for private in [
            "private prompt",
            "private identity",
            "/private/ledger",
            "cost_totals",
            "records",
        ] {
            assert!(!body.contains(private));
        }
        let mut changed_private = fixture();
        changed_private["records"] = json!(["different private content"]);
        assert_eq!(
            report["reportHash"],
            project(changed_private).unwrap()["reportHash"]
        );
    }

    #[test]
    fn mixed_llm_spend_never_masquerades_as_context_comparison() {
        let mut input = fixture();
        input["runtime_saved_total"]["events"] = json!(10);
        input["llm_spend_total"]["events"] = json!(2);
        let report = project(input).unwrap();
        assert_eq!(report["eventCount"], 10);
        assert_eq!(report["savedTokens"], 350);
        assert!(report["baselineTokens"].is_null());
        assert!(report["actualTokens"].is_null());
        assert!(report["netTokens"].is_null());
    }

    #[test]
    fn negative_net_is_not_clamped_to_a_positive_savings_claim() {
        let mut input = fixture();
        input["with_simplicio"]["paid_tokens"] = json!(1100);
        let report = project(input).unwrap();
        assert_eq!(report["netTokens"], -100);
        assert_eq!(report["savedTokens"], 350); // Runtime's gross sum is distinct from the net comparison.
    }

    #[test]
    fn rejects_invalid_ledger_unsafe_numbers_and_inconsistent_counts() {
        for (pointer, replacement) in [
            ("/ledger/hash_chain_valid", json!(false)),
            ("/ledger/corrupt_lines", json!(1)),
            (
                "/runtime_saved_total/saved_tokens",
                json!(MAX_SAFE_INTEGER + 1),
            ),
            ("/runtime_saved_total/events", json!(13)),
            ("/proof_breakdown/estimated", json!(4)),
            (
                "/tokenizer_policy/by_tokenizer_id/heuristic:chars-div-4",
                json!(12),
            ),
        ] {
            let mut input = fixture();
            *input.pointer_mut(pointer).unwrap() = replacement;
            assert!(project(input).is_err(), "accepted {pointer}");
        }
    }

    #[test]
    fn query_requires_existing_ledger_and_uses_fixed_arguments() {
        let suffix = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let repo = std::env::temp_dir().join(format!("simplicio-context-{suffix}"));
        std::fs::create_dir_all(&repo).unwrap();
        assert_eq!(
            query_args(None, &repo).unwrap_err(),
            "context_ledger_unavailable"
        );
        assert!(!repo.join(".simplicio").exists());
        let ledger = repo.join(".simplicio/ledger/savings-events.jsonl");
        std::fs::create_dir_all(ledger.parent().unwrap()).unwrap();
        std::fs::write(&ledger, b"test fixture only").unwrap();
        let args = query_args(None, &repo).unwrap();
        assert_eq!(&args[..3], ["savings", "report", "--repo"]);
        assert_eq!(args[4], "--json");
        assert_eq!(
            PathBuf::from(&args[3]).canonicalize().unwrap(),
            repo.canonicalize().unwrap()
        );
        assert_eq!(
            query_args(Some("--unsafe"), &repo).unwrap_err(),
            "context_query_invalid"
        );
        std::fs::remove_dir_all(&repo).unwrap();
    }
}
