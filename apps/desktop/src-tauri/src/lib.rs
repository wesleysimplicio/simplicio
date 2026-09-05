use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use tauri::Manager;

mod auth_access;
mod auth_login;
mod consolidated_tokens;
mod context_report;
mod desktop_queries;
mod desktop_updater;
mod host_plugins;
mod install_journal;
mod local_projects;
#[cfg(desktop)]
mod native_menu;
mod project_discovery_process;
mod project_usage;
mod projection_queries;
mod runtime_install;
mod runtime_lifecycle;
mod runtime_process;
mod snapshot_exports;
mod supervisor;
mod token_exports;
mod unified_usage_bridge;
mod usage_changefeed;

static INSTALL_PROCESS_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

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
const LOGIN_ARGS: &[&str] = auth_login::LOGIN_ARGS;
const LOGOUT_ARGS: &[&str] = &["logout", "--json"];
const STATUS_ARGS: &[&str] = auth_login::STATUS_ARGS;
const HOST_PLUGIN_PLAN_ARGS: &[&str] = &["host-plugins", "plan", "--all"];
const SUBSCRIPTION_URL: &str = "https://simpleti.com.br/simplicio";
const RELEASES_URL: &str = "https://github.com/wesleysimplicio/simplicio/releases";

fn install_journal_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map(|directory| directory.join("install-attempt.json"))
        .map_err(|_| "runtime_install_journal_unavailable".to_string())
}

fn runtime_capture_limits(args: &[&str]) -> runtime_process::CaptureLimits {
    if matches!(args, ["host-plugins", "apply" | "reconcile", ..]) {
        runtime_process::CaptureLimits::INSTALL
    } else if args == LOGIN_ARGS {
        runtime_process::CaptureLimits::OAUTH
    } else {
        runtime_process::CaptureLimits::QUERY
    }
}

fn run_runtime_capture(args: &[&str]) -> Result<Output, String> {
    let binary = packaged_runtime_authority()?;
    let mut command = Command::new(binary);
    command.args(args).env("SIMPLICIO_DESKTOP_BRIDGE", "1");
    runtime_process::capture(&mut command, runtime_capture_limits(args))
        .map_err(|failure| runtime_failure_code(args, failure))
}

fn runtime_failure_code(args: &[&str], failure: runtime_process::ProcessFailure) -> String {
    use runtime_process::{ChildState, FailureKind};
    if failure.child_state == ChildState::Retained {
        return "runtime_process_cleanup_unconfirmed".into();
    }
    match failure.kind {
        FailureKind::Spawn => "runtime_not_started",
        FailureKind::Deadline if args == LOGIN_ARGS => "runtime_oauth_timeout",
        FailureKind::Deadline if matches!(args, ["host-plugins", "apply" | "reconcile", ..]) => {
            "runtime_install_timeout"
        }
        FailureKind::Deadline => "runtime_query_timeout",
        FailureKind::StdoutLimit => "runtime_stdout_limit",
        FailureKind::StderrLimit => "runtime_stderr_limit",
        FailureKind::Capture => "runtime_output_unavailable",
        FailureKind::CleanupPending => "runtime_process_cleanup_unconfirmed",
    }
    .into()
}

