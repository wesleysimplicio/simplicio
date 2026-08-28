use serde_json::Value;
use std::ffi::OsString;
use std::process::Command;

const SNAPSHOT_SCHEMA: &str = "simplicio.desktop-snapshot/v1";

fn runtime_binary() -> OsString {
    std::env::var_os("SIMPLICIO_RUNTIME_BIN").unwrap_or_else(|| OsString::from("simplicio"))
}

fn run_runtime(args: &[&str]) -> Result<Value, String> {
    let output = Command::new(runtime_binary())
        .args(args)
        .env("SIMPLICIO_DESKTOP_BRIDGE", "1")
        .output()
        .map_err(|_| "Simplicio Runtime não encontrado".to_string())?;

    if !output.status.success() {
        return Err(format!(
            "Simplicio Runtime encerrou com código {}",
            output.status.code().unwrap_or(-1)
        ));
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|_| "Simplicio Runtime devolveu JSON inválido".to_string())
}

fn validate_snapshot(value: Value) -> Result<Value, String> {
    match value.get("schema").and_then(Value::as_str) {
        Some(SNAPSHOT_SCHEMA) => Ok(value),
        _ => Err("Contrato de snapshot do Runtime incompatível".to_string()),
    }
}

#[tauri::command]
fn desktop_snapshot() -> Result<Value, String> {
    validate_snapshot(run_runtime(&["desktop", "snapshot", "--json"])?)
}

#[tauri::command]
fn runtime_status() -> Result<Value, String> {
    run_runtime(&["desktop", "status", "--json"])
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![desktop_snapshot, runtime_status])
        .run(tauri::generate_context!())
        .expect("failed to run Simplicio Desktop");
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn accepts_the_versioned_desktop_snapshot() {
        assert!(validate_snapshot(json!({ "schema": SNAPSHOT_SCHEMA })).is_ok());
    }

    #[test]
    fn rejects_an_unversioned_payload() {
        let error = validate_snapshot(json!({ "status": "healthy" })).unwrap_err();
        assert_eq!(error, "Contrato de snapshot do Runtime incompatível");
    }
}
