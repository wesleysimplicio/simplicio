use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;
use std::process::Command;

const CONNECTION_LOG: &str = ".simplicio/mcp/connections.jsonl";
const MAX_CONNECTION_BYTES: u64 = 1_048_576;
const MAX_EVENT_BYTES: usize = 65_536;
const STATUS_SCHEMA: &str = "simplicio.mcp-connection/v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SessionState {
    Live,
    Stale,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Observation {
    connected_at: i64,
    state: SessionState,
}

fn provider_id(client_name: &str) -> Option<&'static str> {
    let normalized = client_name
        .chars()
        .filter(|character| character.is_ascii_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect::<String>();
    if normalized.contains("antigravity") {
        Some("antigravity")
    } else if normalized.contains("opencode") {
        Some("opencode")
    } else if normalized.contains("codex") {
        Some("codex")
    } else if normalized.contains("claude") {
        Some("claude-code")
    } else if normalized.contains("grok") {
        Some("grok")
    } else if normalized.contains("hermes") {
        Some("hermes")
    } else if normalized.contains("gemini") {
        Some("gemini")
    } else if normalized.contains("vscode") || normalized.contains("visualstudiocode") {
        Some("vscode")
    } else if normalized.contains("cline") {
        Some("cline")
    } else if normalized.contains("cursor") {
        Some("cursor")
    } else if normalized.contains("windsurf") {
        Some("windsurf")
    } else if normalized.contains("kiro") {
        Some("kiro")
    } else if normalized.contains("zed") {
        Some("zed")
    } else if normalized.contains("jetbrains") {
        Some("jetbrains")
    } else if normalized.contains("orca") {
        Some("orca")
    } else {
        None
    }
}

fn read_tail(path: &Path) -> Option<String> {
    let mut file = File::open(path).ok()?;
    let length = file.metadata().ok()?.len();
    let start = length.saturating_sub(MAX_CONNECTION_BYTES);
    file.seek(SeekFrom::Start(start)).ok()?;
    let mut bytes = Vec::with_capacity((length - start).min(MAX_CONNECTION_BYTES) as usize);
    file.take(MAX_CONNECTION_BYTES).read_to_end(&mut bytes).ok()?;
    if start > 0 {
        let boundary = bytes.iter().position(|byte| *byte == b'\n')?;
        bytes.drain(..=boundary);
    }
    String::from_utf8(bytes).ok()
}

#[cfg(unix)]
fn process_alive(pid: u32) -> bool {
    Command::new("/bin/kill")
        .args(["-0", &pid.to_string()])
        .status()
        .is_ok_and(|status| status.success())
}

#[cfg(windows)]
fn process_alive(pid: u32) -> bool {
    let filter = format!("PID eq {pid}");
    Command::new("tasklist")
        .args(["/FI", &filter, "/FO", "CSV", "/NH"])
        .output()
        .ok()
        .filter(|output| output.status.success())
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .is_some_and(|output| !output.contains("No tasks") && output.contains(&pid.to_string()))
}

#[cfg(not(any(unix, windows)))]
fn process_alive(_: u32) -> bool {
    false
}

fn observations_with(raw: &str, alive: impl Fn(u32) -> bool) -> BTreeMap<String, Observation> {
    let mut observations = BTreeMap::<String, Observation>::new();
    for line in raw.lines() {
        if line.len() > MAX_EVENT_BYTES {
            continue;
        }
        let Ok(event) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        if event.get("schema").and_then(Value::as_str) != Some(STATUS_SCHEMA)
            || event.get("event").and_then(Value::as_str) != Some("initialize")
        {
            continue;
        }
        let Some(pid) = event
            .get("pid")
            .and_then(Value::as_u64)
            .and_then(|value| u32::try_from(value).ok())
        else {
            continue;
        };
        let Some(provider) = event
            .pointer("/client/name")
            .and_then(Value::as_str)
            .and_then(provider_id)
        else {
            continue;
        };
        let connected_at = event.get("timestamp").and_then(Value::as_i64).unwrap_or(0);
        if connected_at <= 0 {
            continue;
        }
        let candidate = Observation {
            connected_at,
            state: if alive(pid) {
                SessionState::Live
            } else {
                SessionState::Stale
            },
        };
        let should_replace = observations.get(provider).is_none_or(|current| {
            (candidate.state == SessionState::Live && current.state == SessionState::Stale)
                || (candidate.state == current.state
                    && candidate.connected_at > current.connected_at)
        });
        if should_replace {
            observations.insert(provider.to_string(), candidate);
        }
    }
    observations
}

fn recompute_digest(snapshot: &mut Value) -> Result<(), String> {
    snapshot
        .as_object_mut()
        .ok_or_else(|| "desktop_connection_projection_invalid".to_string())?
        .remove("snapshotDigest");
    let encoded = serde_json::to_vec(snapshot)
        .map_err(|_| "desktop_connection_projection_invalid".to_string())?;
    let digest = format!("sha256:{:x}", Sha256::digest(encoded));
    snapshot["snapshotDigest"] = Value::String(digest);
    Ok(())
}

