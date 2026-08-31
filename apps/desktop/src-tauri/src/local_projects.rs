//! Local Desktop conveniences, not Runtime execution or workspace authority.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::process::Command;

// Inspect resolved path text without relying on the test host's path syntax.
// A canonical Win32 device prefix is allowed only for an ordinary local drive.
fn canonical_local_text(path: &str) -> Result<&str, String> {
    let rendered = path.strip_prefix("\\\\?\\").unwrap_or(path);
    let bytes = rendered.as_bytes();
    let local_drive = bytes.len() >= 3
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':'
        && matches!(bytes[2], b'\\' | b'/');
    let posix = rendered.starts_with('/') && !rendered.starts_with("//");
    if (path.starts_with("\\\\?\\") && !local_drive)
        || (!local_drive && !posix)
        || rendered.len() > 4096
        || rendered.chars().any(char::is_control)
    {
        return Err("project_invalid".into());
    }
    Ok(rendered)
}

fn project_path(input: &str) -> Result<PathBuf, String> {
    if input.is_empty()
        || input.len() > 4096
        || input.chars().any(char::is_control)
        || input.starts_with("//")
        || input.starts_with("\\\\")
        || !Path::new(input).is_absolute()
    {
        return Err("project_invalid".into());
    }
    let path = Path::new(input)
        .canonicalize()
        .map_err(|_| "project_unavailable")?;
    // A local input may resolve through a symlink to a disallowed target.
    // Both bookmark validation and opening use this post-resolution guard.
    canonical_local_text(path.to_str().ok_or("project_invalid")?)?;
    if !path.is_dir() || path.file_name().is_none() {
        return Err("project_not_directory".into());
    }
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or("project_invalid")?;
    if name.chars().count() > 256 {
        return Err("project_invalid".into());
    }
    Ok(path)
}

pub fn validate_project(input: &str) -> Result<Value, String> {
    let path = project_path(input)?;
    let rendered = path.to_str().ok_or("project_invalid")?;
    // The shared guard already verified this prefix belongs to a local drive.
    let rendered = rendered.strip_prefix("\\\\?\\").unwrap_or(rendered);
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or("project_invalid")?;
    Ok(json!({
        "id": format!("project-{:x}", Sha256::digest(rendered.as_bytes())),
        "name": name, "path": rendered,
    }))
}

pub fn open_project(input: &str) -> Result<(), String> {
    // Revalidate even if the caller presents a previously saved bookmark.
    let path = project_path(input)?;
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = Command::new("/usr/bin/open");
        command.arg("--").arg(&path);
        command
    };
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = Command::new("explorer.exe");
        command.arg(&path);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = Command::new("xdg-open");
        command.arg(&path);
        command
    };
    command
        .status()
        .map_err(|_| "project_open_failed".to_string())
        .and_then(|status| {
            if status.success() {
                Ok(())
            } else {
                Err("project_open_failed".into())
            }
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_local_text_preserves_local_paths_and_normalizes_drive_prefixes() {
        for (canonical, expected) in [
            ("/tmp/project", "/tmp/project"),
            (r"C:\Projects\Simplicio", r"C:\Projects\Simplicio"),
            ("C:/Projects/Simplicio", "C:/Projects/Simplicio"),
            (r"\\?\C:\Projects\Simplicio", r"C:\Projects\Simplicio"),
            (r"\\?\d:\Projects\Simplicio", r"d:\Projects\Simplicio"),
        ] {
            assert_eq!(canonical_local_text(canonical).unwrap(), expected);
        }
    }

    #[test]
    fn canonical_local_text_rejects_resolved_network_device_and_control_targets() {
        for canonical in [
            "",
            "relative/project",
            r"C:relative",
            "//server/share/project",
            r"\\server\share\project",
            r"UNC\server\share\project",
            r"\\?\UNC\server\share\project",
            r"\\?\unc\server\share\project",
            r"\\.\C:\project",
            r"\\?\GLOBALROOT\Device\HarddiskVolume1\project",
            r"\\?\Volume{test}\project",
            r"\??\C:\project",
            r"\\?\/tmp/project",
            "/tmp/project\n",
            "C:\\project\tname",
            "\\\\?\\C:\\project\u{7f}",
        ] {
            assert!(canonical_local_text(canonical).is_err(), "{canonical:?}");
        }
    }

    #[test]
    fn canonical_local_text_enforces_the_rendered_path_byte_limit() {
        let at_limit = format!("/{}", "a".repeat(4095));
        assert!(canonical_local_text(&at_limit).is_ok());
        let over_limit = format!("{at_limit}a");
        assert!(canonical_local_text(&over_limit).is_err());
    }

    #[test]
    fn bookmark_metadata_is_stable_and_only_describes_an_existing_directory() {
        let root = std::env::current_dir().unwrap();
        let first = validate_project(root.to_str().unwrap()).unwrap();
        let again = validate_project(root.join(".").to_str().unwrap()).unwrap();
        assert_eq!(first, again);
        assert_eq!(first["id"].as_str().unwrap().len(), 72);
        assert!(first.get("authority").is_none());
        assert!(first.get("files").is_none());
        assert!(validate_project(root.join("Cargo.toml").to_str().unwrap()).is_err());
        assert!(validate_project(
            root.join("nonexistent-desktop-project-qa")
                .to_str()
                .unwrap()
        )
        .is_err());
    }

    #[test]
    fn rejects_relative_paths_urls_networks_devices_and_controls() {
        for value in [
            "",
            ".",
            "../project",
            "https://example.com",
            "file:///tmp/project",
            "//server/share",
            "\\\\server\\share",
            "\\\\?\\C:\\project",
            "/tmp/project\n",
            "/",
        ] {
            assert!(validate_project(value).is_err(), "{value}");
        }
    }
}
