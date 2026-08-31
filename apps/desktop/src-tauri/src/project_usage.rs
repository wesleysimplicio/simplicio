//! Candidate discovery from local ledger markers, never proof of usage or billing.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashSet, VecDeque};
use std::fs::{self, File, Metadata, OpenOptions};
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, UNIX_EPOCH};

pub(crate) const MARKER_PREFIX_BYTES: usize = 512;
pub(crate) const MAX_NAME_BYTES: usize = 256;
pub(crate) const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
pub(crate) const MAX_DIRECTORIES: usize = 4000;
pub(crate) const MAX_ENTRIES: usize = 40_000;
pub(crate) const MAX_RESULTS: usize = 64;
pub(crate) const MAX_DEPTH: usize = 5;
pub(crate) const EXCLUDED: &[&str] = &[
    ".git",
    ".simplicio",
    "node_modules",
    "target",
    "dist",
    "build",
    "bin",
    "binaries",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    "cache",
    "caches",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".turbo",
    ".tox",
    ".npm",
    ".pnpm-store",
    "coverage",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum RootSelection {
    Projetos,
    Projects,
    Desktop,
    Configured,
}

impl RootSelection {
    pub(crate) fn key(self) -> &'static str {
        match self {
            Self::Projetos => "projetos",
            Self::Projects => "projects",
            Self::Desktop => "desktop",
            Self::Configured => "configured",
        }
    }

    pub(crate) fn name(self) -> &'static str {
        match self {
            Self::Projetos => "Projetos",
            Self::Projects => "Projects",
            Self::Desktop => "Desktop",
            Self::Configured => "Configured repository",
        }
    }

    pub(crate) fn from_key(key: &str) -> Option<Self> {
        match key {
            "projetos" => Some(Self::Projetos),
            "projects" => Some(Self::Projects),
            "desktop" => Some(Self::Desktop),
            "configured" => Some(Self::Configured),
            _ => None,
        }
    }
}

#[derive(Clone, Copy)]
struct Limits {
    depth: usize,
    directories: usize,
    entries: usize,
    results: usize,
    deadline: Duration,
}
const LIMITS: Limits = Limits {
    depth: MAX_DEPTH,
    directories: MAX_DIRECTORIES,
    entries: MAX_ENTRIES,
    results: MAX_RESULTS,
    deadline: Duration::from_secs(2),
};

struct Root {
    name: &'static str,
    path: PathBuf,
}

struct Candidate {
    path: String,
    name: String,
    evidence: &'static str,
    modified: Option<u64>,
}

fn display_path_text(path: &str) -> Option<&str> {
    crate::local_projects::canonical_local_text(path).ok()
}

impl Candidate {
    fn id(&self) -> String {
        format!("project-{:x}", Sha256::digest(self.path.as_bytes()))
    }

    fn json(&self) -> Value {
        let mut value = json!({
            "id": self.id(),
            "name": self.name, "path": self.path, "evidenceType": self.evidence,
        });
        if let Some(epoch) = self.modified {
            value["lastModifiedEpoch"] = json!(epoch);
        }
        value
    }
}

/// In-process fixture entry only. Production must use the bounded worker controller.
#[cfg(test)]
pub fn discover(home: &Path, configured_repo: Option<&Path>) -> Value {
    discover_with_limits(home, configured_repo, LIMITS)
}

#[cfg(test)]
fn discover_with_limits(home: &Path, configured_repo: Option<&Path>, limits: Limits) -> Value {
    let started = Instant::now();
    let mut reasons = BTreeSet::new();
    let roots = roots(home, configured_repo, &mut reasons);
    scan_roots(roots, reasons, limits, started)
}

