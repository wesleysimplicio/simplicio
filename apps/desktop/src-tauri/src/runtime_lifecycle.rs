use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fmt::Write as _;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

const SCHEMA: &str = "simplicio.desktop-runtime-lifecycle/v1";
const MANAGED_RECEIPT_SCHEMA: &str = "simplicio.desktop-runtime-receipt/v1";
const MANAGED_RECEIPT_NAME: &str = "desktop-runtime-receipt.json";
const EXECUTABLE_NAME: &str = "simplicio";

fn error(code: &str) -> String {
    code.to_string()
}

fn target_path(home: &Path) -> PathBuf {
    home.join(".simplicio").join("bin").join(if cfg!(windows) {
        "simplicio.exe"
    } else {
        EXECUTABLE_NAME
    })
}

fn backup_path(home: &Path) -> PathBuf {
    home.join(".simplicio").join("bin").join(if cfg!(windows) {
        "simplicio.previous.exe"
    } else {
        "simplicio.previous"
    })
}

fn receipt_path(home: &Path) -> PathBuf {
    home.join(".simplicio").join(MANAGED_RECEIPT_NAME)
}

fn digest(path: &Path) -> Result<String, String> {
    let metadata =
        fs::symlink_metadata(path).map_err(|_| error("runtime_lifecycle_active_unavailable"))?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(error("runtime_lifecycle_path_invalid"));
    }
    let mut file = File::open(path).map_err(|_| error("runtime_lifecycle_active_unavailable"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|_| error("runtime_lifecycle_active_unavailable"))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    let mut encoded = String::from("sha256:");
    for byte in hasher.finalize() {
        write!(&mut encoded, "{byte:02x}").expect("String writes cannot fail");
    }
    Ok(encoded)
}

fn optional_digest(path: &Path) -> Result<Option<String>, String> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() => {
            Err(error("runtime_lifecycle_path_invalid"))
        }
        Ok(metadata) if !metadata.is_file() => Err(error("runtime_lifecycle_path_invalid")),
        Ok(_) => digest(path).map(Some),
        Err(error_value) if error_value.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(_) => Err(error("runtime_lifecycle_active_unavailable")),
    }
}

fn snapshot_version(snapshot: &Value) -> Result<String, String> {
    snapshot
        .pointer("/runtime/version")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty() && value.len() <= 64)
        .map(str::to_string)
        .ok_or_else(|| error("runtime_lifecycle_candidate_invalid"))
}

fn read_previous(home: &Path, target_digest: &str) -> Result<(String, String), String> {
    let path = receipt_path(home);
    let metadata =
        fs::symlink_metadata(&path).map_err(|_| error("runtime_lifecycle_previous_unavailable"))?;
    if metadata.file_type().is_symlink() || !metadata.is_file() || metadata.len() > 1024 {
        return Err(error("runtime_lifecycle_previous_invalid"));
    }
    let bytes = fs::read(&path).map_err(|_| error("runtime_lifecycle_previous_unavailable"))?;
    let value: Value =
        serde_json::from_slice(&bytes).map_err(|_| error("runtime_lifecycle_previous_invalid"))?;
    if value.get("schema").and_then(Value::as_str) != Some(MANAGED_RECEIPT_SCHEMA)
        || value.get("source").and_then(Value::as_str) != Some("bundled")
        || value.get("digest").and_then(Value::as_str) != Some(target_digest)
    {
        return Err(error("runtime_lifecycle_previous_invalid"));
    }
    let version = value
        .get("version")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty() && value.len() <= 64)
        .ok_or_else(|| error("runtime_lifecycle_previous_invalid"))?;
    Ok((version.to_string(), target_digest.to_string()))
}

fn lifecycle_receipt(
    action: &str,
    status: &str,
    candidate_version: String,
    candidate_digest: String,
    active_version: String,
    active_digest: String,
    previous: Option<(String, String)>,
    backup_available: bool,
    rollback_proven: bool,
) -> Value {
    json!({
        "schema": SCHEMA,
        "action": action,
        "status": status,
        "candidate_version": candidate_version,
        "candidate_digest": candidate_digest,
        "active_version": active_version,
        "active_digest": active_digest,
        "previous_version": previous.as_ref().map(|pair| pair.0.clone()),
        "previous_digest": previous.as_ref().map(|pair| pair.1.clone()),
        "validated": true,
        "atomic_swap": true,
        "directory_fsynced": true,
        "receipt_durable": true,
        "runtime_healthy": true,
        "backup_available": backup_available,
        "plugins_mutated": false,
        "rollback_proven": rollback_proven,
    })
}

const LIFECYCLE_STATE_NAME: &str = "desktop-runtime-lifecycle.json";
const MAX_STATE_BYTES: u64 = 4 * 1024;

fn state_path(home: &Path) -> PathBuf {
    home.join(".simplicio").join(LIFECYCLE_STATE_NAME)
}

