use serde_json::Value;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

const MAX_INSTALL_OUTPUT_BYTES: usize = 64 * 1024;

const MAX_INSTALL_ACTIONS: usize = 128;

const INSTALL_ATTEMPT_SCHEMA: &str = "simplicio.desktop-install-attempt/v1";

/// A closed projection: no raw action name, path, detail, stdout or stderr.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InstallDiagnostic {
    schema: &'static str,
    status: &'static str,
    failed_steps: Vec<&'static str>,
    unknown_failed_steps: usize,
}

pub type InstallError = Value;

fn journal_sibling(path: &Path, suffix: &str) -> PathBuf {
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default();
    path.with_extension(format!("{extension}.{suffix}"))
}

fn write_journal(path: &Path, state: &str, error: Option<Value>) -> io::Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "missing journal parent"))?;
    fs::create_dir_all(parent)?;
    let temporary = journal_sibling(path, "tmp");
    let backup = journal_sibling(path, "bak");
    let _ = fs::remove_file(&temporary);
    let mut file = File::create(&temporary)?;
    let record = serde_json::json!({
        "schema": INSTALL_ATTEMPT_SCHEMA,
        "state": state,
        "error": error,
    });
    serde_json::to_writer(&mut file, &record).map_err(io::Error::other)?;
    file.write_all(b"\n")?;
    file.sync_all()?;

    if path.exists() {
        let _ = fs::remove_file(&backup);
        fs::rename(path, &backup)?;
    }
    if let Err(error) = fs::rename(&temporary, path) {
        if !path.exists() && backup.exists() {
            let _ = fs::rename(&backup, path);
        }
        return Err(error);
    }
    if let Ok(directory) = File::open(parent) {
        let _ = directory.sync_all();
    }
    Ok(())
}

fn valid_exit_code(code: &str) -> bool {
    let Some(raw) = code.strip_prefix("integration_install_exit_code:") else {
        return false;
    };
    raw.len() <= 11 && raw.parse::<i32>().is_ok_and(|value| value != 0)
}

fn valid_public_code(code: &str) -> bool {
    matches!(
        code,
        "integration_install_busy"
            | "integration_preflight_unavailable"
            | "integration_plan_changed_review_again"
            | "integration_install_output_unavailable"
            | "integration_install_not_started"
            | "integration_install_timeout"
            | "integration_install_stderr_too_large"
            | "integration_install_cleanup_unconfirmed"
            | "integration_install_reconciliation_required"
            | "integration_install_no_exit_code"
            | "integration_install_invalid_json"
            | "integration_install_response_too_large"
            | "integration_install_receipt_unconfirmed"
            | "integration_install_applied_snapshot_unavailable"
    ) || valid_exit_code(code)
}

fn valid_step_label(step: &str) -> bool {
    matches!(
        step,
        "binary-copy"
            | "path-registration"
            | "install-manifest"
            | "codex"
            | "codex-hooks"
            | "mcp-route-hook"
            | "hermes"
            | "claude-code"
            | "claude-code-hooks"
            | "claude-desktop"
            | "cursor"
            | "windsurf"
            | "windsurf-next"
            | "kiro"
            | "gemini"
            | "trae"
            | "antigravity"
            | "jetbrains-junie"
            | "vscode-cline"
            | "vscode"
            | "zed"
            | "opencode"
            | "grok-mcp-route"
    )
}