fn run_runtime_output(args: &[&str]) -> Result<Output, String> {
    run_runtime_capture(args)
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

fn run_runtime_binary_json(binary: &Path, args: &[&str]) -> Result<Value, String> {
    let mut command = Command::new(binary);
    command.args(args).env("SIMPLICIO_DESKTOP_BRIDGE", "1");
    let output = runtime_process::capture(&mut command, runtime_capture_limits(args))
        .map_err(|failure| runtime_failure_code(args, failure))?;
    if !output.status.success() {
        return Err("runtime_install_verification_failed".to_string());
    }
    serde_json::from_slice(&output.stdout)
        .map_err(|_| "runtime_install_verification_failed".to_string())
}

fn runtime_user_home() -> Result<PathBuf, String> {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .ok_or_else(|| "runtime_install_home_unavailable".to_string())
}

fn run_runtime_action(args: &[&str]) -> Result<(), String> {
    successful_output(args).map(|_| ())
}

fn run_host_plugin_json(args: &[&str]) -> Result<Value, String> {
    let output = run_runtime_capture(args)?;
    let value = serde_json::from_slice::<Value>(&output.stdout)
        .map_err(|_| "host_plugin_response_invalid".to_string())?;
    if output.status.success() {
        return Ok(value);
    }
    let code = host_plugins::cli_error_code(&value).ok_or("host_plugin_failure_invalid")?;
    Err(format!("host_plugin_{code}"))
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
    host_plugins::project_plan(run_host_plugin_json(HOST_PLUGIN_PLAN_ARGS)?)
}

fn host_plugin_apply_args(plan_digest: &str) -> Result<Vec<String>, String> {
    if !host_plugins::valid_digest(plan_digest) {
        return Err("host_plugin_plan_digest_invalid".to_string());
    }
    Ok([
        "host-plugins",
        "apply",
        "--all",
        "--plan-digest",
        plan_digest,
        "--yes",
    ]
    .into_iter()
    .map(str::to_string)
    .collect())
}

fn host_plugin_reconcile_args(receipt_id: &str) -> Result<Vec<String>, String> {
    if !host_plugins::valid_digest(receipt_id) {
        return Err("host_plugin_receipt_id_invalid".to_string());
    }
    Ok(["host-plugins", "reconcile", "--receipt-id", receipt_id]
        .into_iter()
        .map(str::to_string)
        .collect())
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
async fn desktop_usage_changefeed(
    after_sequence: u64,
    after_revision: u64,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_active_access()?;
        let args = usage_changefeed::query_args(after_sequence, after_revision)?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        let value =
            run_runtime_json(&borrowed).map_err(|_| "usage_changefeed_unavailable".to_string())?;
        usage_changefeed::validate_event(value, after_sequence, after_revision)
    })
    .await
    .map_err(|_| "usage_changefeed_unavailable".to_string())?
}

fn default_projection_repo() -> Result<PathBuf, String> {
    std::env::var_os("SIMPLICIO_DESKTOP_REPO")
        .or_else(|| std::env::var_os("HOME"))
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .ok_or_else(|| "projection_query_invalid".to_string())
}

#[tauri::command]
async fn desktop_unified_usage(query: Value, repo_path: Option<String>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_read_access()?;
        let default_repo = default_projection_repo()?;
        let args = projection_queries::query_args(
            "desktop-unified-usage",
            &query,
            repo_path.as_deref(),
            &default_repo,
        )?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        run_runtime_json(&borrowed).map_err(|_| "unified_usage_unavailable".to_string())
    })
    .await
    .map_err(|_| "unified_usage_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_cost_projection(query: Value, repo_path: Option<String>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_read_access()?;
        let default_repo = default_projection_repo()?;
        let args = projection_queries::query_args(
            "desktop-cost-projection",
            &query,
            repo_path.as_deref(),
            &default_repo,
        )?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        run_runtime_json(&borrowed).map_err(|_| "cost_projection_unavailable".to_string())
    })
    .await
    .map_err(|_| "cost_projection_unavailable".to_string())?
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
            vec![packaged_runtime_authority()?.into_os_string()],
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
async fn desktop_update_download(
    app: tauri::AppHandle,
    version: String,
    tag: String,
    asset_name: String,
    asset_bytes: u64,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let app_data = app
            .path()
            .app_data_dir()
            .map_err(|_| "update_storage_unavailable".to_string())?;
        desktop_updater::download(&app_data, &version, &tag, &asset_name, asset_bytes)
    })
    .await
    .map_err(|_| "update_download_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_update_status(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let app_data = app
            .path()
            .app_data_dir()
            .map_err(|_| "update_storage_unavailable".to_string())?;
        desktop_updater::status(&app_data)
    })
    .await
    .map_err(|_| "update_status_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_update_install(app: tauri::AppHandle, update_id: String) -> Result<Value, String> {
    let app_for_exit = app.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let app_data = app
            .path()
            .app_data_dir()
            .map_err(|_| "update_storage_unavailable".to_string())?;
        let current_executable =
            std::env::current_exe().map_err(|_| "update_target_unavailable".to_string())?;
        desktop_updater::install(&app_data, &current_executable, &update_id)
    })
    .await
    .map_err(|_| "update_install_unavailable".to_string())??;
    if matches!(
        result.get("state").and_then(Value::as_str),
        Some("relaunch_pending") | Some("awaiting_health")
    ) {
        app_for_exit.exit(0);
    }
    Ok(result)
}

#[tauri::command]
async fn desktop_update_rollback(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let app_data = app
            .path()
            .app_data_dir()
            .map_err(|_| "update_storage_unavailable".to_string())?;
        let current_executable =
            std::env::current_exe().map_err(|_| "update_target_unavailable".to_string())?;
        desktop_updater::rollback(&app_data, &current_executable)
    })
    .await
    .map_err(|_| "update_rollback_unavailable".to_string())?
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
        && host_plugins::validate_desktop_projection(value.get("hostPlugins")).is_ok()
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

