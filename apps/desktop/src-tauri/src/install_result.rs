use serde_json::Value;

const MAX_INSTALL_OUTPUT_BYTES: usize = 64 * 1024;

const MAX_INSTALL_ACTIONS: usize = 128;

/// A closed projection: no raw action name, path, detail, stdout or stderr.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InstallDiagnostic {
    schema: &'static str,
    status: &'static str,
    failed_steps: Vec<&'static str>,
    unknown_failed_steps: usize,
}

pub type InstallError = Value;

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

/// This state survives closing/reopening the dialog, not application restart.
/// It is not a substitute for a durable Runtime effect-reconciliation receipt.
pub struct InstallAttempt {
    reconciliation_required: bool,
}

impl InstallAttempt {
    pub const fn new() -> Self {
        Self {
            reconciliation_required: false,
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
        Ok(())
    }

    pub fn finish(&mut self, result: &Result<(), InstallFailure>) {
        // Only a validated applied receipt or proof that no Runtime started
        // settles this attempt. Exit failure can still mean partially applied.
        if matches!(result, Ok(()) | Err(InstallFailure::NotStarted)) {
            self.reconciliation_required = false;
        }
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
}