fn sanitized_public_error(value: &Value) -> Option<Value> {
    let object = value.as_object()?;
    if object.len() < 2
        || object.len() > 3
        || value.get("schema")?.as_str()? != "simplicio.desktop-install-error/v1"
    {
        return None;
    }
    let code = value.get("code")?.as_str()?;
    if code.len() > 100 || !valid_public_code(code) {
        return None;
    }
    let Some(diagnostic) = value.get("diagnostic") else {
        return (object.len() == 2).then(|| {
            serde_json::json!({
                "schema": "simplicio.desktop-install-error/v1",
                "code": code,
            })
        });
    };
    if !valid_exit_code(code) || object.len() != 3 {
        return None;
    }
    let diagnostic_object = diagnostic.as_object()?;
    if diagnostic_object.len() != 4
        || diagnostic.get("schema")?.as_str()? != "simplicio.desktop-install-diagnostic/v1"
        || diagnostic.get("status")?.as_str()? != "partial"
    {
        return None;
    }
    let failed_steps = diagnostic.get("failedSteps")?.as_array()?;
    let unknown = diagnostic.get("unknownFailedSteps")?.as_u64()?;
    if failed_steps.len() > MAX_INSTALL_ACTIONS
        || unknown > MAX_INSTALL_ACTIONS as u64
        || failed_steps.len() as u64 + unknown == 0
        || failed_steps.len() as u64 + unknown > MAX_INSTALL_ACTIONS as u64
    {
        return None;
    }
    let mut seen = std::collections::HashSet::new();
    let mut steps = Vec::with_capacity(failed_steps.len());
    for value in failed_steps {
        let step = value.as_str()?;
        if !valid_step_label(step) || !seen.insert(step) {
            return None;
        }
        steps.push(step);
    }
    Some(serde_json::json!({
        "schema": "simplicio.desktop-install-error/v1",
        "code": code,
        "diagnostic": {
            "schema": "simplicio.desktop-install-diagnostic/v1",
            "status": "partial",
            "failedSteps": steps,
            "unknownFailedSteps": unknown,
        }
    }))
}

fn known_step(name: &str) -> Option<&'static str> {
    match name {
        "binary-copy" => Some("binary-copy"),
        "path-registration" => Some("path-registration"),
        "install-manifest" => Some("install-manifest"),
        "assistant-config:codex" => Some("codex"),
        "assistant-config:codex-hooks" => Some("codex-hooks"),
        "assistant-config:mcp-route-hook" => Some("mcp-route-hook"),
        "assistant-config:hermes" => Some("hermes"),
        "assistant-config:claude-code" => Some("claude-code"),
        "assistant-config:claude-code-hooks" => Some("claude-code-hooks"),
        "assistant-config:claude-desktop" => Some("claude-desktop"),
        "assistant-config:cursor" => Some("cursor"),
        "assistant-config:windsurf" => Some("windsurf"),
        "assistant-config:windsurf-next" => Some("windsurf-next"),
        "assistant-config:kiro" => Some("kiro"),
        "assistant-config:gemini" => Some("gemini"),
        "assistant-config:trae" => Some("trae"),
        "assistant-config:antigravity" => Some("antigravity"),
        "assistant-config:jetbrains-junie" => Some("jetbrains-junie"),
        "assistant-config:vscode-cline" => Some("vscode-cline"),
        "assistant-config:vscode" => Some("vscode"),
        "assistant-config:zed" => Some("zed"),
        "assistant-config:opencode" => Some("opencode"),
        "assistant-config:grok-mcp-route" => Some("grok-mcp-route"),
        _ => None,
    }
}

fn partial_diagnostic(stdout: &[u8]) -> Option<InstallDiagnostic> {
    if stdout.len() > MAX_INSTALL_OUTPUT_BYTES {
        return None;
    }
    let receipt: Value = serde_json::from_slice(stdout).ok()?;
    if receipt.get("schema")?.as_str()? != "simplicio.install-apply/v1"
        || receipt.get("status")?.as_str()? != "partial"
    {
        return None;
    }
    let actions = receipt.get("actions")?.as_array()?;
    if actions.is_empty() || actions.len() > MAX_INSTALL_ACTIONS {
        return None;
    }
    let mut names = std::collections::HashSet::new();
    let mut failed_steps = Vec::new();
    let mut unknown_failed_steps = 0;
    for action in actions {
        let name = action.get("name")?.as_str()?;
        if name.is_empty() || name.len() > 128 || !names.insert(name) {
            return None;
        }
        match action.get("status")?.as_str()? {
            "done" | "skipped" => {}
            "failed" => match known_step(name) {
                Some(step) => failed_steps.push(step),
                None => unknown_failed_steps += 1,
            },
            _ => return None,
        }
    }
    if failed_steps.is_empty() && unknown_failed_steps == 0 {
        return None;
    }
    Some(InstallDiagnostic {
        schema: "simplicio.desktop-install-diagnostic/v1",
        status: "partial",
        failed_steps,
        unknown_failed_steps,
    })
}