fn snapshot_from_binary(binary: &Path) -> Result<Value, String> {
    validate_snapshot(run_runtime_binary_json(binary, SNAPSHOT_ARGS)?)
}

fn packaged_runtime_authority() -> Result<PathBuf, String> {
    let current_executable =
        std::env::current_exe().map_err(|_| "runtime_install_package_unavailable".to_string())?;
    runtime_install::bundled_authority(&current_executable, snapshot_from_binary)
}

fn snapshot_from_runtime() -> Result<Value, String> {
    let current_executable =
        std::env::current_exe().map_err(|_| "runtime_install_package_unavailable".to_string())?;
    runtime_install::current_snapshot(
        &current_executable,
        &runtime_user_home()?,
        snapshot_from_binary,
    )?
    .ok_or_else(|| "runtime_install_required".to_string())
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
async fn desktop_install_runtime(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let _process_lock = INSTALL_PROCESS_LOCK
            .lock()
            .map_err(|_| "runtime_install_busy".to_string())?;
        let journal_path = install_journal_path(&app)?;
        let mut attempt = install_journal::InstallAttempt::load(&journal_path);
        if attempt.pending_error().is_some() {
            return Err("runtime_install_reconciliation_required".to_string());
        }
        attempt.begin_persisted(&journal_path)?;
        let current_executable = std::env::current_exe()
            .map_err(|_| "runtime_install_package_unavailable".to_string())?;
        let result = runtime_install::install(
            &current_executable,
            &runtime_user_home()?,
            snapshot_from_binary,
        );
        attempt.finish_persisted(&journal_path, &result)?;
        result
    })
    .await
    .map_err(|_| "runtime_install_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_runtime_install_status(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let path = install_journal_path(&app)?;
        let pending = install_journal::InstallAttempt::load(&path)
            .pending_error()
            .is_some();
        Ok(serde_json::json!({
            "schema": "simplicio.desktop-install-status/v1",
            "status": if pending { "pending" } else { "clear" },
            "redacted": true,
        }))
    })
    .await
    .map_err(|_| "runtime_install_journal_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_reconcile_runtime_install(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let _process_lock = INSTALL_PROCESS_LOCK
            .lock()
            .map_err(|_| "runtime_install_busy".to_string())?;
        let journal_path = install_journal_path(&app)?;
        let mut attempt = install_journal::InstallAttempt::load(&journal_path);
        if attempt.pending_error().is_none() {
            return Ok(serde_json::json!({
                "schema": "simplicio.desktop-install-reconciliation/v1",
                "status": "clear",
                "current": false,
                "redacted": true,
            }));
        }
        let current_executable = std::env::current_exe()
            .map_err(|_| "runtime_install_package_unavailable".to_string())?;
        let home = runtime_user_home()?;
        let snapshot =
            runtime_install::current_snapshot(&current_executable, &home, snapshot_from_binary)?;
        attempt.finish_persisted(
            &journal_path,
            &Ok(serde_json::json!({"status":"reconciled"})),
        )?;
        Ok(serde_json::json!({
            "schema": "simplicio.desktop-install-reconciliation/v1",
            "status": "reconciled",
            "current": snapshot.is_some(),
            "redacted": true,
        }))
    })
    .await
    .map_err(|_| "runtime_install_reconciliation_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_runtime_lifecycle(action: Option<String>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let current_executable =
            std::env::current_exe().map_err(|_| "runtime_lifecycle_unavailable".to_string())?;
        let home = runtime_user_home()?;
        match action.as_deref() {
            None | Some("status") => {
                runtime_lifecycle::read(&current_executable, &home, snapshot_from_binary)
            }
            Some("rollback") => {
                let _process_lock = INSTALL_PROCESS_LOCK
                    .lock()
                    .map_err(|_| "runtime_install_busy".to_string())?;
                runtime_lifecycle::rollback(&home, snapshot_from_binary)
            }
            Some(action) => {
                let _process_lock = INSTALL_PROCESS_LOCK
                    .lock()
                    .map_err(|_| "runtime_install_busy".to_string())?;
                runtime_lifecycle::apply(&current_executable, &home, action, snapshot_from_binary)
            }
        }
    })
    .await
    .map_err(|_| "runtime_lifecycle_unavailable".to_string())?
}
#[tauri::command]
async fn desktop_login() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let authority = packaged_runtime_authority()?;
        auth_login::authenticate([authority.into_os_string()], |binary, args| {
            let mut command = Command::new(binary);
            command.args(args).env("SIMPLICIO_DESKTOP_BRIDGE", "1");
            runtime_process::capture(&mut command, runtime_capture_limits(args))
        })?;
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
async fn desktop_apply_host_plugins(plan_digest: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_active_access()?;
        // Consent is bound to the reviewed digest. Runtime owns locking, the
        // durable receipt, precondition recheck and all host side effects.
        let args = host_plugin_apply_args(&plan_digest)?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        host_plugins::project_operation(run_host_plugin_json(&borrowed)?, "apply")
    })
    .await
    .map_err(|_| "host_plugin_apply_unavailable".to_string())?
}

