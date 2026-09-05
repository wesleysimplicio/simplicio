//! Native Desktop updater for issue #342.
//!
//! The updater owns a small, durable state machine.  The UI can only supply
//! release identity; this module reconstructs the official URL, re-reads the
//! release API digest, downloads into a private staging directory, and refuses
//! to install anything that was not verified.  No authentication state is
//! consulted: checking and installing a public Desktop release is anonymous.

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

const SCHEMA: &str = "simplicio.desktop-update/v1";
const API_URL: &str = "https://api.github.com/repos/wesleysimplicio/simplicio/releases?per_page=30";
const RELEASES_URL: &str = "https://github.com/wesleysimplicio/simplicio/releases";
const MAX_MANIFEST_BYTES: u64 = 2 * 1024 * 1024;
const MAX_ARTIFACT_BYTES: u64 = 5 * 1024 * 1024 * 1024;
const MAX_ASSET_NAME: usize = 180;
const MAX_DOWNLOAD_SECONDS: u64 = 900;
const STATE_DIR: &str = "desktop-updates";
const STATE_FILE: &str = "state.json";

#[derive(Clone, Debug, Eq, PartialEq)]
struct ReleaseArtifact {
    version: String,
    tag: String,
    asset_name: String,
    asset_bytes: u64,
    digest: String,
    url: String,
}

#[derive(Clone, Debug)]
struct UpdateState {
    id: String,
    state: String,
    artifact: ReleaseArtifact,
    received_bytes: u64,
    staged_path: PathBuf,
    previous_path: Option<PathBuf>,
}

fn error(code: &str) -> String {
    code.to_string()
}

fn now_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn update_root(app_data: &Path) -> PathBuf {
    app_data.join(STATE_DIR)
}

fn state_path(app_data: &Path) -> PathBuf {
    update_root(app_data).join(STATE_FILE)
}

fn reject_symlink(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() => Err(error("update_path_invalid")),
        Ok(_) => Ok(()),
        Err(value) if value.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(_) => Err(error("update_path_unavailable")),
    }
}

fn ensure_private_dir(path: &Path) -> Result<(), String> {
    reject_symlink(path)?;
    fs::create_dir_all(path).map_err(|_| error("update_storage_unavailable"))?;
    let metadata = fs::symlink_metadata(path).map_err(|_| error("update_storage_unavailable"))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(error("update_path_invalid"));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))
            .map_err(|_| error("update_storage_unavailable"))?;
    }
    Ok(())
}

fn safe_component(value: &str, max: usize) -> bool {
    !value.is_empty()
        && value.len() <= max
        && value != "."
        && value != ".."
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
}

fn version_valid(value: &str) -> bool {
    let mut core = value.splitn(2, '-');
    let numbers = core.next().unwrap_or_default();
    let prerelease = core.next();
    let parts = numbers.split('.').collect::<Vec<_>>();
    parts.len() == 3
        && parts.iter().all(|part| {
            !part.is_empty()
                && (part.len() == 1 || !part.starts_with('0'))
                && part.bytes().all(|byte| byte.is_ascii_digit())
        })
        && prerelease.map_or(true, |part| {
            !part.is_empty()
                && part.split('.').all(|item| {
                    !item.is_empty()
                        && (item == "0"
                            || !item.starts_with('0')
                            || !item.bytes().all(|byte| byte.is_ascii_digit()))
                        && item
                            .bytes()
                            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
                })
        })
}

fn expected_target() -> (&'static str, &'static str) {
    let platform = match std::env::consts::OS {
        "macos" => "macos",
        "windows" => "windows",
        "linux" => "linux",
        _ => "unknown",
    };
    let arch = match std::env::consts::ARCH {
        "aarch64" => "arm64",
        "x86_64" => "x64",
        "x86" => "x86",
        _ => "unknown",
    };
    (platform, arch)
}

