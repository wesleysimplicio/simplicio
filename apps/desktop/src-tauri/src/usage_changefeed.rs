//! Validated, bounded bridge for the Runtime usage changefeed.
use serde_json::Value;

const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
const MAX_EVENT_BYTES: usize = 256 * 1024;
const SCHEMA: &str = "simplicio.desktop-usage-changefeed/v1";
const PROJECTION_SCHEMA: &str = "simplicio.desktop-unified-usage/v1";

fn safe_text<'a>(value: Option<&'a Value>, code: &str) -> Result<&'a str, String> {
    let text = value
        .and_then(Value::as_str)
        .filter(|text| !text.is_empty() && text.len() <= 256)
        .ok_or(code)?;
    if text
        .bytes()
        .any(|byte| byte == 0 || byte < 0x20 || byte == 0x7f)
    {
        return Err(code.into());
    }
    Ok(text)
}

fn safe_integer(value: Option<&Value>, code: &str) -> Result<u64, String> {
    value
        .and_then(Value::as_u64)
        .filter(|number| *number <= MAX_SAFE_INTEGER)
        .ok_or(code.into())
}

pub(crate) fn query_args(after_sequence: u64, after_revision: u64) -> Result<Vec<String>, String> {
    if after_sequence > MAX_SAFE_INTEGER || after_revision > MAX_SAFE_INTEGER {
        return Err("usage_changefeed_cursor_invalid".into());
    }
    Ok(vec![
        "usage".into(),
        "changefeed".into(),
        "--json".into(),
        "--after-sequence".into(),
        after_sequence.to_string(),
        "--after-revision".into(),
        after_revision.to_string(),
    ])
}

pub(crate) fn validate_event(
    value: Value,
    after_sequence: u64,
    after_revision: u64,
) -> Result<Value, String> {
    let object = value.as_object().ok_or("usage_changefeed_invalid")?;
    if object.get("schema").and_then(Value::as_str) != Some(SCHEMA) {
        return Err("usage_changefeed_invalid".into());
    }
    safe_text(object.get("event_id"), "usage_changefeed_invalid")?;
    let sequence = safe_integer(object.get("sequence"), "usage_changefeed_invalid")?;
    let revision = safe_integer(object.get("revision"), "usage_changefeed_invalid")?;
    let kind = safe_text(object.get("kind"), "usage_changefeed_invalid")?;
    if !matches!(kind, "snapshot" | "delta")
        || sequence <= after_sequence
        || revision <= after_revision
    {
        return Err("usage_changefeed_invalid".into());
    }
    safe_integer(object.get("generated_at_epoch"), "usage_changefeed_invalid")?;
    let projection = object
        .get("projection")
        .and_then(Value::as_object)
        .ok_or("usage_changefeed_invalid")?;
    if projection.get("schema").and_then(Value::as_str) != Some(PROJECTION_SCHEMA)
        || projection.get("source").and_then(Value::as_str) != Some("runtime")
        || projection
            .get("metadata")
            .and_then(Value::as_object)
            .and_then(|metadata| metadata.get("redacted"))
            .and_then(Value::as_bool)
            != Some(true)
    {
        return Err("usage_changefeed_untrusted_projection".into());
    }
    if serde_json::to_vec(&value)
        .map_err(|_| "usage_changefeed_invalid")?
        .len()
        > MAX_EVENT_BYTES
    {
        return Err("usage_changefeed_too_large".into());
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn event() -> Value {
        json!({
            "schema": SCHEMA,
            "event_id": "event-1",
            "sequence": 1,
            "revision": 1,
            "kind": "snapshot",
            "generated_at_epoch": 1700000000,
            "projection": {
                "schema": PROJECTION_SCHEMA,
                "source": "runtime",
                "metadata": {"redacted": true}
            }
        })
    }

    #[test]
    fn builds_bounded_runtime_cursor_arguments() {
        assert_eq!(
            query_args(2, 3).unwrap(),
            [
                "usage",
                "changefeed",
                "--json",
                "--after-sequence",
                "2",
                "--after-revision",
                "3"
            ]
        );
        assert!(query_args(MAX_SAFE_INTEGER + 1, 0).is_err());
    }

    #[test]
    fn validates_redacted_in_order_events() {
        assert!(validate_event(event(), 0, 0).is_ok());
        assert!(validate_event(event(), 1, 1).is_err());
        let mut untrusted = event();
        untrusted["projection"]["metadata"]["redacted"] = json!(false);
        assert_eq!(
            validate_event(untrusted, 0, 0).unwrap_err(),
            "usage_changefeed_untrusted_projection"
        );
    }
}