/// Called only by the headless worker, before Tauri starts. Even resolving HOME
/// and the selected root can block in the filesystem, so none of this belongs
/// in the Desktop parent. This worker never probes another conventional root.
pub(crate) fn discover_root(
    home: &Path,
    selection: RootSelection,
    configured_repo: Option<&Path>,
    directories: usize,
    entries: usize,
) -> Value {
    let started = Instant::now();
    let mut reasons = BTreeSet::new();
    let limits = Limits {
        directories: directories.min(MAX_DIRECTORIES),
        entries: entries.min(MAX_ENTRIES),
        ..LIMITS
    };
    let canonical_home = if home.is_absolute() {
        fs::canonicalize(home)
            .ok()
            .filter(|path| path.to_str().and_then(display_path_text).is_some())
    } else {
        None
    };
    let mut selected = Vec::new();
    if let Some(canonical_home) = canonical_home.as_ref() {
        let proposed = match selection {
            RootSelection::Configured => configured_repo.map(Path::to_path_buf),
            _ => Some(canonical_home.join(selection.name())),
        };
        if let Some(proposed) = proposed {
            if let Some(path) = directory(&proposed, &mut reasons) {
                if path.parent().is_none() || canonical_home.starts_with(&path) {
                    reasons.insert("configured_root_rejected");
                } else {
                    selected.push(Root {
                        name: selection.name(),
                        path,
                    });
                }
            } else if selection == RootSelection::Configured {
                reasons.insert("configured_root_unavailable");
            }
        } else {
            reasons.insert("configured_root_rejected");
        }
    } else {
        reasons.insert("home_unavailable");
    }
    let mut report = scan_roots(selected, reasons, limits, started);
    // This is internal worker metadata. The controller removes it from IPC to
    // the WebView, together with the bounded candidate ID set used for dedup.
    report["canonicalHome"] = json!(canonical_home
        .and_then(|path| { path.to_str().and_then(display_path_text).map(str::to_owned) }));
    report
}

fn scan_roots(
    roots: Vec<Root>,
    mut reasons: BTreeSet<&'static str>,
    limits: Limits,
    started: Instant,
) -> Value {
    let mut scheduled = HashSet::new();
    let mut queue = VecDeque::new();
    for (index, root) in roots.iter().enumerate() {
        scheduled.insert(root.path.clone());
        queue.push_back((root.path.clone(), 0, index));
    }
    let mut projects: Vec<Candidate> = Vec::new();
    let mut directories = 0;
    let mut entries_seen = 0;
    let mut candidate_ids = BTreeSet::new();
    'walk: while let Some((path, depth, root_index)) = queue.pop_front() {
        if expired(started, limits, &mut reasons) {
            break;
        }
        if directories >= limits.directories {
            reasons.insert("directory_limit");
            break;
        }
        // Recheck queued directories rather than following links added during the walk.
        let Some(current) = directory(&path, &mut reasons) else {
            continue;
        };
        if current != path || !current.starts_with(&roots[root_index].path) {
            reasons.insert("path_changed_or_outside_scope");
            continue;
        }
        directories += 1;
        if let Some(candidate) = candidate(&current, &mut reasons) {
            candidate_ids.insert(candidate.id());
            projects.push(candidate);
            projects.sort_by(|left, right| {
                right
                    .modified
                    .cmp(&left.modified)
                    .then_with(|| left.path.cmp(&right.path))
            });
            if projects.len() > limits.results {
                projects.truncate(limits.results);
                reasons.insert("result_limit");
            }
        }
        if expired(started, limits, &mut reasons) {
            break;
        }
        let mut entries = match fs::read_dir(&current) {
            Ok(entries) => entries,
            Err(_) => {
                reasons.insert("directory_unreadable");
                continue;
            }
        };
        loop {
            if expired(started, limits, &mut reasons) {
                break 'walk;
            }
            if entries_seen >= limits.entries {
                reasons.insert("entry_limit");
                break 'walk;
            }
            let Some(entry) = entries.next() else {
                break;
            };
            entries_seen += 1;
            let entry = match entry {
                Ok(entry) => entry,
                Err(_) => {
                    reasons.insert("directory_unreadable");
                    continue;
                }
            };
            let name = entry.file_name();
            if name
                .to_str()
                .is_some_and(|name| EXCLUDED.iter().any(|skip| name.eq_ignore_ascii_case(skip)))
            {
                continue;
            }
            let kind = match entry.file_type() {
                Ok(kind) => kind,
                Err(_) => {
                    reasons.insert("directory_unreadable");
                    continue;
                }
            };
            if kind.is_symlink() {
                reasons.insert("symlink_skipped");
                continue;
            }
            if !kind.is_dir() {
                continue;
            }
            if depth >= limits.depth {
                reasons.insert("depth_limit");
                continue;
            }
            if scheduled.len() >= limits.directories {
                reasons.insert("directory_limit");
                continue;
            }
            let Some(child) = directory(&entry.path(), &mut reasons) else {
                continue;
            };
            if !child.starts_with(&roots[root_index].path) {
                reasons.insert("path_changed_or_outside_scope");
                continue;
            }
            if scheduled.insert(child.clone()) {
                queue.push_back((child, depth + 1, root_index));
            }
        }
    }
    json!({
        "schema": "simplicio.desktop-project-usage/v1",
        "projects": projects.iter().map(Candidate::json).collect::<Vec<_>>(),
        "candidateCount": candidate_ids.len(),
        "candidateIds": candidate_ids,
        "roots": roots.iter().map(|root| json!({"name":root.name,
            "path":root.path.to_str().and_then(display_path_text)})).collect::<Vec<_>>(),
        "scope": {"kind": "conventional_roots_and_configured_repo", "maxDepth": limits.depth,
            "maxDirectories": limits.directories, "maxEntries": limits.entries,
            "maxResults": limits.results, "deadlineMs": limits.deadline.as_millis() as u64,
            "deadlineKind": "cooperative_between_filesystem_calls", "followsSymlinks": false,
            "readsProjectFiles": false, "markerPrefixMaxBytes": MARKER_PREFIX_BYTES,
            "excludedDirectoryNames": EXCLUDED},
        "partial": !reasons.is_empty(), "reasons": reasons,
        "directoriesVisited": directories, "entriesVisited": entries_seen,
        "qualification": "Local ledger markers found; a report query must validate their integrity."
    })
}

