use serde_json::Value;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use tauri::Manager;

mod auth_access;
mod consolidated_tokens;
mod context_report;
mod desktop_queries;
mod install_result;
mod legacy_snapshot;
mod local_projects;
#[cfg(desktop)]
mod native_menu;
mod project_discovery_process;
mod project_usage;
mod runtime_process;
mod snapshot_exports;
mod supervisor;
mod token_exports;

static INSTALL_LOCK: std::sync::Mutex<install_result::InstallAttempt> =
    std::sync::Mutex::new(install_result::InstallAttempt::new());

#[tauri::command]
async fn desktop_validate_project(path: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_read_access()?;
        local_projects::validate_project(&path)
    })
    .await
    .map_err(|_| "project_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_open_project(path: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_active_access()?;
        local_projects::open_project(&path)
    })
    .await
    .map_err(|_| "project_open_failed".to_string())?
}

#[tauri::command]
async fn desktop_export_snapshot(
    app: tauri::AppHandle,
    kind: String,
    filters: Value,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let snapshot = snapshot_from_runtime()?;
        let downloads = app
            .path()
            .download_dir()
            .map_err(|_| "snapshot_export_unavailable")?;
        snapshot_exports::save(&snapshot, &kind, &filters, &downloads)
    })
    .await
    .map_err(|_| "snapshot_export_failed".to_string())?
}

const SNAPSHOT_SCHEMA: &str = "simplicio.desktop-snapshot/v1";
const MAX_SNAPSHOT_BYTES: usize = 65_536;
const SNAPSHOT_ARGS: &[&str] = &["desktop", "snapshot", "--json"];
const LOGIN_ARGS: &[&str] = &["login", "google", "--json"];
const LOGOUT_ARGS: &[&str] = &["logout", "--json"];
const STATUS_ARGS: &[&str] = &["desktop", "status", "--json"];
const LEGACY_AUTH_ARGS: &[&str] = &["auth", "status", "--json"];
const LEGACY_STATUS_ARGS: &[&str] = &["status", "--json"];
const LEGACY_SAVINGS_ARGS: &[&str] = &["savings", "report", "--json"];
const LEGACY_INSTALL_ARGS: &[&str] = &["install", "--global", "--dry-run", "--json"];
// Only dispatched after the reviewed plan digest and explicit UI consent match.
const INSTALL_ARGS: &[&str] = &["install", "--global", "--yes", "--json"];
const SUBSCRIPTION_URL: &str = "https://simpleti.com.br/simplicio";
const RELEASES_URL: &str = "https://github.com/wesleysimplicio/simplicio/releases";

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

fn runtime_capture_limits(args: &[&str]) -> runtime_process::CaptureLimits {
    if args == INSTALL_ARGS {
        runtime_process::CaptureLimits::INSTALL
    } else if args == LOGIN_ARGS {
        runtime_process::CaptureLimits::OAUTH
    } else {
        runtime_process::CaptureLimits::QUERY
    }
}

fn run_runtime_capture(args: &[&str]) -> Result<Output, runtime_process::ProcessFailure> {
    let commands = runtime_candidates().into_iter().map(|binary| {
        let mut command = Command::new(binary);
        command.args(args).env("SIMPLICIO_DESKTOP_BRIDGE", "1");
        command
    });
    runtime_process::capture_candidates(commands, runtime_capture_limits(args))
}

fn runtime_failure_code(args: &[&str], failure: runtime_process::ProcessFailure) -> String {
    use runtime_process::{ChildState, FailureKind};
    if failure.child_state == ChildState::Retained {
        return "runtime_process_cleanup_unconfirmed".into();
    }
    match failure.kind {
        FailureKind::Spawn => "runtime_not_started",
        FailureKind::Deadline if args == LOGIN_ARGS => "runtime_oauth_timeout",
        FailureKind::Deadline if args == INSTALL_ARGS => "runtime_install_timeout",
        FailureKind::Deadline => "runtime_query_timeout",
        FailureKind::StdoutLimit => "runtime_stdout_limit",
        FailureKind::StderrLimit => "runtime_stderr_limit",
        FailureKind::Capture => "runtime_output_unavailable",
        FailureKind::CleanupPending => "runtime_process_cleanup_unconfirmed",
    }
    .into()
}

