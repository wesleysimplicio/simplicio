//! Read-only project discovery workers; the Desktop never scans a root itself.
use crate::project_usage::{self, RootSelection};
use crate::runtime_process::{self, CaptureLimits, ChildState, FailureKind};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::ffi::OsString;
use std::path::{Component, Path, PathBuf};
use std::process::Command;
use std::time::Duration;

const WORKER_FLAG: &str = "--simplicio-project-discovery-worker-v1";
const SCHEMA: &str = "simplicio.desktop-project-usage/v1";
const QUALIFICATION: &str =
    "Local ledger markers found; a report query must validate their integrity.";
const WORKER_LIMITS: CaptureLimits = CaptureLimits {
    deadline: Duration::from_secs(3),
    stdout_bytes: 512 * 1024,
    stderr_bytes: 16 * 1024,
};

#[derive(Clone, Debug)]
struct WorkerRequest {
    home: PathBuf,
    selection: RootSelection,
    configured: Option<PathBuf>,
    directories: usize,
    entries: usize,
}

impl WorkerRequest {
    fn args(&self) -> Vec<OsString> {
        vec![
            WORKER_FLAG.into(),
            self.home.as_os_str().to_owned(),
            self.selection.key().into(),
            self.configured
                .as_ref()
                .map(|path| path.as_os_str().to_owned())
                .unwrap_or_default(),
            self.directories.to_string().into(),
            self.entries.to_string().into(),
        ]
    }

    fn valid(&self) -> bool {
        bounded_path(&self.home)
            && self.home.parent().is_some()
            && (1..=project_usage::MAX_DIRECTORIES).contains(&self.directories)
            && (1..=project_usage::MAX_ENTRIES).contains(&self.entries)
            && match self.selection {
                RootSelection::Configured => self
                    .configured
                    .as_ref()
                    .is_some_and(|path| bounded_path(path)),
                _ => self.configured.is_none(),
            }
    }
}

/// No filesystem call is made on HOME, roots or project paths here. In
/// particular, existence checks and canonicalization run only in the child.
pub fn discover(home: &Path, configured_repo: Option<&Path>, exe: &Path) -> Result<Value, String> {
    if !bounded_path(exe) {
        return Err("project_discovery_unavailable".into());
    }
    discover_with_launcher(home, configured_repo, |request| {
        let mut command = Command::new(exe);
        command.args(request.args());
        // Never set cwd to a root, override HOME, or start a shell/Tauri child.
        capture_worker(&mut command, WORKER_LIMITS)
    })
}

/// The executable calls this before starting Tauri. Malformed worker arguments
/// return an error rather than falling through into a second GUI instance.
pub fn try_discovery_worker() -> Option<Result<Value, String>> {
    dispatch_worker(std::env::args_os().skip(1))
}

fn dispatch_worker(mut args: impl Iterator<Item = OsString>) -> Option<Result<Value, String>> {
    if args.next()? != WORKER_FLAG {
        return None;
    }
    Some((|| {
        // Five fields after the selector. Take one extra to reject trailing
        // options without ever accumulating an unbounded argument list.
        let request = parse_worker_args(args.take(6).collect())?;
        let report = project_usage::discover_root(
            &request.home,
            request.selection,
            request.configured.as_deref(),
            request.directories,
            request.entries,
        );
        validate_worker_report(&request, &report)
            .map_err(|_| "project_discovery_worker_response_invalid".to_string())?;
        if serde_json::to_vec(&report)
            .map_err(|_| "project_discovery_worker_response_invalid")?
            .len()
            > WORKER_LIMITS.stdout_bytes
        {
            return Err("project_discovery_worker_response_too_large".into());
        }
        Ok(report)
    })())
}

fn parse_worker_args(args: Vec<OsString>) -> Result<WorkerRequest, String> {
    let invalid = || "project_discovery_worker_request_invalid".to_string();
    if args.len() != 5 {
        return Err(invalid());
    }
    let selection = args[1]
        .to_str()
        .and_then(RootSelection::from_key)
        .ok_or_else(invalid)?;
    let parse_budget = |value: &OsString| -> Option<usize> {
        let value = value.to_str()?;
        if value.is_empty() || value.len() > 5 || !value.bytes().all(|byte| byte.is_ascii_digit()) {
            return None;
        }
        value.parse().ok()
    };
    let request = WorkerRequest {
        home: PathBuf::from(&args[0]),
        selection,
        configured: if args[2].is_empty() {
            None
        } else {
            Some(PathBuf::from(&args[2]))
        },
        directories: parse_budget(&args[3]).ok_or_else(invalid)?,
        entries: parse_budget(&args[4]).ok_or_else(invalid)?,
    };
    if !request.valid() {
        return Err(invalid());
    }
    Ok(request)
}

