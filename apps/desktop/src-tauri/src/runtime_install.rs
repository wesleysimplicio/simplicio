use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::cmp::Ordering;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

const RESULT_SCHEMA: &str = "simplicio.desktop-runtime-install/v1";
const LOCK_NAME: &str = ".runtime-install.lock";
const MANAGED_RECEIPT_SCHEMA: &str = "simplicio.desktop-runtime-receipt/v1";
const MANAGED_RECEIPT_NAME: &str = "desktop-runtime-receipt.json";
const MAX_MANAGED_RECEIPT_BYTES: u64 = 1_024;
const MAX_RECEIPT_SNAPSHOT_BYTES: u64 = 64 * 1_024;

#[derive(Debug, Eq, PartialEq)]
enum PrereleaseIdentifier {
    Numeric(String),
    Text(String),
}

impl Ord for PrereleaseIdentifier {
    fn cmp(&self, other: &Self) -> Ordering {
        match (self, other) {
            (Self::Numeric(left), Self::Numeric(right)) => {
                left.len().cmp(&right.len()).then_with(|| left.cmp(right))
            }
            (Self::Numeric(_), Self::Text(_)) => Ordering::Less,
            (Self::Text(_), Self::Numeric(_)) => Ordering::Greater,
            (Self::Text(left), Self::Text(right)) => left.cmp(right),
        }
    }
}

impl PartialOrd for PrereleaseIdentifier {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Debug, Eq, PartialEq)]
struct SemanticVersion {
    core: (u64, u64, u64),
    prerelease: Vec<PrereleaseIdentifier>,
}

impl Ord for SemanticVersion {
    fn cmp(&self, other: &Self) -> Ordering {
        self.core.cmp(&other.core).then_with(|| {
            match (self.prerelease.is_empty(), other.prerelease.is_empty()) {
                (true, true) => Ordering::Equal,
                (true, false) => Ordering::Greater,
                (false, true) => Ordering::Less,
                (false, false) => self.prerelease.cmp(&other.prerelease),
            }
        })
    }
}

impl PartialOrd for SemanticVersion {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

fn valid_identifiers(value: &str, prerelease: bool) -> bool {
    !value.is_empty()
        && value.split('.').all(|identifier| {
            !identifier.is_empty()
                && identifier
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
                && (!prerelease
                    || !identifier.bytes().all(|byte| byte.is_ascii_digit())
                    || identifier == "0"
                    || !identifier.starts_with('0'))
        })
}

fn semantic_version(value: &str) -> Result<SemanticVersion, String> {
    let (without_build, build) = value
        .split_once('+')
        .map_or((value, None), |(version, build)| (version, Some(build)));
    if build.is_some_and(|build| build.contains('+') || !valid_identifiers(build, false)) {
        return Err("runtime_install_version_invalid".to_string());
    }
    let (core, prerelease) = without_build
        .split_once('-')
        .map_or((without_build, None), |(core, prerelease)| {
            (core, Some(prerelease))
        });
    if prerelease.is_some_and(|value| !valid_identifiers(value, true)) {
        return Err("runtime_install_version_invalid".to_string());
    }
    let core = core
        .split('.')
        .map(|part| {
            if part.is_empty()
                || (part.len() > 1 && part.starts_with('0'))
                || !part.bytes().all(|byte| byte.is_ascii_digit())
            {
                return Err("runtime_install_version_invalid".to_string());
            }
            part.parse::<u64>()
                .map_err(|_| "runtime_install_version_invalid".to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    if core.len() != 3 {
        return Err("runtime_install_version_invalid".to_string());
    }
    let prerelease = prerelease
        .map(|value| {
            value
                .split('.')
                .map(|identifier| {
                    if identifier.bytes().all(|byte| byte.is_ascii_digit()) {
                        PrereleaseIdentifier::Numeric(identifier.to_string())
                    } else {
                        PrereleaseIdentifier::Text(identifier.to_string())
                    }
                })
                .collect()
        })
        .unwrap_or_default();
    Ok(SemanticVersion {
        core: (core[0], core[1], core[2]),
        prerelease,
    })
}

fn invalid_path() -> String {
    "runtime_install_path_invalid".to_string()
}

fn executable_name() -> &'static str {
    if cfg!(windows) {
        "simplicio.exe"
    } else {
        "simplicio"
    }
}

pub fn bundled_runtime_path(current_executable: &Path) -> Result<PathBuf, String> {
    let parent = current_executable.parent().ok_or_else(invalid_path)?;
    require_directory(parent, "runtime_install_package_unavailable")?;
    Ok(parent.join(executable_name()))
}

fn install_paths(home: &Path) -> (PathBuf, PathBuf, PathBuf) {
    let bin = home.join(".simplicio").join("bin");
    let target = bin.join(executable_name());
    let backup = bin.join(if cfg!(windows) {
        "simplicio.previous.exe"
    } else {
        "simplicio.previous"
    });
    (bin, target, backup)
}

fn managed_receipt_path(home: &Path) -> PathBuf {
    home.join(".simplicio").join(MANAGED_RECEIPT_NAME)
}

fn reject_symlink(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() => Err(invalid_path()),
        Ok(_) | Err(_) => Ok(()),
    }
}

fn reject_symlink_ancestors(path: &Path) -> Result<(), String> {
    let mut ancestor = PathBuf::new();
    for component in path.components() {
        ancestor.push(component.as_os_str());
        match fs::symlink_metadata(&ancestor) {
            Ok(metadata) if metadata.file_type().is_symlink() => return Err(invalid_path()),
            Ok(_) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => break,
            Err(_) => return Err(invalid_path()),
        }
    }
    Ok(())
}

fn require_directory(path: &Path, error_code: &str) -> Result<(), String> {
    reject_symlink_ancestors(path)?;
    fs::metadata(path)
        .ok()
        .filter(|metadata| metadata.is_dir())
        .map(|_| ())
        .ok_or_else(|| error_code.to_string())
}

fn require_regular_file(path: &Path) -> Result<(), String> {
    reject_symlink(path)?;
    fs::metadata(path)
        .ok()
        .filter(|metadata| metadata.is_file())
        .map(|_| ())
        .ok_or_else(|| "runtime_install_package_unavailable".to_string())
}

fn ensure_private_directory(path: &Path) -> Result<(), String> {
    reject_symlink(path)?;
    fs::create_dir_all(path).map_err(|_| "runtime_install_directory_unavailable".to_string())?;
    let metadata =
        fs::metadata(path).map_err(|_| "runtime_install_directory_unavailable".to_string())?;
    if !metadata.is_dir() {
        return Err(invalid_path());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))
            .map_err(|_| "runtime_install_permissions_failed".to_string())?;
    }
    Ok(())
}

fn set_private_executable(path: &Path) -> Result<(), String> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))
            .map_err(|_| "runtime_install_permissions_failed".to_string())?;
    }
    #[cfg(not(unix))]
    let _ = path;
    Ok(())
}

fn digest(path: &Path) -> Result<[u8; 32], String> {
    let mut file = File::open(path).map_err(|_| "runtime_install_read_failed".to_string())?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|_| "runtime_install_read_failed".to_string())?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(hasher.finalize().into())
}

fn digest_text(value: [u8; 32]) -> String {
    let mut encoded = String::with_capacity(71);
    encoded.push_str("sha256:");
    for byte in value {
        use std::fmt::Write as _;
        write!(&mut encoded, "{byte:02x}").expect("writing to a String cannot fail");
    }
    encoded
}

fn parse_digest(value: &str) -> Option<[u8; 32]> {
    let hex = value.strip_prefix("sha256:")?;
    if hex.len() != 64
        || !hex
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return None;
    }
    let mut parsed = [0u8; 32];
    for (index, pair) in hex.as_bytes().chunks_exact(2).enumerate() {
        parsed[index] = u8::from_str_radix(std::str::from_utf8(pair).ok()?, 16).ok()?;
    }
    Some(parsed)
}