fn run_runtime_output(args: &[&str]) -> Result<Output, String> {
    run_runtime_capture(args).map_err(|failure| runtime_failure_code(args, failure))
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

fn repair_provider_integrations() -> Result<(), install_result::InstallFailure> {
    use install_result::InstallFailure;
    use runtime_process::{ChildState, FailureKind};
    let output = run_runtime_capture(INSTALL_ARGS).map_err(|failure| {
        if failure.child_state == ChildState::Retained {
            return InstallFailure::CleanupUnconfirmed;
        }
        match failure.kind {
            FailureKind::Spawn => InstallFailure::NotStarted,
            FailureKind::Deadline => InstallFailure::TimedOut,
            FailureKind::StdoutLimit => InstallFailure::ResponseTooLarge,
            FailureKind::StderrLimit => InstallFailure::StderrTooLarge,
            FailureKind::Capture => InstallFailure::OutputUnavailable,
            FailureKind::CleanupPending => InstallFailure::CleanupUnconfirmed,
        }
    })?;
    install_result::validate_install_output(output.status.code(), &output.stdout)
}

fn require_active_access() -> Result<(), String> {
    if snapshot_from_runtime()?
        .pointer("/access/state")
        .and_then(Value::as_str)
        != Some("active")
    {
        return Err("desktop_access_not_active".into());
    }
    Ok(())
}

fn integration_plan_from_runtime() -> Result<Value, String> {
    require_active_access()?;
    desktop_queries::project_install_plan(run_runtime_json(LEGACY_INSTALL_ARGS)?)
}

fn require_read_access() -> Result<(), String> {
    // A fresh Runtime authorization query, not a cached snapshot or installation inventory.
    auth_access::require_fresh(run_runtime_json)
}

#[tauri::command]
async fn desktop_plan_integrations() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(integration_plan_from_runtime)
        .await
        .map_err(|_| "integration_plan_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_usage_projects() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        require_read_access()?;
        let home = std::env::var_os("HOME")
            .or_else(|| std::env::var_os("USERPROFILE"))
            .map(PathBuf::from)
            .ok_or("project_discovery_unavailable")?;
        let configured = std::env::var_os("SIMPLICIO_DESKTOP_REPO").map(PathBuf::from);
        let executable = std::env::current_exe().map_err(|_| "project_discovery_unavailable")?;
        project_discovery_process::discover(&home, configured.as_deref(), &executable)
    })
    .await
    .map_err(|_| "project_discovery_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_context_report(repo_path: Option<String>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_read_access()?;
        let default_repo = std::env::var_os("SIMPLICIO_DESKTOP_REPO")
            .or_else(|| std::env::var_os("HOME"))
            .or_else(|| std::env::var_os("USERPROFILE"))
            .map(PathBuf::from)
            .ok_or("context_query_invalid")?;
        let args = context_report::query_args(repo_path.as_deref(), &default_repo)?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        context_report::project(
            run_runtime_json(&borrowed).map_err(|_| "context_report_unavailable")?,
        )
    })
    .await
    .map_err(|_| "context_report_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_token_report(
    request: Value,
    reports: tauri::State<'_, token_exports::TokenReports>,
) -> Result<Value, String> {
    let reports = reports.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        require_read_access()?;
        let default_repo = std::env::var_os("SIMPLICIO_DESKTOP_REPO")
            .or_else(|| std::env::var_os("HOME"))
            .or_else(|| std::env::var_os("USERPROFILE"))
            .map(PathBuf::from)
            .ok_or("token_query_invalid")?;
        let args = desktop_queries::token_query_args(&request, &default_repo)?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        reports.remember(run_runtime_json(&borrowed).map_err(|_| "token_report_unavailable")?)
    })
    .await
    .map_err(|_| "token_report_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_consolidated_token_report(request: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let executable = std::env::current_exe().map_err(|_| "consolidated_report_unavailable")?;
        consolidated_tokens::report(
            &request,
            &executable,
            runtime_candidates(),
            require_read_access,
        )
    })
    .await
    .map_err(|_| "consolidated_report_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_export_token_report(
    app: tauri::AppHandle,
    reports: tauri::State<'_, token_exports::TokenReports>,
    report_hash: String,
    format: String,
) -> Result<Value, String> {
    let reports = reports.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        require_active_access()?;
        let downloads = app
            .path()
            .download_dir()
            .map_err(|_| "token_export_downloads_unavailable")?;
        reports.save(&report_hash, &format, &downloads)
    })
    .await
    .map_err(|_| "token_export_write_failed".to_string())?
}

