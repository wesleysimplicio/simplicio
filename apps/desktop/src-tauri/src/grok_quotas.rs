//! Read-only Grok CLI billing. Credentials never leave this module or enter argv.
use serde_json::{json, Value};
use std::{fs::File, io::Read, path::PathBuf, time::Duration};

const MAX_BYTES: u64 = 262144;
const ENDPOINT: &str = "https://cli-chat-proxy.grok.com/v1/billing";
fn timestamp(value: &Value) -> Option<i64> {
    chrono::DateTime::parse_from_rfc3339(value.as_str()?).ok().map(|d| d.timestamp())
}
fn session<'a>(value: &'a Value, now: i64) -> Result<&'a Value, &'static str> {
    let entries = value.as_object().ok_or("invalid_session")?;
    let mut expired = false;
    for (issuer, entry) in entries {
        // Never send a token from an alternate issuer to xAI.
        if issuer != "https://auth.x.ai" && !issuer.starts_with("https://auth.x.ai::") { continue; }
        let Some(key) = entry["key"].as_str().filter(|s| !s.is_empty()) else { continue; };
        if key.len() > 16384 || key.chars().any(char::is_control) { return Err("invalid_session"); }
        if !entry["expires_at"].is_null() {
            let expiry = timestamp(&entry["expires_at"]).ok_or("invalid_session")?;
            if expiry <= now.saturating_add(300) { expired = true; continue; }
        }
        return Ok(entry);
    }
    Err(if expired { "refresh_in_grok" } else { "login_required" })
}
fn number(value: &Value) -> Option<f64> {
    value.as_f64().or_else(|| value.as_str()?.parse().ok()).filter(|n| n.is_finite())
}
fn project(value: &Value) -> Option<Value> {
    // Grok exposes the billing config either at the response root or under
    // \`config\`; accept both shapes without copying any unbounded payload.
    let config = value
        .get("config")
        .filter(|candidate| candidate.is_object())
        .unwrap_or(value);
    let period = config
        .get("currentPeriod")
        .filter(|candidate| candidate.is_object());
    let end = period
        .and_then(|period| timestamp(&period["end"]))
        .or_else(|| timestamp(&config["billingPeriodEnd"]))?;
    let start = period
        .and_then(|period| timestamp(&period["start"]))
        .or_else(|| timestamp(&config["billingPeriodStart"]))?;
    let seconds = end.checked_sub(start)?;
    if !(60..=366 * 24 * 60 * 60).contains(&seconds) || end < 0 {
        return None;
    }
    let percent = number(&config["creditUsagePercent"]).or_else(|| {
        let limit = number(&config["monthlyLimit"]["val"])?;
        let used = number(&config["used"]["val"])?;
        if limit <= 0.0 || used < 0.0 {
            return None;
        }
        Some(used / limit * 100.0)
    })?;
    if !percent.is_finite() || !(0.0..=100.0).contains(&percent) {
        return None;
    }
    Some(json!({"usedPercent":percent,"windowDurationMins":seconds / 60,"resetsAt":end}))
}
fn read_bounded(reader: impl Read) -> Result<Vec<u8>, &'static str> {
    let mut bytes = Vec::new();
    reader.take(MAX_BYTES + 1).read_to_end(&mut bytes).map_err(|_| "read_failed")?;
    if bytes.len() as u64 > MAX_BYTES { return Err("response_too_large"); }
    Ok(bytes)
}
fn query() -> Result<Value, &'static str> {
    let home = std::env::var_os("GROK_HOME").filter(|s| !s.is_empty()).map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".grok")))
        .ok_or("login_required")?;
    let file = File::open(home.join("auth.json")).map_err(|e| if e.kind() == std::io::ErrorKind::NotFound { "login_required" } else { "read_failed" })?;
    if !file.metadata().map_err(|_| "read_failed")?.is_file() { return Err("invalid_session"); }
    let auth: Value = serde_json::from_slice(&read_bounded(file)?).map_err(|_| "invalid_session")?;
    let entry = session(&auth, chrono::Utc::now().timestamp())?;
    // Fixed origin, no redirects, no renderer-controlled URL or credential.
    let client = reqwest::blocking::Client::builder().timeout(Duration::from_secs(10))
        .redirect(reqwest::redirect::Policy::none()).build().map_err(|_| "request_failed")?;
    for suffix in ["?format=credits", ""] {
        let mut request = client.get(format!("{ENDPOINT}{suffix}"))
            .bearer_auth(entry["key"].as_str().ok_or("invalid_session")?)
            .header("X-XAI-Token-Auth", "xai-grok-cli").header("Accept", "application/json");
        if let Some(id) = entry["user_id"].as_str() { request = request.header("x-userid", id); }
        let response = request.send().map_err(|_| "request_failed")?;
        if matches!(response.status().as_u16(), 401 | 403) { return Err("refresh_in_grok"); }
        if !response.status().is_success() { return Err("request_failed"); }
        let body: Value = serde_json::from_slice(&read_bounded(response)?).map_err(|_| "invalid_response")?;
        if let Some(window) = project(&body) { return Ok(window); }
    }
    Err("quota_unavailable")
}
pub fn read() -> Value {
    match query() {
        Ok(window) => json!({"status":"available","source":"grok_cli_billing","windows":[window]}),
        Err(reason) => json!({"status":"unavailable","source":"grok_cli_billing","reason":reason,"windows":[]}),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore = "explicit local acceptance: reads the signed-in Grok CLI session and calls billing"]
    fn local_billing_observation() {
        let observation = read();
        assert_eq!(observation["source"], "grok_cli_billing");
        println!("{observation}");
    }
    #[test] fn expired_and_alternate_sessions_are_not_used() {
        assert_eq!(session(&json!({"other":{"key":"secret"}}), 0).unwrap_err(), "login_required");
        assert_eq!(session(&json!({"https://auth.x.ai":{"key":"secret","expires_at":"2020-01-01T00:00:00Z"}}), 1900000000).unwrap_err(), "refresh_in_grok");
    }
    #[test] fn missing_usage_is_unknown_not_zero() {
        assert!(project(&json!({"config":{"currentPeriod":{"start":"2026-09-01T00:00:00Z","end":"2026-09-08T00:00:00Z"}}})).is_none());
    }
    #[test] fn projects_only_bounded_numeric_quota() {
        let value = json!({"secret":"hidden","config":{"creditUsagePercent":21,"currentPeriod":{"start":"2026-09-01T00:00:00Z","end":"2026-09-08T00:00:00Z"}}});
        let projected = project(&value).unwrap();
        assert_eq!(projected["windowDurationMins"], 10080);
        assert_eq!(projected["usedPercent"], 21.0);
        assert!(!projected.to_string().contains("hidden"));
    }

    #[test]
    fn accepts_top_level_monthly_billing_shape_without_exposing_payload() {
        let value = json!({
            "creditUsagePercent": null,
            "monthlyLimit": {"val": "100"},
            "used": {"val": "21"},
            "billingPeriodStart": "2026-09-01T00:00:00Z",
            "billingPeriodEnd": "2026-10-01T00:00:00Z",
            "private_token": "must-not-leak"
        });
        let projected = project(&value).unwrap();
        assert_eq!(projected["usedPercent"], 21.0);
        assert_eq!(projected["windowDurationMins"], 43_200);
        assert!(!projected.to_string().contains("must-not-leak"));
    }

    #[test]
    fn rejects_unbounded_billing_periods() {
        let value = json!({
            "config": {
                "creditUsagePercent": 21,
                "currentPeriod": {
                    "start": "2020-01-01T00:00:00Z",
                    "end": "2026-09-08T00:00:00Z"
                }
            }
        });
        assert!(project(&value).is_none());
    }
    #[test] fn response_cap_is_enforced() {
        assert_eq!(read_bounded(vec![0; MAX_BYTES as usize + 1].as_slice()).unwrap_err(), "response_too_large");
    }
}
