//! Fresh, auth-only access guard for read-only Desktop queries.
//! The caller owns process deadlines; this does not supervise filesystem scans.
use serde_json::Value;

const UNVERIFIED: &str = "desktop_access_unverified";
const AUTH_STATUS_ARGS: [&str; 3] = ["auth", "status", "--json"];

/// Query once per invocation. No snapshot fallback, cached permit, or retry.
pub fn require_fresh(query: impl FnOnce(&[&str]) -> Result<Value, String>) -> Result<(), String> {
    let status = query(&AUTH_STATUS_ARGS).map_err(safe_query_failure)?;
    require_explicit_active(&status)
}

fn require_explicit_active(status: &Value) -> Result<(), String> {
    // The public legacy fixture establishes this positive contract only.
    // Unknown/negative states are not evidence of an inactive subscription:
    // without a documented negative auth-status payload, keep them unverified.
    if status.get("ok").and_then(Value::as_bool) != Some(true)
        || status.pointer("/identity/status").and_then(Value::as_str) != Some("active")
        || status
            .pointer("/entitlement/status")
            .and_then(Value::as_str)
            != Some("active")
        || status
            .pointer("/entitlement/active")
            .and_then(Value::as_bool)
            != Some(true)
        || status.get("error").is_some_and(|error| !error.is_null())
    {
        return Err(UNVERIFIED.into());
    }
    Ok(())
}

