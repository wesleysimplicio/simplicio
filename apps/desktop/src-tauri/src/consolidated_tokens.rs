//! Bounded read-only token aggregation. Filesystem preflight runs only in the
//! headless child; the Desktop owns every Runtime child directly. A preflight
//! identity is an observation, not an atomic database lease or event-level dedup.
use crate::desktop_queries;
use crate::local_projects::canonical_local_text;
use crate::runtime_process::{self, CaptureLimits, ChildState, FailureKind, ProcessFailure};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::ffi::OsString;
use std::path::Path;
use std::process::{Command, Output};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const SCHEMA: &str = "simplicio.desktop-consolidated-tokens/v1";
const WORKER_SCHEMA: &str = "simplicio.desktop-token-preflight/v1";
const WORKER_FLAG: &str = "--simplicio-token-preflight-worker-v1";
const MAX_PROJECTS: usize = 96;
const MAX_SAFE: u64 = 9_007_199_254_740_991;
const BATCH_DEADLINE: Duration = Duration::from_secs(90);
const PREFLIGHT_DEADLINE: Duration = Duration::from_secs(2);
const REPORT_DEADLINE: Duration = Duration::from_secs(5);
// runtime_process may spend up to 500ms settling its own child after timeout.
const CLEANUP_RESERVE: Duration = Duration::from_millis(500);
const PREFLIGHT_BYTES: usize = 64 * 1024;
const REPORT_BYTES: usize = 256 * 1024;
const STDERR_BYTES: usize = 16 * 1024;
const TOTAL_KEYS: [&str; 9] = [
    "sample_count",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "paid_remote_tokens",
    "total_tokens",
    "missing_usage_events",
    "receipt_count",
];
static BATCH_LOCK: Mutex<()> = Mutex::new(());

#[derive(Clone, Debug, PartialEq, Eq)]
struct Range {
    from: u64,
    to: u64,
    offset: i64,
}

#[derive(Debug)]
struct Request {
    paths: Vec<String>,
    range: Range,
}

fn only_keys(value: &Value, keys: &[&str]) -> bool {
    value.as_object().is_some_and(|object| {
        object.len() == keys.len() && object.keys().all(|key| keys.contains(&key.as_str()))
    })
}

fn input_path(path: &str) -> bool {
    !path.is_empty()
        && path.trim() == path
        && path.len() <= 4096
        && canonical_local_text(path).is_ok_and(|rendered| rendered == path)
}

impl Request {
    fn parse(value: &Value) -> Result<Self, String> {
        let invalid = || "consolidated_query_invalid".to_string();
        if !only_keys(
            value,
            &["repoPaths", "fromEpoch", "toEpoch", "timezoneOffsetSeconds"],
        ) {
            return Err(invalid());
        }
        let paths = value["repoPaths"].as_array().ok_or_else(invalid)?;
        if paths.len() > MAX_PROJECTS {
            return Err(invalid());
        }
        let mut unique = BTreeSet::new();
        let paths = paths
            .iter()
            .map(|value| {
                let path = value
                    .as_str()
                    .filter(|path| input_path(path))
                    .ok_or_else(invalid)?;
                if !unique.insert(path) {
                    return Err(invalid());
                }
                Ok(path.to_string())
            })
            .collect::<Result<Vec<_>, String>>()?;
        let from = value["fromEpoch"]
            .as_u64()
            .filter(|n| *n <= MAX_SAFE)
            .ok_or_else(invalid)?;
        let to = value["toEpoch"]
            .as_u64()
            .filter(|n| *n <= MAX_SAFE)
            .ok_or_else(invalid)?;
        let offset = value["timezoneOffsetSeconds"]
            .as_i64()
            .filter(|n| (-86400..=86400).contains(n))
            .ok_or_else(invalid)?;
        if from >= to {
            return Err(invalid());
        }
        Ok(Self {
            paths,
            range: Range { from, to, offset },
        })
    }
}

#[derive(Clone, Debug)]
struct Project {
    id: String,
    name: String,
    path: String,
}

fn is_windows_drive(path: &str) -> bool {
    let bytes = path.as_bytes();
    bytes.len() >= 3
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':'
        && matches!(bytes[2], b'/' | b'\\')
}

fn path_name(path: &str) -> &str {
    let drive = is_windows_drive(path);
    let trimmed = path.trim_end_matches(|c| c == '/' || (drive && c == '\\'));
    trimmed
        .rsplit(|c| c == '/' || (drive && c == '\\'))
        .next()
        .filter(|name| !name.is_empty())
        .unwrap_or("Projeto")
}

impl Project {
    fn for_path(path: &str) -> Self {
        Self {
            id: format!("project-{:x}", Sha256::digest(path.as_bytes())),
            name: path_name(path).to_string(),
            path: path.to_string(),
        }
    }

    fn value(&self) -> Value {
        json!({"id": self.id, "name": self.name, "path": self.path})
    }

    fn parse(value: &Value) -> Option<Self> {
        if !only_keys(value, &["id", "name", "path"]) {
            return None;
        }
        let path = value["path"].as_str().filter(|path| canonical_path(path))?;
        let project = Self::for_path(path);
        (value["id"].as_str() == Some(&project.id)
            && value["name"].as_str() == Some(&project.name)
            && project.name.len() <= 4096)
            .then_some(project)
    }
}

// Pure text checks: never canonicalize/stat a caller path in the parent.
fn canonical_path(path: &str) -> bool {
    if !input_path(path) {
        return false;
    }
    let drive = is_windows_drive(path);
    let suffix = if drive { &path[3..] } else { &path[1..] };
    !suffix.is_empty()
        && suffix
            .split(|c| c == '/' || (drive && c == '\\'))
            .all(|part| !part.is_empty() && part != "." && part != "..")
}

fn database_key(path: &str) -> String {
    if is_windows_drive(path) {
        path.replace('\\', "/").to_lowercase()
    } else {
        path.to_string()
    }
}

fn database_inside(project: &str, database: &str) -> bool {
    database_key(database)
        .strip_prefix(&database_key(project))
        .is_some_and(|suffix| suffix.starts_with('/') && suffix.len() > 1)
}