fn asset_matches_target(name: &str) -> bool {
    let (platform, arch) = expected_target();
    if platform == "macos" {
        (name.ends_with(".dmg") || name.ends_with(".zip"))
            && (name.contains("arm64") && arch == "arm64"
                || name.contains("aarch64") && arch == "arm64"
                || name.contains("x64") && arch == "x64"
                || name.contains("x86_64") && arch == "x64"
                || name.contains("universal"))
    } else if platform == "windows" {
        (name.ends_with("-setup.exe") || name.ends_with(".msi"))
            && (name.contains("x64") && arch == "x64"
                || name.contains("amd64") && arch == "x64"
                || name.contains("arm64") && arch == "arm64"
                || name.contains("x86") && arch == "x86")
    } else if platform == "linux" {
        (name.ends_with(".AppImage") || name.ends_with(".deb") || name.ends_with(".rpm"))
            && (name.contains("x64") && arch == "x64"
                || name.contains("amd64") && arch == "x64"
                || name.contains("x86_64") && arch == "x64"
                || name.contains("arm64") && arch == "arm64"
                || name.contains("aarch64") && arch == "arm64"
                || name.contains("x86") && arch == "x86")
    } else {
        false
    }
}

fn digest_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    let digest = hasher.finalize();
    let mut result = String::from("sha256:");
    for byte in digest {
        result.push_str(&format!("{byte:02x}"));
    }
    result
}

fn digest_file(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|_| error("update_read_failed"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    let mut total = 0u64;
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|_| error("update_read_failed"))?;
        if count == 0 {
            break;
        }
        total = total.saturating_add(count as u64);
        if total > MAX_ARTIFACT_BYTES {
            return Err(error("update_artifact_too_large"));
        }
        hasher.update(&buffer[..count]);
    }
    let digest = hasher.finalize();
    let mut result = String::from("sha256:");
    for byte in digest {
        result.push_str(&format!("{byte:02x}"));
    }
    Ok(result)
}

fn valid_digest(value: &str) -> bool {
    value
        .strip_prefix("sha256:")
        .is_some_and(|hex| hex.len() == 64 && hex.bytes().all(|byte| byte.is_ascii_hexdigit()))
}

fn fixed_asset_url(tag: &str, asset_name: &str) -> Result<String, String> {
    if !safe_component(tag, 80)
        || !tag.starts_with('v')
        || !safe_component(asset_name, MAX_ASSET_NAME)
    {
        return Err(error("update_identity_invalid"));
    }
    Ok(format!("{RELEASES_URL}/download/{tag}/{asset_name}"))
}

fn parse_manifest(body: &[u8], tag: &str, asset_name: &str) -> Result<ReleaseArtifact, String> {
    if body.len() as u64 > MAX_MANIFEST_BYTES {
        return Err(error("update_manifest_too_large"));
    }
    let value: Value =
        serde_json::from_slice(body).map_err(|_| error("update_manifest_invalid"))?;
    let entries = value
        .as_array()
        .ok_or_else(|| error("update_manifest_invalid"))?;
    let release = entries
        .iter()
        .find(|entry| {
            entry.get("tag_name").and_then(Value::as_str) == Some(tag)
                && entry.get("draft").and_then(Value::as_bool) == Some(false)
                && entry.get("prerelease").and_then(Value::as_bool) == Some(false)
        })
        .ok_or_else(|| error("update_release_unavailable"))?;
    let version = tag
        .strip_prefix('v')
        .ok_or_else(|| error("update_identity_invalid"))?;
    if !version_valid(version)
        || release.get("html_url").and_then(Value::as_str)
            != Some(format!("{RELEASES_URL}/tag/{tag}").as_str())
    {
        return Err(error("update_manifest_invalid"));
    }
    let assets = release
        .get("assets")
        .and_then(Value::as_array)
        .ok_or_else(|| error("update_manifest_invalid"))?;
    let asset = assets
        .iter()
        .find(|asset| asset.get("name").and_then(Value::as_str) == Some(asset_name))
        .ok_or_else(|| error("update_asset_unavailable"))?;
    let bytes = asset
        .get("size")
        .and_then(Value::as_u64)
        .filter(|size| *size > 0 && *size <= MAX_ARTIFACT_BYTES)
        .ok_or_else(|| error("update_asset_invalid"))?;
    let digest = asset
        .get("digest")
        .and_then(Value::as_str)
        .filter(|digest| valid_digest(digest))
        .ok_or_else(|| error("update_digest_unavailable"))?;
    let url = fixed_asset_url(tag, asset_name)?;
    if asset.get("state").and_then(Value::as_str) != Some("uploaded")
        || asset.get("browser_download_url").and_then(Value::as_str) != Some(url.as_str())
        || !asset_matches_target(asset_name)
    {
        return Err(error("update_asset_invalid"));
    }
    Ok(ReleaseArtifact {
        version: version.to_string(),
        tag: tag.to_string(),
        asset_name: asset_name.to_string(),
        asset_bytes: bytes,
        digest: digest.to_string(),
        url,
    })
}