/// Public classifications contain no process output or native error strings.
/// None of these failures authorizes retrying an installation automatically.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum InstallFailure {
    Busy,
    PreflightUnavailable,
    PlanChanged,
    ExitCodeWithDiagnostic {
        code: i32,
        diagnostic: InstallDiagnostic,
    },
    // Command::output may fail while capturing/waiting, not only when spawning.
    // The absence of an output result does not prove there were no effects.
    OutputUnavailable,
    NotStarted,
    TimedOut,
    StderrTooLarge,
    CleanupUnconfirmed,
    ReconciliationRequired,
    ExitCode(i32),
    NoExitCode,
    InvalidJson,
    ResponseTooLarge,
    ReceiptUnconfirmed,
    AppliedSnapshotUnavailable,
}

impl InstallFailure {
    pub fn public_error(&self) -> InstallError {
        let mut error = serde_json::json!({
            "schema": "simplicio.desktop-install-error/v1",
            "code": self.public_code(),
        });
        if let Self::ExitCodeWithDiagnostic { diagnostic, .. } = self {
            error["diagnostic"] = serde_json::json!({
                "schema": diagnostic.schema,
                "status": diagnostic.status,
                "failedSteps": diagnostic.failed_steps,
                "unknownFailedSteps": diagnostic.unknown_failed_steps,
            });
        }
        error
    }

    /// Only fixed tags and an OS-provided i32 can cross the frontend boundary.
    pub fn public_code(&self) -> String {
        match self {
            Self::Busy => "integration_install_busy".into(),
            Self::PreflightUnavailable => "integration_preflight_unavailable".into(),
            Self::PlanChanged => "integration_plan_changed_review_again".into(),
            Self::ExitCodeWithDiagnostic { code, .. } => {
                format!("integration_install_exit_code:{code}")
            }
            Self::OutputUnavailable => "integration_install_output_unavailable".into(),
            Self::NotStarted => "integration_install_not_started".into(),
            Self::TimedOut => "integration_install_timeout".into(),
            Self::StderrTooLarge => "integration_install_stderr_too_large".into(),
            Self::CleanupUnconfirmed => "integration_install_cleanup_unconfirmed".into(),
            Self::ReconciliationRequired => "integration_install_reconciliation_required".into(),
            Self::ExitCode(code) => format!("integration_install_exit_code:{code}"),
            Self::NoExitCode => "integration_install_no_exit_code".into(),
            Self::InvalidJson => "integration_install_invalid_json".into(),
            Self::ResponseTooLarge => "integration_install_response_too_large".into(),
            Self::ReceiptUnconfirmed => "integration_install_receipt_unconfirmed".into(),
            Self::AppliedSnapshotUnavailable => {
                "integration_install_applied_snapshot_unavailable".into()
            }
        }
    }
}

/// Process-local mirror of the durable Desktop installation journal.
pub struct InstallAttempt {
    reconciliation_required: bool,
    last_error: Option<InstallError>,
}

impl InstallAttempt {
    pub const fn new() -> Self {
        Self {
            reconciliation_required: false,
            last_error: None,
        }
    }

    fn blocked(error: Option<InstallError>) -> Self {
        Self {
            reconciliation_required: true,
            last_error: error,
        }
    }