#[derive(Clone, Debug)]
struct Ledger {
    path: String,
    unix_identity: Option<(u64, u64)>,
}

#[derive(Clone, Debug)]
struct Preflight {
    status: &'static str,
    project: Option<Project>,
    ledger: Option<Ledger>,
    args: Vec<String>,
}

impl Preflight {
    fn unavailable(status: &'static str, project: Option<Project>) -> Self {
        Self {
            status,
            project,
            ledger: None,
            args: Vec::new(),
        }
    }

    fn value(&self, requested: &str) -> Value {
        json!({
            "schema": WORKER_SCHEMA, "requestedPath": requested, "status": self.status,
            "project": self.project.as_ref().map(Project::value),
            "ledger": self.ledger.as_ref().map(|ledger| json!({
                "path": ledger.path,
                "unixIdentity": ledger.unix_identity.map(|(device, inode)| json!({
                    "device": device.to_string(), "inode": inode.to_string()
                }))
            })),
            "queryArgs": if self.status == "ready" { json!(self.args) } else { Value::Null },
        })
    }
}

fn report_args(range: &Range, database: &str) -> Vec<String> {
    vec![
        "tokens".into(),
        "report".into(),
        "--json".into(),
        "--tz-offset-seconds".into(),
        range.offset.to_string(),
        "--from".into(),
        range.from.to_string(),
        "--to".into(),
        range.to.to_string(),
        "--db".into(),
        database.to_string(),
    ]
}

fn unix_identity(value: &Value) -> Option<Option<(u64, u64)>> {
    if value.is_null() {
        return Some(None);
    }
    if !only_keys(value, &["device", "inode"]) || !cfg!(unix) {
        return None;
    }
    let number = |key: &str| {
        let text = value[key].as_str()?;
        if text.is_empty() || text.len() > 20 || !text.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        text.parse::<u64>().ok()
    };
    let identity = (number("device")?, number("inode")?);
    (identity.1 != 0).then_some(Some(identity))
}

fn validate_preflight(
    value: Value,
    requested: &str,
    range: &Range,
) -> Result<Preflight, ReadFailure> {
    let invalid = ReadFailure::invalid;
    if !only_keys(
        &value,
        &[
            "schema",
            "requestedPath",
            "status",
            "project",
            "ledger",
            "queryArgs",
        ],
    ) || value["schema"] != WORKER_SCHEMA
        || value["requestedPath"] != requested
    {
        return Err(invalid());
    }
    let project = if value["project"].is_null() {
        None
    } else {
        Some(Project::parse(&value["project"]).ok_or_else(invalid)?)
    };
    let status = match value["status"].as_str() {
        Some("ready") => "ready",
        Some("missing") => "missing",
        Some("invalid") => "invalid",
        _ => return Err(invalid()),
    };
    if status != "ready" {
        if !value["ledger"].is_null() || !value["queryArgs"].is_null() {
            return Err(invalid());
        }
        return Ok(Preflight::unavailable(status, project));
    }
    let project = project.ok_or_else(invalid)?;
    if !only_keys(&value["ledger"], &["path", "unixIdentity"]) {
        return Err(invalid());
    }
    let path = value["ledger"]["path"]
        .as_str()
        .filter(|path| canonical_path(path))
        .ok_or_else(invalid)?;
    if !database_inside(&project.path, path) {
        return Err(invalid());
    }
    let identity = unix_identity(&value["ledger"]["unixIdentity"]).ok_or_else(invalid)?;
    let args = value["queryArgs"]
        .as_array()
        .filter(|args| args.len() == 11)
        .ok_or_else(invalid)?;
    let args = args
        .iter()
        .map(|arg| arg.as_str().map(String::from).ok_or_else(invalid))
        .collect::<Result<Vec<_>, _>>()?;
    // Only a native canonical drive prefix is allowed in the DB argv. All
    // other arguments must exactly equal our fixed query, including its range.
    let database = args.last().ok_or_else(invalid)?;
    if canonical_local_text(database).ok() != Some(path) || args != report_args(range, database) {
        return Err(invalid());
    }
    Ok(Preflight {
        status,
        project: Some(project),
        ledger: Some(Ledger {
            path: path.to_string(),
            unix_identity: identity,
        }),
        args,
    })
}

fn missing_or_invalid(path: &Path) -> &'static str {
    match std::fs::metadata(path) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => "missing",
        _ => "invalid",
    }
}

/// Filesystem access is confined to this worker branch. It never invokes a
/// Runtime, shell, login, Tauri, or installer and never creates a ledger.
fn filesystem_preflight(requested: &str, range: &Range) -> Preflight {
    let project = match crate::local_projects::validate_project(requested)
        .ok()
        .and_then(|value| Project::parse(&value))
    {
        Some(project) => project,
        None => return Preflight::unavailable(missing_or_invalid(Path::new(requested)), None),
    };
    let request = json!({ "repoPath": project.path, "fromEpoch": range.from,
        "toEpoch": range.to, "timezoneOffsetSeconds": range.offset });
    let args = match desktop_queries::token_query_args(&request, Path::new(&project.path)) {
        Ok(args) => args,
        Err(_) => {
            let status = missing_or_invalid(
                &Path::new(&project.path).join(".simplicio/token-usage.sqlite3"),
            );
            return Preflight::unavailable(status, Some(project));
        }
    };
    let database = Path::new(args.last().expect("fixed token query has a database"));
    let metadata = match database.metadata() {
        Ok(metadata) if metadata.is_file() => metadata,
        _ => return Preflight::unavailable(missing_or_invalid(database), Some(project)),
    };
    let Some(path) = database
        .to_str()
        .and_then(|path| canonical_local_text(path).ok())
    else {
        return Preflight::unavailable("invalid", Some(project));
    };
    #[cfg(unix)]
    let identity = {
        use std::os::unix::fs::MetadataExt;
        (metadata.ino() != 0).then_some((metadata.dev(), metadata.ino()))
    };
    #[cfg(not(unix))]
    let identity = {
        let _ = metadata;
        None
    };
    Preflight {
        status: "ready",
        project: Some(project),
        ledger: Some(Ledger {
            path: path.into(),
            unix_identity: identity,
        }),
        args,
    }
}