fn expired(started: Instant, limits: Limits, reasons: &mut BTreeSet<&'static str>) -> bool {
    if started.elapsed() >= limits.deadline {
        reasons.insert("deadline");
        true
    } else {
        false
    }
}

#[cfg(test)]
fn roots(
    home: &Path,
    configured_repo: Option<&Path>,
    reasons: &mut BTreeSet<&'static str>,
) -> Vec<Root> {
    let mut roots = Vec::new();
    let canonical_home = if home.is_absolute() {
        fs::canonicalize(home).ok()
    } else {
        None
    };
    if let Some(home) = canonical_home.as_ref() {
        for name in ["Projetos", "Projects", "Desktop"] {
            if let Some(path) = directory(&home.join(name), reasons) {
                if !roots.iter().any(|root: &Root| root.path == path) {
                    roots.push(Root { name, path });
                }
            }
        }
    } else {
        reasons.insert("home_unavailable");
    }
    if let Some(configured) = configured_repo {
        if let Some(path) = directory(configured, reasons) {
            if path.parent().is_none()
                || canonical_home
                    .as_ref()
                    .is_some_and(|home| home.starts_with(&path))
            {
                reasons.insert("configured_root_rejected");
            } else if !roots.iter().any(|root| root.path == path) {
                roots.push(Root {
                    name: "Configured repository",
                    path,
                });
            }
        } else {
            reasons.insert("configured_root_unavailable");
        }
    }
    if roots.is_empty() {
        reasons.insert("no_accessible_roots");
    }
    roots
}

fn metadata(path: &Path, reasons: &mut BTreeSet<&'static str>) -> Option<Metadata> {
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            if is_link(&metadata) {
                reasons.insert("symlink_skipped");
                None
            } else {
                Some(metadata)
            }
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => None,
        Err(_) => {
            reasons.insert("path_unreadable");
            None
        }
    }
}

fn directory(path: &Path, reasons: &mut BTreeSet<&'static str>) -> Option<PathBuf> {
    if !path.is_absolute() || !metadata(path, reasons)?.is_dir() {
        return None;
    }
    let path = match fs::canonicalize(path) {
        Ok(path) => path,
        Err(_) => {
            reasons.insert("path_unreadable");
            return None;
        }
    };
    if path.to_str().and_then(display_path_text).is_none() {
        reasons.insert("path_not_displayable");
        return None;
    }
    Some(path)
}

