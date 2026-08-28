use serde_json::Value;
use std::ffi::OsString;
use std::path::PathBuf;
use std::process::{Command, Output};

const SNAPSHOT_SCHEMA: &str = "simplicio.desktop-snapshot/v1";
const MAX_SNAPSHOT_BYTES: usize = 65_536;
const SNAPSHOT_ARGS: &[&str] = &["desktop", "snapshot", "--json"];
const LOGIN_ARGS: &[&str] = &["desktop", "login"];
const SUBSCRIPTION_ARGS: &[&str] = &["desktop", "subscribe", "--json"];
const STATUS_ARGS: &[&str] = &["desktop", "status", "--json"];

fn runtime_candidates_with(
    override_binary: Option<OsString>,
    simplicio_home: Option<OsString>,
    user_home: Option<OsString>,
) -> Vec<OsString> {
    if let Some(binary) = override_binary {
        return vec![binary];
    }

    let install_root = simplicio_home
        .map(PathBuf::from)
        .or_else(|| user_home.map(|home| PathBuf::from(home).join(".simplicio")));
    let executable = if cfg!(windows) {
        "simplicio.exe"
    } else {
        "simplicio"
    };

    let mut candidates = Vec::with_capacity(2);
    if let Some(root) = install_root {
        candidates.push(root.join("bin").join(executable).into_os_string());
    }
    candidates.push(OsString::from(executable));
    candidates
}

fn runtime_candidates() -> Vec<OsString> {
    runtime_candidates_with(
        std::env::var_os("SIMPLICIO_RUNTIME_BIN"),
        std::env::var_os("SIMPLICIO_HOME"),
        std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")),
    )
}

fn run_runtime_output(args: &[&str]) -> Result<Output, String> {
    for binary in runtime_candidates() {
        match Command::new(binary)
            .args(args)
            .env("SIMPLICIO_DESKTOP_BRIDGE", "1")
            .output()
        {
            Ok(output) => return Ok(output),
            Err(_) => continue,
        }
    }

    Err("Simplicio Runtime não encontrado".to_string())
}

fn successful_output(args: &[&str]) -> Result<Output, String> {
    let output = run_runtime_output(args)?;

    if !output.status.success() {
        return Err(format!(
            "Simplicio Runtime encerrou com código {}",
            output.status.code().unwrap_or(-1)
        ));
    }

    Ok(output)
}

fn run_runtime_json(args: &[&str]) -> Result<Value, String> {
    let output = successful_output(args)?;
    serde_json::from_slice(&output.stdout)
        .map_err(|_| "Simplicio Runtime devolveu JSON inválido".to_string())
}

fn run_runtime_action(args: &[&str]) -> Result<(), String> {
    successful_output(args).map(|_| ())
}

fn validate_snapshot(value: Value) -> Result<Value, String> {
    let encoded = serde_json::to_vec(&value)
        .map_err(|_| "Contrato de snapshot do Runtime incompatível".to_string())?;
    let access_state = value.pointer("/access/state").and_then(Value::as_str);
    let runtime_state = value.pointer("/runtime/state").and_then(Value::as_str);
    let provider_cache_state = value
        .pointer("/savings/providerCache/status")
        .and_then(Value::as_str);
    let digest = value.get("snapshotDigest").and_then(Value::as_str);
    let digest_valid = digest.is_some_and(|candidate| {
        candidate.len() == 71
            && candidate.starts_with("sha256:")
            && candidate[7..].bytes().all(|byte| byte.is_ascii_hexdigit())
    });
    let valid = value.get("schema").and_then(Value::as_str) == Some(SNAPSHOT_SCHEMA)
        && value.get("source").and_then(Value::as_str) == Some("runtime")
        && matches!(
            access_state,
            Some("signed_out" | "inactive" | "active" | "unknown")
        )
        && matches!(
            runtime_state,
            Some("healthy" | "starting" | "degraded" | "offline")
        )
        && matches!(
            provider_cache_state,
            Some("hit" | "miss" | "mixed" | "unknown")
        )
        && value
            .get("providers")
            .and_then(Value::as_array)
            .is_some_and(|items| items.len() <= 32)
        && value
            .get("activity")
            .and_then(Value::as_array)
            .is_some_and(|items| items.len() <= 5)
        && value
            .pointer("/redaction/credentials")
            .and_then(Value::as_bool)
            == Some(true)
        && value.pointer("/redaction/prompts").and_then(Value::as_bool) == Some(true)
        && value
            .pointer("/runtime/optionalFast/required")
            .and_then(Value::as_bool)
            == Some(false)
        && value
            .pointer("/runtime/optionalFast/hookInjected")
            .and_then(Value::as_bool)
            == Some(false)
        && value
            .pointer("/savings/mapCache/fastInHooks")
            .and_then(Value::as_bool)
            == Some(false)
        && digest_valid
        && encoded.len() <= MAX_SNAPSHOT_BYTES;
    if valid {
        Ok(value)
    } else {
        Err("Contrato de snapshot do Runtime incompatível".to_string())
    }
}

