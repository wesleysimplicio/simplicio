//! Google authentication is negotiated before any account effect.
//! The capability probe and login use one selected Runtime candidate.
use crate::runtime_process::ProcessFailure;
use std::ffi::{OsStr, OsString};
use std::process::Output;

pub const LOGIN_ARGS: &[&str] = &["login", "google", "--authentication-only", "--json"];
pub const STATUS_ARGS: &[&str] = &["desktop", "status", "--json"];
const MAX_AUTH_BYTES: usize = 64 * 1024;

/// Reject overlapping authentication effects, including their confirming snapshots.
pub fn exclusive<T>(gate: &std::sync::Mutex<()>, operation: impl FnOnce() -> Result<T, String>) -> Result<T, String> {
    let _guard = gate.try_lock().map_err(|error| match error {
        std::sync::TryLockError::WouldBlock => "runtime_auth_busy".to_string(),
        std::sync::TryLockError::Poisoned(_) => "runtime_auth_state_unavailable".to_string(),
    })?;
    operation()
}

fn supported(output: &Output) -> bool {
    if !output.status.success() || output.stdout.len() > MAX_AUTH_BYTES {
        return false;
    }
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(&output.stdout) else {
        return false;
    };
    value["schema"] == "simplicio.desktop.app/v1"
        && value["action"] == "status"
        && value["authentication"]["schema"] == "simplicio.desktop-auth-capabilities/v1"
        && value["authentication"]["authentication_only"] == true
}

fn confirmed(output: &Output) -> bool {
    if !output.status.success() || output.stdout.len() > MAX_AUTH_BYTES {
        return false;
    }
    let Ok(text) = std::str::from_utf8(&output.stdout) else {
        return false;
    };
    // Pending device-authorization events may precede the terminal JSONL event.
    let Some(last) = text.lines().rev().find(|line| !line.trim().is_empty()) else {
        return false;
    };
    let Ok(value) = serde_json::from_str::<serde_json::Value>(last) else {
        return false;
    };
    value["schema"] == "simplicio.auth-login/v1"
        && value["status"] == "authenticated"
        && value["bootstrap"]["status"] == "skipped"
        && value["bootstrap"]["reason"] == "authentication_only"
}