fn requests(home: &Path, configured: Option<&Path>) -> Result<Vec<WorkerRequest>, String> {
    if !bounded_path(home) || home.parent().is_none() {
        return Err("project_discovery_request_invalid".into());
    }
    let mut selections = vec![
        RootSelection::Projetos,
        RootSelection::Projects,
        RootSelection::Desktop,
    ];
    if configured.is_some() {
        selections.push(RootSelection::Configured);
    }
    let count = selections.len();
    Ok(selections
        .into_iter()
        .enumerate()
        .map(|(index, selection)| WorkerRequest {
            home: home.to_path_buf(),
            selection,
            configured: if selection == RootSelection::Configured {
                configured.map(Path::to_path_buf)
            } else {
                None
            },
            directories: partition(project_usage::MAX_DIRECTORIES, count, index),
            entries: partition(project_usage::MAX_ENTRIES, count, index),
        })
        .collect())
}

fn partition(total: usize, slots: usize, index: usize) -> usize {
    total / slots + usize::from(index < total % slots)
}

fn discover_with_launcher(
    home: &Path,
    configured: Option<&Path>,
    mut launch: impl FnMut(&WorkerRequest) -> Result<Value, WorkerFailure>,
) -> Result<Value, String> {
    let mut responses = Vec::new();
    let mut stopped = None;
    for request in requests(home, configured)? {
        let response = if let Some(reason) = stopped {
            Err(WorkerFailure {
                reason,
                cleanup_pending: reason == "root_cleanup_unconfirmed",
            })
        } else if !request.valid() {
            Err(WorkerFailure {
                reason: "root_request_invalid",
                cleanup_pending: false,
            })
        } else {
            launch(&request).and_then(|report| {
                validate_worker_report(&request, &report)?;
                Ok(report)
            })
        };
        if let Err(failure) = &response {
            if failure.cleanup_pending {
                stopped = Some("root_cleanup_unconfirmed");
            } else if failure.reason == "root_not_started" {
                // Same executable is unavailable; don't replay three launches.
                stopped = Some("root_not_started");
            }
        }
        responses.push((request.selection.name(), response));
    }
    merge_root_responses(responses)
}