fn curl_to(url: &str, destination: &Path, resume: bool, max_seconds: u64) -> Result<(), String> {
    let mut command = Command::new("curl");
    command.args([
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--connect-timeout",
        "20",
        "--max-time",
        &max_seconds.to_string(),
    ]);
    if resume {
        command.arg("--continue-at").arg("-");
    }
    let status = command
        .arg("--output")
        .arg(destination)
        .arg(url)
        .status()
        .map_err(|_| error("update_download_unavailable"))?;
    if status.success() {
        Ok(())
    } else {
        Err(error("update_download_failed"))
    }
}

fn atomic_write(path: &Path, value: &Value) -> Result<(), String> {
    let parent = path.parent().ok_or_else(|| error("update_path_invalid"))?;
    ensure_private_dir(parent)?;
    reject_symlink(path)?;
    let temp = parent.join(format!(".{}.tmp-{}", STATE_FILE, now_millis()));
    let encoded = serde_json::to_vec(value).map_err(|_| error("update_state_write_failed"))?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temp)
        .map_err(|_| error("update_state_write_failed"))?;
    file.write_all(&encoded)
        .and_then(|()| file.write_all(b"\n"))
        .and_then(|()| file.sync_all())
        .map_err(|_| error("update_state_write_failed"))?;
    drop(file);
    fs::rename(&temp, path).map_err(|_| {
        let _ = fs::remove_file(&temp);
        error("update_state_write_failed")
    })?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))
            .map_err(|_| error("update_state_write_failed"))?;
    }
    Ok(())
}

fn state_to_json(value: &UpdateState) -> Value {
    json!({
        "schema": SCHEMA,
        "id": value.id,
        "state": value.state,
        "version": value.artifact.version,
        "tag": value.artifact.tag,
        "asset_name": value.artifact.asset_name,
        "asset_bytes": value.artifact.asset_bytes,
        "asset_digest": value.artifact.digest,
        "received_bytes": value.received_bytes,
        "staged_path": value.staged_path.display().to_string(),
        "previous_path": value.previous_path.as_ref().map(|path| path.display().to_string()),
        "target": { "platform": expected_target().0, "arch": expected_target().1 },
        "restart_required": value.state == "relaunch_pending" || value.state == "awaiting_health",
        "anonymous": true,
        "integrity": "sha256",
        "provenance": "github-release-api",
    })
}

fn parse_state(value: &Value) -> Result<UpdateState, String> {
    if value.get("schema").and_then(Value::as_str) != Some(SCHEMA) {
        return Err(error("update_state_invalid"));
    }
    let id = value
        .get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| error("update_state_invalid"))?;
    let state = value
        .get("state")
        .and_then(Value::as_str)
        .ok_or_else(|| error("update_state_invalid"))?;
    if !safe_component(id, 160)
        || !matches!(
            state,
            "downloading" | "ready" | "relaunch_pending" | "awaiting_health" | "completed"
        )
    {
        return Err(error("update_state_invalid"));
    }
    let version = value
        .get("version")
        .and_then(Value::as_str)
        .ok_or_else(|| error("update_state_invalid"))?;
    let tag = value
        .get("tag")
        .and_then(Value::as_str)
        .ok_or_else(|| error("update_state_invalid"))?;
    let asset_name = value
        .get("asset_name")
        .and_then(Value::as_str)
        .ok_or_else(|| error("update_state_invalid"))?;
    let asset_bytes = value
        .get("asset_bytes")
        .and_then(Value::as_u64)
        .filter(|size| *size > 0 && *size <= MAX_ARTIFACT_BYTES)
        .ok_or_else(|| error("update_state_invalid"))?;
    let digest = value
        .get("asset_digest")
        .and_then(Value::as_str)
        .filter(|digest| valid_digest(digest))
        .ok_or_else(|| error("update_state_invalid"))?;
    let staged_path = value
        .get("staged_path")
        .and_then(Value::as_str)
        .map(PathBuf::from)
        .ok_or_else(|| error("update_state_invalid"))?;
    if !version_valid(version)
        || !tag.starts_with('v')
        || !safe_component(asset_name, MAX_ASSET_NAME)
        || !asset_matches_target(asset_name)
    {
        return Err(error("update_state_invalid"));
    }
    let previous_path = value
        .get("previous_path")
        .and_then(Value::as_str)
        .map(PathBuf::from);
    Ok(UpdateState {
        id: id.to_string(),
        state: state.to_string(),
        artifact: ReleaseArtifact {
            version: version.to_string(),
            tag: tag.to_string(),
            asset_name: asset_name.to_string(),
            asset_bytes,
            digest: digest.to_string(),
            url: fixed_asset_url(tag, asset_name)?,
        },
        received_bytes: value
            .get("received_bytes")
            .and_then(Value::as_u64)
            .unwrap_or(0),
        staged_path,
        previous_path,
    })
}