fn parse_digest(value: &str) -> Result<[u8; 32], String> {
    let hex = value
        .strip_prefix("sha256:")
        .filter(|hex| hex.len() == 64)
        .ok_or_else(|| error("runtime_lifecycle_digest_invalid"))?;
    if !hex.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(error("runtime_lifecycle_digest_invalid"));
    }
    let mut digest = [0u8; 32];
    for (index, pair) in hex.as_bytes().chunks_exact(2).enumerate() {
        digest[index] = u8::from_str_radix(
            std::str::from_utf8(pair).map_err(|_| error("runtime_lifecycle_digest_invalid"))?,
            16,
        )
        .map_err(|_| error("runtime_lifecycle_digest_invalid"))?;
    }
    Ok(digest)
}

fn persist_state(home: &Path, value: &Value) -> Result<(), String> {
    let root = home.join(".simplicio");
    let metadata =
        fs::symlink_metadata(&root).map_err(|_| error("runtime_lifecycle_state_unavailable"))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(error("runtime_lifecycle_path_invalid"));
    }
    let bytes =
        serde_json::to_vec(value).map_err(|_| error("runtime_lifecycle_state_write_failed"))?;
    if bytes.len() as u64 > MAX_STATE_BYTES {
        return Err(error("runtime_lifecycle_state_write_failed"));
    }
    let temporary = root.join(format!(
        ".runtime-lifecycle-{}-{}.tmp",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    ));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)
        .map_err(|_| error("runtime_lifecycle_state_write_failed"))?;
    file.write_all(&bytes)
        .and_then(|()| file.sync_all())
        .map_err(|_| error("runtime_lifecycle_state_write_failed"))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&temporary, fs::Permissions::from_mode(0o600))
            .map_err(|_| error("runtime_lifecycle_state_write_failed"))?;
    }
    let destination = state_path(home);
    match fs::symlink_metadata(&destination) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_file() => {
            let _ = fs::remove_file(&temporary);
            return Err(error("runtime_lifecycle_path_invalid"));
        }
        Ok(_) | Err(_) => {}
    }
    fs::rename(&temporary, &destination).map_err(|_| {
        let _ = fs::remove_file(&temporary);
        error("runtime_lifecycle_state_write_failed")
    })?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&destination, fs::Permissions::from_mode(0o600))
            .map_err(|_| error("runtime_lifecycle_state_write_failed"))?;
    }
    File::open(&root)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| error("runtime_lifecycle_state_write_failed"))?;
    Ok(())
}

fn load_state(home: &Path) -> Result<Option<Value>, String> {
    let path = state_path(home);
    let metadata = match fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error_value) if error_value.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(error("runtime_lifecycle_state_unavailable")),
    };
    if metadata.file_type().is_symlink() || !metadata.is_file() || metadata.len() > MAX_STATE_BYTES
    {
        return Err(error("runtime_lifecycle_state_invalid"));
    }
    let bytes = fs::read(&path).map_err(|_| error("runtime_lifecycle_state_unavailable"))?;
    let value: Value =
        serde_json::from_slice(&bytes).map_err(|_| error("runtime_lifecycle_state_invalid"))?;
    if value.get("schema").and_then(Value::as_str) != Some(SCHEMA) {
        return Err(error("runtime_lifecycle_state_invalid"));
    }
    Ok(Some(value))
}

fn maybe_previous(home: &Path, target_digest: &str) -> Result<Option<(String, String)>, String> {
    match fs::symlink_metadata(receipt_path(home)) {
        Ok(metadata) if metadata.file_type().is_symlink() => {
            Err(error("runtime_lifecycle_previous_invalid"))
        }
        Ok(_) => read_previous(home, target_digest).map(Some),
        Err(error_value) if error_value.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(_) => Err(error("runtime_lifecycle_previous_unavailable")),
    }
}

pub fn read<F>(current_executable: &Path, home: &Path, mut validate: F) -> Result<Value, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    let source = super::runtime_install::bundled_authority(current_executable, &mut validate)?;
    let source_snapshot = validate(&source)?;
    let source_version = snapshot_version(&source_snapshot)?;
    let candidate_digest = digest(&source)?;
    if let Some(state) = load_state(home)? {
        if state.get("candidate_digest").and_then(Value::as_str) == Some(candidate_digest.as_str())
            && state.get("active_digest").and_then(Value::as_str)
                == optional_digest(&target_path(home))?.as_deref()
        {
            return Ok(state);
        }
    }
    let active = super::runtime_install::current_snapshot(current_executable, home, &mut validate)?
        .ok_or_else(|| error("runtime_install_required"))?;
    let active_version = snapshot_version(&active)?;
    let active_digest = digest(&target_path(home))?;
    let backup_available = optional_digest(&backup_path(home))?.is_some();
    let receipt = lifecycle_receipt(
        "install",
        "already_current",
        source_version,
        candidate_digest,
        active_version,
        active_digest,
        None,
        backup_available,
        false,
    );
    persist_state(home, &receipt)?;
    Ok(receipt)
}