    /// Restore only the closed, sanitized projection. Missing evidence is clear;
    /// interrupted, malformed, or unreadable evidence fails closed.
    pub fn load(path: &Path) -> Self {
        let backup = journal_sibling(path, "bak");
        let temporary = journal_sibling(path, "tmp");
        let selected = if path.exists() {
            Some(path.to_path_buf())
        } else if backup.exists() {
            Some(backup)
        } else if temporary.exists() {
            Some(temporary)
        } else {
            None
        };
        let Some(selected) = selected else {
            return Self::new();
        };
        let Ok(bytes) = fs::read(selected) else {
            return Self::blocked(None);
        };
        if bytes.len() > 4096 {
            return Self::blocked(None);
        }
        let Ok(record) = serde_json::from_slice::<Value>(&bytes) else {
            return Self::blocked(None);
        };
        let Some(object) = record.as_object() else {
            return Self::blocked(None);
        };
        if object.len() != 3
            || record.get("schema").and_then(Value::as_str) != Some(INSTALL_ATTEMPT_SCHEMA)
        {
            return Self::blocked(None);
        }
        match record.get("state").and_then(Value::as_str) {
            Some("settled") if record.get("error").is_some_and(Value::is_null) => Self::new(),
            Some("in_progress") if record.get("error").is_some_and(Value::is_null) => {
                Self::blocked(None)
            }
            Some("reconciliation_required") => record
                .get("error")
                .and_then(sanitized_public_error)
                .map(|error| Self::blocked(Some(error)))
                .unwrap_or_else(|| Self::blocked(None)),
            _ => Self::blocked(None),
        }
    }

    pub fn pending_error(&self) -> Option<InstallError> {
        self.reconciliation_required.then(|| {
            self.last_error
                .clone()
                .unwrap_or_else(|| InstallFailure::ReconciliationRequired.public_error())
        })
    }

    pub fn diagnostic(&self) -> Value {
        match self.pending_error() {
            Some(error) => serde_json::json!({
                "schema": INSTALL_ATTEMPT_SCHEMA,
                "status": "reconciliation_required",
                "error": error,
            }),
            None => serde_json::json!({
                "schema": INSTALL_ATTEMPT_SCHEMA,
                "status": "clear",
                "error": null,
            }),
        }
    }

    pub fn check_ready(&self) -> Result<(), InstallFailure> {
        if self.reconciliation_required {
            Err(InstallFailure::ReconciliationRequired)
        } else {
            Ok(())
        }
    }

    pub fn begin(&mut self) -> Result<(), InstallFailure> {
        self.check_ready()?;
        self.reconciliation_required = true;
        self.last_error = None;
        Ok(())
    }

    pub fn begin_persisted(&mut self, path: &Path) -> Result<(), InstallFailure> {
        self.check_ready()?;
        write_journal(path, "in_progress", None).map_err(|_| InstallFailure::NotStarted)?;
        self.reconciliation_required = true;
        self.last_error = None;
        Ok(())
    }

    pub fn finish(&mut self, result: &Result<(), InstallFailure>) {
        // Only a validated applied receipt or proof that no Runtime started
        // settles this attempt. Exit failure can still mean partially applied.
        if matches!(result, Ok(()) | Err(InstallFailure::NotStarted)) {
            self.reconciliation_required = false;
            self.last_error = None;
        } else if let Err(failure) = result {
            self.last_error = Some(failure.public_error());
        }
    }

    pub fn finish_persisted(
        &mut self,
        path: &Path,
        result: &Result<(), InstallFailure>,
    ) -> Result<(), InstallFailure> {
        self.finish(result);
        let (state, error) = if self.reconciliation_required {
            ("reconciliation_required", self.pending_error())
        } else {
            ("settled", None)
        };
        if write_journal(path, state, error).is_err() {
            self.reconciliation_required = true;
            self.last_error = Some(InstallFailure::ReconciliationRequired.public_error());
            return Err(InstallFailure::ReconciliationRequired);
        }
        Ok(())
    }
}