fn apply_observations(
    mut snapshot: Value,
    observations: &BTreeMap<String, Observation>,
) -> Result<Value, String> {
    let providers = snapshot
        .get_mut("providers")
        .and_then(Value::as_array_mut)
        .ok_or_else(|| "desktop_connection_projection_invalid".to_string())?;
    for provider in providers {
        let Some(id) = provider.get("id").and_then(Value::as_str) else {
            continue;
        };
        let Some(observation) = observations.get(id) else {
            continue;
        };
        match observation.state {
            SessionState::Live => {
                provider["state"] = Value::String("connected".into());
                provider["detail"] = Value::String("Sessão MCP ativa".into());
                provider["handshakeState"] = Value::String("live".into());
                provider["freshness"] = Value::String("current".into());
                provider["reasonCode"] =
                    Value::String("mcp_initialize_process_alive".into());
            }
            SessionState::Stale => {
                if provider.get("handshakeState").and_then(Value::as_str) != Some("live") {
                    provider["handshakeState"] = Value::String("stale".into());
                    provider["reasonCode"] =
                        Value::String("mcp_initialize_process_ended".into());
                }
            }
        }
    }
    recompute_digest(&mut snapshot)?;
    Ok(snapshot)
}

pub fn enrich(snapshot: Value, home: &Path) -> Result<Value, String> {
    let path = home.join(CONNECTION_LOG);
    let observations = read_tail(&path)
        .map(|raw| observations_with(&raw, process_alive))
        .unwrap_or_default();
    apply_observations(snapshot, &observations)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn snapshot() -> Value {
        json!({
            "providers": [
                {
                    "id": "codex",
                    "state": "registered",
                    "detail": "Registro encontrado, sessão não confirmada",
                    "handshakeState": "unverified",
                    "freshness": "current",
                    "reasonCode": "handshake_not_observed"
                },
                {
                    "id": "opencode",
                    "state": "detected",
                    "detail": "Cliente encontrado",
                    "handshakeState": "unverified",
                    "freshness": "current",
                    "reasonCode": "handshake_not_observed"
                }
            ],
            "snapshotDigest": format!("sha256:{}", "a".repeat(64))
        })
    }

    fn event(pid: u32, client: &str, timestamp: i64) -> String {
        json!({
            "schema": STATUS_SCHEMA,
            "event": "initialize",
            "pid": pid,
            "client": { "name": client, "version": "1" },
            "timestamp": timestamp
        })
        .to_string()
    }

    #[test]
    fn maps_supported_mcp_client_names_without_guessing_unknown_clients() {
        assert_eq!(provider_id("codex-mcp-client"), Some("codex"));
        assert_eq!(provider_id("OpenCode"), Some("opencode"));
        assert_eq!(provider_id("Visual Studio Code"), Some("vscode"));
        assert_eq!(provider_id("Cline"), Some("cline"));
        assert_eq!(provider_id("Grok Build"), Some("grok"));
        assert_eq!(provider_id("unrelated-client"), None);
    }

    #[test]
    fn live_session_wins_over_a_newer_stale_process_for_the_same_provider() {
        let raw = [event(10, "codex-mcp-client", 100), event(20, "Codex", 200)].join("\n");
        let observations = observations_with(&raw, |pid| pid == 10);
        assert_eq!(
            observations.get("codex"),
            Some(&Observation {
                connected_at: 100,
                state: SessionState::Live
            })
        );
    }

    #[test]
    fn overlays_only_observed_provider_state_and_rebinds_the_digest() {
        let raw = [event(10, "codex-mcp-client", 100), event(20, "OpenCode", 200)].join("\n");
        let observations = observations_with(&raw, |pid| pid == 10);
        let original_digest = snapshot()["snapshotDigest"].clone();
        let enriched = apply_observations(snapshot(), &observations).unwrap();
        assert_eq!(enriched["providers"][0]["state"], "connected");
        assert_eq!(enriched["providers"][0]["handshakeState"], "live");
        assert_eq!(
            enriched["providers"][0]["reasonCode"],
            "mcp_initialize_process_alive"
        );
        assert_eq!(enriched["providers"][1]["state"], "detected");
        assert_eq!(enriched["providers"][1]["handshakeState"], "stale");
        assert_ne!(enriched["snapshotDigest"], original_digest);
        assert!(enriched["snapshotDigest"]
            .as_str()
            .is_some_and(|digest| digest.starts_with("sha256:") && digest.len() == 71));
    }

    #[test]
    fn ignores_malformed_oversized_and_non_initialize_events() {
        let oversized = "x".repeat(MAX_EVENT_BYTES + 1);
        let raw = format!(
            "{}\n{}\n{}\n{}",
            "not-json",
            oversized,
            json!({"schema": STATUS_SCHEMA, "event": "tool_call", "pid": 1}),
            json!({"schema": "other", "event": "initialize", "pid": 1})
        );
        assert!(observations_with(&raw, |_| true).is_empty());
    }
}
