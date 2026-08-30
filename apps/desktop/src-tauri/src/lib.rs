use serde_json::Value;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

mod legacy_snapshot;
mod supervisor;

const SNAPSHOT_SCHEMA: &str = "simplicio.desktop-snapshot/v1";
const MAX_SNAPSHOT_BYTES: usize = 65_536;
const SNAPSHOT_ARGS: &[&str] = &["desktop", "snapshot", "--json"];
const LOGIN_ARGS: &[&str] = &["login", "google", "--json"];
const LOGOUT_ARGS: &[&str] = &["logout", "--json"];
const SUBSCRIPTION_ARGS: &[&str] = &["desktop", "subscribe", "--json"];
const STATUS_ARGS: &[&str] = &["desktop", "status", "--json"];
const LEGACY_AUTH_ARGS: &[&str] = &["auth", "status", "--json"];
const LEGACY_STATUS_ARGS: &[&str] = &["status", "--json"];
const LEGACY_SAVINGS_ARGS: &[&str] = &["savings", "report", "--json"];
const LEGACY_INSTALL_ARGS: &[&str] = &["install", "--global", "--dry-run", "--json"];
const INSTALL_ARGS: &[&str] = &["install", "--global", "--json"];
const SUBSCRIPTION_URL: &str = "https://simpleti.com.br/simplicio";

fn runtime_candidates_with(
    override_binary: Option<OsString>,
    simplicio_home: Option<OsString>,
    user_home: Option<OsString>,
    current_executable: Option<OsString>,
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

    let mut candidates = Vec::with_capacity(3);
    if let Some(parent) = current_executable
        .map(PathBuf::from)
        .and_then(|path| path.parent().map(Path::to_path_buf))
    {
        candidates.push(parent.join(executable).into_os_string());
    }
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
        std::env::current_exe().ok().map(PathBuf::into_os_string),
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

fn repair_provider_integrations() -> Result<(), String> {
    run_runtime_action(INSTALL_ARGS)
        .map_err(|_| "O Runtime não conseguiu reparar as integrações".to_string())
}

fn open_subscription_url() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = Command::new("open");
        command.arg(SUBSCRIPTION_URL);
        command
    };
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = Command::new("cmd");
        command.args(["/C", "start", "", SUBSCRIPTION_URL]);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = Command::new("xdg-open");
        command.arg(SUBSCRIPTION_URL);
        command
    };

    command
        .status()
        .map_err(|_| "Não foi possível abrir os planos no navegador".to_string())
        .and_then(|status| {
            if status.success() {
                Ok(())
            } else {
                Err("Não foi possível abrir os planos no navegador".to_string())
            }
        })
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
    let output = run_runtime_output(SNAPSHOT_ARGS)?;
    if output.status.success() {
        let value = serde_json::from_slice(&output.stdout)
            .map_err(|_| "Simplicio Runtime devolveu JSON inválido".to_string())?;
        return validate_snapshot(value);
    }

    let stderr = String::from_utf8_lossy(&output.stderr);
    if !stderr.contains("unknown desktop sub: snapshot") {
        return Err(format!(
            "Simplicio Runtime encerrou com código {}",
            output.status.code().unwrap_or(-1)
        ));
    }

    let auth = run_runtime_json(LEGACY_AUTH_ARGS)?;
    let status = run_runtime_json(LEGACY_STATUS_ARGS)?;
    let savings = run_runtime_json(LEGACY_SAVINGS_ARGS)?;
    let install = run_runtime_json(LEGACY_INSTALL_ARGS)?;
    validate_snapshot(legacy_snapshot::build_legacy_snapshot(
        &auth, &status, &savings, &install,
    )?)
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
async fn desktop_logout() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        run_runtime_action(LOGOUT_ARGS)?;
        snapshot_from_runtime()
    })
    .await
    .map_err(|_| "Falha interna durante o logout".to_string())?
}

#[tauri::command]
async fn desktop_repair_providers() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        repair_provider_integrations()?;
        snapshot_from_runtime()
    })
    .await
    .map_err(|_| "Falha interna durante o reparo das integrações".to_string())?
}

#[tauri::command]
async fn desktop_open_subscription() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(|| {
        run_runtime_action(SUBSCRIPTION_ARGS).or_else(|_| open_subscription_url())
    })
    .await
    .map_err(|_| "Falha interna ao abrir os planos".to_string())?
}

/// The Desktop owns the transport boundary, not the Bot/Agent authority.
/// Runtime releases that expose Agent API can replace this implementation
/// without changing the frontend contract; until then, fail closed.
#[tauri::command]
async fn desktop_bot_action(_request: Value) -> Result<Value, String> {
    Err("Agent API do Runtime indisponível (agent_api_unavailable)".to_string())
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
            desktop_logout,
            desktop_repair_providers,
            desktop_open_subscription,
            desktop_bot_action,
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
        assert_eq!(LOGIN_ARGS, ["login", "google", "--json"]);
        assert_eq!(LOGOUT_ARGS, ["logout", "--json"]);
        assert_eq!(SUBSCRIPTION_ARGS, ["desktop", "subscribe", "--json"]);
        assert_eq!(STATUS_ARGS, ["desktop", "status", "--json"]);
        assert_eq!(LEGACY_AUTH_ARGS, ["auth", "status", "--json"]);
        assert_eq!(LEGACY_STATUS_ARGS, ["status", "--json"]);
        assert_eq!(LEGACY_SAVINGS_ARGS, ["savings", "report", "--json"]);
        assert_eq!(
            LEGACY_INSTALL_ARGS,
            ["install", "--global", "--dry-run", "--json"]
        );
        assert_eq!(INSTALL_ARGS, ["install", "--global", "--json"]);
        assert_eq!(SUBSCRIPTION_URL, "https://simpleti.com.br/simplicio");
    }

    #[test]
    fn bridge_prefers_the_bundled_runtime_then_managed_install_and_honors_an_explicit_override() {
        let managed = runtime_candidates_with(
            None,
            Some(OsString::from("/managed/simplicio")),
            Some(OsString::from("/ignored/home")),
            Some(OsString::from("/bundle/simplicio-desktop")),
        );
        assert_eq!(
            managed,
            [
                PathBuf::from("/bundle")
                    .join(if cfg!(windows) {
                        "simplicio.exe"
                    } else {
                        "simplicio"
                    })
                    .into_os_string(),
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
                Some(OsString::from("/bundle/simplicio-desktop")),
            ),
            [OsString::from("/explicit/runtime")]
        );
    }
}