/// Interprets one completed invocation without executing commands or retrying.
/// A nonzero/absent exit code takes precedence over even success-looking JSON.
/// Stderr is deliberately not accepted by this interface.
pub fn validate_install_output(
    exit_code: Option<i32>,
    stdout: &[u8],
) -> Result<(), InstallFailure> {
    match exit_code {
        Some(0) => {}
        Some(code) => {
            return Err(match partial_diagnostic(stdout) {
                Some(diagnostic) => InstallFailure::ExitCodeWithDiagnostic { code, diagnostic },
                None => InstallFailure::ExitCode(code),
            })
        }
        None => return Err(InstallFailure::NoExitCode),
    }
    if stdout.len() > MAX_INSTALL_OUTPUT_BYTES {
        return Err(InstallFailure::ResponseTooLarge);
    }
    let receipt: Value = serde_json::from_slice(stdout).map_err(|_| InstallFailure::InvalidJson)?;
    crate::desktop_queries::validate_install_receipt(&receipt)
        .map_err(|_| InstallFailure::ReceiptUnconfirmed)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn applied_receipt() -> Value {
        json!({
            "schema": "simplicio.install-apply/v1",
            "status": "applied",
            "actions": [
                { "name": "binary-copy", "status": "skipped" },
                { "name": "assistant-config:codex", "status": "done" },
                { "name": "install-manifest", "status": "done" }
            ]
        })
    }

    #[test]
    fn requires_a_zero_exit_code_even_with_a_successful_receipt() {
        let stdout = serde_json::to_vec(&applied_receipt()).unwrap();
        for code in [1, 7, -1, i32::MIN, i32::MAX] {
            assert_eq!(
                validate_install_output(Some(code), &stdout),
                Err(InstallFailure::ExitCode(code))
            );
        }
        assert_eq!(
            validate_install_output(None, &stdout),
            Err(InstallFailure::NoExitCode)
        );
        assert_eq!(validate_install_output(Some(0), &stdout), Ok(()));
    }

    #[test]
    fn an_ambiguous_install_cannot_be_authorized_again_by_releasing_the_mutex() {
        let lock = std::sync::Mutex::new(InstallAttempt::new());
        {
            let mut attempt = lock.lock().unwrap();
            attempt.begin().unwrap();
            attempt.finish(&Err(InstallFailure::TimedOut));
        }
        let mut next_dialog = lock.lock().unwrap();
        assert_eq!(
            next_dialog.check_ready(),
            Err(InstallFailure::ReconciliationRequired)
        );
        assert_eq!(
            next_dialog.begin(),
            Err(InstallFailure::ReconciliationRequired)
        );
    }

    #[test]
    fn only_a_confirmed_receipt_or_proven_no_start_can_settle_an_attempt() {
        for failure in [
            InstallFailure::TimedOut,
            InstallFailure::OutputUnavailable,
            InstallFailure::ExitCode(1),
            InstallFailure::NoExitCode,
            InstallFailure::InvalidJson,
            InstallFailure::ResponseTooLarge,
            InstallFailure::StderrTooLarge,
            InstallFailure::ReceiptUnconfirmed,
            InstallFailure::CleanupUnconfirmed,
        ] {
            let mut attempt = InstallAttempt::new();
            attempt.begin().unwrap();
            attempt.finish(&Err(failure));
            assert_eq!(attempt.begin(), Err(InstallFailure::ReconciliationRequired));
        }
        for result in [Ok(()), Err(InstallFailure::NotStarted)] {
            let mut attempt = InstallAttempt::new();
            attempt.begin().unwrap();
            attempt.finish(&result);
            assert!(attempt.begin().is_ok());
        }
    }

    #[test]
    fn keeps_exit_failure_precedence_over_invalid_or_oversized_output() {
        assert_eq!(
            validate_install_output(Some(9), b"invalid JSON"),
            Err(InstallFailure::ExitCode(9))
        );
        assert_eq!(
            validate_install_output(Some(9), &vec![b' '; MAX_INSTALL_OUTPUT_BYTES + 1]),
            Err(InstallFailure::ExitCode(9))
        );
    }

    #[test]
    fn distinguishes_invalid_json_from_an_unconfirmed_receipt() {
        for stdout in [b"".as_slice(), b"not JSON".as_slice(), &[0xff, 0xfe]] {
            assert_eq!(
                validate_install_output(Some(0), stdout),
                Err(InstallFailure::InvalidJson)
            );
        }
        for value in [
            Value::Null,
            json!([]),
            json!({ "schema": "simplicio.install-plan/v1", "status": "planned" }),
        ] {
            assert_eq!(
                validate_install_output(Some(0), &serde_json::to_vec(&value).unwrap()),
                Err(InstallFailure::ReceiptUnconfirmed)
            );
        }
    }

    #[test]
    fn enforces_the_output_byte_limit_before_json_parsing() {
        let mut stdout = serde_json::to_vec(&applied_receipt()).unwrap();
        stdout.resize(MAX_INSTALL_OUTPUT_BYTES, b' ');
        assert_eq!(validate_install_output(Some(0), &stdout), Ok(()));
        stdout.push(b' ');
        assert_eq!(
            validate_install_output(Some(0), &stdout),
            Err(InstallFailure::ResponseTooLarge)
        );
    }

    #[test]
    fn uses_the_canonical_receipt_validator_for_partial_and_incomplete_results() {
        let mut partial = applied_receipt();
        partial["status"] = json!("partial");
        let mut failed_action = applied_receipt();
        failed_action["actions"][1]["status"] = json!("failed");
        let mut duplicate_action = applied_receipt();
        duplicate_action["actions"]
            .as_array_mut()
            .unwrap()
            .push(json!({ "name": "binary-copy", "status": "done" }));
        let mut missing_binary = applied_receipt();
        missing_binary["actions"].as_array_mut().unwrap().remove(0);
        let mut missing_manifest = applied_receipt();
        missing_manifest["actions"].as_array_mut().unwrap().pop();
        let mut skipped_manifest = applied_receipt();
        skipped_manifest["actions"][2]["status"] = json!("skipped");
        let mut empty_actions = applied_receipt();
        empty_actions["actions"] = json!([]);

        for receipt in [
            partial,
            failed_action,
            duplicate_action,
            missing_binary,
            missing_manifest,
            skipped_manifest,
            empty_actions,
        ] {
            assert_eq!(
                validate_install_output(Some(0), &serde_json::to_vec(&receipt).unwrap()),
                Err(InstallFailure::ReceiptUnconfirmed)
            );
        }
    }

    #[test]
    fn never_includes_response_content_in_the_public_or_debug_error() {
        let stdout = br#"{"token":"DO_NOT_LEAK_TEST_SECRET","path":"/private/test-user"}"#;
        let failure = validate_install_output(Some(0), stdout).unwrap_err();
        assert_eq!(
            failure.public_code(),
            "integration_install_receipt_unconfirmed"
        );
        for rendered in [failure.public_code(), format!("{failure:?}")] {
            assert!(!rendered.contains("DO_NOT_LEAK_TEST_SECRET"));
            assert!(!rendered.contains("/private/test-user"));
        }
    }

    #[test]
    fn exposes_only_the_closed_error_contract_including_post_apply_verification() {
        for (failure, expected) in [
            (
                InstallFailure::OutputUnavailable,
                "integration_install_output_unavailable",
            ),
            (
                InstallFailure::NotStarted,
                "integration_install_not_started",
            ),
            (InstallFailure::TimedOut, "integration_install_timeout"),
            (
                InstallFailure::StderrTooLarge,
                "integration_install_stderr_too_large",
            ),
            (
                InstallFailure::CleanupUnconfirmed,
                "integration_install_cleanup_unconfirmed",
            ),
            (
                InstallFailure::ReconciliationRequired,
                "integration_install_reconciliation_required",
            ),
            (
                InstallFailure::ExitCode(1),
                "integration_install_exit_code:1",
            ),
            (
                InstallFailure::ExitCode(-1),
                "integration_install_exit_code:-1",
            ),
            (
                InstallFailure::NoExitCode,
                "integration_install_no_exit_code",
            ),
            (
                InstallFailure::InvalidJson,
                "integration_install_invalid_json",
            ),
            (
                InstallFailure::ResponseTooLarge,
                "integration_install_response_too_large",
            ),
            (
                InstallFailure::ReceiptUnconfirmed,
                "integration_install_receipt_unconfirmed",
            ),
            (
                InstallFailure::AppliedSnapshotUnavailable,
                "integration_install_applied_snapshot_unavailable",
            ),
        ] {
            assert_eq!(failure.public_code(), expected);
        }
    }
}