fn safe_query_failure(error: String) -> String {
    // Exact query-lane codes from lib.rs::runtime_failure_code(ProcessFailure).
    // Never allow an arbitrary runtime_* prefix, suffix, stderr, or account data.
    match error.as_str() {
        "runtime_not_started"
        | "runtime_query_timeout"
        | "runtime_stdout_limit"
        | "runtime_stderr_limit"
        | "runtime_output_unavailable"
        | "runtime_process_cleanup_unconfirmed" => error,
        _ => UNVERIFIED.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::cell::Cell;

    fn active() -> Value {
        json!({
            "ok": true,
            "identity": { "status": "active" },
            "entitlement": { "status": "active", "active": true }
        })
    }

    fn check(status: Value) -> Result<(), String> {
        require_fresh(|args| {
            assert_eq!(args, ["auth", "status", "--json"]);
            Ok(status)
        })
    }

    #[test]
    fn accepts_only_explicit_active_with_one_fixed_read_only_query() {
        let calls = Cell::new(0);
        assert_eq!(
            require_fresh(|args| {
                calls.set(calls.get() + 1);
                assert_eq!(args, ["auth", "status", "--json"]);
                Ok(active())
            }),
            Ok(())
        );
        assert_eq!(calls.get(), 1);
    }

    #[test]
    fn rejects_missing_fields_and_nonobject_payloads() {
        for payload in [
            Value::Null,
            json!({}),
            json!([]),
            json!(true),
            json!("active"),
        ] {
            assert_eq!(check(payload), Err(UNVERIFIED.into()));
        }
        for key in ["ok", "identity", "entitlement"] {
            let mut payload = active();
            payload.as_object_mut().unwrap().remove(key);
            assert_eq!(check(payload), Err(UNVERIFIED.into()));
        }
        for (parent, key) in [
            ("identity", "status"),
            ("entitlement", "status"),
            ("entitlement", "active"),
        ] {
            let mut payload = active();
            payload[parent].as_object_mut().unwrap().remove(key);
            assert_eq!(check(payload), Err(UNVERIFIED.into()));
        }
    }

    #[test]
    fn rejects_wrong_types_without_coercion() {
        for (pointer, wrong) in [
            ("/ok", json!("true")),
            ("/ok", json!(1)),
            ("/identity", json!("active")),
            ("/identity/status", json!(true)),
            ("/identity/status", json!(["active"])),
            ("/entitlement", json!([])),
            ("/entitlement/status", json!(true)),
            ("/entitlement/status", json!({"active": true})),
            ("/entitlement/active", json!("true")),
            ("/entitlement/active", json!(1)),
        ] {
            let mut payload = active();
            *payload.pointer_mut(pointer).unwrap() = wrong;
            assert_eq!(check(payload), Err(UNVERIFIED.into()));
        }
        for pointer in [
            "/ok",
            "/identity/status",
            "/entitlement/status",
            "/entitlement/active",
        ] {
            let mut payload = active();
            *payload.pointer_mut(pointer).unwrap() = Value::Null;
            assert_eq!(check(payload), Err(UNVERIFIED.into()));
        }
    }

    #[test]
    fn unknown_status_cannot_be_promoted_by_an_active_flag() {
        for status in ["unknown", "error", "unavailable", "", "ACTIVE", "active "] {
            let mut identity = active();
            identity["identity"]["status"] = json!(status);
            assert_eq!(check(identity), Err(UNVERIFIED.into()));
            for flag in [false, true] {
                let mut entitlement = active();
                entitlement["entitlement"]["status"] = json!(status);
                entitlement["entitlement"]["active"] = json!(flag);
                assert_eq!(check(entitlement), Err(UNVERIFIED.into()));
            }
        }
    }

    #[test]
    fn rejects_contradictory_success_and_error_states() {
        let mut inactive_flag = active();
        inactive_flag["entitlement"]["active"] = json!(false);
        assert_eq!(check(inactive_flag), Err(UNVERIFIED.into()));
        let mut unsuccessful = active();
        unsuccessful["ok"] = json!(false);
        assert_eq!(check(unsuccessful), Err(UNVERIFIED.into()));
        let mut with_error = active();
        with_error["error"] = json!({"message": "private diagnostic, not UI text"});
        assert_eq!(check(with_error), Err(UNVERIFIED.into()));
    }

    #[test]
    fn undocumented_negative_statuses_remain_unverified_not_subscription_denials() {
        for status in ["revoked", "expired", "signed_out", "inactive", "denied"] {
            let mut payload = active();
            payload["identity"]["status"] = json!(status);
            payload["entitlement"]["status"] = json!(status);
            payload["entitlement"]["active"] = json!(false);
            assert_eq!(check(payload), Err(UNVERIFIED.into()));
        }
    }

    #[test]
    fn preserves_only_exact_safe_query_process_failure_codes() {
        for code in [
            "runtime_not_started",
            "runtime_query_timeout",
            "runtime_stdout_limit",
            "runtime_stderr_limit",
            "runtime_output_unavailable",
            "runtime_process_cleanup_unconfirmed",
        ] {
            let calls = Cell::new(0);
            let result = require_fresh(|args| {
                calls.set(calls.get() + 1);
                assert_eq!(args, ["auth", "status", "--json"]);
                Err(code.into())
            });
            assert_eq!(result, Err(code.into()));
            assert_eq!(calls.get(), 1);
        }
    }

    #[test]
    fn drops_raw_errors_pii_like_text_unknown_prefixes_and_nonquery_codes() {
        for error in [
            "",
            "person@example.test /private/test-path",
            "runtime_arbitrary_private_detail",
            "runtime_query_timeout: private diagnostic",
            "runtime_query_timeout\nprivate diagnostic",
            " runtime_not_started",
            "runtime_not_started ",
            "runtime_oauth_timeout",
            "runtime_install_timeout",
            "desktop_access_not_active",
            "Simplicio Runtime devolveu JSON inválido",
        ] {
            assert_eq!(require_fresh(|_| Err(error.into())), Err(UNVERIFIED.into()));
        }
    }

    #[test]
    fn does_not_cache_active_access_across_a_later_revocation() {
        let mut revoked = active();
        revoked["identity"]["status"] = json!("revoked");
        revoked["entitlement"]["active"] = json!(false);
        let mut responses = [active(), revoked].into_iter();
        let calls = Cell::new(0);
        let mut query = |args: &[&str]| {
            calls.set(calls.get() + 1);
            assert_eq!(args, ["auth", "status", "--json"]);
            Ok(responses.next().expect("one fresh response per query"))
        };
        assert_eq!(require_fresh(&mut query), Ok(()));
        assert_eq!(require_fresh(&mut query), Err(UNVERIFIED.into()));
        assert_eq!(calls.get(), 2);
    }

    #[test]
    fn does_not_reuse_success_when_a_later_query_fails() {
        let mut responses = [Ok(active()), Err("runtime_query_timeout".into())].into_iter();
        let mut calls = 0;
        let mut query = |args: &[&str]| {
            calls += 1;
            assert_eq!(args, ["auth", "status", "--json"]);
            responses.next().unwrap()
        };
        assert_eq!(require_fresh(&mut query), Ok(()));
        assert_eq!(
            require_fresh(&mut query),
            Err("runtime_query_timeout".into())
        );
        assert_eq!(calls, 2);
    }
}