/// Only a failed spawn before the read-only probe may select another candidate.
/// No process output, credential, argument, or executable path becomes an error.
pub fn authenticate(
    candidates: impl IntoIterator<Item = OsString>,
    mut capture: impl FnMut(&OsStr, &'static [&'static str]) -> Result<Output, ProcessFailure>,
) -> Result<(), String> {
    for binary in candidates {
        let capability = match capture(&binary, STATUS_ARGS) {
            Err(failure) if failure.may_try_another_candidate() => continue,
            Err(failure) => return Err(crate::runtime_failure_code(STATUS_ARGS, failure)),
            Ok(output) => output,
        };
        if !supported(&capability) {
            return Err("runtime_auth_only_unsupported".into());
        }
        let result = capture(&binary, LOGIN_ARGS)
            .map_err(|failure| crate::runtime_failure_code(LOGIN_ARGS, failure))?;
        if !confirmed(&result) {
            return Err("runtime_auth_result_unconfirmed".into());
        }
        return Ok(());
    }
    Err("runtime_not_started".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime_process::{ChildState, FailureKind};
    use serde_json::{json, Value};

    #[test]
    fn gate_rejects_overlap_and_releases_after_failure() {
        let gate = std::sync::Mutex::new(());
        let result: Result<(), String> = exclusive(&gate, || {
            assert_eq!(exclusive(&gate, || -> Result<(), String> { panic!("overlapping effect") }), Err("runtime_auth_busy".into()));
            Err("provider_failed".into())
        });
        assert_eq!(result, Err("provider_failed".into()));
        assert_eq!(exclusive(&gate, || Ok(42)), Ok(42));
    }

    fn output(code: i32, value: Value) -> Output {
        bytes_output(code, serde_json::to_vec(&value).unwrap())
    }

    fn bytes_output(code: i32, stdout: Vec<u8>) -> Output {
        #[cfg(unix)]
        use std::os::unix::process::ExitStatusExt;
        #[cfg(windows)]
        use std::os::windows::process::ExitStatusExt;
        #[cfg(unix)]
        let status = std::process::ExitStatus::from_raw(code << 8);
        #[cfg(windows)]
        let status = std::process::ExitStatus::from_raw(code as u32);
        Output {
            status,
            stdout,
            stderr: b"SECRET_STDERR /private/example".to_vec(),
        }
    }

    fn capability() -> Value {
        json!({
            "schema": "simplicio.desktop.app/v1",
            "action": "status",
            "authentication": {
                "schema": "simplicio.desktop-auth-capabilities/v1",
                "authentication_only": true
            }
        })
    }

    fn receipt() -> Value {
        json!({
            "schema": "simplicio.auth-login/v1",
            "status": "authenticated",
            "bootstrap": { "status": "skipped", "reason": "authentication_only" }
        })
    }

    fn candidates() -> Vec<OsString> {
        vec!["bundled".into(), "managed".into()]
    }

    #[test]
    fn rejects_legacy_missing_false_malformed_or_oversized_capability_before_login() {
        let mut disabled = capability();
        disabled["authentication"]["authentication_only"] = json!(false);
        let mut untyped = capability();
        untyped["authentication"]["authentication_only"] = json!("true");
        let mut wrong_schema = capability();
        wrong_schema["schema"] = json!("simplicio.desktop-app/v1");
        let mut wrong_action = capability();
        wrong_action["action"] = json!("login");
        let mut wrong_auth_schema = capability();
        wrong_auth_schema["authentication"]["schema"] = json!("unknown");
        let bad = vec![
            output(0, json!({"schema":"simplicio.desktop.app/v1"})),
            output(0, Value::Null),
            output(0, disabled),
            output(0, untyped),
            output(0, wrong_schema),
            output(0, wrong_auth_schema),
            output(0, wrong_action),
            output(1, capability()),
            bytes_output(0, b"SECRET_OUTPUT".to_vec()),
            bytes_output(0, vec![b' '; MAX_AUTH_BYTES + 1]),
        ];
        for response in bad {
            let mut response = Some(response);
            let mut calls = 0;
            let result = authenticate(candidates(), |binary, args| {
                calls += 1;
                assert_eq!(binary, OsStr::new("bundled"));
                assert_eq!(args, STATUS_ARGS);
                Ok(response.take().unwrap())
            });
            assert_eq!(result, Err("runtime_auth_only_unsupported".into()));
            assert_eq!(calls, 1);
        }
    }

    #[test]
    fn a_verified_candidate_is_used_for_exact_authentication_only_arguments() {
        let mut calls = vec![];
        let result = authenticate(candidates(), |binary, args| {
            calls.push((binary.to_os_string(), args.to_vec()));
            if args == STATUS_ARGS {
                Ok(output(0, capability()))
            } else {
                assert_eq!(args, LOGIN_ARGS);
                Ok(output(0, receipt()))
            }
        });
        assert_eq!(result, Ok(()));
        assert_eq!(
            calls,
            vec![
                (OsString::from("bundled"), STATUS_ARGS.to_vec()),
                (OsString::from("bundled"), LOGIN_ARGS.to_vec()),
            ]
        );
    }

    #[test]
    fn fallback_is_only_for_an_unstarted_read_only_probe() {
        let mut calls = vec![];
        let result = authenticate(candidates(), |binary, args| {
            calls.push((binary.to_os_string(), args.to_vec()));
            if binary == OsStr::new("bundled") {
                Err(ProcessFailure {
                    kind: FailureKind::Spawn,
                    child_state: ChildState::NotStarted,
                })
            } else if args == STATUS_ARGS {
                Ok(output(0, capability()))
            } else {
                Ok(output(0, receipt()))
            }
        });
        assert_eq!(result, Ok(()));
        assert_eq!(
            calls,
            vec![
                (OsString::from("bundled"), STATUS_ARGS.to_vec()),
                (OsString::from("managed"), STATUS_ARGS.to_vec()),
                (OsString::from("managed"), LOGIN_ARGS.to_vec()),
            ]
        );
    }

    #[test]
    fn never_falls_back_after_a_verified_candidate_even_if_login_does_not_spawn() {
        let mut calls = 0;
        let result = authenticate(candidates(), |binary, args| {
            calls += 1;
            assert_eq!(binary, OsStr::new("bundled"));
            if args == STATUS_ARGS {
                Ok(output(0, capability()))
            } else {
                Err(ProcessFailure {
                    kind: FailureKind::Spawn,
                    child_state: ChildState::NotStarted,
                })
            }
        });
        assert_eq!(result, Err("runtime_not_started".into()));
        assert_eq!(calls, 2);
    }

    #[test]
    fn probe_timeout_or_unconfirmed_cleanup_never_launches_login() {
        for failure in [
            ProcessFailure {
                kind: FailureKind::Deadline,
                child_state: ChildState::Reaped,
            },
            ProcessFailure {
                kind: FailureKind::Capture,
                child_state: ChildState::Retained,
            },
        ] {
            let mut calls = 0;
            let result = authenticate(candidates(), |_, args| {
                calls += 1;
                assert_eq!(args, STATUS_ARGS);
                Err(failure)
            });
            assert!(result.is_err());
            assert_eq!(calls, 1);
        }
    }

    #[test]
    fn requires_successful_terminal_auth_only_receipt_and_never_reflects_output() {
        let mut bootstrapped = receipt();
        bootstrapped["bootstrap"]["status"] = json!("applied");
        let mut unknown = receipt();
        unknown["status"] = json!("unknown");
        let mut legacy = receipt();
        legacy.as_object_mut().unwrap().remove("schema");
        for response in [
            output(1, receipt()),
            output(0, bootstrapped),
            output(0, unknown),
            output(0, legacy),
            bytes_output(0, b"SECRET_OUTPUT /private/example".to_vec()),
            bytes_output(0, vec![0xff]),
            bytes_output(0, vec![b' '; MAX_AUTH_BYTES + 1]),
        ] {
            let mut response = Some(response);
            let mut calls = 0;
            let result = authenticate(candidates(), |_, args| {
                calls += 1;
                if args == STATUS_ARGS {
                    Ok(output(0, capability()))
                } else {
                    Ok(response.take().unwrap())
                }
            });
            assert_eq!(result, Err("runtime_auth_result_unconfirmed".into()));
            assert_eq!(calls, 2);
            assert!(!format!("{result:?}").contains("SECRET"));
        }
    }

    #[test]
    fn accepts_jsonl_pending_then_terminal_receipt_but_not_trailing_pending_or_garbage() {
        let success = serde_json::to_string(&receipt()).unwrap();
        let pending = r#"{"status":"pending","device_code":"SECRET"}"#;
        assert!(confirmed(&bytes_output(
            0,
            format!("{pending}\n{success}\n\n").into_bytes()
        )));
        assert!(!confirmed(&bytes_output(
            0,
            format!("{success}\n{pending}").into_bytes()
        )));
        assert!(!confirmed(&bytes_output(
            0,
            format!("{success}\ngarbage").into_bytes()
        )));
    }
}