fn candidate(path: &Path, reasons: &mut BTreeSet<&'static str>) -> Option<Candidate> {
    let state = path.join(".simplicio");
    if !metadata(&state, reasons)?.is_dir() {
        return None;
    }
    let ledger = state.join("ledger");
    let context = if metadata(&ledger, reasons).is_some_and(|entry| entry.is_dir()) {
        marker(&ledger.join("savings-events.jsonl"), false, reasons)
    } else {
        None
    };
    // Match token_query_args: usage has its own database, independent of context savings.
    let usage = marker(&state.join("token-usage.sqlite3"), true, reasons);
    let evidence = match (context.is_some(), usage.is_some()) {
        (true, true) => "both",
        (true, false) => "context",
        (false, true) => "usage",
        _ => return None,
    };
    let name = path.file_name()?.to_str()?;
    if name.is_empty() || name.len() > MAX_NAME_BYTES || name.chars().any(char::is_control) {
        reasons.insert("path_not_displayable");
        return None;
    }
    Some(Candidate {
        // Keep native PathBufs for every filesystem call; only projected
        // metadata and its ID use the shared, local-drive display contract.
        path: display_path_text(path.to_str()?)?.into(),
        name: name.into(),
        evidence,
        modified: context.flatten().max(usage.flatten()),
    })
}

fn marker(path: &Path, sqlite: bool, reasons: &mut BTreeSet<&'static str>) -> Option<Option<u64>> {
    let before = metadata(path, reasons)?;
    if !before.is_file() {
        reasons.insert("marker_not_regular");
        return None;
    }
    if before.len() == 0 {
        return None;
    }
    let mut file = match open_marker(path) {
        Ok(file) => file,
        Err(_) => {
            reasons.insert("marker_unreadable");
            return None;
        }
    };
    let current = match file.metadata() {
        Ok(current) if current.is_file() && !is_link(&current) => current,
        _ => {
            reasons.insert("marker_not_regular");
            return None;
        }
    };
    let mut prefix = [0u8; MARKER_PREFIX_BYTES];
    let count = match file.read(if sqlite {
        &mut prefix[..100]
    } else {
        &mut prefix
    }) {
        Ok(count) => count,
        Err(_) => {
            reasons.insert("marker_unreadable");
            return None;
        }
    };
    let prefix = &prefix[..count];
    // Only signature/size checks. Neither JSONL content nor SQLite tables are parsed.
    let recognizable = if sqlite {
        current.len() >= 100 && prefix.starts_with(b"SQLite format 3\0")
    } else {
        let prefix = prefix.strip_prefix(b"\xef\xbb\xbf").unwrap_or(prefix);
        current.len() >= 2 && prefix.iter().find(|byte| !byte.is_ascii_whitespace()) == Some(&b'{')
    };
    if !recognizable {
        reasons.insert("marker_header_invalid");
        return None;
    }
    Some(
        current
            .modified()
            .ok()
            .and_then(|time| time.duration_since(UNIX_EPOCH).ok())
            .map(|duration| duration.as_secs())
            .filter(|epoch| *epoch <= MAX_SAFE_INTEGER),
    )
}

fn is_link(metadata: &Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        // WinNT.h FILE_ATTRIBUTE_REPARSE_POINT includes junctions as well as symlinks.
        if metadata.file_attributes() & 0x0000_0400 != 0 {
            return true;
        }
    }
    metadata.file_type().is_symlink()
}