fn worker_args(requested: &str, range: &Range) -> Vec<OsString> {
    vec![
        WORKER_FLAG.into(),
        requested.into(),
        range.from.to_string().into(),
        range.to.to_string().into(),
        range.offset.to_string().into(),
    ]
}

/// Called before Tauri starts. A malformed recognized flag must not fall
/// through to GUI startup. It performs one bounded-input filesystem preflight.
pub fn try_preflight_worker() -> Option<Result<Value, String>> {
    dispatch_worker(std::env::args_os().skip(1))
}

fn dispatch_worker(mut args: impl Iterator<Item = OsString>) -> Option<Result<Value, String>> {
    if args.next()? != WORKER_FLAG {
        return None;
    }
    Some((|| {
        let invalid = || "consolidated_preflight_request_invalid".to_string();
        let args = args.take(5).collect::<Vec<_>>();
        if args.len() != 4 {
            return Err(invalid());
        }
        let path = args[0]
            .to_str()
            .filter(|path| input_path(path))
            .ok_or_else(invalid)?;
        let number = |index: usize| -> Option<&str> {
            let text = args[index].to_str()?;
            (!text.is_empty() && text.len() <= 17).then_some(text)
        };
        let from = number(1)
            .and_then(|s| s.parse::<u64>().ok())
            .ok_or_else(invalid)?;
        let to = number(2)
            .and_then(|s| s.parse::<u64>().ok())
            .ok_or_else(invalid)?;
        let offset = number(3)
            .and_then(|s| s.parse::<i64>().ok())
            .ok_or_else(invalid)?;
        let request = Request::parse(&json!({ "repoPaths": [path], "fromEpoch": from,
            "toEpoch": to, "timezoneOffsetSeconds": offset }))
        .map_err(|_| invalid())?;
        if args
            != worker_args(path, &request.range)
                .into_iter()
                .skip(1)
                .collect::<Vec<_>>()
        {
            return Err(invalid());
        }
        let report = filesystem_preflight(path, &request.range).value(path);
        validate_preflight(report.clone(), path, &request.range).map_err(|_| invalid())?;
        if serde_json::to_vec(&report).map_err(|_| invalid())?.len() > PREFLIGHT_BYTES {
            return Err(invalid());
        }
        Ok(report)
    })())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct ReadFailure {
    status: &'static str,
    stop: bool,
}

impl ReadFailure {
    fn invalid() -> Self {
        Self {
            status: "invalid",
            stop: false,
        }
    }

    fn process(failure: ProcessFailure) -> Self {
        Self {
            status: if failure.kind == FailureKind::Deadline {
                "timeout"
            } else {
                "invalid"
            },
            stop: failure.child_state == ChildState::Retained
                || matches!(
                    failure.kind,
                    FailureKind::CleanupPending | FailureKind::Spawn
                ),
        }
    }
}

fn decode_json(success: bool, stdout: &[u8], max_bytes: usize) -> Result<Value, ReadFailure> {
    if !success || stdout.len() > max_bytes {
        return Err(ReadFailure::invalid());
    }
    serde_json::from_slice(stdout).map_err(|_| ReadFailure::invalid())
}

fn captured_json(
    result: Result<Output, ProcessFailure>,
    max_bytes: usize,
) -> Result<Value, ReadFailure> {
    let output = result.map_err(ReadFailure::process)?;
    decode_json(output.status.success(), &output.stdout, max_bytes)
}

fn capture_limits(deadline: Duration, stdout_bytes: usize) -> CaptureLimits {
    CaptureLimits {
        deadline,
        stdout_bytes,
        stderr_bytes: STDERR_BYTES,
    }
}

fn deadline(remaining: Duration, maximum: Duration) -> Option<Duration> {
    remaining
        .checked_sub(CLEANUP_RESERVE)
        .filter(|time| !time.is_zero())
        .map(|time| time.min(maximum))
}

#[derive(Debug)]
struct Sample {
    totals: [u64; 9],
    hash: String,
}

fn valid_hash(hash: &str) -> bool {
    hash.len() == 71
        && hash.starts_with("sha256:")
        && hash[7..]
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn custom_sample(value: Value, range: &Range) -> Result<Sample, ReadFailure> {
    // Missing session metadata is not proof this is an all-session report.
    if value.get("session_id") != Some(&Value::Null) {
        return Err(ReadFailure::invalid());
    }
    let value = desktop_queries::project_token_report(value).map_err(|_| ReadFailure::invalid())?;
    if value["timezone_offset_seconds"].as_i64() != Some(range.offset) {
        return Err(ReadFailure::invalid());
    }
    let hash = value["report_hash"]
        .as_str()
        .filter(|hash| valid_hash(hash))
        .ok_or_else(ReadFailure::invalid)?
        .to_string();
    let custom = value["periods"]
        .as_array()
        .and_then(|periods| periods.iter().find(|period| period["window"] == "custom"))
        .ok_or_else(ReadFailure::invalid)?;
    if custom["from_epoch"].as_u64() != Some(range.from)
        || custom["to_epoch"].as_u64() != Some(range.to)
    {
        return Err(ReadFailure::invalid());
    }
    let mut totals = [0; 9];
    for (index, key) in TOTAL_KEYS.iter().enumerate() {
        totals[index] = custom["totals"][*key]
            .as_u64()
            .ok_or_else(ReadFailure::invalid)?;
    }
    Ok(Sample { totals, hash })
}

fn totals_value(totals: &[u64; 9]) -> Value {
    Value::Object(
        TOTAL_KEYS
            .iter()
            .zip(totals.iter())
            .map(|(key, value)| ((*key).into(), json!(value)))
            .collect::<Map<_, _>>(),
    )
}

fn row(requested: &str, project: &Project, status: &str, sample: Option<&Sample>) -> Value {
    // Echo the original request so aliases retain their own UI row. Canonical
    // metadata and DB identities are used internally, never to collapse rows.
    json!({ "id": project.id, "name": project.name, "path": requested, "status": status,
        "totals": sample.map(|sample| totals_value(&sample.totals)),
        "reportHash": sample.map(|sample| sample.hash.clone()) })
}

fn collect(
    request: &Request,
    generated_epoch: u64,
    mut remaining: impl FnMut() -> Duration,
    mut preflight: impl FnMut(&str, &Range, Duration) -> Result<Preflight, ReadFailure>,
    mut runtime: impl FnMut(&[String], Duration) -> Result<Value, ReadFailure>,
) -> Result<Value, String> {
    let mut projects = Vec::with_capacity(request.paths.len());
    let mut database_paths = BTreeSet::new();
    let mut unix_ids = BTreeSet::new();
    let mut sum = [0_u64; 9];
    let mut ready = 0;
    let mut stopped = false;
    for path in &request.paths {
        let fallback = Project::for_path(path);
        let limit = deadline(remaining(), PREFLIGHT_DEADLINE);
        if stopped || limit.is_none() {
            stopped = true;
            projects.push(row(path, &fallback, "skipped", None));
            continue;
        }
        let checked = match preflight(path, &request.range, limit.unwrap()) {
            Ok(checked) => checked,
            Err(failure) => {
                stopped = failure.stop;
                projects.push(row(path, &fallback, failure.status, None));
                continue;
            }
        };
        let project = checked.project.as_ref().unwrap_or(&fallback);
        if checked.status != "ready" {
            projects.push(row(path, project, checked.status, None));
            continue;
        }
        let Some(ledger) = checked.ledger else {
            projects.push(row(path, project, "invalid", None));
            continue;
        };
        let key = database_key(&ledger.path);
        if database_paths.contains(&key)
            || ledger
                .unix_identity
                .is_some_and(|id| unix_ids.contains(&id))
        {
            projects.push(row(path, project, "duplicate", None));
            continue;
        }
        let Some(limit) = deadline(remaining(), REPORT_DEADLINE) else {
            stopped = true;
            projects.push(row(path, project, "skipped", None));
            continue;
        };
        let sample = match runtime(&checked.args, limit)
            .and_then(|value| custom_sample(value, &request.range))
        {
            Ok(sample) => sample,
            Err(failure) => {
                stopped = failure.stop;
                projects.push(row(path, project, failure.status, None));
                continue;
            }
        };
        for (total, value) in sum.iter_mut().zip(sample.totals.iter()) {
            *total = total
                .checked_add(*value)
                .filter(|n| *n <= MAX_SAFE)
                .ok_or("consolidated_totals_overflow")?;
        }
        // Only an actually counted ledger can exclude a later requested
        // alias. A failed read must not be labelled "already accounted for".
        database_paths.insert(key);
        if let Some(id) = ledger.unix_identity {
            unix_ids.insert(id);
        }
        ready += 1;
        projects.push(row(path, project, "ready", Some(&sample)));
    }
    let mut report = json!({ "schema": SCHEMA, "source": "runtime",
        "fromEpoch": request.range.from, "toEpoch": request.range.to,
        "timezoneOffsetSeconds": request.range.offset, "generatedAtEpoch": generated_epoch,
        "projects": projects, "totals": (ready > 0).then(|| totals_value(&sum)),
    });
    let bytes = serde_json::to_vec(&report).map_err(|_| "consolidated_report_unavailable")?;
    report["reportHash"] = json!(format!("sha256:{:x}", Sha256::digest(bytes)));
    Ok(report)
}

/// One process-local batch, one fresh authorization, no fallback after a child
/// starts. The total budget includes authorization; no project FS calls here.
pub fn report(
    value: &Value,
    exe: &Path,
    runtime_binaries: Vec<OsString>,
    authorize: impl FnOnce() -> Result<(), String>,
) -> Result<Value, String> {
    let request = Request::parse(value)?;
    if !exe.is_absolute() || runtime_binaries.is_empty() || runtime_binaries.len() > 3 {
        return Err("consolidated_report_unavailable".into());
    }
    let _batch = BATCH_LOCK.try_lock().map_err(|error| match error {
        std::sync::TryLockError::WouldBlock => "consolidated_report_busy",
        std::sync::TryLockError::Poisoned(_) => "consolidated_report_unavailable",
    })?;
    let started = Instant::now();
    authorize()?;
    let generated_epoch = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| "consolidated_report_unavailable")?
        .as_secs();
    if generated_epoch > MAX_SAFE {
        return Err("consolidated_report_unavailable".into());
    }
    collect(
        &request,
        generated_epoch,
        || BATCH_DEADLINE.saturating_sub(started.elapsed()),
        |path, range, limit| {
            let mut command = Command::new(exe);
            command.args(worker_args(path, range));
            // stdin is null in capture. No cwd/HOME override, shell, or Runtime
            // is launched by this worker, even when its filesystem call hangs.
            let value = captured_json(
                runtime_process::capture(&mut command, capture_limits(limit, PREFLIGHT_BYTES)),
                PREFLIGHT_BYTES,
            )?;
            validate_preflight(value, path, range)
        },
        |args, limit| {
            let commands = runtime_binaries.iter().map(|binary| {
                let mut command = Command::new(binary);
                command.args(args).env("SIMPLICIO_DESKTOP_BRIDGE", "1");
                command
            });
            captured_json(
                runtime_process::capture_candidates(commands, capture_limits(limit, REPORT_BYTES)),
                REPORT_BYTES,
            )
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;
    use std::path::PathBuf;

    fn range() -> Range {
        Range {
            from: 100,
            to: 200,
            offset: -10800,
        }
    }

    fn query(paths: &[&str]) -> Value {
        json!({"repoPaths": paths, "fromEpoch": 100, "toEpoch": 200,
            "timezoneOffsetSeconds": -10800})
    }

    fn totals() -> [u64; 9] {
        [2, 100, 25, 30, 7, 112, 137, 1, 1]
    }

    fn runtime_report(totals: [u64; 9]) -> Value {
        json!({"schema": "workspace.token-analytics-report/v1", "now_epoch": 250,
            "session_id": null, "timezone_offset_seconds": -10800,
            "generated_by": "sqlite_ledger", "report_hash": format!("sha256:{}", "a".repeat(64)),
            "periods": [
                {"window": "today", "from_epoch": 1, "to_epoch": 250,
                    "totals": totals_value(&[9, 900, 200, 300, 70, 999, 1270, 0, 9])},
                {"window": "custom", "from_epoch": 100, "to_epoch": 200,
                    "totals": totals_value(&totals)}],
            "raw_prompt": "DO_NOT_LEAK_CONSOLIDATED_PROMPT"})
    }

    fn ready(project: &str, database: &str) -> Preflight {
        Preflight {
            status: "ready",
            project: Some(Project::for_path(project)),
            ledger: Some(Ledger {
                path: database.into(),
                unix_identity: None,
            }),
            args: report_args(&range(), database),
        }
    }

    fn unlimited() -> Duration {
        BATCH_DEADLINE
    }

    #[test]
    fn request_is_bounded_unique_and_requires_an_explicit_common_range() {
        assert!(Request::parse(&query(&["/project"])).is_ok());
        assert!(Request::parse(&query(&[r"C:\Projects\Simplicio"])).is_ok());
        assert!(Request::parse(&query(&[])).is_ok());
        for paths in [
            vec!["relative"],
            vec!["--help"],
            vec!["/project\n"],
            vec!["//server/share"],
            vec![r"\\?\C:\project"],
            vec!["/project", "/project"],
        ] {
            assert_eq!(
                Request::parse(&query(&paths)).unwrap_err(),
                "consolidated_query_invalid"
            );
        }
        for (field, value) in [
            ("fromEpoch", json!(200)),
            ("toEpoch", json!(-1)),
            ("toEpoch", json!(MAX_SAFE + 1)),
            ("timezoneOffsetSeconds", json!(86401)),
            ("sessionId", json!("must-not-filter")),
            ("fromEpoch", json!(1.5)),
        ] {
            let mut request = query(&["/project"]);
            request[field] = value;
            assert!(Request::parse(&request).is_err(), "{field}");
        }
        let paths = (0..97).map(|n| format!("/project-{n}")).collect::<Vec<_>>();
        let mut request = query(&[]);
        request["repoPaths"] = json!(paths);
        assert!(Request::parse(&request).is_err());
        assert!(Request::parse(&query(&[&format!("/{}", "x".repeat(4096))])).is_err());
    }

    #[test]
    fn custom_window_is_selected_once_and_must_echo_range_offset_and_null_session() {
        let sample = custom_sample(runtime_report(totals()), &range()).unwrap();
        assert_eq!(sample.totals, totals());
        for pointer in [
            "/periods/1/from_epoch",
            "/periods/1/to_epoch",
            "/timezone_offset_seconds",
            "/session_id",
            "/periods/1/window",
            "/report_hash",
        ] {
            let mut value = runtime_report(totals());
            *value.pointer_mut(pointer).unwrap() = match pointer {
                "/session_id" => json!("session-other"),
                "/periods/1/window" => json!("7d"),
                "/report_hash" => json!(format!("sha256:{}", "A".repeat(64))),
                _ => json!(999),
            };
            assert_eq!(
                custom_sample(value, &range()).unwrap_err(),
                ReadFailure::invalid()
            );
        }
        let mut missing = runtime_report(totals());
        missing.as_object_mut().unwrap().remove("session_id");
        assert!(custom_sample(missing, &range()).is_err());
        let mut duplicate = runtime_report(totals());
        duplicate["periods"].as_array_mut().unwrap().push(json!({
            "window": "custom", "from_epoch": 100, "to_epoch": 200, "totals": totals_value(&totals())}));
        assert!(custom_sample(duplicate, &range()).is_err());
        let mut invalid_totals = totals();
        invalid_totals[6] += 1;
        assert!(custom_sample(runtime_report(invalid_totals), &range()).is_err());
    }

    #[test]
    fn preflight_protocol_accepts_only_fixed_args_and_contained_canonical_paths() {
        let checked = ready("/project", "/project/.simplicio/token-usage.sqlite3");
        let value = checked.value("/alias");
        let parsed = validate_preflight(value.clone(), "/alias", &range()).unwrap();
        assert_eq!(parsed.args, checked.args);
        for (pointer, replacement) in [
            ("/queryArgs/0", json!("install")),
            ("/queryArgs/6", json!("101")),
            ("/queryArgs/10", json!("/outside/ledger")),
            ("/requestedPath", json!("/other")),
            ("/project/id", json!("not-the-path-hash")),
            ("/ledger/path", json!("/project2/db")),
            ("/project/path", json!("/project/../other")),
        ] {
            let mut malformed = value.clone();
            *malformed.pointer_mut(pointer).unwrap() = replacement;
            assert!(
                validate_preflight(malformed, "/alias", &range()).is_err(),
                "{pointer}"
            );
        }
        let mut extra = value;
        extra["rawStderr"] = json!("DO_NOT_LEAK_CONSOLIDATED_STDERR");
        assert!(validate_preflight(extra, "/alias", &range()).is_err());
        let mut missing = Preflight::unavailable("missing", None).value("/alias");
        missing["queryArgs"] = json!(["install"]);
        assert!(validate_preflight(missing, "/alias", &range()).is_err());
    }

    #[test]
    fn windows_database_identity_is_case_and_separator_insensitive_without_fs_calls() {
        assert_eq!(
            database_key(r"C:\Projects\App\.simplicio\token-usage.sqlite3"),
            database_key("c:/projects/app/.simplicio/TOKEN-USAGE.SQLITE3")
        );
        let mut checked = ready(
            r"C:\Projects\App",
            r"C:\Projects\App\.simplicio\token-usage.sqlite3",
        );
        checked.args[10] = r"\\?\C:\Projects\App\.simplicio\token-usage.sqlite3".into();
        assert!(validate_preflight(checked.value(r"C:\alias"), r"C:\alias", &range()).is_ok());
        assert!(!database_inside("/project", "/project-other/db"));
        assert!(!canonical_path(r"C:\Projects\..\escape"));
    }

    #[test]
    fn colon_in_a_posix_name_does_not_become_a_windows_drive_or_split_utf8() {
        assert!(canonical_path("/:é/projeto"));
        assert!(!is_windows_drive("/:é/projeto"));
        assert_eq!(path_name("/:é/projeto"), "projeto");
        assert_eq!(database_key("/:A/db"), "/:A/db");
        assert_ne!(database_key("/:A/db"), database_key("/:a/db"));
        assert!(!database_inside("/:A", "/:a/db"));
        assert!(is_windows_drive(r"C:\Projects"));
        assert!(is_windows_drive("c:/Projects"));
    }

    struct Fixture(PathBuf);

    impl Fixture {
        fn new() -> Self {
            static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
            let sequence = NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            let stamp = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "simplicio-consolidated-{}-{stamp}-{sequence}",
                std::process::id()
            ));
            std::fs::create_dir(&path).unwrap();
            Self(path)
        }

        fn project(&self, name: &str, ledger: bool) -> String {
            let path = self.0.join(name);
            std::fs::create_dir(&path).unwrap();
            if ledger {
                std::fs::create_dir(path.join(".simplicio")).unwrap();
                // Preflight checks metadata only; it must never run SQLite or
                // turn a fixture into a Runtime analytics mutation.
                std::fs::write(path.join(".simplicio/token-usage.sqlite3"), b"fixture").unwrap();
            }
            path.to_str().unwrap().into()
        }
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn worker_preflight_uses_existing_root_ledger_and_never_creates_a_missing_one() {
        let fixture = Fixture::new();
        let without = fixture.project("without", false);
        let missing = filesystem_preflight(&without, &range());
        assert_eq!(missing.status, "missing");
        assert!(!Path::new(&without).join(".simplicio").exists());
        let project = fixture.project("with", true);
        let checked = filesystem_preflight(&project, &range());
        assert_eq!(checked.status, "ready");
        let parsed = validate_preflight(checked.value(&project), &project, &range()).unwrap();
        assert_eq!(parsed.args[0..3], ["tokens", "report", "--json"]);
        assert!(parsed.args[10].ends_with("token-usage.sqlite3"));
        assert!(!Path::new(&project).join(".simplicio/ledger").exists());
        assert_eq!(
            parsed.project.unwrap().id,
            crate::local_projects::validate_project(&project).unwrap()["id"]
        );
        assert_eq!(
            filesystem_preflight(fixture.0.join("absent").to_str().unwrap(), &range()).status,
            "missing"
        );
    }

    #[cfg(unix)]
    #[test]
    fn symlink_project_alias_and_hardlink_database_have_real_matching_identities() {
        let fixture = Fixture::new();
        let first = fixture.project("first", true);
        let alias = fixture.0.join("alias");
        std::os::unix::fs::symlink(&first, &alias).unwrap();
        let second = fixture.project("second", false);
        std::fs::create_dir(Path::new(&second).join(".simplicio")).unwrap();
        std::fs::hard_link(
            Path::new(&first).join(".simplicio/token-usage.sqlite3"),
            Path::new(&second).join(".simplicio/token-usage.sqlite3"),
        )
        .unwrap();
        let one = filesystem_preflight(&first, &range());
        let two = filesystem_preflight(&second, &range());
        let aliased = filesystem_preflight(alias.to_str().unwrap(), &range());
        assert_eq!(
            one.project.as_ref().unwrap().id,
            aliased.project.unwrap().id
        );
        assert_eq!(
            one.ledger.as_ref().unwrap().path,
            aliased.ledger.unwrap().path
        );
        assert!(one.ledger.as_ref().unwrap().unix_identity.is_some());
        assert_eq!(
            one.ledger.as_ref().unwrap().unix_identity,
            two.ledger.as_ref().unwrap().unix_identity
        );
        let calls = Cell::new(0);
        let request = Request::parse(&query(&[&first, &second])).unwrap();
        let result = collect(
            &request,
            250,
            unlimited,
            |path, _, _| {
                Ok(if path == first {
                    one.clone()
                } else {
                    two.clone()
                })
            },
            |_, _| {
                calls.set(calls.get() + 1);
                Ok(runtime_report(totals()))
            },
        )
        .unwrap();
        assert_eq!(calls.get(), 1);
        assert_eq!(result["projects"][1]["status"], "duplicate");
    }

    #[test]
    fn aggregation_keeps_one_row_per_alias_and_sums_all_nine_fields_only_once_per_db() {
        let request = Request::parse(&query(&["/one", "/alias", "/two"])).unwrap();
        let calls = Cell::new(0);
        let result = collect(
            &request,
            250,
            unlimited,
            |path, _, _| {
                Ok(if path == "/two" {
                    ready("/two", "/two/db")
                } else {
                    ready("/one", "/one/db")
                })
            },
            |_, _| {
                calls.set(calls.get() + 1);
                Ok(runtime_report(totals()))
            },
        )
        .unwrap();
        assert_eq!(calls.get(), 2);
        assert_eq!(result["projects"].as_array().unwrap().len(), 3);
        assert_eq!(result["projects"][1]["path"], "/alias");
        assert_eq!(result["projects"][1]["status"], "duplicate");
        assert_eq!(result["projects"][0]["id"], result["projects"][1]["id"]);
        assert!(result["projects"][1]["totals"].is_null());
        assert!(result["projects"][1]["reportHash"].is_null());
        for (index, key) in TOTAL_KEYS.iter().enumerate() {
            assert_eq!(result["totals"][*key], totals()[index] * 2);
        }
        // Equal Runtime hashes in distinct DBs are not evidence that events
        // are duplicates. We deliberately do not promise copied-event dedup.
        assert_eq!(
            result["projects"][0]["reportHash"],
            result["projects"][2]["reportHash"]
        );
        let text = result.to_string();
        assert!(!text.contains("DO_NOT_LEAK"));
        assert!(!text.contains("unixIdentity"));
        assert!(!text.contains("queryArgs"));
        let mut unhashed = result.clone();
        unhashed.as_object_mut().unwrap().remove("reportHash");
        assert_eq!(
            result["reportHash"],
            format!(
                "sha256:{:x}",
                Sha256::digest(serde_json::to_vec(&unhashed).unwrap())
            )
        );
    }

    #[test]
    fn completed_rows_survive_missing_invalid_timeout_and_batch_deadline() {
        let paths = ["/ready", "/missing", "/invalid", "/timeout", "/after"];
        let request = Request::parse(&query(&paths)).unwrap();
        let expired = Cell::new(false);
        let calls = Cell::new(0);
        let result = collect(
            &request,
            250,
            || {
                if expired.get() {
                    Duration::ZERO
                } else {
                    BATCH_DEADLINE
                }
            },
            |path, _, limit| {
                assert!(limit <= PREFLIGHT_DEADLINE);
                calls.set(calls.get() + 1);
                match path {
                    "/missing" => Ok(Preflight::unavailable("missing", None)),
                    "/invalid" => Err(ReadFailure::invalid()),
                    "/timeout" => {
                        expired.set(true);
                        Err(ReadFailure {
                            status: "timeout",
                            stop: false,
                        })
                    }
                    _ => Ok(ready(path, &format!("{path}/db"))),
                }
            },
            |_, limit| {
                assert!(limit <= REPORT_DEADLINE);
                Ok(runtime_report(totals()))
            },
        )
        .unwrap();
        let statuses = result["projects"]
            .as_array()
            .unwrap()
            .iter()
            .map(|row| row["status"].as_str().unwrap())
            .collect::<Vec<_>>();
        assert_eq!(
            statuses,
            ["ready", "missing", "invalid", "timeout", "skipped"]
        );
        assert_eq!(calls.get(), 4);
        assert_eq!(result["totals"], totals_value(&totals()));
        for row in result["projects"].as_array().unwrap().iter().skip(1) {
            assert!(row["totals"].is_null() && row["reportHash"].is_null());
        }
    }

    #[test]
    fn failed_first_read_does_not_falsely_count_or_exclude_a_requested_alias() {
        let request = Request::parse(&query(&["/one", "/alias", "/third-alias"])).unwrap();
        let calls = Cell::new(0);
        let result = collect(
            &request,
            250,
            unlimited,
            |_, _, _| Ok(ready("/one", "/one/db")),
            |_, _| {
                calls.set(calls.get() + 1);
                if calls.get() == 1 {
                    Err(ReadFailure::invalid())
                } else {
                    Ok(runtime_report(totals()))
                }
            },
        )
        .unwrap();
        assert_eq!(calls.get(), 2);
        assert_eq!(result["projects"][0]["status"], "invalid");
        assert_eq!(result["projects"][1]["status"], "ready");
        assert_eq!(result["projects"][2]["status"], "duplicate");
        assert_eq!(result["totals"], totals_value(&totals()));
    }

    #[test]
    fn expired_budget_after_preflight_never_starts_runtime_and_cleanup_blocks_later_work() {
        let request = Request::parse(&query(&["/one", "/two"])).unwrap();
        let expired = Cell::new(false);
        let result = collect(
            &request,
            250,
            || {
                if expired.get() {
                    Duration::ZERO
                } else {
                    BATCH_DEADLINE
                }
            },
            |path, _, _| {
                expired.set(true);
                Ok(ready(path, &format!("{path}/db")))
            },
            |_, _| panic!("Runtime started beyond the batch deadline"),
        )
        .unwrap();
        assert!(result["projects"]
            .as_array()
            .unwrap()
            .iter()
            .all(|row| row["status"] == "skipped"));
        let calls = Cell::new(0);
        let result = collect(
            &request,
            250,
            unlimited,
            |_, _, _| {
                calls.set(calls.get() + 1);
                Err(ReadFailure::process(ProcessFailure {
                    kind: FailureKind::Deadline,
                    child_state: ChildState::Retained,
                }))
            },
            |_, _| panic!("Runtime started with unresolved worker ownership"),
        )
        .unwrap();
        assert_eq!(calls.get(), 1);
        assert_eq!(result["projects"][0]["status"], "timeout");
        assert_eq!(result["projects"][1]["status"], "skipped");
        assert!(result["totals"].is_null());
        assert_eq!(
            deadline(Duration::from_millis(700), REPORT_DEADLINE),
            Some(Duration::from_millis(200))
        );
        assert!(deadline(CLEANUP_RESERVE, REPORT_DEADLINE).is_none());
    }

    #[test]
    fn no_ready_is_null_but_a_valid_zero_sample_report_preserves_its_totals() {
        let request = Request::parse(&query(&["/one"])).unwrap();
        let missing = collect(
            &request,
            250,
            unlimited,
            |_, _, _| Ok(Preflight::unavailable("missing", None)),
            |_, _| unreachable!(),
        )
        .unwrap();
        assert!(missing["totals"].is_null());
        let empty = collect(
            &request,
            250,
            unlimited,
            |_, _, _| Ok(ready("/one", "/one/db")),
            |_, _| Ok(runtime_report([0; 9])),
        )
        .unwrap();
        assert_eq!(empty["totals"], totals_value(&[0; 9]));
        assert_eq!(empty["projects"][0]["status"], "ready");
    }

    #[test]
    fn unsafe_aggregate_is_rejected_instead_of_saturating_or_returning_null() {
        let request = Request::parse(&query(&["/one", "/two"])).unwrap();
        let high = [1, MAX_SAFE, 0, 0, 0, MAX_SAFE, MAX_SAFE, 0, 1];
        let error = collect(
            &request,
            250,
            unlimited,
            |path, _, _| Ok(ready(path, &format!("{path}/db"))),
            |_, _| Ok(runtime_report(high)),
        )
        .unwrap_err();
        assert_eq!(error, "consolidated_totals_overflow");
    }

    #[test]
    fn nonzero_malformed_and_oversized_output_never_become_success_or_leak_output() {
        let success_looking = serde_json::to_vec(&runtime_report(totals())).unwrap();
        assert_eq!(
            decode_json(false, &success_looking, REPORT_BYTES),
            Err(ReadFailure::invalid())
        );
        assert_eq!(
            decode_json(true, b"DO_NOT_LEAK_CONSOLIDATED_STDERR", REPORT_BYTES),
            Err(ReadFailure::invalid())
        );
        assert_eq!(
            decode_json(true, &success_looking, 16),
            Err(ReadFailure::invalid())
        );
        let failure = ReadFailure::process(ProcessFailure {
            kind: FailureKind::StdoutLimit,
            child_state: ChildState::Reaped,
        });
        assert_eq!(failure, ReadFailure::invalid());
        assert!(
            ReadFailure::process(ProcessFailure {
                kind: FailureKind::Spawn,
                child_state: ChildState::NotStarted
            })
            .stop
        );
    }

    #[test]
    fn worker_dispatch_rejects_options_and_trailing_arguments_without_starting_gui() {
        assert!(dispatch_worker(Vec::<OsString>::new().into_iter()).is_none());
        assert!(dispatch_worker(vec![OsString::from("--unrelated")].into_iter()).is_none());
        for args in [
            vec![WORKER_FLAG],
            vec![WORKER_FLAG, "relative", "100", "200", "0"],
            vec![WORKER_FLAG, "/one", "100", "200", "0", "--anything"],
            vec![WORKER_FLAG, "/one", "+100", "200", "0"],
        ] {
            assert!(dispatch_worker(args.into_iter().map(OsString::from))
                .unwrap()
                .is_err());
        }
        let fixture = Fixture::new();
        let project = fixture.project("worker-only", true);
        let output = dispatch_worker(worker_args(&project, &range()).into_iter())
            .unwrap()
            .unwrap();
        assert_eq!(output["status"], "ready");
        assert!(validate_preflight(output, &project, &range()).is_ok());
    }

    #[test]
    fn process_local_batch_lock_prevents_duplicate_authorization_and_empty_batch_is_bounded() {
        let exe = std::env::current_exe().unwrap();
        let calls = Cell::new(0);
        let held = BATCH_LOCK.lock().unwrap();
        let blocked = report(&query(&[]), &exe, vec!["unused".into()], || {
            calls.set(calls.get() + 1);
            Ok(())
        });
        assert_eq!(blocked.unwrap_err(), "consolidated_report_busy");
        assert_eq!(calls.get(), 0);
        drop(held);
        let result = report(&query(&[]), &exe, vec!["unused".into()], || {
            calls.set(calls.get() + 1);
            Ok(())
        })
        .unwrap();
        assert_eq!(calls.get(), 1);
        assert_eq!(result["projects"], json!([]));
        assert!(result["totals"].is_null());
    }

    #[test]
    fn preflight_child_fixture() {
        if std::env::var_os("SIMPLICIO_CONSOLIDATED_PREFLIGHT_FIXTURE").is_none() {
            return;
        }
        eprintln!("DO_NOT_LEAK_CONSOLIDATED_STDERR");
        // This owned fixture has no descendants and performs no filesystem IO.
        std::thread::sleep(Duration::from_secs(3));
        std::process::exit(0);
    }

    #[test]
    #[ignore = "requires explicit verified Runtime and freshly built Desktop executable paths"]
    fn native_runtime_and_desktop_worker_smoke() {
        let binary =
            std::env::var_os("SIMPLICIO_TEST_RUNTIME_BIN").expect("explicit Runtime required");
        let desktop =
            std::env::var_os("SIMPLICIO_TEST_DESKTOP_BIN").expect("explicit Desktop required");
        assert!(Path::new(&binary).is_absolute() && Path::new(&desktop).is_absolute());
        let fixture = Fixture::new();
        let first = fixture.project("first-real-ledger", false);
        let second = fixture.project("second-real-ledger", false);
        let missing = fixture.project("no-ledger", false);
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        for (id, project, input_tokens, occurred) in [
            ("first", &first, 100, now - 10),
            ("second", &second, 900, now - 10),
            ("outside-window", &first, 50, now - 3600),
        ] {
            let input = fixture.0.join(format!("{id}.json"));
            let sample = json!({"schema":"workspace.token-analytics/v1", "sample_id":id,
                "receipt_ref":id, "session_id":"consolidated-synthetic-smoke", "occurred_at_epoch":occurred,
                "input_tokens":input_tokens, "cached_input_tokens":20, "output_tokens":30,
                "reasoning_tokens":7, "paid_remote_tokens":input_tokens+37, "provenance":"measured"});
            std::fs::write(&input, serde_json::to_vec(&sample).unwrap()).unwrap();
            let mut record = Command::new(&binary);
            record
                .args(["tokens", "record", "--input"])
                .arg(&input)
                .arg("--db")
                .arg(Path::new(project).join(".simplicio/token-usage.sqlite3"))
                .current_dir(project)
                .env("SIMPLICIO_DESKTOP_BRIDGE", "1");
            let output = runtime_process::capture(&mut record, CaptureLimits::QUERY).unwrap();
            assert!(output.status.success(), "synthetic Runtime record failed");
        }
        let alias = format!("{first}/.");
        let request = json!({"repoPaths":[first, alias, second, missing],
            "fromEpoch":now-60, "toEpoch":now+1, "timezoneOffsetSeconds":-10800});
        // Authorization is separately covered by the batch admission test and
        // native GUI smoke. This fixture reads only its own synthetic ledgers.
        let result = report(&request, Path::new(&desktop), vec![binary], || Ok(())).unwrap();
        let states = result["projects"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p["status"].as_str().unwrap())
            .collect::<Vec<_>>();
        assert_eq!(states, ["ready", "duplicate", "ready", "missing"]);
        assert_eq!(result["totals"]["sample_count"], 2);
        assert_eq!(result["totals"]["total_tokens"], 1074);
        assert_eq!(result["totals"]["cached_input_tokens"], 40);
        assert_eq!(result["totals"]["receipt_count"], 2);
        assert!(!Path::new(request["repoPaths"][3].as_str().unwrap())
            .join(".simplicio")
            .exists());
    }

    #[test]
    fn hanging_preflight_is_killed_and_reaped_within_its_capture_budget() {
        let mut child = Command::new(std::env::current_exe().unwrap());
        child
            .args([
                "--exact",
                "consolidated_tokens::tests::preflight_child_fixture",
                "--nocapture",
            ])
            .env("SIMPLICIO_CONSOLIDATED_PREFLIGHT_FIXTURE", "1");
        let started = Instant::now();
        let failure = runtime_process::capture(
            &mut child,
            capture_limits(Duration::from_millis(80), PREFLIGHT_BYTES),
        )
        .unwrap_err();
        assert_eq!(failure.kind, FailureKind::Deadline);
        assert_eq!(failure.child_state, ChildState::Reaped);
        assert!(started.elapsed() < Duration::from_secs(2));
        assert_eq!(
            ReadFailure::process(failure),
            ReadFailure {
                status: "timeout",
                stop: false
            }
        );
    }
}