#[tauri::command]
async fn desktop_reconcile_host_plugins(receipt_id: String) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        require_active_access()?;
        // Reconciliation is explicit and targets exactly the opaque identifier
        // selected by the Runtime snapshot. It never repeats apply.
        let args = host_plugin_reconcile_args(&receipt_id)?;
        let borrowed = args.iter().map(String::as_str).collect::<Vec<_>>();
        host_plugins::project_operation(run_host_plugin_json(&borrowed)?, "reconcile")
    })
    .await
    .map_err(|_| "host_plugin_reconcile_unavailable".to_string())?
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
            let current_executable = std::env::current_exe().ok();
            if let (Some(current_executable), Ok(app_data)) =
                (current_executable, app.path().app_data_dir())
            {
                if let Err(error) =
                    desktop_updater::reconcile_startup(&app_data, &current_executable)
                {
                    eprintln!("Simplicio: Desktop update recovery is pending: {error}");
                }
            }
            #[cfg(desktop)]
            native_menu::install(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            desktop_snapshot,
            desktop_install_runtime,
            desktop_runtime_install_status,
            desktop_reconcile_runtime_install,
            desktop_runtime_lifecycle,
            desktop_validate_project,
            desktop_open_project,
            desktop_export_snapshot,
            refresh_desktop_snapshot,
            desktop_login,
            desktop_logout,
            desktop_apply_host_plugins,
            desktop_reconcile_host_plugins,
            desktop_plan_integrations,
            desktop_usage_projects,
            desktop_usage_changefeed,
            desktop_unified_usage,
            desktop_cost_projection,
            desktop_context_report,
            desktop_token_report,
            desktop_consolidated_token_report,
            desktop_export_token_report,
            desktop_open_subscription,
            desktop_update_target,
            desktop_update_download,
            desktop_update_status,
            desktop_update_install,
            desktop_update_rollback,
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
    use std::fs;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_SIDECAR_FIXTURE: AtomicU64 = AtomicU64::new(1);

    fn valid_snapshot() -> Value {
        json!({
            "schema": SNAPSHOT_SCHEMA,
            "source": "runtime",
            "access": { "state": "active" },
            "runtime": {
                "state": "healthy",
                "version": "3.8.40",
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
        assert_eq!(
            LOGIN_ARGS,
            ["login", "google", "--authentication-only", "--json"]
        );
        assert_eq!(LOGOUT_ARGS, ["logout", "--json"]);
        assert_eq!(STATUS_ARGS, ["desktop", "status", "--json"]);
        assert_eq!(HOST_PLUGIN_PLAN_ARGS, ["host-plugins", "plan", "--all"]);
        let digest = format!("sha256:{}", "a".repeat(64));
        assert_eq!(
            host_plugin_apply_args(&digest).unwrap(),
            [
                "host-plugins",
                "apply",
                "--all",
                "--plan-digest",
                digest.as_str(),
                "--yes"
            ]
        );
        assert_eq!(
            host_plugin_reconcile_args(&digest).unwrap(),
            ["host-plugins", "reconcile", "--receipt-id", digest.as_str()]
        );
        assert!(host_plugin_apply_args("sha256:bad").is_err());
        assert!(host_plugin_reconcile_args("/private/receipt").is_err());
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
            runtime_capture_limits(HOST_PLUGIN_PLAN_ARGS).deadline,
            Duration::from_secs(20)
        );
        assert_eq!(
            runtime_capture_limits(LOGIN_ARGS).deadline,
            Duration::from_secs(180)
        );
        let digest = format!("sha256:{}", "a".repeat(64));
        let apply = host_plugin_apply_args(&digest).unwrap();
        let apply = apply.iter().map(String::as_str).collect::<Vec<_>>();
        assert_eq!(
            runtime_capture_limits(&apply).deadline,
            Duration::from_secs(300)
        );
        assert_eq!(runtime_capture_limits(&apply).stdout_bytes, 65_536);
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
        let digest = format!("sha256:{}", "a".repeat(64));
        let apply = host_plugin_apply_args(&digest).unwrap();
        let apply = apply.iter().map(String::as_str).collect::<Vec<_>>();
        assert_eq!(
            runtime_failure_code(&apply, timeout),
            "runtime_install_timeout"
        );
        assert_eq!(
            runtime_failure_code(
                &apply,
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
    fn sensitive_commands_resolve_only_the_packaged_sibling_sidecar() {
        let bundle = std::env::temp_dir()
            .canonicalize()
            .unwrap_or_else(|_| std::env::temp_dir());
        let app = bundle.join(if cfg!(windows) {
            "simplicio-desktop.exe"
        } else {
            "simplicio-desktop"
        });
        assert_eq!(
            runtime_install::bundled_runtime_path(&app).unwrap(),
            bundle.join(if cfg!(windows) {
                "simplicio.exe"
            } else {
                "simplicio"
            })
        );
    }

    fn sidecar_fixture() -> (PathBuf, PathBuf, PathBuf) {
        let temporary_root = std::env::temp_dir()
            .canonicalize()
            .unwrap_or_else(|_| std::env::temp_dir());
        let root = temporary_root.join(format!(
            "simplicio-desktop-real-sidecar-{}-{}",
            std::process::id(),
            NEXT_SIDECAR_FIXTURE.fetch_add(1, Ordering::Relaxed)
        ));
        let bundle = root.join("bundle");
        let home = root.join("home");
        fs::create_dir_all(&bundle).unwrap();
        fs::create_dir_all(&home).unwrap();
        let app = bundle.join(if cfg!(windows) {
            "simplicio-desktop.exe"
        } else {
            "simplicio-desktop"
        });
        (root, app, home)
    }

    #[cfg(unix)]
    fn write_real_snapshot_sidecar(app: &Path) {
        use std::os::unix::fs::PermissionsExt;

        let sidecar = runtime_install::bundled_runtime_path(app).unwrap();
        let payload = serde_json::to_string(&valid_snapshot()).unwrap();
        let script = format!(
            "#!/bin/sh\nif [ \"$1\" = desktop ] && [ \"$2\" = snapshot ] && [ \"$3\" = --json ]; then\n  printf '%s\\n' '{}'\n  exit 0\nfi\nexit 64\n",
            payload
        );
        fs::write(&sidecar, script).unwrap();
        fs::set_permissions(&sidecar, fs::Permissions::from_mode(0o700)).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn real_executable_sidecar_round_trips_through_install_and_fresh_snapshot() {
        let (root, app, home) = sidecar_fixture();
        write_real_snapshot_sidecar(&app);
        let receipt = runtime_install::install(&app, &home, snapshot_from_binary).unwrap();
        assert_eq!(receipt["status"], "installed");
        assert_eq!(receipt["pluginsMutated"], false);
        let snapshot = runtime_install::current_snapshot(&app, &home, snapshot_from_binary)
            .unwrap()
            .unwrap();
        assert_eq!(snapshot["runtime"]["state"], "healthy");
        assert_eq!(snapshot["runtime"]["version"], "3.8.40");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    #[ignore = "release gate: requires SIMPLICIO_DESKTOP_RELEASE_SIDECAR pointing to a signature-verified target binary"]
    fn packaged_release_sidecar_smoke() {
        let source = std::env::var_os("SIMPLICIO_DESKTOP_RELEASE_SIDECAR")
            .map(PathBuf::from)
            .expect("SIMPLICIO_DESKTOP_RELEASE_SIDECAR is required");
        assert!(
            source.is_absolute(),
            "release sidecar path must be absolute"
        );
        assert!(source.is_file(), "release sidecar must be a regular file");
        let (root, app, home) = sidecar_fixture();
        let bundled = runtime_install::bundled_runtime_path(&app).unwrap();
        fs::copy(&source, &bundled).expect("copy verified release sidecar into fixture bundle");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&bundled, fs::Permissions::from_mode(0o700)).unwrap();
        }
        let receipt = runtime_install::install(&app, &home, snapshot_from_binary)
            .expect("verified release sidecar must install and validate");
        assert_eq!(receipt["validated"], true);
        assert_eq!(receipt["pluginsMutated"], false);
        let snapshot = runtime_install::current_snapshot(&app, &home, snapshot_from_binary)
            .expect("release sidecar snapshot query")
            .expect("managed installation is current");
        assert_eq!(snapshot["runtime"]["state"], "healthy");
        fs::remove_dir_all(root).unwrap();
    }
}