fn read_state(app_data: &Path) -> Result<Option<UpdateState>, String> {
    let path = state_path(app_data);
    reject_symlink(&path)?;
    let body = match fs::read(&path) {
        Ok(body) => body,
        Err(value) if value.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(error("update_state_read_failed")),
    };
    parse_state(&serde_json::from_slice(&body).map_err(|_| error("update_state_invalid"))?)
        .map(Some)
}

fn write_state(app_data: &Path, state: &UpdateState) -> Result<(), String> {
    atomic_write(&state_path(app_data), &state_to_json(state))
}

fn update_id(artifact: &ReleaseArtifact) -> String {
    let digest = digest_bytes(
        format!(
            "{}:{}:{}",
            artifact.tag, artifact.asset_name, artifact.digest
        )
        .as_bytes(),
    );
    digest.trim_start_matches("sha256:")[..32].to_string()
}

fn load_manifest(
    temporary_root: &Path,
    tag: &str,
    asset_name: &str,
) -> Result<ReleaseArtifact, String> {
    let manifest = temporary_root.join(format!("manifest-{}.json", now_millis()));
    curl_to(API_URL, &manifest, false, 60)?;
    let body = fs::read(&manifest).map_err(|_| error("update_manifest_read_failed"))?;
    let _ = fs::remove_file(&manifest);
    parse_manifest(&body, tag, asset_name)
}

pub fn download(
    app_data: &Path,
    version: &str,
    tag: &str,
    asset_name: &str,
    asset_bytes_hint: u64,
) -> Result<Value, String> {
    if !version_valid(version)
        || tag != format!("v{version}")
        || !safe_component(asset_name, MAX_ASSET_NAME)
        || !asset_matches_target(asset_name)
        || asset_bytes_hint == 0
        || asset_bytes_hint > MAX_ARTIFACT_BYTES
    {
        return Err(error("update_identity_invalid"));
    }
    ensure_private_dir(&update_root(app_data))?;
    let artifact = load_manifest(&update_root(app_data), tag, asset_name)?;
    if artifact.version != version
        || (asset_bytes_hint != 0 && artifact.asset_bytes != asset_bytes_hint)
    {
        return Err(error("update_manifest_changed"));
    }
    let id = update_id(&artifact);
    let staged_path = update_root(app_data).join(format!("{id}.part"));
    let received_bytes = fs::metadata(&staged_path)
        .map(|metadata| metadata.len())
        .unwrap_or(0);
    if received_bytes > artifact.asset_bytes {
        let _ = fs::remove_file(&staged_path);
    }
    let received_bytes = fs::metadata(&staged_path)
        .map(|metadata| metadata.len())
        .unwrap_or(0);
    let mut state = UpdateState {
        id: id.clone(),
        state: "downloading".to_string(),
        artifact: artifact.clone(),
        received_bytes,
        staged_path: staged_path.clone(),
        previous_path: None,
    };
    write_state(app_data, &state)?;
    curl_to(
        &artifact.url,
        &staged_path,
        received_bytes > 0,
        MAX_DOWNLOAD_SECONDS,
    )?;
    let actual_bytes = fs::metadata(&staged_path)
        .map(|metadata| metadata.len())
        .map_err(|_| error("update_download_incomplete"))?;
    if actual_bytes != artifact.asset_bytes {
        state.received_bytes = actual_bytes;
        write_state(app_data, &state)?;
        return Err(error("update_download_incomplete"));
    }
    let actual_digest = digest_file(&staged_path)?;
    if !actual_digest.eq_ignore_ascii_case(&artifact.digest) {
        state.received_bytes = actual_bytes;
        write_state(app_data, &state)?;
        return Err(error("update_checksum_mismatch"));
    }
    let final_path = update_root(app_data).join(format!("{id}-{}", artifact.asset_name));
    reject_symlink(&final_path)?;
    fs::rename(&staged_path, &final_path).map_err(|_| error("update_stage_failed"))?;
    state.state = "ready".to_string();
    state.received_bytes = actual_bytes;
    state.staged_path = final_path;
    write_state(app_data, &state)?;
    Ok(state_to_json(&state))
}

