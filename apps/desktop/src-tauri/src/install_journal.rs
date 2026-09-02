//! Durable, redacted state for the Desktop Runtime installation effect.
//!
//! The Runtime installer already owns the filesystem transaction. This module
//! records only whether that transaction is clear or needs an explicit
//! read-only reconciliation after an interrupted/ambiguous attempt.

use serde_json::{json, Value};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

const SCHEMA: &str = "simplicio.desktop-install-attempt/v1";
const MAX_BYTES: usize = 4 * 1024;

fn sibling(path: &Path, suffix: &str) -> PathBuf {
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default();
    path.with_extension(format!("{extension}.{suffix}"))
}

fn reject_symlink(path: &Path) -> io::Result<()> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() => {
            Err(io::Error::new(io::ErrorKind::InvalidInput, "symlink"))
        }
        Ok(_) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error),
    }
}

fn write_atomic(path: &Path, state: &str, error: Option<&str>) -> io::Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "missing parent"))?;
    fs::create_dir_all(parent)?;
    reject_symlink(path)?;
    let temporary = sibling(path, "tmp");
    let backup = sibling(path, "bak");
    reject_symlink(&temporary)?;
    reject_symlink(&backup)?;
    let _ = fs::remove_file(&temporary);

    let record = json!({
        "schema": SCHEMA,
        "state": state,
        "error": error,
    });
    let encoded = serde_json::to_vec(&record).map_err(io::Error::other)?;
    if encoded.len() > MAX_BYTES {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "journal too large"));
    }

    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)?;
    file.write_all(&encoded)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    drop(file);

    if path.exists() {
        let _ = fs::remove_file(&backup);
        fs::rename(path, &backup)?;
    }
    if let Err(rename_error) = fs::rename(&temporary, path) {
        if !path.exists() && backup.exists() {
            let _ = fs::rename(&backup, path);
        }
        return Err(rename_error);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    }
    if let Ok(directory) = File::open(parent) {
        let _ = directory.sync_all();
    }
    Ok(())
}

fn safe_error(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value.bytes().enumerate().all(|(index, byte)| {
            byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || byte == b'_' && index > 0
        })
        && value.as_bytes()[0].is_ascii_lowercase()
}

fn candidate(path: &Path) -> Option<PathBuf> {
    [path.to_path_buf(), sibling(path, "bak"), sibling(path, "tmp")]
        .into_iter()
        .find(|candidate| candidate.exists())
}

/// The only durable states exposed to the Desktop are clear and blocked.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct InstallAttempt {
    blocked: bool,
}

impl InstallAttempt {
    pub fn load(path: &Path) -> Self {
        let Some(selected) = candidate(path) else {
            return Self::default();
        };
        if reject_symlink(&selected).is_err() {
            return Self { blocked: true };
        }
        let Ok(metadata) = fs::metadata(&selected) else {
            return Self { blocked: true };
        };
        if !metadata.is_file() || metadata.len() as usize > MAX_BYTES {
            return Self { blocked: true };
        }
        let Ok(mut file) = File::open(selected) else {
            return Self { blocked: true };
        };
        let mut bytes = Vec::new();
        if std::io::Read::by_ref(&mut file)
            .take((MAX_BYTES + 1) as u64)
            .read_to_end(&mut bytes)
            .is_err()
            || bytes.len() > MAX_BYTES
        {
            return Self { blocked: true };
        }
        let Ok(value) = serde_json::from_slice::<Value>(&bytes) else {
            return Self { blocked: true };
        };
        let Some(object) = value.as_object() else {
            return Self { blocked: true };
        };
        if object.len() != 3 || value.get("schema").and_then(Value::as_str) != Some(SCHEMA) {
            return Self { blocked: true };
        }
        match value.get("state").and_then(Value::as_str) {
            Some("settled") if value.get("error").is_some_and(Value::is_null) => Self::default(),
            Some("in_progress") if value.get("error").is_some_and(Value::is_null) => {
                Self { blocked: true }
            }
            Some("reconciliation_required") => {
                let _valid = value
                    .get("error")
                    .and_then(Value::as_str)
                    .is_some_and(safe_error);
                Self { blocked: true }
            }
            _ => Self { blocked: true },
        }
    }

    pub fn begin_persisted(&mut self, path: &Path) -> Result<(), String> {
        if self.blocked {
            return Err("runtime_install_reconciliation_required".into());
        }
        write_atomic(path, "in_progress", None)
            .map_err(|_| "runtime_install_journal_unavailable".to_string())?;
        self.blocked = true;
        Ok(())
    }

    pub fn finish_persisted(
        &mut self,
        path: &Path,
        result: &Result<Value, String>,
    ) -> Result<(), String> {
        let (state, error) = match result {
            Ok(_) => ("settled", None),
            Err(code) if safe_error(code) => ("reconciliation_required", Some(code.as_str())),
            Err(_) => (
                "reconciliation_required",
                Some("runtime_install_reconciliation_required"),
            ),
        };
        write_atomic(path, state, error)
            .map_err(|_| "runtime_install_reconciliation_required".to_string())?;
        self.blocked = state != "settled";
        Ok(())
    }

    pub fn pending_error(&self) -> Option<String> {
        self.blocked
            .then(|| "runtime_install_reconciliation_required".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    fn path(name: &str) -> PathBuf {
        static NEXT: AtomicU64 = AtomicU64::new(1);
        std::env::temp_dir().join(format!(
            "simplicio-install-journal-{name}-{}-{}.json",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ))
    }

    fn cleanup(path: &Path) {
        let _ = fs::remove_file(path);
        let _ = fs::remove_file(sibling(path, "tmp"));
        let _ = fs::remove_file(sibling(path, "bak"));
    }

    #[test]
    fn interrupted_attempt_stays_blocked_after_reload_without_raw_error_data() {
        let path = path("reload");
        cleanup(&path);
        let mut attempt = InstallAttempt::default();
        attempt.begin_persisted(&path).unwrap();
        let result = Err("runtime_install_timeout".to_string());
        attempt.finish_persisted(&path, &result).unwrap();

        let restored = InstallAttempt::load(&path);
        assert_eq!(
            restored.pending_error().as_deref(),
            Some("runtime_install_reconciliation_required")
        );
        cleanup(&path);
    }

    #[test]
    fn malformed_or_interrupted_journal_fails_closed() {
        let path = path("malformed");
        cleanup(&path);
        fs::write(&path, br#"{"schema":"simplicio.desktop-install-attempt/v1","state":"in_progress"}"#)
            .unwrap();
        assert!(InstallAttempt::load(&path).pending_error().is_some());
        cleanup(&path);
    }

    #[test]
    fn settled_attempt_is_clear_after_reload() {
        let path = path("settled");
        cleanup(&path);
        let mut attempt = InstallAttempt::default();
        attempt.begin_persisted(&path).unwrap();
        attempt.finish_persisted(&path, &Ok(json!({"status":"installed"})))
            .unwrap();
        assert!(InstallAttempt::load(&path).pending_error().is_none());
        cleanup(&path);
    }
}