fn open_browser_url(url: &str) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = Command::new("/usr/bin/open");
        command.arg(url);
        command
    };
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = Command::new("cmd");
        command.args(["/C", "start", "", url]);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = Command::new("xdg-open");
        command.arg(url);
        command
    };

    command
        .status()
        .map_err(|_| "Não foi possível abrir o link no navegador".to_string())
        .and_then(|status| {
            if status.success() {
                Ok(())
            } else {
                Err("Não foi possível abrir o link no navegador".to_string())
            }
        })
}

fn open_subscription_url() -> Result<(), String> {
    open_browser_url(SUBSCRIPTION_URL)
}

#[tauri::command]
fn desktop_update_target() -> Value {
    let platform = match std::env::consts::OS {
        "macos" => "macos",
        "windows" => "windows",
        "linux" => "linux",
        _ => "unknown",
    };
    let arch = match std::env::consts::ARCH {
        "aarch64" => "arm64",
        "x86_64" => "x64",
        "x86" => "x86",
        _ => "unknown",
    };
    serde_json::json!({ "platform": platform, "arch": arch })
}

#[tauri::command]
async fn desktop_open_releases() -> Result<(), String> {
    // Only the fixed public release page may be opened; IPC accepts no URL.
    tauri::async_runtime::spawn_blocking(|| open_browser_url(RELEASES_URL))
        .await
        .map_err(|_| "release_page_unavailable".to_string())?
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
async fn desktop_repair_providers(plan_digest: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut attempt = INSTALL_LOCK.try_lock().map_err(|error| match error {
            std::sync::TryLockError::WouldBlock => "integration_install_busy",
            std::sync::TryLockError::Poisoned(_) => "integration_install_reconciliation_required",
        })?;
        attempt
            .check_ready()
            .map_err(|failure| failure.public_code())?;
        // Preflight is read-only: no installer has started before attempt.begin().
        let plan =
            integration_plan_from_runtime().map_err(|_| "integration_preflight_unavailable")?;
        if plan["planDigest"].as_str() != Some(plan_digest.as_str()) {
            return Err("integration_plan_changed_review_again".into());
        }
        attempt.begin().map_err(|failure| failure.public_code())?;
        let result = repair_provider_integrations();
        attempt.finish(&result);
        result.map_err(|failure| failure.public_code())?;
        snapshot_from_runtime()
            .map_err(|_| install_result::InstallFailure::AppliedSnapshotUnavailable.public_code())
    })
    .await
    .map_err(|_| "Falha interna durante o reparo das integrações".to_string())?
}