fn current_bundle(current_executable: &Path) -> Result<PathBuf, String> {
    #[cfg(target_os = "macos")]
    {
        for ancestor in current_executable.ancestors() {
            if ancestor.extension().and_then(|value| value.to_str()) == Some("app")
                && ancestor.join("Contents").is_dir()
            {
                return Ok(ancestor.to_path_buf());
            }
        }
    }
    let parent = current_executable
        .parent()
        .ok_or_else(|| error("update_target_unavailable"))?;
    Ok(parent.to_path_buf())
}

fn find_app(root: &Path) -> Option<PathBuf> {
    if root.extension().and_then(|value| value.to_str()) == Some("app")
        && root.join("Contents").is_dir()
    {
        return Some(root.to_path_buf());
    }
    let mut stack = vec![(root.to_path_buf(), 0usize)];
    while let Some((directory, depth)) = stack.pop() {
        if depth > 3 {
            continue;
        }
        let entries = fs::read_dir(&directory).ok()?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|value| value.to_str()) == Some("app")
                && path.join("Contents").is_dir()
            {
                return Some(path);
            }
            if path.is_dir() && depth < 3 {
                stack.push((path, depth + 1));
            }
        }
    }
    None
}

fn command_ok(program: &str, args: &[&str]) -> Result<(), String> {
    let status = Command::new(program)
        .args(args)
        .status()
        .map_err(|_| error("update_install_tool_unavailable"))?;
    if status.success() {
        Ok(())
    } else {
        Err(error("update_install_tool_failed"))
    }
}

fn extract_archive(artifact: &Path, destination: &Path) -> Result<PathBuf, String> {
    ensure_private_dir(destination)?;
    let extension = artifact.extension().and_then(|value| value.to_str());
    if extension == Some("zip") {
        command_ok(
            "/usr/bin/ditto",
            &[
                "-x",
                "-k",
                artifact
                    .to_str()
                    .ok_or_else(|| error("update_path_invalid"))?,
                destination
                    .to_str()
                    .ok_or_else(|| error("update_path_invalid"))?,
            ],
        )?;
        return find_app(destination).ok_or_else(|| error("update_bundle_missing"));
    }
    if extension == Some("dmg") {
        let mount = destination.with_extension("mount");
        ensure_private_dir(&mount)?;
        let artifact_path = artifact
            .to_str()
            .ok_or_else(|| error("update_path_invalid"))?;
        let mount_path = mount.to_str().ok_or_else(|| error("update_path_invalid"))?;
        let attach = command_ok(
            "/usr/bin/hdiutil",
            &[
                "attach",
                artifact_path,
                "-nobrowse",
                "-readonly",
                "-noautoopen",
                "-mountpoint",
                mount_path,
            ],
        );
        if let Err(error_value) = attach {
            let _ = fs::remove_dir_all(&mount);
            return Err(error_value);
        }
        let candidate = find_app(&mount);
        let result = match candidate {
            Some(candidate) => {
                let destination_app = destination.join(
                    candidate
                        .file_name()
                        .unwrap_or_else(|| std::ffi::OsStr::new("Simplicio.app")),
                );
                let source_path = candidate
                    .to_str()
                    .ok_or_else(|| error("update_path_invalid"))?;
                let destination_path = destination_app
                    .to_str()
                    .ok_or_else(|| error("update_path_invalid"))?;
                command_ok("/usr/bin/ditto", &[source_path, destination_path])
                    .map(|()| destination_app)
            }
            None => Err(error("update_bundle_missing")),
        };
        let _ = command_ok("/usr/bin/hdiutil", &["detach", mount_path]);
        let _ = fs::remove_dir_all(&mount);
        return result;
    }
    Err(error("update_package_unsupported"))
}