#[derive(Debug, Eq, PartialEq)]
struct ManagedEvidence {
    version: SemanticVersion,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct ManagedReceiptDocument {
    schema: String,
    digest: String,
    version: String,
    source: String,
}

fn read_managed_receipt(home: &Path) -> Result<Option<Vec<u8>>, String> {
    let path = managed_receipt_path(home);
    reject_symlink(&path)?;
    let mut file = match File::open(&path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("runtime_install_receipt_read_failed".to_string()),
    };
    let metadata = file
        .metadata()
        .map_err(|_| "runtime_install_receipt_read_failed".to_string())?;
    if !metadata.is_file() {
        return Err(invalid_path());
    }
    if metadata.len() > MAX_MANAGED_RECEIPT_BYTES {
        return Err("runtime_install_receipt_invalid".to_string());
    }
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    Read::by_ref(&mut file)
        .take(MAX_MANAGED_RECEIPT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "runtime_install_receipt_read_failed".to_string())?;
    if bytes.len() as u64 > MAX_MANAGED_RECEIPT_BYTES {
        return Err("runtime_install_receipt_invalid".to_string());
    }
    Ok(Some(bytes))
}

#[derive(Clone, Debug, Eq, PartialEq)]
enum ReceiptSnapshot {
    Missing,
    Bytes(Vec<u8>),
}

fn read_receipt_snapshot_bytes(home: &Path) -> Result<Option<Vec<u8>>, String> {
    let path = managed_receipt_path(home);
    reject_symlink(&path)?;
    let mut file = match File::open(&path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("runtime_install_receipt_read_failed".to_string()),
    };
    let metadata = file
        .metadata()
        .map_err(|_| "runtime_install_receipt_read_failed".to_string())?;
    if !metadata.is_file() {
        return Err(invalid_path());
    }
    if metadata.len() > MAX_RECEIPT_SNAPSHOT_BYTES {
        return Err("runtime_install_receipt_invalid".to_string());
    }
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    Read::by_ref(&mut file)
        .take(MAX_RECEIPT_SNAPSHOT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "runtime_install_receipt_read_failed".to_string())?;
    if bytes.len() as u64 > MAX_RECEIPT_SNAPSHOT_BYTES {
        return Err("runtime_install_receipt_invalid".to_string());
    }
    Ok(Some(bytes))
}

fn snapshot_managed_receipt(home: &Path) -> Result<ReceiptSnapshot, String> {
    match read_receipt_snapshot_bytes(home) {
        Ok(Some(bytes)) => Ok(ReceiptSnapshot::Bytes(bytes)),
        Ok(None) => Ok(ReceiptSnapshot::Missing),
        Err(error) => Err(error),
    }
}

fn receipt_matches_snapshot(home: &Path, expected: &ReceiptSnapshot) -> Result<bool, String> {
    match (read_receipt_snapshot_bytes(home), expected) {
        (Ok(Some(actual)), ReceiptSnapshot::Bytes(expected)) => Ok(actual == *expected),
        (Ok(None), ReceiptSnapshot::Missing) => Ok(true),
        (Ok(_), _) => Ok(false),
        (Err(error), _) => Err(error),
    }
}

fn managed_receipt_is_private(home: &Path) -> Result<bool, String> {
    let path = managed_receipt_path(home);
    reject_symlink(&path)?;
    let metadata =
        fs::metadata(&path).map_err(|_| "runtime_install_receipt_read_failed".to_string())?;
    if !metadata.is_file() {
        return Err(invalid_path());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        return Ok(metadata.permissions().mode() & 0o077 == 0);
    }
    #[cfg(not(unix))]
    Ok(true)
}

fn managed_evidence(bytes: Option<&[u8]>, target_digest: [u8; 32]) -> Option<ManagedEvidence> {
    let document = serde_json::from_slice::<ManagedReceiptDocument>(bytes?).ok()?;
    if document.schema != MANAGED_RECEIPT_SCHEMA
        || document.source != "bundled"
        || parse_digest(&document.digest)? != target_digest
    {
        return None;
    }
    if document.version.is_empty() || document.version.len() > 64 {
        return None;
    }
    Some(ManagedEvidence {
        version: semantic_version(&document.version).ok()?,
    })
}

fn managed_receipt_bytes(version: &str, installed_digest: [u8; 32]) -> Result<Vec<u8>, String> {
    semantic_version(version).map_err(|_| "runtime_install_receipt_invalid".to_string())?;
    let bytes = serde_json::to_vec(&json!({
        "schema": MANAGED_RECEIPT_SCHEMA,
        "digest": digest_text(installed_digest),
        "version": version,
        "source": "bundled",
    }))
    .map_err(|_| "runtime_install_receipt_write_failed".to_string())?;
    if bytes.len() as u64 > MAX_MANAGED_RECEIPT_BYTES {
        return Err("runtime_install_receipt_write_failed".to_string());
    }
    Ok(bytes)
}

struct InstallLock {
    // The operating system releases this lock when the process exits, including
    // an unclean exit. The durable file is only a rendezvous point and is never
    // treated as evidence that another installer is still alive.
    _file: File,
}

#[cfg(unix)]
fn try_lock_file(file: &File) -> Result<(), String> {
    use std::os::fd::AsRawFd;

    const LOCK_EX: i32 = 2;
    const LOCK_NB: i32 = 4;
    extern "C" {
        fn flock(fd: i32, operation: i32) -> i32;
    }
    // SAFETY: flock only observes the live descriptor owned by `file`; the
    // descriptor remains open for the complete lifetime of InstallLock.
    if unsafe { flock(file.as_raw_fd(), LOCK_EX | LOCK_NB) } == 0 {
        Ok(())
    } else {
        Err("runtime_install_busy".to_string())
    }
}

fn set_private_file(path: &Path) -> Result<(), String> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))
            .map_err(|_| "runtime_install_permissions_failed".to_string())?;
    }
    #[cfg(not(unix))]
    let _ = path;
    Ok(())
}

fn acquire_lock(bin: &Path) -> Result<InstallLock, String> {
    let path = bin.join(LOCK_NAME);
    reject_symlink(&path)?;
    let mut options = OpenOptions::new();
    options.read(true).write(true).create(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        // Denying every sharing mode is an OS-held exclusive lock. A crashed
        // process releases the handle, so the persistent rendezvous file is
        // immediately reusable and can never strand installation.
        options.share_mode(0);
    }
    let mut file = options
        .open(&path)
        .map_err(|_| "runtime_install_busy".to_string())?;
    #[cfg(unix)]
    try_lock_file(&file)?;
    set_private_file(&path)?;
    file.set_len(0)
        .map_err(|_| "runtime_install_lock_failed".to_string())?;
    writeln!(file, "{}", std::process::id())
        .and_then(|()| file.sync_all())
        .map_err(|_| "runtime_install_lock_failed".to_string())?;
    Ok(InstallLock { _file: file })
}

struct TemporaryFile(Option<PathBuf>);

impl TemporaryFile {
    fn path(&self) -> &Path {
        self.0.as_deref().expect("staged file is armed")
    }

    fn disarm(&mut self) {
        self.0 = None;
    }
}

impl Drop for TemporaryFile {
    fn drop(&mut self) {
        if let Some(path) = &self.0 {
            let _ = fs::remove_file(path);
        }
    }
}