#[cfg(test)]
mod diagnostic_tests {
    use super::*;
    use serde_json::json;

    fn partial(actions: Value) -> Vec<u8> {
        serde_json::to_vec(&json!({
            "schema":"simplicio.install-apply/v1", "status":"partial", "actions":actions
        }))
        .unwrap()
    }

    #[test]
    fn partial_exit_exposes_only_known_steps_and_does_not_release_attempt() {
        let stdout = partial(json!([
            {"name":"binary-copy","status":"done"},
            {"name":"assistant-config:hermes","status":"failed","detail":"DO_NOT_LEAK /private/test-user"},
            {"name":"unknown-private-name","status":"failed","token":"DO_NOT_LEAK"},
            {"name":"install-manifest","status":"done"}
        ]));
        let failure = validate_install_output(Some(1), &stdout).unwrap_err();
        let projection = serde_json::to_value(failure.public_error()).unwrap();
        assert_eq!(projection["code"], "integration_install_exit_code:1");
        assert_eq!(projection["diagnostic"]["failedSteps"], json!(["hermes"]));
        assert_eq!(projection["diagnostic"]["unknownFailedSteps"], 1);
        for rendered in [projection.to_string(), format!("{failure:?}")] {
            for secret in ["DO_NOT_LEAK", "/private/test-user", "unknown-private-name"] {
                assert!(!rendered.contains(secret));
            }
        }
        let mut attempt = InstallAttempt::new();
        attempt.begin().unwrap();
        attempt.finish(&Err(failure));
        assert_eq!(
            attempt.check_ready(),
            Err(InstallFailure::ReconciliationRequired)
        );
        assert_eq!(
            validate_install_output(Some(0), &stdout),
            Err(InstallFailure::ReceiptUnconfirmed)
        );
    }