fn install_bundle(
    app_data: &Path,
    current_executable: &Path,
    state: &mut UpdateState,
) -> Result<Value, String> {
    if !cfg!(target_os = "macos")
        || !(state.artifact.asset_name.ends_with(".zip")
            || state.artifact.asset_name.ends_with(".dmg"))
    {
        return Err(error("update_package_unsupported"));
    }
    let current = current_bundle(current_executable)?;
    let extraction = update_root(app_data).join(format!("extract-{}", state.id));
    let candidate = extract_archive(&state.staged_path, &extraction)?;
    let parent = current
        .parent()
        .ok_or_else(|| error("update_target_unavailable"))?;
    let backup = parent.join(format!(
        "{}.previous-{}",
        current
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or_else(|| error("update_target_unavailable"))?,
        state.id
    ));
    reject_symlink(&current)?;
    reject_symlink(&backup)?;
    if backup.exists() {
        return Err(error("update_backup_exists"));
    }
    if let Err(rename_error) = fs::rename(&current, &backup) {
        return Err(format!("update_install_failed:{rename_error}"));
    }
    if let Err(rename_error) = fs::rename(&candidate, &current) {
        let _ = fs::rename(&backup, &current);
        return Err(format!("update_install_failed:{rename_error}"));
    }
    state.state = "relaunch_pending".to_string();
    state.previous_path = Some(backup);
    write_state(app_data, state)?;
    command_ok(
        "/usr/bin/open",
        &[
            "-n",
            current
                .to_str()
                .ok_or_else(|| error("update_path_invalid"))?,
        ],
    )?;
    state.state = "awaiting_health".to_string();
    write_state(app_data, state)?;
    Ok(state_to_json(state))
}

fn bundle_version(bundle: &Path) -> Option<String> {
    let plist = fs::read_to_string(bundle.join("Contents/Info.plist")).ok()?;
    let key = plist.find("<key>CFBundleShortVersionString</key>")?;
    let rest = &plist[key..];
    let start = rest.find("<string>")? + "<string>".len();
    let end = rest[start..].find("</string>")?;
    Some(rest[start..start + end].to_string())
}

fn swap_back(
    app_data: &Path,
    state: &mut UpdateState,
    current_executable: &Path,
) -> Result<Value, String> {
    let current = current_bundle(current_executable)?;
    let previous = state
        .previous_path
        .clone()
        .ok_or_else(|| error("update_rollback_unavailable"))?;
    let current_parent = current
        .parent()
        .ok_or_else(|| error("update_rollback_unavailable"))?;
    let current_name = current
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| error("update_rollback_unavailable"))?;
    let previous_name = previous
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| error("update_rollback_unavailable"))?;
    if previous.parent() != Some(current_parent)
        || !previous_name.starts_with(&format!("{current_name}.previous-"))
        || !previous.exists()
    {
        return Err(error("update_rollback_unavailable"));
    }
    let failed = current.with_extension(format!("failed-{}", state.id));
    reject_symlink(&current)?;
    reject_symlink(&previous)?;
    if failed.exists() {
        return Err(error("update_rollback_target_exists"));
    }
    fs::rename(&current, &failed).map_err(|_| error("update_rollback_failed"))?;
    if fs::rename(&previous, &current).is_err() {
        let _ = fs::rename(&failed, &current);
        return Err(error("update_rollback_failed"));
    }
    let _ = fs::remove_dir_all(&failed);
    state.state = "completed".to_string();
    state.previous_path = None;
    write_state(app_data, state)?;
    Ok(json!({
        "schema": SCHEMA,
        "status": "rolled_back",
        "id": state.id,
        "rollback": true,
        "run_outcome": "recovered",
    }))
}

pub fn install(
    app_data: &Path,
    current_executable: &Path,
    update_id: &str,
) -> Result<Value, String> {
    if !safe_component(update_id, 160) {
        return Err(error("update_identity_invalid"));
    }
    let mut state = read_state(app_data)?.ok_or_else(|| error("update_not_downloaded"))?;
    if state.id != update_id || state.state != "ready" {
        return Err(error("update_not_ready"));
    }
    let root = update_root(app_data);
    if state.staged_path.parent() != Some(root.as_path()) {
        return Err(error("update_path_invalid"));
    }
    reject_symlink(&state.staged_path)?;
    if !state.staged_path.is_file() {
        return Err(error("update_stage_missing"));
    }
    if digest_file(&state.staged_path)? != state.artifact.digest {
        return Err(error("update_checksum_mismatch"));
    }
    install_bundle(app_data, current_executable, &mut state)
}