fn merge_root_responses(
    responses: Vec<(&'static str, Result<Value, WorkerFailure>)>,
) -> Result<Value, String> {
    let slots = responses.len();
    if !(3..=4).contains(&slots) {
        return Err("project_discovery_response_invalid".into());
    }
    let mut reasons = BTreeSet::new();
    let mut unavailable = Vec::new();
    let mut roots = Vec::new();
    let mut root_paths = BTreeSet::new();
    let mut ids = BTreeSet::new();
    let mut projects = BTreeMap::<String, Value>::new();
    let mut directories = 0_u64;
    let mut entries = 0_u64;
    let mut partitions = Vec::new();
    for (index, (name, response)) in responses.into_iter().enumerate() {
        partitions.push(json!({"name": name,
            "maxDirectories": partition(project_usage::MAX_DIRECTORIES, slots, index),
            "maxEntries": partition(project_usage::MAX_ENTRIES, slots, index)}));
        let report = match response {
            Ok(report) => report,
            Err(failure) => {
                reasons.insert(failure.reason.to_string());
                if failure.cleanup_pending {
                    reasons.insert("root_cleanup_unconfirmed".into());
                }
                unavailable.push(name);
                continue;
            }
        };
        // Only validated worker reports reach this merge. Count incomplete
        // workers as unknown; never invent how many entries they had read.
        let worker_roots = report["roots"]
            .as_array()
            .ok_or("project_discovery_response_invalid")?;
        let worker_reasons = report["reasons"]
            .as_array()
            .ok_or("project_discovery_response_invalid")?;
        if worker_roots.is_empty() && !worker_reasons.is_empty() {
            unavailable.push(name);
        }
        for reason in worker_reasons {
            reasons.insert(
                reason
                    .as_str()
                    .ok_or("project_discovery_response_invalid")?
                    .to_owned(),
            );
        }
        for root in worker_roots {
            if root_paths.insert(
                root["path"]
                    .as_str()
                    .ok_or("project_discovery_response_invalid")?
                    .to_owned(),
            ) {
                roots.push(root.clone());
            }
        }
        for id in report["candidateIds"]
            .as_array()
            .ok_or("project_discovery_response_invalid")?
        {
            ids.insert(
                id.as_str()
                    .ok_or("project_discovery_response_invalid")?
                    .to_owned(),
            );
        }
        directories += report["directoriesVisited"]
            .as_u64()
            .ok_or("project_discovery_response_invalid")?;
        entries += report["entriesVisited"]
            .as_u64()
            .ok_or("project_discovery_response_invalid")?;
        for candidate in report["projects"]
            .as_array()
            .ok_or("project_discovery_response_invalid")?
        {
            let path = candidate["path"]
                .as_str()
                .ok_or("project_discovery_response_invalid")?
                .to_owned();
            if let Some(existing) = projects.get_mut(&path) {
                if existing["evidenceType"] != candidate["evidenceType"] {
                    existing["evidenceType"] = json!("both");
                }
                if candidate["lastModifiedEpoch"].as_u64() > existing["lastModifiedEpoch"].as_u64()
                {
                    existing["lastModifiedEpoch"] = candidate["lastModifiedEpoch"].clone();
                }
            } else {
                projects.insert(path, candidate.clone());
            }
        }
    }
    let mut projects = projects.into_values().collect::<Vec<_>>();
    projects.sort_by(|left, right| {
        right["lastModifiedEpoch"]
            .as_u64()
            .cmp(&left["lastModifiedEpoch"].as_u64())
            .then_with(|| left["path"].as_str().cmp(&right["path"].as_str()))
    });
    if projects.len() > project_usage::MAX_RESULTS {
        projects.truncate(project_usage::MAX_RESULTS);
        reasons.insert("result_limit".into());
    }
    if directories > project_usage::MAX_DIRECTORIES as u64
        || entries > project_usage::MAX_ENTRIES as u64
        || ids.len() > project_usage::MAX_DIRECTORIES
    {
        return Err("project_discovery_response_invalid".into());
    }
    Ok(json!({
        "schema": SCHEMA, "projects": projects, "candidateCount": ids.len(), "roots": roots,
        "scope": {"kind":"conventional_roots_and_configured_repo", "maxDepth":project_usage::MAX_DEPTH,
            "maxDirectories":project_usage::MAX_DIRECTORIES, "maxEntries":project_usage::MAX_ENTRIES,
            "maxResults":project_usage::MAX_RESULTS, "deadlineMs":3000, "deadlineKind":"process_per_root",
            "cooperativeDeadlineMs":2000, "cleanupGraceMs":500, "maxWorkers":slots,
            "budgetAllocation":"deterministic_partition_including_missing_roots", "rootBudgets":partitions,
            "counterScope":"completed_worker_responses", "candidateCountKind":"unique_ids_in_completed_worker_responses",
            "followsSymlinks":false, "readsProjectFiles":false, "markerPrefixMaxBytes":project_usage::MARKER_PREFIX_BYTES,
            "excludedDirectoryNames":project_usage::EXCLUDED},
        "partial":!reasons.is_empty(), "reasons":reasons, "unavailableRoots":unavailable,
        "directoriesVisited":directories, "entriesVisited":entries, "qualification":QUALIFICATION
    }))
}

#[derive(Debug, PartialEq, Eq)]
struct WorkerFailure {
    reason: &'static str,
    cleanup_pending: bool,
}

fn capture_worker(command: &mut Command, limits: CaptureLimits) -> Result<Value, WorkerFailure> {
    let output = runtime_process::capture(command, limits).map_err(|failure| WorkerFailure {
        reason: match failure.kind {
            FailureKind::Spawn => "root_not_started",
            FailureKind::Deadline => "root_timeout",
            FailureKind::StdoutLimit => "root_response_too_large",
            FailureKind::StderrLimit => "root_diagnostics_too_large",
            FailureKind::Capture => "root_capture_failed",
            FailureKind::CleanupPending => "root_cleanup_unconfirmed",
        },
        cleanup_pending: failure.child_state == ChildState::Retained,
    })?;
    if !output.status.success() {
        return Err(WorkerFailure {
            reason: "root_failed",
            cleanup_pending: false,
        });
    }
    serde_json::from_slice(&output.stdout).map_err(|_| WorkerFailure {
        reason: "root_response_invalid",
        cleanup_pending: false,
    })
}

// Lexical checks only. Canonicalizing even a seemingly harmless path here
// would reintroduce the filesystem hang into the Desktop process.
fn bounded_path(path: &Path) -> bool {
    path.is_absolute()
        && path
            .to_str()
            .is_some_and(|text| crate::local_projects::canonical_local_text(text).is_ok())
}

fn canonical_path(value: &Value) -> Option<&Path> {
    let text = value.as_str()?;
    // Worker output is already projected. Never accept a raw device prefix
    // into the WebView or hash a different spelling than the displayed path.
    if crate::local_projects::canonical_local_text(text).ok()? != text {
        return None;
    }
    let path = Path::new(text);
    if !bounded_path(path)
        || path
            .components()
            .any(|part| matches!(part, Component::ParentDir | Component::CurDir))
    {
        return None;
    }
    let normalized = path.components().collect::<PathBuf>();
    (normalized.as_os_str() == path.as_os_str()).then_some(path)
}

fn only_fields(value: &Value, fields: &[&str]) -> bool {
    value
        .as_object()
        .is_some_and(|map| map.keys().all(|key| fields.contains(&key.as_str())))
}

fn valid_id(id: &str) -> bool {
    id.len() == 72
        && id.starts_with("project-")
        && id.as_bytes()[8..]
            .iter()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(byte))
}