pub fn apply<F>(
    current_executable: &Path,
    home: &Path,
    action: &str,
    mut validate: F,
) -> Result<Value, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    if !matches!(action, "install" | "upgrade" | "repair") {
        return Err(error("runtime_lifecycle_action_unsupported"));
    }
    let source = super::runtime_install::bundled_authority(current_executable, &mut validate)?;
    let source_snapshot = validate(&source)?;
    let candidate_version = snapshot_version(&source_snapshot)?;
    let candidate_digest = digest(&source)?;
    let target = target_path(home);
    let previous = match optional_digest(&target)? {
        Some(value) => maybe_previous(home, &value)?,
        None => None,
    };
    let result = super::runtime_install::install(current_executable, home, &mut validate)?;
    let active_digest = digest(&target)?;
    if active_digest != candidate_digest {
        return Err(error("runtime_lifecycle_verification_failed"));
    }
    let status = if action == "repair" {
        "repaired"
    } else {
        result
            .get("status")
            .and_then(Value::as_str)
            .filter(|value| matches!(*value, "installed" | "already_current"))
            .ok_or_else(|| error("runtime_lifecycle_verification_failed"))?
    };
    let backup_available = optional_digest(&backup_path(home))?.is_some();
    let receipt = lifecycle_receipt(
        action,
        status,
        candidate_version.clone(),
        candidate_digest,
        candidate_version,
        active_digest,
        previous,
        backup_available,
        false,
    );
    persist_state(home, &receipt)?;
    Ok(receipt)
}

pub fn rollback<F>(home: &Path, mut validate: F) -> Result<Value, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    let state = load_state(home)?.ok_or_else(|| error("runtime_lifecycle_rollback_unavailable"))?;
    if state.get("action").and_then(Value::as_str) == Some("rollback")
        || state.get("backup_available").and_then(Value::as_bool) != Some(true)
    {
        return Err(error("runtime_lifecycle_rollback_unavailable"));
    }
    let current_version = state
        .get("active_version")
        .and_then(Value::as_str)
        .ok_or_else(|| error("runtime_lifecycle_state_invalid"))?;
    let current_digest_text = state
        .get("active_digest")
        .and_then(Value::as_str)
        .ok_or_else(|| error("runtime_lifecycle_state_invalid"))?;
    let previous_version = state
        .get("previous_version")
        .and_then(Value::as_str)
        .ok_or_else(|| error("runtime_lifecycle_rollback_unavailable"))?;
    let previous_digest_text = state
        .get("previous_digest")
        .and_then(Value::as_str)
        .ok_or_else(|| error("runtime_lifecycle_rollback_unavailable"))?;
    let current_digest = parse_digest(current_digest_text)?;
    let previous_digest = parse_digest(previous_digest_text)?;
    super::runtime_install::rollback(
        home,
        current_digest,
        previous_digest,
        previous_version,
        &mut validate,
    )?;
    let receipt = lifecycle_receipt(
        "rollback",
        "rolled_back",
        current_version.to_string(),
        current_digest_text.to_string(),
        previous_version.to_string(),
        previous_digest_text.to_string(),
        Some((
            previous_version.to_string(),
            previous_digest_text.to_string(),
        )),
        true,
        true,
    );
    persist_state(home, &receipt)?;
    Ok(receipt)
}

#[cfg(test)]
mod tests {
    use super::*;

    const DIGEST_A: &str =
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

    #[test]
    fn receipt_is_versioned_redacted_and_non_mutating() {
        let value = lifecycle_receipt(
            "upgrade",
            "installed",
            "3.8.41".to_string(),
            DIGEST_A.to_string(),
            "3.8.41".to_string(),
            DIGEST_A.to_string(),
            Some(("3.8.40".to_string(), DIGEST_A.to_string())),
            true,
            false,
        );
        assert_eq!(value["schema"], SCHEMA);
        assert_eq!(value["plugins_mutated"], false);
        assert_eq!(value["atomic_swap"], true);
        assert!(value.get("path").is_none());
    }

    #[test]
    fn digest_rejects_symlinked_active_targets() {
        let root =
            std::env::temp_dir().join(format!("simplicio-lifecycle-test-{}", std::process::id()));
        let target = root.join("target");
        let link = root.join("link");
        fs::create_dir_all(&root).unwrap();
        fs::write(&target, b"runtime").unwrap();
        #[cfg(unix)]
        std::os::unix::fs::symlink(&target, &link).unwrap();
        #[cfg(unix)]
        assert_eq!(digest(&link).unwrap_err(), "runtime_lifecycle_path_invalid");
        let _ = fs::remove_dir_all(root);
    }
}