pub fn rollback(app_data: &Path, current_executable: &Path) -> Result<Value, String> {
    let mut state = read_state(app_data)?.ok_or_else(|| error("update_rollback_unavailable"))?;
    if !matches!(state.state.as_str(), "relaunch_pending" | "awaiting_health") {
        return Err(error("update_rollback_unavailable"));
    }
    swap_back(app_data, &mut state, current_executable)
}

pub fn status(app_data: &Path) -> Result<Value, String> {
    Ok(read_state(app_data)?
        .map(|state| state_to_json(&state))
        .unwrap_or_else(|| {
            json!({
                "schema": SCHEMA,
                "state": "idle",
                "anonymous": true,
                "target": { "platform": expected_target().0, "arch": expected_target().1 },
            })
        }))
}

/// Called at startup.  A healthy new bundle settles the receipt; an invalid
/// or missing candidate is rolled back before the UI is exposed.
pub fn reconcile_startup(
    app_data: &Path,
    current_executable: &Path,
) -> Result<Option<Value>, String> {
    let mut state = match read_state(app_data)? {
        Some(state) if state.state == "awaiting_health" => state,
        _ => return Ok(None),
    };
    let current = current_bundle(current_executable)?;
    if bundle_version(&current).as_deref() == Some(state.artifact.version.as_str()) {
        state.state = "completed".to_string();
        write_state(app_data, &state)?;
        return Ok(Some(json!({
            "schema": SCHEMA,
            "status": "healthy",
            "id": state.id,
            "running_version": state.artifact.version,
            "run_outcome": "completed",
        })));
    }
    swap_back(app_data, &mut state, current_executable).map(Some)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    fn fixture(name: &str) -> (PathBuf, PathBuf) {
        static NEXT: AtomicU64 = AtomicU64::new(1);
        let root = std::env::temp_dir().join(format!(
            "simplicio-desktop-update-{name}-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let app_data = root.join("data");
        let app = root.join("Simplicio.app");
        fs::create_dir_all(app.join("Contents").join("MacOS")).unwrap();
        fs::create_dir_all(&app_data).unwrap();
        (root, app)
    }

    fn artifact(version: &str) -> ReleaseArtifact {
        ReleaseArtifact {
            version: version.to_string(),
            tag: format!("v{version}"),
            asset_name: "Simplicio-3.8.99-arm64.zip".to_string(),
            asset_bytes: 10,
            digest: "sha256:".to_string() + &"a".repeat(64),
            url: fixed_asset_url(&format!("v{version}"), "Simplicio-3.8.99-arm64.zip").unwrap(),
        }
    }

    #[test]
    fn rejects_manifest_without_digest_or_official_urls() {
        let payload = json!([{
            "tag_name": "v3.8.99",
            "draft": false,
            "prerelease": false,
            "html_url": format!("{RELEASES_URL}/tag/v3.8.99"),
            "assets": [{
                "name": "Simplicio-3.8.99-arm64.zip",
                "state": "uploaded",
                "size": 10,
                "browser_download_url": format!("{RELEASES_URL}/download/v3.8.99/Simplicio-3.8.99-arm64.zip")
            }]
        }]);
        assert_eq!(
            parse_manifest(
                payload.to_string().as_bytes(),
                "v3.8.99",
                "Simplicio-3.8.99-arm64.zip"
            )
            .unwrap_err(),
            "update_digest_unavailable"
        );
    }

    #[test]
    fn keeps_version_and_identity_bound_to_the_manifest() {
        let payload = json!([{
            "tag_name": "v3.8.99",
            "draft": false,
            "prerelease": false,
            "html_url": format!("{RELEASES_URL}/tag/v3.8.99"),
            "assets": [{
                "name": "Simplicio-3.8.99-arm64.zip",
                "state": "uploaded",
                "size": 10,
                "digest": "sha256:".to_string() + &"a".repeat(64),
                "browser_download_url": format!("{RELEASES_URL}/download/v3.8.99/Simplicio-3.8.99-arm64.zip")
            }]
        }]);
        assert!(parse_manifest(
            payload.to_string().as_bytes(),
            "v3.8.99",
            "Simplicio-3.8.99-arm64.zip"
        )
        .is_ok());
        assert_eq!(
            fixed_asset_url("v3.8.99", "a/b").unwrap_err(),
            "update_identity_invalid"
        );
    }

    #[test]
    fn state_is_durable_and_never_claims_health_before_startup_reconcile() {
        let (root, app) = fixture("state");
        let app_data = root.join("data");
        let artifact = artifact("3.8.99");
        let state = UpdateState {
            id: "test-state".to_string(),
            state: "awaiting_health".to_string(),
            artifact,
            received_bytes: 10,
            staged_path: root.join("package.zip"),
            previous_path: Some(root.join("Simplicio.app.previous-test")),
        };
        write_state(&app_data, &state).unwrap();
        assert_eq!(status(&app_data).unwrap()["state"], "awaiting_health");
        fs::remove_dir_all(root).unwrap();
        let _ = app;
    }

    #[test]
    fn startup_reconcile_accepts_expected_bundle_version() {
        let (root, app) = fixture("healthy");
        let app_data = root.join("data");
        fs::write(
            app.join("Contents").join("Info.plist"),
            "<key>CFBundleShortVersionString</key><string>3.8.99</string>",
        )
        .unwrap();
        let artifact = artifact("3.8.99");
        let state = UpdateState {
            id: "healthy-state".to_string(),
            state: "awaiting_health".to_string(),
            artifact,
            received_bytes: 10,
            staged_path: root.join("package.zip"),
            previous_path: Some(root.join("Simplicio.app.previous")),
        };
        write_state(&app_data, &state).unwrap();
        let result = reconcile_startup(
            &app_data,
            &app.join("Contents").join("MacOS").join("simplicio-desktop"),
        )
        .unwrap();
        assert_eq!(result.unwrap()["status"], "healthy");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rollback_restores_previous_bundle_after_failed_launch() {
        let (root, app) = fixture("rollback");
        let app_data = root.join("data");
        fs::write(
            app.join("Contents").join("Info.plist"),
            "<key>CFBundleShortVersionString</key><string>3.8.99</string>",
        )
        .unwrap();
        let previous = root.join("Simplicio.app.previous-rollback-state");
        fs::create_dir_all(previous.join("Contents").join("MacOS")).unwrap();
        fs::write(
            previous.join("Contents").join("Info.plist"),
            "<key>CFBundleShortVersionString</key><string>3.8.98</string>",
        )
        .unwrap();
        let state = UpdateState {
            id: "rollback-state".to_string(),
            state: "awaiting_health".to_string(),
            artifact: artifact("3.8.99"),
            received_bytes: 10,
            staged_path: root.join("package.zip"),
            previous_path: Some(previous),
        };
        write_state(&app_data, &state).unwrap();

        let result = rollback(
            &app_data,
            &app.join("Contents").join("MacOS").join("simplicio-desktop"),
        )
        .unwrap();
        assert_eq!(result["status"], "rolled_back");
        assert_eq!(bundle_version(&app), Some("3.8.98".to_string()));
        assert_eq!(status(&app_data).unwrap()["state"], "completed");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn startup_reconcile_rolls_back_when_candidate_version_is_wrong() {
        let (root, app) = fixture("failed-candidate");
        let app_data = root.join("data");
        fs::write(
            app.join("Contents").join("Info.plist"),
            "<key>CFBundleShortVersionString</key><string>3.8.98</string>",
        )
        .unwrap();
        let previous = root.join("Simplicio.app.previous-failed-candidate");
        fs::create_dir_all(previous.join("Contents").join("MacOS")).unwrap();
        fs::write(
            previous.join("Contents").join("Info.plist"),
            "<key>CFBundleShortVersionString</key><string>3.8.97</string>",
        )
        .unwrap();
        let state = UpdateState {
            id: "failed-candidate".to_string(),
            state: "awaiting_health".to_string(),
            artifact: artifact("3.8.99"),
            received_bytes: 10,
            staged_path: root.join("package.zip"),
            previous_path: Some(previous),
        };
        write_state(&app_data, &state).unwrap();

        let result = reconcile_startup(
            &app_data,
            &app.join("Contents").join("MacOS").join("simplicio-desktop"),
        )
        .unwrap()
        .unwrap();
        assert_eq!(result["status"], "rolled_back");
        assert_eq!(bundle_version(&app), Some("3.8.97".to_string()));
        assert_eq!(status(&app_data).unwrap()["state"], "completed");
        fs::remove_dir_all(root).unwrap();
    }
}
