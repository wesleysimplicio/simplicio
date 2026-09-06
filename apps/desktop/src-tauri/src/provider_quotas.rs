//! Provider quotas are independent from Runtime token ledgers.
use serde_json::{json, Value};
use std::{path::PathBuf, process::Command, sync::Mutex, time::{Duration, Instant, SystemTime, UNIX_EPOCH}};

const SCHEMA: &str = "simplicio.provider-quotas/v2";
const MAX_STALE_SECS: u64 = 15 * 60;
const MAX_WINDOW_DURATION_MINS: u64 = 366 * 24 * 60;
const MAX_SAFE_EPOCH_SECS: u64 = 9_007_199_254_740_991;
const MAX_WINDOWS: usize = 32;
static CACHE: Mutex<Option<(Instant, Value)>> = Mutex::new(None);

fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|value| value.as_secs()).unwrap_or(0)
}

fn safe_reason(value: &str) -> &'static str {
    match value {
        "cli_unavailable" | "login_required" | "refresh_in_grok" | "request_failed"
        | "invalid_response" | "quota_unavailable" | "response_too_large" | "invalid_session"
        | "read_failed" | "busy" => match value {
            "cli_unavailable" => "cli_unavailable",
            "login_required" => "login_required",
            "refresh_in_grok" => "refresh_in_grok",
            "request_failed" => "request_failed",
            "invalid_response" => "invalid_response",
            "quota_unavailable" => "quota_unavailable",
            "response_too_large" => "response_too_large",
            "invalid_session" => "invalid_session",
            "read_failed" => "read_failed",
            _ => "busy",
        },
        _ => "quota_unavailable",
    }
}

fn window(value: &Value) -> Option<Value> {
    let used = value.get("usedPercent")?.as_f64()?;
    let minutes = value.get("windowDurationMins")?.as_u64()?;
    let resets = value.get("resetsAt")?.as_u64()?;
    if !used.is_finite() || !(0.0..=100.0).contains(&used)
        || minutes == 0 || minutes > MAX_WINDOW_DURATION_MINS
        || resets > MAX_SAFE_EPOCH_SECS { return None; }
    Some(json!({"usedPercent": used, "windowDurationMins": minutes, "resetsAt": resets}))
}

fn project(result: &Value) -> Vec<Value> {
    let mut groups = Vec::new();
    if let Some(by_id) = result.get("rateLimitsByLimitId").and_then(Value::as_object) {
        for (id, limits) in by_id.iter().take(16) { groups.push((id.as_str(), limits)); }
    }
    if groups.is_empty() {
        if let Some(limits) = result.get("rateLimits").filter(|value| value.is_object()) {
            groups.push(("codex", limits));
        }
    }
    groups.into_iter().map(|(id, limits)| json!({
        "id": id.chars().take(80).collect::<String>(),
        "windows": (["primary", "secondary"].iter().filter_map(|name| window(&limits[*name])).collect::<Vec<_>>())
    })).filter(|group| group["windows"].as_array().is_some_and(|value| !value.is_empty())).collect()
}

fn flatten_windows(groups: &[Value]) -> Vec<Value> {
    groups.iter()
        .filter_map(|group| group.get("windows").and_then(Value::as_array))
        .flat_map(|windows| windows.iter().cloned())
        .take(MAX_WINDOWS)
        .collect()
}

fn provider(id: &str, source: &str, account_scope: &str, observed_at: u64, status: &str, windows: Vec<Value>, reason: Option<&str>) -> Value {
    let mut value = json!({
        "id": id,
        "source": source,
        "observedAt": observed_at,
        "accountScope": account_scope,
        "redacted": true,
        "status": status,
        "windows": windows,
    });
    if let Some(reason) = reason { value["error"] = json!(safe_reason(reason)); }
    value
}

fn root_status(providers: &[Value]) -> &'static str {
    if providers.iter().any(|value| value["status"] == "fresh") { "available" }
    else if providers.iter().any(|value| value["status"] == "stale") { "stale" }
    else { "unavailable" }
}

fn mark_stale(value: &mut Value, now: u64) {
    let status = if let Some(providers) = value.get_mut("providers").and_then(Value::as_array_mut) {
        for provider in &mut *providers {
            let observed = provider.get("observedAt").and_then(Value::as_u64).unwrap_or(0);
            if provider["status"] == "fresh" && now.saturating_sub(observed) > MAX_STALE_SECS {
                provider["status"] = json!("stale");
                provider["error"] = json!("stale");
            }
        }
        root_status(providers)
    } else { return; };
    value["status"] = json!(status);
}

fn codex_path() -> Option<PathBuf> {
    let mut paths = Vec::new();
    if let Some(home) = std::env::var_os("HOME") {
        let home = PathBuf::from(home);
        paths.push(home.join(".local/bin/codex"));
        paths.push(home.join(".cargo/bin/codex"));
    }
    paths.extend([PathBuf::from("/opt/homebrew/bin/codex"), PathBuf::from("/usr/local/bin/codex")]);
    paths.into_iter().find(|path| path.is_file())
}

