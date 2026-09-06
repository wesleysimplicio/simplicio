//! Provider quotas are independent from Runtime token ledgers.
use serde_json::{json, Value};
use std::{path::PathBuf, process::Command, sync::Mutex, time::{Duration, Instant, SystemTime, UNIX_EPOCH}};
static CACHE: Mutex<Option<(Instant, Value)>> = Mutex::new(None);

fn window(value: &Value) -> Option<Value> {
    let used = value.get("usedPercent")?.as_f64()?;
    let minutes = value.get("windowDurationMins")?.as_u64()?;
    let resets = value.get("resetsAt")?.as_u64()?;
    if !used.is_finite() || !(0.0..=100.0).contains(&used) || minutes == 0 { return None; }
    Some(json!({"usedPercent":used,"windowDurationMins":minutes,"resetsAt":resets}))
}
fn project(result: &Value) -> Vec<Value> {
    let mut groups = Vec::new();
    if let Some(by_id) = result.get("rateLimitsByLimitId").and_then(Value::as_object) {
        for (id, limits) in by_id.iter().take(16) { groups.push((id.as_str(), limits)); }
    }
    if groups.is_empty() {
        if let Some(limits) = result.get("rateLimits").filter(|v| v.is_object()) {
            groups.push(("codex", limits));
        }
    }
    groups.into_iter().map(|(id, limits)| json!({
        "id": id.chars().take(80).collect::<String>(),
        "windows": (["primary", "secondary"].iter().filter_map(|name| window(&limits[*name])).collect::<Vec<_>>())
    })).filter(|group| group["windows"].as_array().is_some_and(|v| !v.is_empty())).collect()
}
fn codex_path() -> Option<PathBuf> {
    let mut paths = Vec::new();
    if let Some(home) = std::env::var_os("HOME") {
        let home = PathBuf::from(home);
        paths.push(home.join(".local/bin/codex"));
        paths.push(home.join(".cargo/bin/codex"));
    }
    paths.extend([PathBuf::from("/opt/homebrew/bin/codex"), PathBuf::from("/usr/local/bin/codex")]);
    paths.into_iter().find(|p| p.is_file())
}
pub fn read() -> Value {
    let Ok(mut cache) = CACHE.try_lock() else { return json!({"schema":"simplicio.provider-quotas/v1","status":"busy","groups":[]}); };
    if let Some((time, value)) = cache.as_ref() {
        if time.elapsed() < Duration::from_secs(30) { return value.clone(); }
    }
    let observed = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
    let result = match codex_path() {
        Some(path) => crate::runtime_process::codex_account_limits(Command::new(path).arg("app-server")),
        None => Err("cli_unavailable"),
    };
    let mut response = match result {
        Ok(value) => { let groups = project(&value); json!({"schema":"simplicio.provider-quotas/v1","status":if groups.is_empty() {"unavailable"} else {"available"},"source":"codex_app_server","observedAt":observed,"groups":groups}) },
        Err(reason) => json!({"schema":"simplicio.provider-quotas/v1","status":"unavailable","source":"codex_app_server","observedAt":observed,"reason":reason,"groups":[]})
    };
    response["grok"] = crate::grok_quotas::read();
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
        assert!(window(&json!({"usedPercent":101,"windowDurationMins":10080,"resetsAt":1})).is_none());
        assert!(project(&json!({"rateLimits":null})).is_empty());
    }

    #[test]
    fn falls_back_to_legacy_limits_when_limit_id_map_is_empty() {
        let result = project(&json!({
            "rateLimitsByLimitId": {},
            "rateLimits": {
                "primary": {"usedPercent": 21, "windowDurationMins": 10080, "resetsAt": 1900000000}
            }
        }));
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["id"], "codex");
        assert_eq!(result[0]["windows"][0]["usedPercent"], 21.0);
    }
    #[test] fn preserves_quota_window_identity_and_omits_secrets() {
        let result = project(&json!({"rateLimits":{"primary":{"usedPercent":21,"windowDurationMins":10080,"resetsAt":1900000000},"token":"secret"}}));
        assert_eq!(result[0]["windows"][0]["usedPercent"],21.0);
        assert!(!serde_json::to_string(&result).unwrap().contains("secret"));
    }
}