fn open_marker(path: &Path) -> io::Result<File> {
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(target_os = "macos")]
    {
        use std::os::unix::fs::OpenOptionsExt;
        // Darwin fcntl.h: O_NOFOLLOW | O_NONBLOCK (never wait on a substituted FIFO).
        options.custom_flags(0x0000_0100 | 0x0000_0004);
    }
    #[cfg(all(
        target_os = "linux",
        any(target_arch = "aarch64", target_arch = "x86_64")
    ))]
    {
        use std::os::unix::fs::OpenOptionsExt;
        // Linux asm-generic/fcntl.h, used by the supported Linux targets.
        options.custom_flags((1 << 17) | (1 << 11));
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        // CreateFileW FILE_FLAG_OPEN_REPARSE_POINT, checked again on the opened handle.
        options.custom_flags(0x0020_0000);
    }
    #[cfg(not(any(
        target_os = "macos",
        windows,
        all(
            target_os = "linux",
            any(target_arch = "aarch64", target_arch = "x86_64")
        )
    )))]
    return Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "project marker platform unsupported",
    ));
    options.open(path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn windows_projection_uses_local_drive_text_for_project_root_and_home() {
        for (canonical, displayed) in [
            (
                r"\\?\C:\Users\person\Projects\project",
                r"C:\Users\person\Projects\project",
            ),
            (r"\\?\C:\Users\person\Projects", r"C:\Users\person\Projects"),
            (r"\\?\C:\Users\person", r"C:\Users\person"),
        ] {
            assert_eq!(display_path_text(canonical), Some(displayed));
        }
        for rejected in [
            r"\\?\UNC\server\share\project",
            r"\\.\C:\project",
            r"\\?\GLOBALROOT\Device\volume",
        ] {
            assert_eq!(display_path_text(rejected), None);
        }
        let canonical = r"\\?\C:\Users\person\Projects\project";
        let project = Candidate {
            path: display_path_text(canonical).unwrap().into(),
            name: "project".into(),
            evidence: "usage",
            modified: None,
        }
        .json();
        assert_eq!(project["path"], r"C:\Users\person\Projects\project");
        assert_eq!(
            project["id"],
            format!(
                "project-{:x}",
                Sha256::digest(r"C:\Users\person\Projects\project".as_bytes())
            )
        );
        assert_ne!(
            project["id"],
            format!("project-{:x}", Sha256::digest(canonical.as_bytes()))
        );
    }

    struct Home(PathBuf);
    impl Home {
        fn new() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "simplicio-project-usage-{}-{nonce}",
                std::process::id()
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }

        fn context_ledger(&self, relative: &str) -> PathBuf {
            let project = self.0.join(relative);
            let ledger = project.join(".simplicio/ledger");
            fs::create_dir_all(&ledger).unwrap();
            fs::write(
                ledger.join("savings-events.jsonl"),
                b"{\"private_field\":\"PRIVATE_PROJECT_USAGE_SENTINEL\"}\n",
            )
            .unwrap();
            project
        }

        fn usage_ledger(&self, relative: &str) -> PathBuf {
            let project = self.0.join(relative);
            let state = project.join(".simplicio");
            fs::create_dir_all(&state).unwrap();
            // SQLite's documented magic and 100-byte header, not a valid ledger database.
            // Discovery must identify a candidate without claiming its integrity or contents.
            let mut header = [0u8; 100];
            header[..16].copy_from_slice(b"SQLite format 3\0");
            fs::write(state.join("token-usage.sqlite3"), header).unwrap();
            project
        }
    }
    impl Drop for Home {
        fn drop(&mut self) {
            // The fixture owns this exact newly-created directory, never user data.
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn discovers_a_context_ledger_without_exposing_its_contents_or_claiming_usage() {
        let home = Home::new();
        let project = home.context_ledger("Projects/customer-material");
        let marker = project.join(".simplicio/ledger/savings-events.jsonl");
        let before = fs::metadata(&marker).unwrap().modified().unwrap();
        let report = discover(&home.0, None);
        let projects = report["projects"].as_array().unwrap();
        assert_eq!(
            projects.len(),
            1,
            "a real local ledger marker was not discovered"
        );
        assert_eq!(projects[0]["name"], "customer-material");
        let canonical_project = fs::canonicalize(project).unwrap();
        assert_eq!(
            projects[0]["path"],
            display_path_text(canonical_project.to_str().unwrap()).unwrap()
        );
        assert_eq!(projects[0]["evidenceType"], "context");
        assert!(projects[0]["id"].as_str().unwrap().starts_with("project-"));
        assert_eq!(projects[0]["id"].as_str().unwrap().len(), 72);
        assert!(projects[0]["lastModifiedEpoch"].as_u64().is_some());
        assert_eq!(report["candidateCount"], 1);
        assert!(report["qualification"]
            .as_str()
            .unwrap()
            .contains("report query must validate"));
        assert!(!report
            .to_string()
            .contains("PRIVATE_PROJECT_USAGE_SENTINEL"));
        assert!(!report.to_string().contains("private_field"));
        assert_eq!(fs::metadata(marker).unwrap().modified().unwrap(), before);
    }

    #[test]
    fn discovered_project_matches_the_local_project_selector_contract() {
        let home = Home::new();
        let project = home.context_ledger("Projects/same-project-in-picker-and-discovery");
        let selected = crate::local_projects::validate_project(project.to_str().unwrap()).unwrap();
        let report = discover(&home.0, None);
        let candidate = &report["projects"][0];
        assert_eq!(candidate["path"], selected["path"]);
        assert_eq!(
            candidate["id"], selected["id"],
            "discovery and the native selector disagree on project identity"
        );
    }

    #[test]
    fn absent_markers_bookmarks_and_other_home_folders_are_not_reported_as_usage() {
        let home = Home::new();
        home.context_ledger("Private/unrelated-folder");
        fs::create_dir_all(home.0.join("Projects/bookmarked/.simplicio")).unwrap();
        fs::write(
            home.0.join("Projects/bookmarked/notes.txt"),
            b"PRIVATE_NOT_A_LEDGER",
        )
        .unwrap();
        let report = discover(&home.0, None);
        assert_eq!(report["projects"], json!([]));
        assert_eq!(report["candidateCount"], 0);
        assert_eq!(report["roots"].as_array().unwrap().len(), 1);
        assert_eq!(report["roots"][0]["name"], "Projects");
        assert_eq!(report["partial"], false);
        assert!(!report.to_string().contains("unrelated-folder"));
        assert!(!report.to_string().contains("PRIVATE_NOT_A_LEDGER"));
    }

    #[test]
    fn sqlite_magic_classifies_usage_or_both_but_does_not_prove_database_integrity() {
        let home = Home::new();
        home.usage_ledger("Projetos/usage-only");
        home.context_ledger("Desktop/both-markers");
        home.usage_ledger("Desktop/both-markers");
        let report = discover(&home.0, None);
        let projects = report["projects"].as_array().unwrap();
        assert_eq!(projects.len(), 2);
        assert_eq!(
            projects.iter().find(|p| p["name"] == "usage-only").unwrap()["evidenceType"],
            "usage"
        );
        assert_eq!(
            projects
                .iter()
                .find(|p| p["name"] == "both-markers")
                .unwrap()["evidenceType"],
            "both"
        );
        assert!(projects
            .iter()
            .all(|p| p.get("tokens").is_none() && p.get("savings").is_none()));
        assert_eq!(report["partial"], false);
    }

    #[test]
    fn token_ledger_path_is_canonical_even_without_context_ledger() {
        let home = Home::new();
        let project = home.usage_ledger("Projects/sqlite-without-context");
        let database = fs::canonicalize(project.join(".simplicio/token-usage.sqlite3")).unwrap();
        assert!(!project.join(".simplicio/ledger").exists());
        let args = crate::desktop_queries::token_query_args(
            &json!({"timezoneOffsetSeconds": 0}),
            &project,
        )
        .unwrap();
        assert!(args
            .windows(2)
            .any(|pair| { pair[0] == "--db" && Path::new(&pair[1]) == database }));
        let report = discover(&home.0, None);
        assert_eq!(
            report["projects"].as_array().unwrap().len(),
            1,
            "discovery missed the canonical token ledger accepted by token_query_args"
        );
        assert_eq!(report["projects"][0]["evidenceType"], "usage");
        let canonical_project = fs::canonicalize(&project).unwrap();
        assert_eq!(
            report["projects"][0]["path"],
            display_path_text(canonical_project.to_str().unwrap()).unwrap()
        );
        assert_eq!(report["partial"], false);
    }

    #[test]
    fn token_ledger_path_rejects_the_obsolete_nested_location() {
        let home = Home::new();
        let project = home.usage_ledger("Projects/obsolete-nested-database");
        fs::create_dir(project.join(".simplicio/ledger")).unwrap();
        fs::rename(
            project.join(".simplicio/token-usage.sqlite3"),
            project.join(".simplicio/ledger/token-usage.sqlite3"),
        )
        .unwrap();
        assert_eq!(
            crate::desktop_queries::token_query_args(
                &json!({"timezoneOffsetSeconds": 0}),
                &project
            )
            .unwrap_err(),
            "token_ledger_unavailable"
        );
        let report = discover(&home.0, None);
        assert_eq!(
            report["projects"],
            json!([]),
            "discovery must not advertise the obsolete token ledger rejected by report queries"
        );
        assert_eq!(report["candidateCount"], 0);
    }

    #[test]
    fn empty_non_regular_and_unrecognized_markers_are_not_candidates() {
        let home = Home::new();
        let empty = home.context_ledger("Projects/empty");
        fs::write(empty.join(".simplicio/ledger/savings-events.jsonl"), b"").unwrap();
        let invalid_json = home.context_ledger("Projects/wrong-json-header");
        fs::write(
            invalid_json.join(".simplicio/ledger/savings-events.jsonl"),
            b"PRIVATE_INVALID_HEADER",
        )
        .unwrap();
        let invalid_sqlite = home.usage_ledger("Projects/wrong-sqlite-header");
        fs::write(
            invalid_sqlite.join(".simplicio/token-usage.sqlite3"),
            [b'x'; 100],
        )
        .unwrap();
        let short_sqlite = home.usage_ledger("Projects/short-sqlite");
        fs::write(
            short_sqlite.join(".simplicio/token-usage.sqlite3"),
            b"SQLite format 3\0",
        )
        .unwrap();
        fs::create_dir_all(
            home.0
                .join("Projects/not-a-file/.simplicio/token-usage.sqlite3"),
        )
        .unwrap();
        let report = discover(&home.0, None);
        assert_eq!(report["projects"], json!([]));
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("marker_header_invalid")));
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("marker_not_regular")));
        assert!(!report.to_string().contains("PRIVATE_INVALID_HEADER"));
    }

    #[test]
    fn generated_trees_are_excluded_but_worktrees_remain_in_scope() {
        let home = Home::new();
        for excluded in [
            ".git",
            "node_modules",
            "target",
            "dist",
            "bin",
            "binaries",
            "build",
            "vendor",
            ".venv",
            "venv",
            ".cache",
            "caches",
            ".simplicio",
        ] {
            home.context_ledger(&format!("Projects/{excluded}/excluded-project"));
        }
        home.context_ledger("Projects/repository/.worktrees/real-source");
        let report = discover(&home.0, None);
        assert_eq!(report["projects"].as_array().unwrap().len(), 1);
        assert_eq!(report["projects"][0]["name"], "real-source");
        assert_eq!(report["scope"]["readsProjectFiles"], false);
        assert_eq!(report["scope"]["followsSymlinks"], false);
    }

    #[test]
    fn canonical_roots_are_deduplicated_and_home_is_never_accepted_as_a_scan_root() {
        let home = Home::new();
        home.context_ledger("Projects/project");
        let alias = home.0.join("Projects/../Projects");
        let report = discover(&home.0, Some(&alias));
        assert_eq!(report["roots"].as_array().unwrap().len(), 1);
        assert_eq!(report["candidateCount"], 1);
        let rejected = discover(&home.0, Some(&home.0));
        assert!(rejected["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("configured_root_rejected")));
        assert_eq!(rejected["roots"].as_array().unwrap().len(), 1);
        assert_ne!(
            rejected["roots"][0]["path"],
            fs::canonicalize(&home.0).unwrap().to_str().unwrap()
        );
        let configured = home.context_ledger("Explicit/project-outside-conventional-roots");
        assert_eq!(discover(&home.0, None)["candidateCount"], 1);
        assert_eq!(discover(&home.0, Some(&configured))["candidateCount"], 2);
    }

    #[test]
    fn depth_limit_is_visible_instead_of_claiming_an_exhaustive_inventory() {
        let home = Home::new();
        home.context_ledger("Projects/visible");
        home.context_ledger("Projects/too/deep");
        let report = discover_with_limits(&home.0, None, Limits { depth: 1, ..LIMITS });
        assert_eq!(report["projects"].as_array().unwrap().len(), 1);
        assert_eq!(report["projects"][0]["name"], "visible");
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("depth_limit")));
    }

    #[test]
    fn directory_and_entry_budgets_bound_the_frontier_and_flat_file_directories() {
        let home = Home::new();
        home.context_ledger("Projects/first");
        home.context_ledger("Projects/second");
        let report = discover_with_limits(
            &home.0,
            None,
            Limits {
                directories: 1,
                ..LIMITS
            },
        );
        assert_eq!(report["directoriesVisited"], 1);
        assert_eq!(report["candidateCount"], 0);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("directory_limit")));
        for index in 0..8 {
            fs::write(
                home.0.join(format!("Projects/file-{index}")),
                b"do not read",
            )
            .unwrap();
        }
        let report = discover_with_limits(
            &home.0,
            None,
            Limits {
                entries: 3,
                ..LIMITS
            },
        );
        assert_eq!(report["entriesVisited"], 3);
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("entry_limit")));
    }

    #[test]
    fn elapsed_deadline_returns_partial_without_starting_a_detached_scan() {
        let home = Home::new();
        home.context_ledger("Projects/project");
        let started = Instant::now();
        let report = discover_with_limits(
            &home.0,
            None,
            Limits {
                deadline: Duration::ZERO,
                ..LIMITS
            },
        );
        assert_eq!(report["directoriesVisited"], 0);
        assert_eq!(report["entriesVisited"], 0);
        assert_eq!(report["projects"], json!([]));
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("deadline")));
        assert!(started.elapsed() < Duration::from_secs(1));
    }

    #[test]
    fn retains_the_newest_64_candidates_not_the_first_bfs_entries() {
        let home = Home::new();
        for index in 0..65 {
            let project = home.context_ledger(&format!("Projects/project-{index:02}"));
            OpenOptions::new()
                .write(true)
                .open(project.join(".simplicio/ledger/savings-events.jsonl"))
                .unwrap()
                .set_modified(UNIX_EPOCH + Duration::from_secs(1_700_000_000 + index))
                .unwrap();
        }
        let report = discover(&home.0, None);
        let projects = report["projects"].as_array().unwrap();
        assert_eq!(report["candidateCount"], 65);
        assert_eq!(projects.len(), 64);
        assert_eq!(projects[0]["name"], "project-64");
        assert_eq!(projects[0]["lastModifiedEpoch"], 1_700_000_064u64);
        assert_eq!(projects[63]["name"], "project-01");
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("result_limit")));
        let second = discover(&home.0, None);
        assert_eq!(second["projects"], report["projects"]);
    }

    #[cfg(unix)]
    #[test]
    fn does_not_follow_project_state_ledger_file_or_root_symlinks() {
        use std::os::unix::fs::symlink;
        let home = Home::new();
        let outside = Home::new();
        let source = outside.context_ledger("private-outside-project");
        let projects = home.0.join("Projects");
        fs::create_dir(&projects).unwrap();
        symlink(&source, projects.join("linked-project")).unwrap();
        fs::create_dir(projects.join("linked-state")).unwrap();
        symlink(
            source.join(".simplicio"),
            projects.join("linked-state/.simplicio"),
        )
        .unwrap();
        fs::create_dir_all(projects.join("linked-ledger/.simplicio")).unwrap();
        symlink(
            source.join(".simplicio/ledger"),
            projects.join("linked-ledger/.simplicio/ledger"),
        )
        .unwrap();
        fs::create_dir_all(projects.join("linked-file/.simplicio/ledger")).unwrap();
        symlink(
            source.join(".simplicio/ledger/savings-events.jsonl"),
            projects.join("linked-file/.simplicio/ledger/savings-events.jsonl"),
        )
        .unwrap();
        symlink(&source, home.0.join("Desktop")).unwrap();
        let report = discover(&home.0, None);
        assert_eq!(report["projects"], json!([]));
        assert_eq!(report["roots"].as_array().unwrap().len(), 1);
        assert_eq!(report["partial"], true);
        assert!(report["reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("symlink_skipped")));
        assert!(!report.to_string().contains("private-outside-project"));
    }
}