fn stage(source: &Path, bin: &Path, expected_digest: [u8; 32]) -> Result<TemporaryFile, String> {
    let path = bin.join(format!(
        ".simplicio.runtime.tmp-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    ));
    let mut input = File::open(source).map_err(|_| "runtime_install_read_failed".to_string())?;
    let staged = TemporaryFile(Some(path));
    let mut output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(staged.path())
        .map_err(|_| "runtime_install_stage_failed".to_string())?;
    std::io::copy(&mut input, &mut output)
        .and_then(|_| output.sync_all())
        .map_err(|_| "runtime_install_stage_failed".to_string())?;
    set_private_executable(staged.path())?;
    output
        .sync_all()
        .map_err(|_| "runtime_install_stage_failed".to_string())?;
    if digest(staged.path())? != expected_digest {
        return Err("runtime_install_stage_failed".to_string());
    }
    Ok(staged)
}

fn stage_bytes(bytes: &[u8], directory: &Path, error_code: &str) -> Result<TemporaryFile, String> {
    let path = directory.join(format!(
        ".simplicio.receipt.tmp-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    ));
    let staged = TemporaryFile(Some(path));
    let mut output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(staged.path())
        .map_err(|_| error_code.to_string())?;
    output
        .write_all(bytes)
        .and_then(|()| output.sync_all())
        .map_err(|_| error_code.to_string())?;
    set_private_file(staged.path()).map_err(|_| error_code.to_string())?;
    output.sync_all().map_err(|_| error_code.to_string())?;
    Ok(staged)
}

#[cfg(unix)]
fn atomic_replace(source: &Path, target: &Path, error_code: &str) -> Result<(), String> {
    fs::rename(source, target).map_err(|_| error_code.to_string())
}

#[cfg(windows)]
fn atomic_replace(source: &Path, target: &Path, error_code: &str) -> Result<(), String> {
    use std::os::windows::ffi::OsStrExt;

    const MOVEFILE_REPLACE_EXISTING: u32 = 0x1;
    const MOVEFILE_WRITE_THROUGH: u32 = 0x8;
    #[link(name = "kernel32")]
    extern "system" {
        fn MoveFileExW(existing: *const u16, replacement: *const u16, flags: u32) -> i32;
    }
    let source = source
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    let target = target
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect::<Vec<_>>();
    // SAFETY: both buffers are NUL-terminated and remain alive for the call.
    // Paths are same-directory installer-owned paths. WRITE_THROUGH is the
    // Windows durability equivalent of syncing the containing directory.
    let moved = unsafe {
        MoveFileExW(
            source.as_ptr(),
            target.as_ptr(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
    };
    if moved == 0 {
        Err(error_code.to_string())
    } else {
        Ok(())
    }
}

fn sync_regular_file(path: &Path, error_code: &str) -> Result<(), String> {
    File::open(path)
        .and_then(|file| file.sync_all())
        .map_err(|_| error_code.to_string())
}

#[cfg(unix)]
fn sync_directory(path: &Path, error_code: &str) -> Result<(), String> {
    File::open(path)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| error_code.to_string())
}

#[cfg(windows)]
fn sync_directory(_path: &Path, _error_code: &str) -> Result<(), String> {
    // MoveFileExW(MOVEFILE_WRITE_THROUGH) flushes the move metadata before it
    // returns. File contents are separately sync_all'd before every move.
    Ok(())
}

fn replace_staged(
    temporary: &mut TemporaryFile,
    target: &Path,
    error_code: &str,
) -> Result<(), String> {
    replace_staged_with(temporary, target, error_code, &mut atomic_replace)
}

fn replace_staged_with<R>(
    temporary: &mut TemporaryFile,
    target: &Path,
    error_code: &str,
    replacer: &mut R,
) -> Result<(), String>
where
    R: FnMut(&Path, &Path, &str) -> Result<(), String>,
{
    reject_symlink(target)?;
    replacer(temporary.path(), target, error_code)?;
    temporary.disarm();
    Ok(())
}

fn backup_existing(
    source: &Path,
    backup: &Path,
    bin: &Path,
    expected_digest: [u8; 32],
) -> Result<(), String> {
    let mut temporary = stage(source, bin, expected_digest)
        .map_err(|_| "runtime_install_backup_failed".to_string())?;
    replace_staged(&mut temporary, backup, "runtime_install_backup_failed")?;
    sync_regular_file(backup, "runtime_install_backup_failed")?;
    sync_directory(bin, "runtime_install_backup_failed")?;
    if digest(backup).map_err(|_| "runtime_install_backup_failed".to_string())? != expected_digest {
        return Err("runtime_install_backup_failed".to_string());
    }
    Ok(())
}

fn restore_backup(
    backup: &Path,
    target: &Path,
    bin: &Path,
    expected_digest: [u8; 32],
) -> Result<(), String> {
    require_regular_file(backup).map_err(|_| "runtime_install_rollback_failed".to_string())?;
    if digest(backup).map_err(|_| "runtime_install_rollback_failed".to_string())? != expected_digest
    {
        return Err("runtime_install_rollback_failed".to_string());
    }
    let mut temporary = stage(backup, bin, expected_digest)
        .map_err(|_| "runtime_install_rollback_failed".to_string())?;
    replace_staged(&mut temporary, target, "runtime_install_rollback_failed")?;
    set_private_executable(target).map_err(|_| "runtime_install_rollback_failed".to_string())?;
    sync_regular_file(target, "runtime_install_rollback_failed")?;
    sync_directory(bin, "runtime_install_rollback_failed")?;
    if digest(target).map_err(|_| "runtime_install_rollback_failed".to_string())? != expected_digest
    {
        return Err("runtime_install_rollback_failed".to_string());
    }
    Ok(())
}

fn safe_existing_file(path: &Path) -> Result<bool, String> {
    reject_symlink(path)?;
    match fs::metadata(path) {
        Ok(metadata) if metadata.is_file() => Ok(true),
        Ok(_) => Err(invalid_path()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err("runtime_install_read_failed".to_string()),
    }
}

fn metadata_is_stable(before: &fs::Metadata, after: &fs::Metadata) -> bool {
    if before.len() != after.len()
        || before.modified().ok() != after.modified().ok()
        || !before.is_file()
        || !after.is_file()
    {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if before.dev() != after.dev() || before.ino() != after.ino() {
            return false;
        }
    }
    true
}

fn stable_regular_digest(path: &Path) -> Result<Option<[u8; 32]>, String> {
    let before = match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_file() => {
            return Err(invalid_path())
        }
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("runtime_install_read_failed".to_string()),
    };
    let actual = digest(path)?;
    let after =
        fs::symlink_metadata(path).map_err(|_| "runtime_install_read_failed".to_string())?;
    if after.file_type().is_symlink() || !metadata_is_stable(&before, &after) {
        return Err("runtime_install_precondition_changed".to_string());
    }
    Ok(Some(actual))
}

fn target_matches_previous(
    target: &Path,
    previous_digest: Option<[u8; 32]>,
) -> Result<bool, String> {
    match previous_digest {
        Some(expected) => stable_regular_digest(target).map(|actual| actual == Some(expected)),
        None => stable_regular_digest(target).map(|actual| actual.is_none()),
    }
}

fn write_managed_receipt(home: &Path, bytes: &[u8]) -> Result<(), String> {
    let root = home.join(".simplicio");
    require_directory(&root, "runtime_install_receipt_write_failed")?;
    let path = managed_receipt_path(home);
    reject_symlink(&path)?;
    let mut temporary = stage_bytes(bytes, &root, "runtime_install_receipt_write_failed")?;
    replace_staged(
        &mut temporary,
        &path,
        "runtime_install_receipt_write_failed",
    )?;
    set_private_file(&path).map_err(|_| "runtime_install_receipt_write_failed".to_string())?;
    sync_regular_file(&path, "runtime_install_receipt_write_failed")?;
    sync_directory(&root, "runtime_install_receipt_write_failed")?;
    let persisted = read_managed_receipt(home)
        .map_err(|_| "runtime_install_receipt_write_failed".to_string())?;
    if persisted.as_deref() != Some(bytes) {
        return Err("runtime_install_receipt_write_failed".to_string());
    }
    Ok(())
}

fn restore_managed_receipt(home: &Path, previous: &ReceiptSnapshot) -> Result<(), String> {
    let root = home.join(".simplicio");
    let path = managed_receipt_path(home);
    reject_symlink(&path).map_err(|_| "runtime_install_rollback_failed".to_string())?;
    match previous {
        ReceiptSnapshot::Bytes(bytes) => {
            let mut temporary = stage_bytes(bytes, &root, "runtime_install_rollback_failed")?;
            replace_staged(&mut temporary, &path, "runtime_install_rollback_failed")?;
            set_private_file(&path).map_err(|_| "runtime_install_rollback_failed".to_string())?;
            sync_regular_file(&path, "runtime_install_rollback_failed")?;
        }
        ReceiptSnapshot::Missing => match fs::metadata(&path) {
            Ok(metadata) if metadata.is_file() => {
                fs::remove_file(&path).map_err(|_| "runtime_install_rollback_failed".to_string())?
            }
            Ok(_) => return Err("runtime_install_rollback_failed".to_string()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => return Err("runtime_install_rollback_failed".to_string()),
        },
    }
    sync_directory(&root, "runtime_install_rollback_failed")?;
    if !receipt_matches_snapshot(home, previous)
        .map_err(|_| "runtime_install_rollback_failed".to_string())?
    {
        return Err("runtime_install_rollback_failed".to_string());
    }
    Ok(())
}

fn write_managed_receipt_transactional<W>(
    home: &Path,
    previous: &ReceiptSnapshot,
    desired: &[u8],
    writer: &mut W,
) -> Result<(), String>
where
    W: FnMut(&Path, &[u8]) -> Result<(), String>,
{
    let desired_snapshot = ReceiptSnapshot::Bytes(desired.to_vec());
    if receipt_matches_snapshot(home, &desired_snapshot)
        .map_err(|_| "runtime_install_receipt_write_failed".to_string())?
        && managed_receipt_is_private(home)
            .map_err(|_| "runtime_install_receipt_write_failed".to_string())?
    {
        return Ok(());
    }
    let write_result = writer(home, desired);
    let desired_persisted = matches!(receipt_matches_snapshot(home, &desired_snapshot), Ok(true))
        && matches!(managed_receipt_is_private(home), Ok(true));
    if write_result.is_ok() && desired_persisted {
        return Ok(());
    }
    if matches!(receipt_matches_snapshot(home, previous), Ok(true)) {
        return Err("runtime_install_receipt_write_failed".to_string());
    }
    if restore_managed_receipt(home, previous).is_err() {
        return Err("runtime_install_rollback_failed".to_string());
    }
    Err("runtime_install_receipt_write_failed".to_string())
}

fn rollback_published_install<H>(
    home: &Path,
    bin: &Path,
    target: &Path,
    backup: &Path,
    published_digest: [u8; 32],
    previous_digest: Option<[u8; 32]>,
    previous_receipt: &ReceiptSnapshot,
    phase_hook: &mut H,
) -> Result<(), String>
where
    H: FnMut(InstallPhase),
{
    if stable_regular_digest(target).map_err(|_| "runtime_install_rollback_failed".to_string())?
        != Some(published_digest)
    {
        return Err("runtime_install_rollback_failed".to_string());
    }
    let target_result = if let Some(previous_digest) = previous_digest {
        restore_backup(backup, target, bin, previous_digest)
    } else {
        (|| {
            reject_symlink(target).map_err(|_| "runtime_install_rollback_failed".to_string())?;
            match fs::metadata(target) {
                Ok(metadata) if metadata.is_file() => fs::remove_file(target)
                    .map_err(|_| "runtime_install_rollback_failed".to_string())?,
                Ok(_) => return Err("runtime_install_rollback_failed".to_string()),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(_) => return Err("runtime_install_rollback_failed".to_string()),
            }
            sync_directory(bin, "runtime_install_rollback_failed")?;
            Ok(())
        })()
    };
    let receipt_result = restore_managed_receipt(home, previous_receipt);
    if previous_digest.is_none() && target_result.is_ok() && receipt_result.is_ok() {
        phase_hook(InstallPhase::FreshRollbackSynced);
    }
    let target_verified = target_matches_previous(target, previous_digest).unwrap_or(false);
    let receipt_verified = receipt_matches_snapshot(home, previous_receipt).unwrap_or(false);
    // Re-read the target after the receipt so a non-cooperating writer cannot
    // recreate it during receipt restoration and still receive a "removed"
    // result.
    let target_still_verified = target_matches_previous(target, previous_digest).unwrap_or(false);
    if target_result.is_err()
        || receipt_result.is_err()
        || !target_verified
        || !receipt_verified
        || !target_still_verified
    {
        Err("runtime_install_rollback_failed".to_string())
    } else {
        Ok(())
    }
}

fn runtime_summary(snapshot: &Value) -> Result<Value, String> {
    let runtime = snapshot
        .get("runtime")
        .and_then(Value::as_object)
        .ok_or_else(|| "runtime_install_verification_failed".to_string())?;
    let state = runtime
        .get("state")
        .and_then(Value::as_str)
        .filter(|state| *state == "healthy")
        .ok_or_else(|| "runtime_install_verification_failed".to_string())?;
    let version = runtime
        .get("version")
        .and_then(Value::as_str)
        .filter(|version| {
            !version.is_empty()
                && version.len() <= 64
                && version.bytes().all(|byte| {
                    byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'+' | b'_' | b'-')
                })
        })
        .ok_or_else(|| "runtime_install_verification_failed".to_string())?;
    semantic_version(version).map_err(|_| "runtime_install_verification_failed".to_string())?;
    Ok(json!({ "state": state, "version": version }))
}

fn runtime_version(snapshot: &Value) -> Result<SemanticVersion, String> {
    let summary = runtime_summary(snapshot)?;
    semantic_version(
        summary
            .get("version")
            .and_then(Value::as_str)
            .ok_or_else(|| "runtime_install_verification_failed".to_string())?,
    )
    .map_err(|_| "runtime_install_verification_failed".to_string())
}

fn validate_stable_runtime<F>(
    path: &Path,
    validate: &mut F,
    error_code: &str,
) -> Result<(Value, SemanticVersion, [u8; 32]), String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    require_regular_file(path).map_err(|_| error_code.to_string())?;
    let before = digest(path).map_err(|_| error_code.to_string())?;
    let snapshot = validate(path).map_err(|_| error_code.to_string())?;
    require_regular_file(path).map_err(|_| error_code.to_string())?;
    let after = digest(path).map_err(|_| error_code.to_string())?;
    if before != after {
        return Err(error_code.to_string());
    }
    let version = runtime_version(&snapshot).map_err(|_| error_code.to_string())?;
    Ok((snapshot, version, after))
}

fn receipt(status: &str, backup_available: bool, snapshot: &Value) -> Result<Value, String> {
    Ok(json!({
        "schema": RESULT_SCHEMA,
        "status": status,
        "scope": "runtime_core",
        "source": "packaged_sidecar",
        "installed": true,
        "current": true,
        "validated": true,
        "backupAvailable": backup_available,
        "pluginsMutated": false,
        "runtime": runtime_summary(snapshot)?,
    }))
}

enum TargetState {
    Absent,
    Exact,
    Replace([u8; 32]),
    NewerReceipted,
    Untrusted,
}

fn inspect_target(
    target: &Path,
    home: &Path,
    source_version: &SemanticVersion,
    source_digest: [u8; 32],
) -> Result<(TargetState, Option<Vec<u8>>), String> {
    if !safe_existing_file(target)? {
        return Ok((TargetState::Absent, None));
    }
    let before = digest(target)?;
    require_regular_file(target).map_err(|_| "runtime_install_precondition_changed".to_string())?;
    let after = digest(target).map_err(|_| "runtime_install_precondition_changed".to_string())?;
    if before != after {
        return Err("runtime_install_precondition_changed".to_string());
    }
    if after == source_digest {
        return Ok((TargetState::Exact, None));
    }
    let receipt_bytes = read_managed_receipt(home)?;
    let Some(evidence) = managed_evidence(receipt_bytes.as_deref(), after) else {
        return Ok((TargetState::Untrusted, receipt_bytes));
    };
    let state = if evidence.version > *source_version {
        TargetState::NewerReceipted
    } else {
        TargetState::Replace(after)
    };
    Ok((state, receipt_bytes))
}

/// Resolves and validates the packaged sidecar without consulting PATH,
/// SIMPLICIO_RUNTIME_BIN, or the writable per-user installation.
pub fn bundled_authority<F>(current_executable: &Path, mut validate: F) -> Result<PathBuf, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    let source = bundled_runtime_path(current_executable)?;
    validate_stable_runtime(&source, &mut validate, "runtime_install_package_invalid")?;
    Ok(source)
}

/// Returns the packaged sidecar snapshot only when the managed installation is
/// exact, or when a receipt-bound newer managed binary must be preserved
/// without becoming an authority. Unreceipted divergent targets fail closed;
/// receipt-bound equal/older targets require repair.
pub fn current_snapshot<F>(
    current_executable: &Path,
    home: &Path,
    mut validate: F,
) -> Result<Option<Value>, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    require_directory(home, "runtime_install_home_unavailable")?;
    let source = bundled_runtime_path(current_executable)?;
    let (_, target, _) = install_paths(home);
    let (source_snapshot, source_version, source_digest) =
        validate_stable_runtime(&source, &mut validate, "runtime_install_package_invalid")?;
    match inspect_target(&target, home, &source_version, source_digest)?.0 {
        TargetState::Exact | TargetState::NewerReceipted => Ok(Some(source_snapshot)),
        TargetState::Absent | TargetState::Replace(_) => Ok(None),
        TargetState::Untrusted => Err("runtime_install_managed_unverified".to_string()),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum InstallPhase {
    BackupDurable,
    Published,
    FreshRollbackSynced,
}

/// Installs only the packaged Runtime binary. It never invokes the legacy global
/// installer and therefore cannot mutate MCP, plugin, hook, IDE, or LLM configs.
pub fn install<F>(current_executable: &Path, home: &Path, mut validate: F) -> Result<Value, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
{
    install_with_controls(
        current_executable,
        home,
        &mut validate,
        |_| {},
        sync_regular_file,
        sync_directory,
        atomic_replace,
        write_managed_receipt,
    )
}

fn install_with_hook<F, H>(
    current_executable: &Path,
    home: &Path,
    validate: &mut F,
    phase_hook: H,
) -> Result<Value, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
    H: FnMut(InstallPhase),
{
    install_with_controls(
        current_executable,
        home,
        validate,
        phase_hook,
        sync_regular_file,
        sync_directory,
        atomic_replace,
        write_managed_receipt,
    )
}

fn install_with_controls<F, H, S, D, P, W>(
    current_executable: &Path,
    home: &Path,
    validate: &mut F,
    mut phase_hook: H,
    mut post_sync_file: S,
    mut post_sync_directory: D,
    mut publish_runtime: P,
    mut write_receipt: W,
) -> Result<Value, String>
where
    F: FnMut(&Path) -> Result<Value, String>,
    H: FnMut(InstallPhase),
    S: FnMut(&Path, &str) -> Result<(), String>,
    D: FnMut(&Path, &str) -> Result<(), String>,
    P: FnMut(&Path, &Path, &str) -> Result<(), String>,
    W: FnMut(&Path, &[u8]) -> Result<(), String>,
{
    require_directory(home, "runtime_install_home_unavailable")?;
    let source = bundled_runtime_path(current_executable)?;
    let (source_snapshot, source_version, source_digest) =
        validate_stable_runtime(&source, validate, "runtime_install_package_invalid")?;

    let root = home.join(".simplicio");
    let (bin, target, backup) = install_paths(home);
    ensure_private_directory(&root)?;
    ensure_private_directory(&bin)?;
    reject_symlink(&target)?;
    reject_symlink(&backup)?;
    let _lock = acquire_lock(&bin)?;

    let source_version_text = runtime_summary(&source_snapshot)?
        .get("version")
        .and_then(Value::as_str)
        .ok_or_else(|| "runtime_install_package_invalid".to_string())?
        .to_string();
    let desired_receipt = managed_receipt_bytes(&source_version_text, source_digest)?;
    let (target_state, classified_receipt) =
        inspect_target(&target, home, &source_version, source_digest)?;
    let previous_receipt: ReceiptSnapshot;
    let previous_digest = match target_state {
        TargetState::Absent => {
            previous_receipt = snapshot_managed_receipt(home)?;
            None
        }
        TargetState::Exact => {
            let exact_receipt = snapshot_managed_receipt(home)?;
            let backup_available = safe_existing_file(&backup)?;
            let success = receipt("already_current", backup_available, &source_snapshot)?;
            require_regular_file(&target)
                .map_err(|_| "runtime_install_precondition_changed".to_string())?;
            if digest(&target).map_err(|_| "runtime_install_precondition_changed".to_string())?
                != source_digest
            {
                return Err("runtime_install_precondition_changed".to_string());
            }
            write_managed_receipt_transactional(
                home,
                &exact_receipt,
                &desired_receipt,
                &mut write_receipt,
            )?;
            let target_still_exact = matches!(
                stable_regular_digest(&target),
                Ok(Some(actual)) if actual == source_digest
            );
            if !target_still_exact {
                if restore_managed_receipt(home, &exact_receipt).is_err() {
                    return Err("runtime_install_rollback_failed".to_string());
                }
                return Err("runtime_install_precondition_changed".to_string());
            }
            return Ok(success);
        }
        TargetState::NewerReceipted => {
            return Err("runtime_install_managed_newer_preserved".to_string());
        }
        TargetState::Untrusted => return Err("runtime_install_managed_unverified".to_string()),
        TargetState::Replace(target_digest) => {
            previous_receipt = ReceiptSnapshot::Bytes(
                classified_receipt.ok_or_else(|| "runtime_install_receipt_invalid".to_string())?,
            );
            Some(target_digest)
        }
    };

    if digest(&source).map_err(|_| "runtime_install_package_invalid".to_string())? != source_digest
    {
        return Err("runtime_install_package_invalid".to_string());
    }
    let mut temporary = stage(&source, &bin, source_digest)?;
    let had_target = previous_digest.is_some();
    if let Some(previous_digest) = previous_digest {
        require_regular_file(&target)
            .map_err(|_| "runtime_install_precondition_changed".to_string())?;
        if digest(&target).map_err(|_| "runtime_install_precondition_changed".to_string())?
            != previous_digest
        {
            return Err("runtime_install_precondition_changed".to_string());
        }
        backup_existing(&target, &backup, &bin, previous_digest)?;
        if digest(&target).map_err(|_| "runtime_install_precondition_changed".to_string())?
            != previous_digest
        {
            return Err("runtime_install_precondition_changed".to_string());
        }
        phase_hook(InstallPhase::BackupDurable);
    } else if safe_existing_file(&target)? {
        return Err("runtime_install_precondition_changed".to_string());
    }

    if replace_staged_with(
        &mut temporary,
        &target,
        "runtime_install_publish_failed",
        &mut publish_runtime,
    )
    .is_err()
    {
        let staged_readback = stable_regular_digest(temporary.path());
        let target_readback = stable_regular_digest(&target);
        let receipt_unchanged = receipt_matches_snapshot(home, &previous_receipt).unwrap_or(false);
        let staged_is_source =
            matches!(&staged_readback, Ok(Some(actual)) if *actual == source_digest);
        let staged_is_missing = matches!(&staged_readback, Ok(None));
        let target_is_source =
            matches!(&target_readback, Ok(Some(actual)) if *actual == source_digest);
        if staged_is_source
            && target_matches_previous(&target, previous_digest).unwrap_or(false)
            && receipt_unchanged
        {
            return Err("runtime_install_publish_failed".to_string());
        }
        let publish_effect_owned = staged_is_missing && target_is_source && receipt_unchanged;
        if !publish_effect_owned {
            return Err("runtime_install_rollback_failed".to_string());
        }
        if rollback_published_install(
            home,
            &bin,
            &target,
            &backup,
            source_digest,
            previous_digest,
            &previous_receipt,
            &mut phase_hook,
        )
        .is_err()
        {
            return Err("runtime_install_rollback_failed".to_string());
        }
        return Err(if had_target {
            "runtime_install_publish_failed_restored".to_string()
        } else {
            "runtime_install_publish_failed_removed".to_string()
        });
    }
    phase_hook(InstallPhase::Published);

    let activated = (|| {
        set_private_executable(&target)
            .map_err(|_| "runtime_install_post_replace_failed".to_string())?;
        post_sync_file(&target, "runtime_install_post_replace_failed")?;
        post_sync_directory(&bin, "runtime_install_post_replace_failed")?;
        require_regular_file(&target)
            .map_err(|_| "runtime_install_post_replace_failed".to_string())?;
        if digest(&target).map_err(|_| "runtime_install_post_replace_failed".to_string())?
            != source_digest
        {
            return Err("runtime_install_post_replace_failed".to_string());
        }
        write_managed_receipt_transactional(
            home,
            &previous_receipt,
            &desired_receipt,
            &mut write_receipt,
        )
        .map_err(|_| "runtime_install_post_replace_failed".to_string())?;
        Ok(source_snapshot.clone())
    })();

    match activated {
        Ok(snapshot) => receipt("installed", had_target, &snapshot),
        Err(_) => {
            if rollback_published_install(
                home,
                &bin,
                &target,
                &backup,
                source_digest,
                previous_digest,
                &previous_receipt,
                &mut phase_hook,
            )
            .is_err()
            {
                return Err("runtime_install_rollback_failed".to_string());
            }
            Err(if had_target {
                "runtime_install_post_replace_failed_restored".to_string()
            } else {
                "runtime_install_post_replace_failed_removed".to_string()
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT: AtomicU64 = AtomicU64::new(1);

    fn fixture() -> (PathBuf, PathBuf, PathBuf) {
        let temporary_root = std::env::temp_dir()
            .canonicalize()
            .unwrap_or_else(|_| std::env::temp_dir());
        let root = temporary_root.join(format!(
            "simplicio-runtime-install-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let bundle = root.join("bundle");
        let home = root.join("home");
        fs::create_dir_all(&bundle).unwrap();
        fs::create_dir_all(&home).unwrap();
        let app = bundle.join(if cfg!(windows) {
            "simplicio-desktop.exe"
        } else {
            "simplicio-desktop"
        });
        fs::write(bundle.join(executable_name()), b"runtime-current").unwrap();
        (root, app, home)
    }

    fn versioned_snapshot(version: &str) -> Value {
        json!({ "runtime": { "state": "healthy", "version": version } })
    }

    fn valid_snapshot() -> Value {
        versioned_snapshot("3.8.40")
    }

    fn record_managed(home: &Path, target: &Path, version: &str) {
        ensure_private_directory(&home.join(".simplicio")).unwrap();
        let bytes = managed_receipt_bytes(version, digest(target).unwrap()).unwrap();
        write_managed_receipt(home, &bytes).unwrap();
    }

    #[test]
    fn installs_atomically_with_private_permissions_and_a_sanitized_receipt() {
        let (root, app, home) = fixture();
        let result = install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        let (_, target, _) = install_paths(&home);
        assert_eq!(fs::read(&target).unwrap(), b"runtime-current");
        assert_eq!(result["status"], "installed");
        assert_eq!(result["pluginsMutated"], false);
        let installed_receipt = read_managed_receipt(&home).unwrap().unwrap();
        let installed_receipt: Value = serde_json::from_slice(&installed_receipt).unwrap();
        assert_eq!(installed_receipt["schema"], MANAGED_RECEIPT_SCHEMA);
        assert_eq!(installed_receipt["source"], "bundled");
        assert_eq!(installed_receipt["version"], "3.8.40");
        assert_eq!(
            installed_receipt["digest"],
            digest_text(digest(&target).unwrap())
        );
        let encoded = result.to_string();
        assert!(!encoded.contains(root.to_string_lossy().as_ref()));
        assert!(!encoded.contains("config"));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(&target).unwrap().permissions().mode() & 0o777,
                0o700
            );
            assert_eq!(
                fs::metadata(managed_receipt_path(&home))
                    .unwrap()
                    .permissions()
                    .mode()
                    & 0o777,
                0o600
            );
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn identical_install_is_idempotent_and_does_not_create_a_backup() {
        let (root, app, home) = fixture();
        install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        let result = install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        let (_, _, backup) = install_paths(&home);
        assert_eq!(result["status"], "already_current");
        assert_eq!(result["backupAvailable"], false);
        assert!(!backup.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn published_target_swap_is_never_executed_or_overwritten_by_rollback() {
        use std::os::unix::fs::PermissionsExt;

        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let previous_receipt = fs::read(managed_receipt_path(&home)).unwrap();
        let sentinel = root.join("published-target-executed");
        let target_for_hook = target.clone();
        let sentinel_for_hook = sentinel.clone();
        let mut validate = |path: &Path| {
            if path == target {
                let _ = std::process::Command::new(path).status();
                return Err("writable target was executed".to_string());
            }
            Ok(valid_snapshot())
        };
        let error = install_with_hook(&app, &home, &mut validate, move |phase| {
            if phase == InstallPhase::Published {
                fs::write(
                    &target_for_hook,
                    format!("#!/bin/sh\ntouch '{}'\n", sentinel_for_hook.display()),
                )
                .unwrap();
                fs::set_permissions(&target_for_hook, fs::Permissions::from_mode(0o700)).unwrap();
            }
        })
        .unwrap_err();
        assert_eq!(error, "runtime_install_rollback_failed");
        assert!(!sentinel.exists());
        assert!(fs::read_to_string(&target).unwrap().contains("touch"));
        assert_eq!(fs::read(&backup).unwrap(), b"runtime-previous");
        assert_eq!(
            fs::read(managed_receipt_path(&home)).unwrap(),
            previous_receipt
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn core_install_never_touches_plugin_or_host_configuration() {
        let (root, app, home) = fixture();
        let codex = home.join(".codex").join("config.toml");
        let plugins = home.join(".simplicio").join("plugins.json");
        fs::create_dir_all(codex.parent().unwrap()).unwrap();
        fs::create_dir_all(plugins.parent().unwrap()).unwrap();
        fs::write(&codex, "owned-by-user").unwrap();
        fs::write(&plugins, "owned-by-runtime").unwrap();
        install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        assert_eq!(fs::read_to_string(codex).unwrap(), "owned-by-user");
        assert_eq!(fs::read_to_string(plugins).unwrap(), "owned-by-runtime");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn current_snapshot_is_read_only_and_requires_the_packaged_version() {
        let (root, app, home) = fixture();
        assert!(current_snapshot(&app, &home, |_| Ok(valid_snapshot()))
            .unwrap()
            .is_none());
        install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        assert!(current_snapshot(&app, &home, |_| Ok(valid_snapshot()))
            .unwrap()
            .is_some());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn exact_bundle_bytes_ignore_and_repair_an_invalid_receipt() {
        for invalid in [b"not-json".to_vec(), vec![b'x'; 1_025]] {
            let (root, app, home) = fixture();
            let (bin, target, _) = install_paths(&home);
            fs::create_dir_all(&bin).unwrap();
            fs::copy(bundled_runtime_path(&app).unwrap(), &target).unwrap();
            fs::write(managed_receipt_path(&home), invalid).unwrap();
            assert!(current_snapshot(&app, &home, |path| {
                assert_ne!(path, target, "exact managed target must not be executed");
                Ok(valid_snapshot())
            })
            .unwrap()
            .is_some());
            assert_eq!(
                install(&app, &home, |path| {
                    assert_ne!(path, target, "exact managed target must not be executed");
                    Ok(valid_snapshot())
                })
                .unwrap()["status"],
                "already_current"
            );
            let repaired = read_managed_receipt(&home).unwrap().unwrap();
            assert!(managed_evidence(Some(&repaired), digest(&target).unwrap()).is_some());
            fs::remove_dir_all(root).unwrap();
        }
    }

    #[test]
    fn exact_target_receipt_partial_failure_restores_raw_receipt_without_touching_target() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::copy(bundled_runtime_path(&app).unwrap(), &target).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&target, fs::Permissions::from_mode(0o555)).unwrap();
        }
        let target_bytes = fs::read(&target).unwrap();
        #[cfg(unix)]
        let target_permissions = fs::metadata(&target).unwrap().permissions();
        #[cfg(unix)]
        let target_inode = {
            use std::os::unix::fs::MetadataExt;
            fs::metadata(&target).unwrap().ino()
        };
        let previous_receipt = vec![b'x'; 1_025];
        fs::write(managed_receipt_path(&home), &previous_receipt).unwrap();
        let mut validate = |path: &Path| {
            assert_ne!(path, target, "exact managed target must not be executed");
            Ok(valid_snapshot())
        };
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            sync_regular_file,
            sync_directory,
            atomic_replace,
            |writer_home: &Path, _desired: &[u8]| {
                let receipt_root = writer_home.join(".simplicio");
                let receipt_path = managed_receipt_path(writer_home);
                let mut temporary = stage_bytes(
                    b"{\"partial\":",
                    &receipt_root,
                    "runtime_install_receipt_write_failed",
                )?;
                replace_staged(
                    &mut temporary,
                    &receipt_path,
                    "runtime_install_receipt_write_failed",
                )?;
                sync_regular_file(&receipt_path, "runtime_install_receipt_write_failed")?;
                sync_directory(&receipt_root, "runtime_install_receipt_write_failed")?;
                Ok(())
            },
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_receipt_write_failed");
        assert_eq!(fs::read(&target).unwrap(), target_bytes);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(&target).unwrap().permissions().mode() & 0o777,
                target_permissions.mode() & 0o777
            );
            use std::os::unix::fs::MetadataExt;
            assert_eq!(fs::metadata(&target).unwrap().ino(), target_inode);
        }
        assert_eq!(
            fs::read(managed_receipt_path(&home)).unwrap(),
            previous_receipt
        );
        assert!(!backup.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn exact_target_change_after_receipt_commit_restores_receipt_without_touching_target() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::copy(bundled_runtime_path(&app).unwrap(), &target).unwrap();
        let previous_receipt = b"previous-desktop-receipt".to_vec();
        fs::write(managed_receipt_path(&home), &previous_receipt).unwrap();
        let target_for_writer = target.clone();
        let mut validate = |path: &Path| {
            assert_ne!(path, target, "exact managed target must not be executed");
            Ok(valid_snapshot())
        };
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            sync_regular_file,
            sync_directory,
            atomic_replace,
            move |writer_home: &Path, desired: &[u8]| {
                write_managed_receipt(writer_home, desired)?;
                fs::write(&target_for_writer, b"concurrent-target")
                    .map_err(|_| "injected_target_change".to_string())?;
                Ok(())
            },
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_precondition_changed");
        assert_eq!(fs::read(&target).unwrap(), b"concurrent-target");
        assert_eq!(
            fs::read(managed_receipt_path(&home)).unwrap(),
            previous_receipt
        );
        assert!(!backup.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn exact_bundle_bytes_are_current_without_a_receipt() {
        let (root, app, home) = fixture();
        let (bin, target, _) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::copy(bundled_runtime_path(&app).unwrap(), &target).unwrap();
        assert!(current_snapshot(&app, &home, |path| {
            assert_ne!(path, target, "exact managed target must not be executed");
            Ok(valid_snapshot())
        })
        .unwrap()
        .is_some());
        assert!(!managed_receipt_path(&home).exists());
        assert_eq!(
            install(&app, &home, |path| {
                assert_ne!(path, target, "exact managed target must not be executed");
                Ok(valid_snapshot())
            })
            .unwrap()["status"],
            "already_current"
        );
        assert!(managed_receipt_path(&home).exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn absent_target_replaces_stale_oversized_receipt_during_fresh_install() {
        let (root, app, home) = fixture();
        fs::create_dir_all(home.join(".simplicio")).unwrap();
        fs::write(managed_receipt_path(&home), vec![b'x'; 1_025]).unwrap();
        let result = install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        let (_, target, _) = install_paths(&home);
        assert_eq!(result["status"], "installed");
        let repaired = read_managed_receipt(&home).unwrap().unwrap();
        assert!(managed_evidence(Some(&repaired), digest(&target).unwrap()).is_some());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn newer_receipted_managed_runtime_is_preserved_but_never_used_as_authority() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-newer").unwrap();
        record_managed(&home, &target, "3.9.0");
        let validate = |path: &Path| {
            assert_ne!(path, target, "managed target must never be executed");
            Ok(valid_snapshot())
        };
        let snapshot = current_snapshot(&app, &home, validate).unwrap().unwrap();
        assert_eq!(snapshot["runtime"]["version"], "3.8.40");
        assert_eq!(
            install(&app, &home, validate).unwrap_err(),
            "runtime_install_managed_newer_preserved"
        );
        assert_eq!(fs::read(&target).unwrap(), b"runtime-newer");
        assert!(!backup.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn equal_version_with_different_bytes_is_repaired_with_a_backup() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"different-build-same-version").unwrap();
        record_managed(&home, &target, "3.8.40");
        assert!(current_snapshot(&app, &home, |_| Ok(valid_snapshot()))
            .unwrap()
            .is_none());
        let result = install(&app, &home, |_| Ok(valid_snapshot())).unwrap();
        assert_eq!(result["status"], "installed");
        assert_eq!(fs::read(&target).unwrap(), b"runtime-current");
        assert_eq!(fs::read(&backup).unwrap(), b"different-build-same-version");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn receipted_managed_runtime_with_invalid_executable_bytes_is_repairable() {
        for previous in [
            b"unreadable".as_slice(),
            b"degraded".as_slice(),
            b"invalid-version".as_slice(),
        ] {
            let (root, app, home) = fixture();
            let (bin, target, backup) = install_paths(&home);
            fs::create_dir_all(&bin).unwrap();
            fs::write(&target, previous).unwrap();
            record_managed(&home, &target, "3.8.39");
            let result = install(&app, &home, |path| {
                match fs::read(path).unwrap().as_slice() {
                    b"unreadable" | b"degraded" | b"invalid-version" => {
                        panic!("managed target must never be executed")
                    }
                    _ => Ok(valid_snapshot()),
                }
            })
            .unwrap();
            assert_eq!(result["status"], "installed");
            assert_eq!(fs::read(&target).unwrap(), b"runtime-current");
            assert_eq!(fs::read(&backup).unwrap(), previous);
            fs::remove_dir_all(root).unwrap();
        }
    }

    #[cfg(unix)]
    #[test]
    fn unverified_managed_script_is_never_executed_or_replaced() {
        use std::os::unix::fs::PermissionsExt;

        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        let sentinel = root.join("managed-target-executed");
        fs::write(
            &target,
            format!("#!/bin/sh\ntouch '{}'\n", sentinel.display()),
        )
        .unwrap();
        fs::set_permissions(&target, fs::Permissions::from_mode(0o700)).unwrap();
        let original = fs::read(&target).unwrap();

        let snapshot_error = current_snapshot(&app, &home, |path| {
            if path == target {
                let _ = std::process::Command::new(path).status();
                return Err("managed target was executed".to_string());
            }
            Ok(valid_snapshot())
        })
        .unwrap_err();
        assert_eq!(snapshot_error, "runtime_install_managed_unverified");
        let install_error = install(&app, &home, |path| {
            if path == target {
                let _ = std::process::Command::new(path).status();
                return Err("managed target was executed".to_string());
            }
            Ok(valid_snapshot())
        })
        .unwrap_err();
        assert_eq!(install_error, "runtime_install_managed_unverified");
        assert!(!sentinel.exists());
        assert_eq!(fs::read(&target).unwrap(), original);
        assert!(!backup.exists());

        let mismatched = managed_receipt_bytes(
            "3.9.0",
            digest(&bundled_runtime_path(&app).unwrap()).unwrap(),
        )
        .unwrap();
        write_managed_receipt(&home, &mismatched).unwrap();
        assert_eq!(
            install(&app, &home, |path| {
                if path == target {
                    let _ = std::process::Command::new(path).status();
                    return Err("managed target was executed".to_string());
                }
                Ok(valid_snapshot())
            })
            .unwrap_err(),
            "runtime_install_managed_unverified"
        );
        assert!(!sentinel.exists());
        assert_eq!(fs::read(&target).unwrap(), original);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn post_replace_file_sync_failure_restores_target_and_receipt() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let old_receipt = fs::read(managed_receipt_path(&home)).unwrap();
        let mut validate = |path: &Path| {
            assert_ne!(
                fs::read(path).unwrap(),
                b"runtime-previous",
                "managed target must never be executed"
            );
            Ok(valid_snapshot())
        };
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            |_, _| Err("injected file sync failure".to_string()),
            sync_directory,
            atomic_replace,
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_post_replace_failed_restored");
        assert_eq!(fs::read(&target).unwrap(), b"runtime-previous");
        assert_eq!(fs::read(&backup).unwrap(), b"runtime-previous");
        assert_eq!(fs::read(managed_receipt_path(&home)).unwrap(), old_receipt);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn uncertain_publish_effect_reconciles_and_restores_target_and_receipt() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let previous_receipt = fs::read(managed_receipt_path(&home)).unwrap();
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            sync_regular_file,
            sync_directory,
            |staged: &Path, publish_target: &Path, error_code: &str| {
                atomic_replace(staged, publish_target, error_code)?;
                Err(error_code.to_string())
            },
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_publish_failed_restored");
        assert_eq!(fs::read(&target).unwrap(), b"runtime-previous");
        assert_eq!(fs::read(&backup).unwrap(), b"runtime-previous");
        assert_eq!(
            fs::read(managed_receipt_path(&home)).unwrap(),
            previous_receipt
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn uncertain_fresh_publish_effect_removes_target_and_restores_prior_receipt() {
        let (root, app, home) = fixture();
        let (_, target, backup) = install_paths(&home);
        fs::create_dir_all(home.join(".simplicio")).unwrap();
        let previous_receipt = b"stale-receipt-before-fresh-install".to_vec();
        fs::write(managed_receipt_path(&home), &previous_receipt).unwrap();
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            sync_regular_file,
            sync_directory,
            |staged: &Path, publish_target: &Path, error_code: &str| {
                atomic_replace(staged, publish_target, error_code)?;
                Err(error_code.to_string())
            },
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_publish_failed_removed");
        assert!(!target.exists());
        assert!(!backup.exists());
        assert_eq!(
            fs::read(managed_receipt_path(&home)).unwrap(),
            previous_receipt
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn uncertain_publish_with_unknown_target_fails_closed_without_overwrite() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let previous_receipt = fs::read(managed_receipt_path(&home)).unwrap();
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            sync_regular_file,
            sync_directory,
            |staged: &Path, publish_target: &Path, error_code: &str| {
                atomic_replace(staged, publish_target, error_code)?;
                fs::write(publish_target, b"concurrent-unknown-runtime")
                    .map_err(|_| error_code.to_string())?;
                Err(error_code.to_string())
            },
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_rollback_failed");
        assert_eq!(fs::read(&target).unwrap(), b"concurrent-unknown-runtime");
        assert_eq!(fs::read(&backup).unwrap(), b"runtime-previous");
        assert_eq!(
            fs::read(managed_receipt_path(&home)).unwrap(),
            previous_receipt
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn post_replace_directory_sync_failure_restores_target_and_receipt() {
        let (root, app, home) = fixture();
        let (bin, target, _) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let old_receipt = fs::read(managed_receipt_path(&home)).unwrap();
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            sync_regular_file,
            |_, _| Err("injected directory sync failure".to_string()),
            atomic_replace,
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_post_replace_failed_restored");
        assert_eq!(fs::read(&target).unwrap(), b"runtime-previous");
        assert_eq!(fs::read(managed_receipt_path(&home)).unwrap(), old_receipt);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn fresh_post_replace_failure_removes_target_and_receipt() {
        let (root, app, home) = fixture();
        let (_, target, _) = install_paths(&home);
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            |_, _| Err("injected file sync failure".to_string()),
            sync_directory,
            atomic_replace,
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_post_replace_failed_removed");
        assert!(!target.exists());
        assert!(!managed_receipt_path(&home).exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn fresh_rollback_fails_closed_when_target_is_recreated_after_sync() {
        let (root, app, home) = fixture();
        let (_, target, _) = install_paths(&home);
        let recreated_target = target.clone();
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            move |phase| {
                if phase == InstallPhase::FreshRollbackSynced {
                    fs::write(&recreated_target, b"concurrent-runtime").unwrap();
                }
            },
            |_, _| Err("injected file sync failure".to_string()),
            sync_directory,
            atomic_replace,
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_rollback_failed");
        assert_eq!(fs::read(&target).unwrap(), b"concurrent-runtime");
        assert!(!managed_receipt_path(&home).exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn fresh_published_target_swap_fails_closed_without_execution_or_overwrite() {
        use std::os::unix::fs::PermissionsExt;

        let (root, app, home) = fixture();
        let (_, target, _) = install_paths(&home);
        let sentinel = root.join("fresh-published-target-executed");
        let target_for_hook = target.clone();
        let sentinel_for_hook = sentinel.clone();
        let mut validate = |path: &Path| {
            if path == target {
                let _ = std::process::Command::new(path).status();
                return Err("writable target was executed".to_string());
            }
            Ok(valid_snapshot())
        };
        let error = install_with_hook(&app, &home, &mut validate, move |phase| {
            if phase == InstallPhase::Published {
                fs::write(
                    &target_for_hook,
                    format!("#!/bin/sh\ntouch '{}'\n", sentinel_for_hook.display()),
                )
                .unwrap();
                fs::set_permissions(&target_for_hook, fs::Permissions::from_mode(0o700)).unwrap();
            }
        })
        .unwrap_err();
        assert_eq!(error, "runtime_install_rollback_failed");
        assert!(!sentinel.exists());
        assert!(target.exists());
        assert!(fs::read_to_string(&target).unwrap().contains("touch"));
        assert!(!managed_receipt_path(&home).exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_rollback_is_reported_distinctly() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let receipt_path = managed_receipt_path(&home);
        let old_receipt = fs::read(&receipt_path).unwrap();
        let backup_to_remove = backup.clone();
        let receipt_to_corrupt = receipt_path.clone();
        let mut validate = |_: &Path| Ok(valid_snapshot());
        let error = install_with_controls(
            &app,
            &home,
            &mut validate,
            |_| {},
            move |_, _| {
                fs::remove_file(&backup_to_remove).unwrap();
                fs::write(&receipt_to_corrupt, b"corrupt").unwrap();
                Err("injected file sync failure".to_string())
            },
            sync_directory,
            atomic_replace,
            write_managed_receipt,
        )
        .unwrap_err();
        assert_eq!(error, "runtime_install_rollback_failed");
        assert_eq!(fs::read(receipt_path).unwrap(), old_receipt);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn interruption_after_backup_keeps_target_present_and_next_attempt_recovers() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let target_at_hook = target.clone();
        let mut validate = |path: &Path| {
            assert_ne!(
                fs::read(path).unwrap(),
                b"runtime-previous",
                "managed target must never be executed"
            );
            Ok(valid_snapshot())
        };
        let crashed = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _ = install_with_hook(&app, &home, &mut validate, |phase| {
                assert_eq!(phase, InstallPhase::BackupDurable);
                assert_eq!(fs::read(&target_at_hook).unwrap(), b"runtime-previous");
                panic!("simulated crash");
            });
        }));
        assert!(crashed.is_err());
        assert_eq!(fs::read(&target).unwrap(), b"runtime-previous");
        assert_eq!(fs::read(&backup).unwrap(), b"runtime-previous");
        assert!(bin.join(LOCK_NAME).exists());
        assert_eq!(
            install(&app, &home, validate).unwrap()["status"],
            "installed"
        );
        assert_eq!(fs::read(&target).unwrap(), b"runtime-current");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn interruption_after_publish_is_idempotently_recovered_on_next_attempt() {
        let (root, app, home) = fixture();
        let (bin, target, backup) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        fs::write(&target, b"runtime-previous").unwrap();
        record_managed(&home, &target, "3.8.39");
        let mut validate = |path: &Path| {
            assert_ne!(
                fs::read(path).unwrap(),
                b"runtime-previous",
                "managed target must never be executed"
            );
            Ok(valid_snapshot())
        };
        let crashed = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let _ = install_with_hook(&app, &home, &mut validate, |phase| {
                if phase == InstallPhase::Published {
                    panic!("simulated crash");
                }
            });
        }));
        assert!(crashed.is_err());
        assert_eq!(fs::read(&target).unwrap(), b"runtime-current");
        assert_eq!(fs::read(&backup).unwrap(), b"runtime-previous");
        let recovered = install(&app, &home, validate).unwrap();
        assert_eq!(recovered["status"], "already_current");
        assert_eq!(recovered["backupAvailable"], true);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn advisory_lock_blocks_only_while_the_owner_handle_is_alive() {
        let (root, _, home) = fixture();
        let (bin, _, _) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        let owner = acquire_lock(&bin).unwrap();
        assert!(matches!(
            acquire_lock(&bin),
            Err(error) if error == "runtime_install_busy"
        ));
        drop(owner);
        acquire_lock(&bin).unwrap();
        assert!(bin.join(LOCK_NAME).exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn packaged_authority_must_be_healthy() {
        let (root, app, _) = fixture();
        assert_eq!(
            bundled_authority(&app, |_| Ok(json!({
                "runtime": { "state": "degraded", "version": "3.8.40" }
            })))
            .unwrap_err(),
            "runtime_install_package_invalid"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn semantic_version_order_handles_prerelease_and_ignores_build_metadata() {
        assert!(semantic_version("3.8.40").unwrap() > semantic_version("3.8.40-rc.2").unwrap());
        assert!(
            semantic_version("3.8.40-rc.10").unwrap() > semantic_version("3.8.40-rc.2").unwrap()
        );
        assert_eq!(
            semantic_version("3.8.40+desktop.1").unwrap(),
            semantic_version("3.8.40+desktop.2").unwrap()
        );
        for invalid in ["3.8", "v3.8.40", "3.08.40", "3.8.40-01", "3.8.40+"] {
            assert!(semantic_version(invalid).is_err(), "{invalid}");
        }
    }

    #[test]
    fn managed_receipt_parser_rejects_noncanonical_or_ambiguous_evidence() {
        let target_digest: [u8; 32] = Sha256::digest(b"target").into();
        let canonical_digest = digest_text(target_digest);
        let invalid = [
            "{}".to_string(),
            format!(
                "{{\"schema\":\"wrong\",\"digest\":\"{canonical_digest}\",\"version\":\"3.8.40\",\"source\":\"bundled\"}}"
            ),
            format!(
                "{{\"schema\":\"{MANAGED_RECEIPT_SCHEMA}\",\"digest\":\"{canonical_digest}\",\"version\":\"3.8.40\",\"source\":\"other\"}}"
            ),
            format!(
                "{{\"schema\":\"{MANAGED_RECEIPT_SCHEMA}\",\"digest\":\"{}\",\"version\":\"3.8.40\",\"source\":\"bundled\"}}",
                format!("sha256:{}", canonical_digest[7..].to_ascii_uppercase())
            ),
            format!(
                "{{\"schema\":\"{MANAGED_RECEIPT_SCHEMA}\",\"digest\":\"{canonical_digest}\",\"version\":\"3.8.40\",\"source\":\"bundled\",\"extra\":true}}"
            ),
            format!(
                "{{\"schema\":\"{MANAGED_RECEIPT_SCHEMA}\",\"digest\":\"{canonical_digest}\",\"version\":\"3.8.40\",\"version\":\"3.9.0\",\"source\":\"bundled\"}}"
            ),
            format!(
                "{{\"schema\":\"{MANAGED_RECEIPT_SCHEMA}\",\"digest\":\"{canonical_digest}\",\"source\":\"bundled\"}}"
            ),
        ];
        for bytes in invalid {
            assert!(
                managed_evidence(Some(bytes.as_bytes()), target_digest).is_none(),
                "accepted invalid evidence: {bytes}"
            );
        }
        assert!(managed_evidence(None, target_digest).is_none());
        let mismatched = managed_receipt_bytes("3.8.40", Sha256::digest(b"other").into()).unwrap();
        assert!(managed_evidence(Some(&mismatched), target_digest).is_none());
    }

    #[test]
    fn managed_receipt_reader_rejects_more_than_one_kibibyte() {
        let (root, _, home) = fixture();
        fs::create_dir_all(home.join(".simplicio")).unwrap();
        fs::write(managed_receipt_path(&home), vec![b'x'; 1_025]).unwrap();
        assert_eq!(
            read_managed_receipt(&home).unwrap_err(),
            "runtime_install_receipt_invalid"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlinked_destination_ancestor_and_target() {
        use std::os::unix::fs::symlink;

        let (root, app, home) = fixture();
        let linked_home = root.join("linked-home");
        symlink(&home, &linked_home).unwrap();
        assert_eq!(
            install(&app, &linked_home, |_| Ok(valid_snapshot())).unwrap_err(),
            "runtime_install_path_invalid"
        );

        let (bin, target, _) = install_paths(&home);
        fs::create_dir_all(&bin).unwrap();
        let victim = root.join("user-owned-runtime");
        fs::write(&victim, b"do-not-touch").unwrap();
        symlink(&victim, &target).unwrap();
        assert_eq!(
            install(&app, &home, |_| Ok(valid_snapshot())).unwrap_err(),
            "runtime_install_path_invalid"
        );
        assert_eq!(fs::read(&victim).unwrap(), b"do-not-touch");
        fs::remove_dir_all(root).unwrap();
    }
}