#[tauri::command]
async fn desktop_open_subscription() -> Result<(), String> {
    // One fixed navigation, never retry an uncertain Runtime action with a second opener.
    tauri::async_runtime::spawn_blocking(open_subscription_url)
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
        .plugin(tauri_plugin_dialog::init())
        .manage(token_exports::TokenReports::default())
        .setup(|app| {
            #[cfg(desktop)]
            native_menu::install(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            desktop_snapshot,
            desktop_validate_project,
            desktop_open_project,
            desktop_export_snapshot,
            refresh_desktop_snapshot,
            desktop_login,
            desktop_logout,
            desktop_repair_providers,
            desktop_plan_integrations,
            desktop_usage_projects,
            desktop_context_report,
            desktop_token_report,
            desktop_consolidated_token_report,
            desktop_export_token_report,
            desktop_open_subscription,
            desktop_update_target,
            desktop_open_releases,
            desktop_bot_action,
            runtime_status
        ])
        .run(tauri::generate_context!())
        .expect("failed to run Simplicio Desktop");
}

/// Internal read-only worker entrypoint, checked before initializing the WebView.
/// Desktop IPC still requires fresh Runtime access before launching a worker.
pub fn try_project_discovery_worker() -> Option<Result<Value, String>> {
    project_discovery_process::try_discovery_worker()
}

/// Internal metadata-only token preflight; dispatch before Tauri initialization.
pub fn try_consolidated_token_preflight_worker() -> Option<Result<Value, String>> {
    consolidated_tokens::try_preflight_worker()
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
        assert_eq!(STATUS_ARGS, ["desktop", "status", "--json"]);
        assert_eq!(LEGACY_AUTH_ARGS, ["auth", "status", "--json"]);
        assert_eq!(LEGACY_STATUS_ARGS, ["status", "--json"]);
        assert_eq!(LEGACY_SAVINGS_ARGS, ["savings", "report", "--json"]);
        assert_eq!(
            LEGACY_INSTALL_ARGS,
            ["install", "--global", "--dry-run", "--json"]
        );
        assert_eq!(INSTALL_ARGS, ["install", "--global", "--yes", "--json"]);
        assert_eq!(SUBSCRIPTION_URL, "https://simpleti.com.br/simplicio");
        assert_eq!(
            RELEASES_URL,
            "https://github.com/wesleysimplicio/simplicio/releases"
        );
    }

    #[test]
    fn process_deadlines_are_explicit_per_query_oauth_and_install() {
        use std::time::Duration;
        assert_eq!(
            runtime_capture_limits(SNAPSHOT_ARGS).deadline,
            Duration::from_secs(20)
        );
        assert_eq!(
            runtime_capture_limits(LEGACY_INSTALL_ARGS).deadline,
            Duration::from_secs(20)
        );
        assert_eq!(
            runtime_capture_limits(LOGIN_ARGS).deadline,
            Duration::from_secs(180)
        );
        assert_eq!(
            runtime_capture_limits(INSTALL_ARGS).deadline,
            Duration::from_secs(300)
        );
        assert_eq!(runtime_capture_limits(INSTALL_ARGS).stdout_bytes, 65_536);
    }

    #[test]
    fn public_process_errors_are_fixed_codes_and_do_not_infer_auth_state() {
        use runtime_process::{ChildState, FailureKind, ProcessFailure};
        let timeout = ProcessFailure {
            kind: FailureKind::Deadline,
            child_state: ChildState::Reaped,
        };
        assert_eq!(
            runtime_failure_code(LOGIN_ARGS, timeout),
            "runtime_oauth_timeout"
        );
        assert_eq!(
            runtime_failure_code(SNAPSHOT_ARGS, timeout),
            "runtime_query_timeout"
        );
        assert_eq!(
            runtime_failure_code(INSTALL_ARGS, timeout),
            "runtime_install_timeout"
        );
        assert_eq!(
            runtime_failure_code(
                INSTALL_ARGS,
                ProcessFailure {
                    child_state: ChildState::Retained,
                    ..timeout
                }
            ),
            "runtime_process_cleanup_unconfirmed"
        );
    }

    #[test]
    fn desktop_build_uses_the_simplicio_product_identity() {
        let config: Value = serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
        assert_eq!(config["productName"], "Simplicio");
        assert_eq!(config["app"]["windows"][0]["title"], "Simplicio");
        assert_eq!(config["identifier"], "br.com.simpleti.simplicio");
    }

    #[test]
    fn update_target_exposes_only_platform_and_architecture() {
        let target = desktop_update_target();
        assert_eq!(target.as_object().unwrap().len(), 2);
        assert!(matches!(
            target["platform"].as_str(),
            Some("macos" | "windows" | "linux" | "unknown")
        ));
        assert!(matches!(
            target["arch"].as_str(),
            Some("arm64" | "x64" | "x86" | "unknown")
        ));
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