    #[test]
    fn malformed_partial_diagnostics_never_override_nonzero_exit() {
        for actions in [
            json!([]),
            json!([{"name":"assistant-config:hermes","status":"unknown"}]),
            json!([{"name":"assistant-config:hermes","status":"done"}]),
            json!([{"name":"assistant-config:hermes","status":"failed"},{"name":"assistant-config:hermes","status":"done"}]),
            json!([{"name":"","status":"failed"}]),
            Value::Null,
        ] {
            let failure = validate_install_output(Some(7), &partial(actions)).unwrap_err();
            assert_eq!(failure, InstallFailure::ExitCode(7));
            assert!(serde_json::to_value(failure.public_error())
                .unwrap()
                .get("diagnostic")
                .is_none());
        }
        for stdout in [b"not JSON".to_vec(), vec![b' '; MAX_INSTALL_OUTPUT_BYTES + 1],
            br#"{"schema":"wrong","status":"partial","actions":[{"name":"binary-copy","status":"failed"}]}"#.to_vec()] {
            assert_eq!(validate_install_output(Some(7), &stdout), Err(InstallFailure::ExitCode(7)));
        }
    }

    #[test]
    fn exactly_128_unique_actions_are_bounded_and_129_are_refused() {
        let mut actions: Vec<Value> = (0..128)
            .map(|i| {
                json!({
                    "name":format!("private-{i}"),"status":"failed"
                })
            })
            .collect();
        let failure = validate_install_output(Some(1), &partial(json!(actions))).unwrap_err();
        let projection = serde_json::to_value(failure.public_error()).unwrap();
        assert_eq!(projection["diagnostic"]["unknownFailedSteps"], 128);
        assert!(!projection.to_string().contains("private-"));
        actions.push(json!({"name":"one-too-many","status":"failed"}));
        assert_eq!(
            validate_install_output(Some(1), &partial(json!(actions))),
            Err(InstallFailure::ExitCode(1))
        );
    }

