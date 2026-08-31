use serde_json::Value;

const MAX_INSTALL_OUTPUT_BYTES: usize = 64 * 1024;

/// Public classifications contain no process output or native error strings.
/// None of these failures authorizes retrying an installation automatically.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum InstallFailure {
    // Command::output may fail while capturing/waiting, not only when spawning.
    // The absence of an output result does not prove there were no effects.
    OutputUnavailable,
    ExitCode(i32),
    NoExitCode,
    InvalidJson,
    ResponseTooLarge,
    ReceiptUnconfirmed,
    AppliedSnapshotUnavailable,
}

impl InstallFailure {
    /// Only fixed tags and an OS-provided i32 can cross the frontend boundary.
    pub fn public_code(&self) -> String {
        match self {
            Self::OutputUnavailable => "integration_install_output_unavailable".into(),
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

/// Interprets one completed invocation without executing commands or retrying.
/// A nonzero/absent exit code takes precedence over even success-looking JSON.
/// Stderr is deliberately not accepted by this interface.
pub fn validate_install_output(
    exit_code: Option<i32>,
    stdout: &[u8],
) -> Result<(), InstallFailure> {
    match exit_code {
        Some(0) => {}
        Some(code) => return Err(InstallFailure::ExitCode(code)),
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