fn snapshot_from_runtime() -> Result<Value, String> {
    validate_snapshot(run_runtime_json(SNAPSHOT_ARGS)?)
}

#[tauri::command]
async fn desktop_snapshot() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(snapshot_from_runtime)
        .await
        .map_err(|_| "Falha interna ao consultar o Runtime".to_string())?
}

#[tauri::command]
async fn refresh_desktop_snapshot() -> Result<Value, String> {
    desktop_snapshot().await
}

#[tauri::command]
async fn desktop_login() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        run_runtime_action(LOGIN_ARGS)?;
        snapshot_from_runtime()
    })
    .await
    .map_err(|_| "Falha interna durante o login".to_string())?
}

#[tauri::command]
async fn desktop_open_subscription() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(|| run_runtime_action(SUBSCRIPTION_ARGS))
        .await
        .map_err(|_| "Falha interna ao abrir os planos".to_string())?
}

#[tauri::command]
async fn runtime_status() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(|| run_runtime_json(STATUS_ARGS))
        .await
        .map_err(|_| "Falha interna ao consultar o status".to_string())?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            desktop_snapshot,
            refresh_desktop_snapshot,
            desktop_login,
            desktop_open_subscription,
            runtime_status
        ])
        .run(tauri::generate_context!())
        .expect("failed to run Simplicio Desktop");
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn valid_snapshot() -> Value {
        json!({
            "schema": SNAPSHOT_SCHEMA,
            "source": "runtime",
            "access": { "state": "active" },
            "runtime": {
                "state": "healthy",
                "optionalFast": { "required": false, "hookInjected": false }
            },
            "savings": {
                "providerCache": { "status": "unknown" },
                "mapCache": { "fastInHooks": false }
            },
            "providers": [],
            "activity": [],
            "redaction": { "credentials": true, "prompts": true },
            "snapshotDigest": format!("sha256:{}", "a".repeat(64))
        })
    }

    #[test]
    fn accepts_the_versioned_desktop_snapshot() {
        assert!(validate_snapshot(valid_snapshot()).is_ok());
    }

    #[test]
    fn rejects_an_unversioned_payload() {
        let error = validate_snapshot(json!({ "status": "healthy" })).unwrap_err();
        assert_eq!(error, "Contrato de snapshot do Runtime incompatível");
    }

    #[test]
    fn rejects_snapshot_that_could_inject_fast_or_expose_unredacted_state() {
        let mut snapshot = valid_snapshot();
        snapshot["runtime"]["optionalFast"]["hookInjected"] = json!(true);
        assert!(validate_snapshot(snapshot).is_err());

        let mut snapshot = valid_snapshot();
        snapshot["redaction"]["credentials"] = json!(false);
        assert!(validate_snapshot(snapshot).is_err());
    }

    #[test]
    fn bridge_exposes_only_fixed_runtime_arguments() {
        assert_eq!(SNAPSHOT_ARGS, ["desktop", "snapshot", "--json"]);
        assert_eq!(LOGIN_ARGS, ["desktop", "login"]);
        assert_eq!(SUBSCRIPTION_ARGS, ["desktop", "subscribe", "--json"]);
        assert_eq!(STATUS_ARGS, ["desktop", "status", "--json"]);
    }

    #[test]
    fn bridge_prefers_the_managed_runtime_and_honors_an_explicit_override() {
        let managed = runtime_candidates_with(
            None,
            Some(OsString::from("/managed/simplicio")),
            Some(OsString::from("/ignored/home")),
        );
        assert_eq!(
            managed,
            [
                PathBuf::from("/managed/simplicio")
                    .join("bin")
                    .join(if cfg!(windows) {
                        "simplicio.exe"
                    } else {
                        "simplicio"
                    })
                    .into_os_string(),
                OsString::from(if cfg!(windows) {
                    "simplicio.exe"
                } else {
                    "simplicio"
                }),
            ]
        );

        assert_eq!(
            runtime_candidates_with(
                Some(OsString::from("/explicit/runtime")),
                Some(OsString::from("/managed/simplicio")),
                None,
            ),
            [OsString::from("/explicit/runtime")]
        );
    }
}