pub fn read() -> Value {
    let observed = now_secs();
    let Ok(mut cache) = CACHE.try_lock() else {
        return json!({"schema": SCHEMA, "status": "busy", "observedAt": observed, "providers": []});
    };
    if let Some((time, value)) = cache.as_ref() {
        if time.elapsed() < Duration::from_secs(30) {
            let mut cached = value.clone();
            mark_stale(&mut cached, observed);
            return cached;
        }
    }
    let codex = match codex_path() {
        Some(path) => match crate::runtime_process::codex_account_limits(Command::new(path).arg("app-server")) {
            Ok(value) => {
                let groups = project(&value);
                let windows = flatten_windows(&groups);
                let status = if windows.is_empty() { "unavailable" } else { "fresh" };
                let reason = if windows.is_empty() { Some("quota_unavailable") } else { None };
                provider("codex", "codex_app_server", "local_authenticated_account", observed,
                    status, windows, reason)
            }
            Err(reason) => provider("codex", "codex_app_server", "local_authenticated_account", observed, "unavailable", vec![], Some(reason)),
        },
        None => provider("codex", "codex_app_server", "local_authenticated_account", observed, "unavailable", vec![], Some("cli_unavailable")),
    };
    let grok = crate::grok_quotas::read(observed);
    let providers = vec![codex, grok];
    let response = json!({"schema": SCHEMA, "status": root_status(&providers), "observedAt": observed, "providers": providers});
    *cache = Some((Instant::now(), response.clone()));
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rpc_initializes_then_reads_limits_without_starting_a_turn() {
        let script = r#"import json,sys,time
request=json.loads(sys.stdin.readline())
assert request['method']=='initialize'
print(json.dumps({'id':1,'result':{}}),flush=True)
assert json.loads(sys.stdin.readline())['method']=='initialized'
request=json.loads(sys.stdin.readline())
assert request['method']=='account/rateLimits/read'
print(json.dumps({'id':2,'result':{'rateLimits':{'primary':{'usedPercent':21,'windowDurationMins':10080,'resetsAt':1900000000}}}}),flush=True)
time.sleep(10)
"#;
        let value = crate::runtime_process::codex_account_limits(Command::new("python3").arg("-c").arg(script)).unwrap();
        assert_eq!(project(&value)[0]["windows"][0]["usedPercent"], 21.0);
    }
    #[test] fn invalid_windows_are_not_zero_usage() {
        assert!(window(&json!({"usedPercent": 101, "windowDurationMins": 10080, "resetsAt": 1})).is_none());
        assert!(project(&json!({"rateLimits": null})).is_empty());
    }
    #[test]
    fn rejects_unbounded_window_fields() {
        assert!(window(&json!({"usedPercent": 21, "windowDurationMins": MAX_WINDOW_DURATION_MINS + 1, "resetsAt": 1900000000})).is_none());
        assert!(window(&json!({"usedPercent": 21, "windowDurationMins": 10080, "resetsAt": MAX_SAFE_EPOCH_SECS + 1})).is_none());
    }
    #[test]
    fn falls_back_to_legacy_limits_when_limit_id_map_is_empty() {
        let result = project(&json!({"rateLimitsByLimitId": {}, "rateLimits": {"primary": {"usedPercent": 21, "windowDurationMins": 10080, "resetsAt": 1900000000}}}));
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["id"], "codex");
        assert_eq!(result[0]["windows"][0]["usedPercent"], 21.0);
    }
    #[test]
    fn contract_has_source_scope_timestamp_and_redaction_without_secrets() {
        let groups = project(&json!({"rateLimits": {"primary": {"usedPercent": 21, "windowDurationMins": 10080, "resetsAt": 1900000000}, "token": "secret"}}));
        let value = provider("codex", "codex_app_server", "local_authenticated_account", 1900000000, "fresh", flatten_windows(&groups), None);
        assert_eq!(value["source"], "codex_app_server");
        assert_eq!(value["accountScope"], "local_authenticated_account");
        assert_eq!(value["observedAt"], 1900000000);
        assert_eq!(value["redacted"], true);
        assert_eq!(value["windows"][0]["usedPercent"], 21.0);
        assert!(!value.to_string().contains("secret"));
    }
    #[test]
    fn stale_cache_is_not_presented_as_fresh() {
        let mut value = json!({"providers": [provider("codex", "codex_app_server", "local_authenticated_account", 1, "fresh", vec![json!({"usedPercent": 21, "windowDurationMins": 10080, "resetsAt": 1900000000})], None)]});
        mark_stale(&mut value, MAX_STALE_SECS + 2);
        assert_eq!(value["providers"][0]["status"], "stale");
        assert_eq!(value["providers"][0]["error"], "stale");
    }
    #[test]
    fn root_status_preserves_fresh_stale_and_unavailable_states() {
        assert_eq!(root_status(&[provider("codex", "codex_app_server", "local_authenticated_account", 1, "fresh", vec![json!({"usedPercent": 1, "windowDurationMins": 10080, "resetsAt": 1900000000})], None)]), "available");
        assert_eq!(root_status(&[provider("codex", "codex_app_server", "local_authenticated_account", 1, "stale", vec![json!({"usedPercent": 1, "windowDurationMins": 10080, "resetsAt": 1900000000})], Some("stale"))]), "stale");
        assert_eq!(root_status(&[provider("codex", "codex_app_server", "local_authenticated_account", 1, "unavailable", vec![], Some("login_required"))]), "unavailable");
    }
}