fn worker_scope(directories: usize, entries: usize) -> Value {
    json!({"kind":"conventional_roots_and_configured_repo", "maxDepth":project_usage::MAX_DEPTH,
        "maxDirectories":directories, "maxEntries":entries, "maxResults":project_usage::MAX_RESULTS,
        "deadlineMs":2000, "deadlineKind":"cooperative_between_filesystem_calls",
        "followsSymlinks":false, "readsProjectFiles":false,
        "markerPrefixMaxBytes":project_usage::MARKER_PREFIX_BYTES, "excludedDirectoryNames":project_usage::EXCLUDED})
}

fn validate_worker_report(request: &WorkerRequest, report: &Value) -> Result<(), WorkerFailure> {
    worker_contract(request, report).ok_or(WorkerFailure {
        reason: "root_response_invalid",
        cleanup_pending: false,
    })
}

fn worker_contract(request: &WorkerRequest, report: &Value) -> Option<()> {
    const REASONS: &[&str] = &[
        "directory_limit",
        "entry_limit",
        "result_limit",
        "depth_limit",
        "deadline",
        "home_unavailable",
        "configured_root_rejected",
        "configured_root_unavailable",
        "no_accessible_roots",
        "path_unreadable",
        "path_not_displayable",
        "directory_unreadable",
        "path_changed_or_outside_scope",
        "symlink_skipped",
        "marker_not_regular",
        "marker_unreadable",
        "marker_header_invalid",
    ];
    if !only_fields(
        report,
        &[
            "schema",
            "projects",
            "candidateCount",
            "candidateIds",
            "roots",
            "scope",
            "partial",
            "reasons",
            "directoriesVisited",
            "entriesVisited",
            "qualification",
            "canonicalHome",
        ],
    ) || report.get("schema")?.as_str()? != SCHEMA
        || report.get("scope")? != &worker_scope(request.directories, request.entries)
        || report.get("qualification")?.as_str()? != QUALIFICATION
    {
        return None;
    }
    let roots = report.get("roots")?.as_array()?;
    let projects = report.get("projects")?.as_array()?;
    let candidate_ids = report.get("candidateIds")?.as_array()?;
    let candidate_count = report.get("candidateCount")?.as_u64()?;
    let directories = report.get("directoriesVisited")?.as_u64()?;
    let entries = report.get("entriesVisited")?.as_u64()?;
    let reasons = report.get("reasons")?.as_array()?;
    if roots.len() > 1
        || projects.len() > project_usage::MAX_RESULTS
        || candidate_ids.len() > request.directories
        || candidate_count != candidate_ids.len() as u64
        || candidate_count > directories
        || directories > request.directories as u64
        || entries > request.entries as u64
        || directories > entries + 1
        || projects.len() > candidate_ids.len()
        || reasons.len() > REASONS.len()
        || report.get("partial")?.as_bool()? != !reasons.is_empty()
    {
        return None;
    }
    let mut seen_reasons = BTreeSet::new();
    for reason in reasons {
        let reason = reason.as_str()?;
        if !REASONS.contains(&reason) || !seen_reasons.insert(reason) {
            return None;
        }
    }
    let home_value = report.get("canonicalHome")?;
    let home = if home_value.is_null() {
        None
    } else {
        Some(canonical_path(home_value)?)
    };
    if home.is_none() && (!roots.is_empty() || !seen_reasons.contains("home_unavailable")) {
        return None;
    }
    if roots.is_empty() {
        if directories != 0 || entries != 0 || candidate_count != 0 || !projects.is_empty() {
            return None;
        }
        if request.selection == RootSelection::Configured && reasons.is_empty() {
            return None;
        }
        return Some(());
    }
    let root = &roots[0];
    if !only_fields(root, &["name", "path"])
        || root.get("name")?.as_str()? != request.selection.name()
    {
        return None;
    }
    let root_path = canonical_path(root.get("path")?)?;
    let home = home?;
    if root_path.parent().is_none() || home.starts_with(root_path) {
        return None;
    }
    if request.selection != RootSelection::Configured
        && root_path != home.join(request.selection.name())
    {
        return None;
    }
    let mut ids = BTreeSet::new();
    for id in candidate_ids {
        let id = id.as_str()?;
        if !valid_id(id) || !ids.insert(id) {
            return None;
        }
    }
    let mut project_ids = BTreeSet::new();
    for project in projects {
        if !only_fields(
            project,
            &["id", "name", "path", "evidenceType", "lastModifiedEpoch"],
        ) {
            return None;
        }
        let path = canonical_path(project.get("path")?)?;
        let path_text = path.to_str()?;
        let name = project.get("name")?.as_str()?;
        let id = project.get("id")?.as_str()?;
        if !path.starts_with(root_path)
            || path.strip_prefix(root_path).ok()?.components().count() > project_usage::MAX_DEPTH
            || name.is_empty()
            || name.len() > project_usage::MAX_NAME_BYTES
            || name.chars().any(char::is_control)
            || path.file_name()?.to_str()? != name
            || !ids.contains(id)
            || !project_ids.insert(id)
            || id != format!("project-{:x}", Sha256::digest(path_text.as_bytes()))
            || !matches!(
                project.get("evidenceType")?.as_str()?,
                "context" | "usage" | "both"
            )
        {
            return None;
        }
        if let Some(modified) = project.get("lastModifiedEpoch") {
            if modified.as_u64()? > project_usage::MAX_SAFE_INTEGER {
                return None;
            }
        }
    }
    Some(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

    fn child_case(case: &str) -> Command {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command.args([
            "--exact",
            "project_discovery_process::tests::discovery_child_fixture",
            "--nocapture",
        ]);
        command.env("SIMPLICIO_DISCOVERY_PROCESS_TEST_CASE", case);
        command
    }

    #[test]
    fn discovery_child_fixture() {
        let Ok(case) = std::env::var("SIMPLICIO_DISCOVERY_PROCESS_TEST_CASE") else {
            return;
        };
        if case == "blocked-root" {
            eprintln!("PRIVATE_DISCOVERY_DIAGNOSTIC_SENTINEL");
            std::thread::sleep(Duration::from_secs(2));
        } else if case == "stdout-flood" {
            let block = [b'x'; 16 * 1024];
            for _ in 0..40 {
                if std::io::stdout().write_all(&block).is_err() {
                    break;
                }
            }
        } else if case == "stderr-flood" {
            let _ = std::io::stderr().write_all(&[b'x'; 32 * 1024]);
        } else if case == "delayed-invalid" {
            std::thread::sleep(Duration::from_millis(50));
            print!("not-json");
        } else if case == "success-looking-nonzero" {
            print!("{{\"schema\":\"simplicio.desktop-project-usage/v1\"}}");
            std::process::exit(7);
        }
        std::process::exit(0);
    }

    #[test]
    fn a_blocked_root_is_bounded_and_does_not_leak_its_output() {
        let started = Instant::now();
        let failure = capture_worker(
            &mut child_case("blocked-root"),
            CaptureLimits {
                deadline: Duration::from_millis(150),
                stdout_bytes: 512 * 1024,
                stderr_bytes: 16 * 1024,
            },
        )
        .unwrap_err();
        assert_eq!(failure.reason, "root_timeout");
        assert!(!failure.cleanup_pending);
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(!format!("{failure:?}").contains("PRIVATE_DISCOVERY_DIAGNOSTIC_SENTINEL"));
    }

    #[test]
    fn worker_streams_are_bounded_and_nonzero_exit_precedes_json() {
        let limits = CaptureLimits {
            deadline: Duration::from_secs(1),
            ..WORKER_LIMITS
        };
        assert_eq!(
            capture_worker(&mut child_case("stdout-flood"), limits)
                .unwrap_err()
                .reason,
            "root_response_too_large"
        );
        assert_eq!(
            capture_worker(&mut child_case("stderr-flood"), limits)
                .unwrap_err()
                .reason,
            "root_diagnostics_too_large"
        );
        assert_eq!(
            capture_worker(&mut child_case("delayed-invalid"), limits)
                .unwrap_err()
                .reason,
            "root_response_invalid"
        );
        assert_eq!(
            capture_worker(&mut child_case("success-looking-nonzero"), limits)
                .unwrap_err()
                .reason,
            "root_failed"
        );
    }

    #[test]
    fn completed_projects_survive_a_later_timeout_and_invalid_worker_output() {
        let limits = CaptureLimits {
            deadline: Duration::from_millis(150),
            stdout_bytes: 512 * 1024,
            stderr_bytes: 16 * 1024,
        };
        let completed = json!({
            "schema": "simplicio.desktop-project-usage/v1",
            "projects": [{"id": "project-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "name":"known-project", "path":"/bounded/Projetos/known-project", "evidenceType":"usage"}],
            "candidateIds": ["project-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
            "candidateCount":1, "directoriesVisited":2, "entriesVisited":1,
            "roots":[{"name":"Projetos", "path":"/bounded/Projetos"}],
            "reasons":[], "partial":false
        });
        let response = merge_root_responses(vec![
            ("Projetos", Ok(completed)),
            (
                "Projects",
                capture_worker(&mut child_case("blocked-root"), limits),
            ),
            (
                "Desktop",
                capture_worker(&mut child_case("invalid-json"), limits),
            ),
        ]);
        assert!(
            response.is_ok(),
            "a failed root discarded earlier completed projects"
        );
        let report = response.unwrap();
        assert_eq!(report["projects"].as_array().unwrap().len(), 1);
        assert_eq!(report["projects"][0]["name"], "known-project");
        assert_eq!(report["candidateCount"], 1);
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("root_timeout")));
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("root_response_invalid")));
        assert_eq!(report["unavailableRoots"], json!(["Projects", "Desktop"]));
        assert!(!report
            .to_string()
            .contains("PRIVATE_DISCOVERY_DIAGNOSTIC_SENTINEL"));
        assert!(report.get("candidateIds").is_none());
    }

    fn empty_worker_report(request: &WorkerRequest) -> Value {
        let home = request.home.to_str().unwrap();
        let root_path = match request.selection {
            RootSelection::Configured => request.configured.clone().unwrap(),
            _ => request.home.join(request.selection.name()),
        };
        json!({"schema":SCHEMA, "projects":[], "candidateIds":[], "candidateCount":0,
            "roots":[{"name":request.selection.name(), "path":root_path.to_str().unwrap()}],
            "scope":worker_scope(request.directories, request.entries), "partial":false, "reasons":[],
            "directoriesVisited":1, "entriesVisited":0, "qualification":QUALIFICATION,
            "canonicalHome":home})
    }

    fn fixture_home() -> PathBuf {
        #[cfg(windows)]
        {
            PathBuf::from(r"C:\bounded\home")
        }
        #[cfg(not(windows))]
        {
            PathBuf::from("/bounded/home")
        }
    }

    fn report_with_project(request: &WorkerRequest, project: &Path) -> Value {
        let mut report = empty_worker_report(request);
        let path = project.to_str().unwrap();
        let id = format!("project-{:x}", Sha256::digest(path.as_bytes()));
        report["projects"] = json!([{"id":id, "name":project.file_name().unwrap().to_str().unwrap(),
            "path":path, "evidenceType":"usage", "lastModifiedEpoch":1234}]);
        report["candidateIds"] = json!([id]);
        report["candidateCount"] = json!(1);
        report["directoriesVisited"] = json!(2);
        report["entriesVisited"] = json!(1);
        report
    }

    #[test]
    fn parent_partitions_the_global_budget_without_resolving_home() {
        let home = std::env::temp_dir().join(format!("missing-parent-root-{}", std::process::id()));
        assert!(!home.exists());
        let mut seen = Vec::new();
        let report = discover_with_launcher(&home, None, |request| {
            seen.push((request.selection, request.directories, request.entries));
            Err(WorkerFailure {
                reason: "root_timeout",
                cleanup_pending: false,
            })
        })
        .unwrap();
        assert_eq!(seen.len(), 3);
        assert_eq!(
            seen.iter().map(|(_, value, _)| value).sum::<usize>(),
            project_usage::MAX_DIRECTORIES
        );
        assert_eq!(
            seen.iter().map(|(_, _, value)| value).sum::<usize>(),
            project_usage::MAX_ENTRIES
        );
        assert_eq!(
            report["unavailableRoots"],
            json!(["Projetos", "Projects", "Desktop"])
        );
        assert_eq!(report["projects"], json!([]));
        assert_eq!(report["partial"], true);
        assert!(
            !home.exists(),
            "the parent created or resolved the absent HOME fixture"
        );
    }

    #[test]
    fn four_workers_share_budgets_and_deduplicate_an_overlapping_configured_root() {
        let home = fixture_home();
        let configured = home.join("Projetos");
        let project = configured.join("known-project");
        let mut budgets = Vec::new();
        let report = discover_with_launcher(&home, Some(&configured), |request| {
            budgets.push((request.directories, request.entries));
            Ok(
                if matches!(
                    request.selection,
                    RootSelection::Projetos | RootSelection::Configured
                ) {
                    report_with_project(request, &project)
                } else {
                    empty_worker_report(request)
                },
            )
        })
        .unwrap();
        assert_eq!(budgets, vec![(1000, 10_000); 4]);
        assert_eq!(report["candidateCount"], 1);
        assert_eq!(report["projects"].as_array().unwrap().len(), 1);
        assert_eq!(report["roots"].as_array().unwrap().len(), 3);
        assert_eq!(report["unavailableRoots"], json!([]));
        assert_eq!(report["partial"], false);
    }

    #[test]
    fn worker_arguments_and_reports_fail_closed_before_scanning() {
        let valid = vec![
            fixture_home().into_os_string(),
            OsString::from("projects"),
            OsString::new(),
            OsString::from("1333"),
            OsString::from("13333"),
        ];
        let request = parse_worker_args(valid.clone()).unwrap();
        assert_eq!(request.selection, RootSelection::Projects);
        let mut extra = valid.clone();
        extra.push("unexpected".into());
        assert_eq!(
            parse_worker_args(extra).unwrap_err(),
            "project_discovery_worker_request_invalid"
        );
        let mut excessive = valid.clone();
        excessive[3] = "4001".into();
        assert_eq!(
            parse_worker_args(excessive).unwrap_err(),
            "project_discovery_worker_request_invalid"
        );
        let mut configured_missing = valid;
        configured_missing[1] = "configured".into();
        assert_eq!(
            parse_worker_args(configured_missing).unwrap_err(),
            "project_discovery_worker_request_invalid"
        );

        let mut report = empty_worker_report(&request);
        report["directoriesVisited"] = json!(request.directories as u64 + 1);
        assert_eq!(
            validate_worker_report(&request, &report)
                .unwrap_err()
                .reason,
            "root_response_invalid"
        );
        let mut report = empty_worker_report(&request);
        report["privateUnexpected"] = json!("PRIVATE_WORKER_SENTINEL");
        assert_eq!(
            validate_worker_report(&request, &report)
                .unwrap_err()
                .reason,
            "root_response_invalid"
        );
        let mut report = report_with_project(&request, &request.home.join("Projects/project"));
        report["projects"][0]["id"] =
            json!("project-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
        assert_eq!(
            validate_worker_report(&request, &report)
                .unwrap_err()
                .reason,
            "root_response_invalid"
        );
        let mut report = empty_worker_report(&request);
        report["roots"][0]["path"] = json!(request.home.join("Desktop").to_str().unwrap());
        assert_eq!(
            validate_worker_report(&request, &report)
                .unwrap_err()
                .reason,
            "root_response_invalid"
        );
    }

    #[test]
    fn global_results_keep_the_newest_64_across_all_completed_roots() {
        let home = fixture_home();
        let mut first = 0_u64;
        let report = discover_with_launcher(&home, None, |request| {
            let mut report = empty_worker_report(request);
            let root = request.home.join(request.selection.name());
            let projects = (first..first + 30)
                .map(|index| {
                    let path = root.join(format!("project-{index:02}"));
                    let mut project = report_with_project(request, &path)["projects"][0].clone();
                    project["lastModifiedEpoch"] = json!(index);
                    project
                })
                .collect::<Vec<_>>();
            report["candidateIds"] = json!(projects
                .iter()
                .map(|project| project["id"].clone())
                .collect::<Vec<_>>());
            report["projects"] = json!(projects);
            report["candidateCount"] = json!(30);
            report["directoriesVisited"] = json!(31);
            report["entriesVisited"] = json!(30);
            first += 30;
            Ok(report)
        })
        .unwrap();
        assert_eq!(report["candidateCount"], 90);
        assert_eq!(report["projects"].as_array().unwrap().len(), 64);
        assert_eq!(report["projects"][0]["name"], "project-89");
        assert_eq!(report["projects"][63]["name"], "project-26");
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("result_limit")));
    }

    #[test]
    fn unresolved_cleanup_prevents_starting_other_root_helpers() {
        let home = fixture_home();
        let mut launches = 0;
        let report = discover_with_launcher(&home, None, |_| {
            launches += 1;
            Err(WorkerFailure {
                reason: "root_timeout",
                cleanup_pending: true,
            })
        })
        .unwrap();
        assert_eq!(launches, 1);
        assert_eq!(
            report["unavailableRoots"],
            json!(["Projetos", "Projects", "Desktop"])
        );
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("root_cleanup_unconfirmed")));
    }

    struct WorkerHome(PathBuf);
    impl WorkerHome {
        fn with_project() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let home = std::env::temp_dir().join(format!(
                "simplicio-worker-home-{}-{nonce}",
                std::process::id()
            ));
            let ledger = home.join("Projects/real-project/.simplicio/ledger");
            fs::create_dir_all(&ledger).unwrap();
            fs::write(ledger.join("savings-events.jsonl"), b"{}\n").unwrap();
            Self(home)
        }
    }
    impl Drop for WorkerHome {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn headless_dispatch_scans_exactly_the_selected_fixture_root() {
        let home = WorkerHome::with_project();
        #[cfg(unix)]
        std::os::unix::fs::symlink(home.0.join("Projects"), home.0.join("Desktop")).unwrap();
        let args = [
            WORKER_FLAG.into(),
            home.0.as_os_str().to_owned(),
            "projects".into(),
            OsString::new(),
            "1333".into(),
            "13333".into(),
        ];
        let report = dispatch_worker(args.into_iter()).unwrap().unwrap();
        assert_eq!(report["projects"].as_array().unwrap().len(), 1);
        assert_eq!(report["projects"][0]["name"], "real-project");
        assert_eq!(report["roots"].as_array().unwrap().len(), 1);
        assert_eq!(report["roots"][0]["name"], "Projects");
        assert_eq!(report["candidateCount"], 1);
        assert_eq!(report["partial"], false, "worker probed an unselected root");
        assert!(report.to_string().len() < WORKER_LIMITS.stdout_bytes);
        let missing = [
            WORKER_FLAG.into(),
            home.0.as_os_str().to_owned(),
            "projetos".into(),
            OsString::new(),
            "1333".into(),
            "13333".into(),
        ];
        let missing = dispatch_worker(missing.into_iter()).unwrap().unwrap();
        assert_eq!(missing["projects"], json!([]));
        assert_eq!(missing["roots"], json!([]));
        assert_eq!(missing["reasons"], json!([]));
        assert_eq!(missing["partial"], false);
    }
}