    fn journal_path(name: &str) -> std::path::PathBuf {
        static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(1);
        let id = NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        std::env::temp_dir().join(format!(
            "simplicio-desktop-install-{name}-{}-{id}.json",
            std::process::id()
        ))
    }

    fn remove_journal(path: &std::path::Path) {
        let _ = std::fs::remove_file(path);
        let _ = std::fs::remove_file(path.with_extension("json.bak"));
        let _ = std::fs::remove_file(path.with_extension("json.tmp"));
    }

    #[test]
    fn durable_journal_preserves_the_sanitized_code_one_diagnostic_after_restart() {
        let path = journal_path("partial");
        remove_journal(&path);
        let stdout = partial(json!([
            {"name":"assistant-config:hermes","status":"failed","detail":"DO_NOT_LEAK /private/test-user"},
            {"name":"private-step","status":"failed","token":"DO_NOT_LEAK"}
        ]));
        let failure = validate_install_output(Some(1), &stdout).unwrap_err();
        let mut attempt = InstallAttempt::new();
        attempt.begin_persisted(&path).unwrap();
        attempt.finish_persisted(&path, &Err(failure)).unwrap();

        let restored = InstallAttempt::load(&path);
        let diagnostic = restored
            .pending_error()
            .expect("durable pending diagnostic");
        assert_eq!(diagnostic["code"], "integration_install_exit_code:1");
        assert_eq!(diagnostic["diagnostic"]["failedSteps"], json!(["hermes"]));
        assert_eq!(diagnostic["diagnostic"]["unknownFailedSteps"], 1);
        let rendered = diagnostic.to_string();
        for secret in ["DO_NOT_LEAK", "/private/test-user", "private-step"] {
            assert!(!rendered.contains(secret));
        }
        remove_journal(&path);
    }

    #[test]
    fn an_interrupted_or_malformed_journal_fails_closed_after_restart() {
        for contents in [
            r#"{"schema":"simplicio.desktop-install-attempt/v1","state":"in_progress"}"#,
            r#"{"schema":"wrong","state":"failed","error":{"token":"DO_NOT_LEAK"}}"#,
        ] {
            let path = journal_path("uncertain");
            remove_journal(&path);
            std::fs::write(&path, contents).unwrap();
            let restored = InstallAttempt::load(&path);
            let diagnostic = restored
                .pending_error()
                .expect("uncertain attempts stay blocked");
            assert_eq!(
                diagnostic["code"],
                "integration_install_reconciliation_required"
            );
            assert!(!diagnostic.to_string().contains("DO_NOT_LEAK"));
            remove_journal(&path);
        }
    }

    #[test]
    fn a_settled_attempt_is_clear_after_restart() {
        let path = journal_path("settled");
        remove_journal(&path);
        let mut attempt = InstallAttempt::new();
        attempt.begin_persisted(&path).unwrap();
        attempt.finish_persisted(&path, &Ok(())).unwrap();
        let restored = InstallAttempt::load(&path);
        assert!(restored.pending_error().is_none());
        assert!(restored.check_ready().is_ok());
        remove_journal(&path);
    }
}
