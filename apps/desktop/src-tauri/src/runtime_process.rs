//! Owned Runtime process boundary. Errors never contain output, arguments, or paths.
use std::io;
use std::process::{Child, Command, Output, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

const POLL_INTERVAL: Duration = Duration::from_millis(5);
const CLEANUP_DEADLINE: Duration = Duration::from_millis(500);
// Only Child handles created by capture are retained here. No PID lookup,
// process-group signal, external-process termination, or Runtime lock deletion.
static PENDING_CHILDREN: Mutex<Vec<Child>> = Mutex::new(Vec::new());

#[derive(Clone, Copy, Debug)]
pub struct CaptureLimits {
    pub deadline: Duration,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
}

impl CaptureLimits {
    pub const QUERY: Self = Self {
        deadline: Duration::from_secs(20),
        stdout_bytes: 256 * 1024,
        stderr_bytes: 16 * 1024,
    };
    pub const OAUTH: Self = Self {
        deadline: Duration::from_secs(180),
        stdout_bytes: 64 * 1024,
        stderr_bytes: 16 * 1024,
    };
    pub const INSTALL: Self = Self {
        deadline: Duration::from_secs(300),
        stdout_bytes: 64 * 1024,
        stderr_bytes: 16 * 1024,
    };
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FailureKind {
    Spawn,
    Deadline,
    StdoutLimit,
    StderrLimit,
    Capture,
    CleanupPending,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ChildState {
    NotStarted,
    Reaped,
    Retained,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ProcessFailure {
    pub kind: FailureKind,
    pub child_state: ChildState,
}

impl ProcessFailure {
    pub fn may_try_another_candidate(self) -> bool {
        self.kind == FailureKind::Spawn && self.child_state == ChildState::NotStarted
    }
}

/// Candidate fallback is permitted only before a process starts. Nonzero exit,
/// timeout, pipe failure, and pending cleanup are final for this invocation.
pub fn capture_candidates(
    commands: impl IntoIterator<Item = Command>,
    limits: CaptureLimits,
) -> Result<Output, ProcessFailure> {
    for mut command in commands {
        match capture(&mut command, limits) {
            Err(failure) if failure.may_try_another_candidate() => continue,
            result => return result,
        }
    }
    Err(ProcessFailure {
        kind: FailureKind::Spawn,
        child_state: ChildState::NotStarted,
    })
}

pub fn capture(command: &mut Command, limits: CaptureLimits) -> Result<Output, ProcessFailure> {
    {
        let mut pending = PENDING_CHILDREN
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        pending.retain_mut(|child| !matches!(child.try_wait(), Ok(Some(_))));
        if !pending.is_empty() {
            return Err(ProcessFailure {
                kind: FailureKind::CleanupPending,
                child_state: ChildState::Retained,
            });
        }
    }
    let started = Instant::now();
    let mut child = command
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| ProcessFailure {
            kind: FailureKind::Spawn,
            child_state: ChildState::NotStarted,
        })?;
    match capture_started(&mut child, limits, started) {
        Ok(output) => Ok(output),
        Err(kind) => Err(ProcessFailure {
            kind,
            child_state: settle_owned_child(child),
        }),
    }
}

/// Read-only Codex account RPC. Never starts a thread/turn or imports credentials.
pub fn codex_account_limits(command: &mut Command) -> Result<serde_json::Value, &'static str> {
    use std::io::Write;
    {
        let mut pending = PENDING_CHILDREN.lock().unwrap_or_else(|e| e.into_inner());
        pending.retain_mut(|child| !matches!(child.try_wait(), Ok(Some(_))));
        if !pending.is_empty() { return Err("cleanup_pending"); }
    }
    let mut child = command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null())
        .spawn().map_err(|_| "cli_unavailable")?;
    let result = (|| {
        let mut input = child.stdin.take().ok_or("rpc_failed")?;
        let mut output = child.stdout.take().ok_or("rpc_failed")?;
        pipe::prepare(&output).map_err(|_| "rpc_failed")?;
        input.write_all(b"{\"id\":1,\"method\":\"initialize\",\"params\":{\"clientInfo\":{\"name\":\"simplicio_desktop\",\"version\":\"1.0.0\"}}}\n").map_err(|_| "rpc_failed")?;
        let start = Instant::now();
        let mut bytes = Vec::new();
        let mut eof = false;
        let mut offset = 0;
        let mut initialized = false;
        loop {
            if start.elapsed() > Duration::from_secs(15) { return Err("timeout"); }
            drain_one(&mut output, &mut bytes, &mut eof, 256 * 1024, FailureKind::StdoutLimit).map_err(|_| "rpc_output_invalid")?;
            while let Some(end) = bytes[offset..].iter().position(|b| *b == b'\n') {
                let end = offset + end;
                let message = serde_json::from_slice::<serde_json::Value>(&bytes[offset..end]);
                offset = end + 1;
                let Ok(message) = message else { continue; };
                if message["id"] == 1 && !initialized {
                    if message.get("error").is_some() { return Err("rpc_initialize_failed"); }
                    initialized = true;
                    input.write_all(b"{\"method\":\"initialized\",\"params\":{}}\n{\"id\":2,\"method\":\"account/rateLimits/read\",\"params\":{}}\n").map_err(|_| "rpc_failed")?;
                } else if initialized && message["id"] == 2 {
                    if message.get("error").is_some() { return Err("account_unavailable"); }
                    return message.get("result").cloned().ok_or("rpc_output_invalid");
                }
            }
            if eof || matches!(child.try_wait(), Ok(Some(_))) { return Err("rpc_exited"); }
            std::thread::sleep(POLL_INTERVAL);
        }
    })();
    if settle_owned_child(child) != ChildState::Reaped { return Err("cleanup_pending"); }
    result
}

fn settle_owned_child(mut child: Child) -> ChildState {
    // Pipe readers are already dropped. Do not wait for a descendant to close
    // an inherited descriptor, and never leave an unbounded reader thread.
    match child.try_wait() {
        Ok(Some(_)) => return ChildState::Reaped,
        Ok(None) => {
            let _ = child.kill();
        }
        Err(_) => {
            // If OS ownership cannot be confirmed, never turn a stale numeric
            // PID into a termination request. Keep the handle unresolved.
            PENDING_CHILDREN
                .lock()
                .unwrap_or_else(|error| error.into_inner())
                .push(child);
            return ChildState::Retained;
        }
    }
    let started = Instant::now();
    while started.elapsed() < CLEANUP_DEADLINE {
        if matches!(child.try_wait(), Ok(Some(_))) {
            return ChildState::Reaped;
        }
        std::thread::sleep(POLL_INTERVAL);
    }
    // An OS-level failure to terminate/reap is not a successful cleanup. Keep
    // ownership and refuse subsequent capture until try_wait proves exit.
    PENDING_CHILDREN
        .lock()
        .unwrap_or_else(|error| error.into_inner())
        .push(child);
    ChildState::Retained
}

fn capture_started(
    child: &mut Child,
    limits: CaptureLimits,
    started: Instant,
) -> Result<Output, FailureKind> {
    let mut stdout_pipe = child.stdout.take().ok_or(FailureKind::Capture)?;
    let mut stderr_pipe = child.stderr.take().ok_or(FailureKind::Capture)?;
    pipe::prepare(&stdout_pipe).map_err(|_| FailureKind::Capture)?;
    pipe::prepare(&stderr_pipe).map_err(|_| FailureKind::Capture)?;
    let mut stdout = Vec::new();
    let mut stderr = Vec::new();
    let mut stdout_eof = false;
    let mut stderr_eof = false;
    let mut status = None;
    loop {
        if started.elapsed() >= limits.deadline {
            return Err(FailureKind::Deadline);
        }
        let out_progress = drain_one(
            &mut stdout_pipe,
            &mut stdout,
            &mut stdout_eof,
            limits.stdout_bytes,
            FailureKind::StdoutLimit,
        )?;
        let err_progress = drain_one(
            &mut stderr_pipe,
            &mut stderr,
            &mut stderr_eof,
            limits.stderr_bytes,
            FailureKind::StderrLimit,
        )?;
        if status.is_none() {
            status = child.try_wait().map_err(|_| FailureKind::Capture)?;
        }
        if stdout_eof && stderr_eof {
            if let Some(status) = status {
                return Ok(Output {
                    status,
                    stdout,
                    stderr,
                });
            }
        }
        if !out_progress && !err_progress {
            std::thread::sleep(
                POLL_INTERVAL.min(limits.deadline.saturating_sub(started.elapsed())),
            );
        }
    }
}

fn drain_one<T: pipe::Pipe>(
    pipe: &mut T,
    output: &mut Vec<u8>,
    eof: &mut bool,
    limit: usize,
    overflow: FailureKind,
) -> Result<bool, FailureKind> {
    if *eof {
        return Ok(false);
    }
    let mut bytes = [0_u8; 8192];
    let available = limit.saturating_sub(output.len());
    let read_size = bytes.len().min(available.saturating_add(1));
    match pipe::read_ready(pipe, &mut bytes[..read_size]) {
        Ok(Some(0)) => {
            *eof = true;
            Ok(false)
        }
        Ok(Some(count)) if count > available => Err(overflow),
        Ok(Some(count)) => {
            output.extend_from_slice(&bytes[..count]);
            Ok(true)
        }
        Ok(None) => Ok(false),
        Err(error) if error.kind() == io::ErrorKind::Interrupted => Ok(false),
        Err(_) => Err(FailureKind::Capture),
    }
}

#[cfg(any(
    target_os = "macos",
    all(
        target_os = "linux",
        any(target_arch = "x86_64", target_arch = "aarch64")
    )
))]
mod pipe {
    use std::io::{self, Read};
    use std::os::fd::AsRawFd;
    use std::os::raw::c_int;

    pub trait Pipe: Read + AsRawFd {}
    impl<T: Read + AsRawFd> Pipe for T {}

    // Apple xnu bsd/sys/fcntl.h and Linux uapi/asm-generic/fcntl.h.
    // These flags intentionally differ by OS; other targets fail closed below.
    const F_GETFL: c_int = 3;
    const F_SETFL: c_int = 4;
    #[cfg(target_os = "macos")]
    const O_NONBLOCK: c_int = 0x0004;
    #[cfg(target_os = "linux")]
    const O_NONBLOCK: c_int = 1 << 11;

    extern "C" {
        fn fcntl(fd: c_int, command: c_int, ...) -> c_int;
    }

    pub fn prepare<T: Pipe>(pipe: &T) -> io::Result<()> {
        // SAFETY: fd belongs to the live, exclusively-owned child pipe; the
        // commands and promoted c_int argument match this platform's ABI.
        let flags = unsafe { fcntl(pipe.as_raw_fd(), F_GETFL) };
        if flags < 0 || unsafe { fcntl(pipe.as_raw_fd(), F_SETFL, flags | O_NONBLOCK) } < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    pub fn read_ready<T: Pipe>(pipe: &mut T, buffer: &mut [u8]) -> io::Result<Option<usize>> {
        match pipe.read(buffer) {
            Ok(count) => Ok(Some(count)),
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => Ok(None),
            Err(error) => Err(error),
        }
    }
}

#[cfg(windows)]
mod pipe {
    use std::ffi::c_void;
    use std::io::{self, Read};
    use std::os::windows::io::AsRawHandle;
    use std::ptr;

    pub trait Pipe: Read + AsRawHandle {}
    impl<T: Read + AsRawHandle> Pipe for T {}

    #[link(name = "kernel32")]
    extern "system" {
        fn PeekNamedPipe(
            handle: *mut c_void,
            buffer: *mut c_void,
            size: u32,
            read: *mut u32,
            available: *mut u32,
            left: *mut u32,
        ) -> i32;
    }

    pub fn prepare<T: Pipe>(_pipe: &T) -> io::Result<()> {
        Ok(())
    }

    pub fn read_ready<T: Pipe>(pipe: &mut T, buffer: &mut [u8]) -> io::Result<Option<usize>> {
        let mut available = 0_u32;
        // SAFETY: Command::spawn's parent-side pipes are overlapped handles
        // (Rust std windows/pipe.rs); only this thread accesses this pipe.
        // Peek only obtains the available byte count. No borrowed handle is
        // closed, replaced, or shared with another reader.
        let result = unsafe {
            PeekNamedPipe(
                pipe.as_raw_handle(),
                ptr::null_mut(),
                0,
                ptr::null_mut(),
                &mut available,
                ptr::null_mut(),
            )
        };
        if result == 0 {
            let error = io::Error::last_os_error();
            return if error.kind() == io::ErrorKind::BrokenPipe {
                Ok(Some(0))
            } else {
                Err(error)
            };
        }
        if available == 0 {
            return Ok(None);
        }
        let count = buffer.len().min(available as usize);
        // No other reader can consume the peeked bytes between these calls.
        pipe.read(&mut buffer[..count]).map(Some)
    }
}

#[cfg(not(any(
    windows,
    target_os = "macos",
    all(
        target_os = "linux",
        any(target_arch = "x86_64", target_arch = "aarch64")
    )
)))]
mod pipe {
    use std::io::{self, Read};
    pub trait Pipe: Read {}
    impl<T: Read> Pipe for T {}
    pub fn prepare<T: Pipe>(_pipe: &T) -> io::Result<()> {
        Err(io::ErrorKind::Unsupported.into())
    }
    pub fn read_ready<T: Pipe>(_pipe: &mut T, _buffer: &mut [u8]) -> io::Result<Option<usize>> {
        Err(io::ErrorKind::Unsupported.into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn child_case(case: &str) -> Command {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command.args([
            "--exact",
            "runtime_process::tests::runtime_child_fixture",
            "--nocapture",
        ]);
        command.env("SIMPLICIO_DESKTOP_CAPTURE_TEST_CASE", case);
        command
    }

    #[test]
    fn runtime_child_fixture() {
        let Ok(case) = std::env::var("SIMPLICIO_DESKTOP_CAPTURE_TEST_CASE") else {
            return;
        };
        match case.as_str() {
            "stdout-flood" => {
                std::io::stdout().write_all(&[b'x'; 64 * 1024]).unwrap();
                std::io::stdout().flush().unwrap();
                std::thread::sleep(Duration::from_secs(2));
            }
            "stderr-flood" => {
                std::io::stderr().write_all(&[b'x'; 64 * 1024]).unwrap();
                std::io::stderr().flush().unwrap();
                std::thread::sleep(Duration::from_secs(2));
            }
            "wait" => {
                eprintln!("DO_NOT_LEAK_CAPTURE_SENTINEL");
                std::thread::sleep(Duration::from_secs(2));
            }
            "bounded" => {
                println!("fixture-ready");
                eprintln!("fixture-diagnostic");
            }
            "exit-seven" => {
                println!("{{\"status\":\"applied\"}}");
                std::process::exit(7);
            }
            "pipe-holder" => {
                std::thread::sleep(Duration::from_millis(600));
                let path = std::env::var_os("SIMPLICIO_DESKTOP_CAPTURE_TEST_DONE").unwrap();
                std::fs::write(path, b"holder-finished").unwrap();
            }
            "inherit-pipe" => {
                let mut holder = child_case("pipe-holder");
                holder.stdout(Stdio::inherit()).stderr(Stdio::inherit());
                // This finite fixture is the only descendant launched by a
                // test. It self-terminates; the outer test waits for its done
                // marker without killing a PID learned from process output.
                let _holder = holder.spawn().unwrap();
            }
            _ => panic!("unknown fixture case"),
        }
        std::process::exit(0);
    }

    #[test]
    fn stdout_is_capped_during_capture_not_after_collecting_the_child() {
        let started = Instant::now();
        let failure = capture(
            &mut child_case("stdout-flood"),
            CaptureLimits {
                deadline: Duration::from_secs(3),
                stdout_bytes: 1024,
                stderr_bytes: 1024,
            },
        )
        .err()
        .expect("capture accepted output beyond its memory budget");
        assert_eq!(failure.kind, FailureKind::StdoutLimit);
        assert_eq!(failure.child_state, ChildState::Reaped);
        assert!(!failure.may_try_another_candidate());
        assert!(
            started.elapsed() < Duration::from_secs(1),
            "limit was checked only after the child finished"
        );
    }

    fn short_limits() -> CaptureLimits {
        CaptureLimits {
            deadline: Duration::from_millis(200),
            stdout_bytes: 4096,
            stderr_bytes: 4096,
        }
    }

    #[test]
    fn deadline_terminates_and_reaps_only_the_started_child() {
        let started = Instant::now();
        let failure = capture(&mut child_case("wait"), short_limits())
            .err()
            .expect("deadline was ignored");
        assert_eq!(failure.kind, FailureKind::Deadline);
        assert_eq!(failure.child_state, ChildState::Reaped);
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(!format!("{failure:?}").contains("DO_NOT_LEAK_CAPTURE_SENTINEL"));
    }

    #[test]
    fn stderr_has_an_independent_memory_bound() {
        let started = Instant::now();
        let failure = capture(&mut child_case("stderr-flood"), short_limits())
            .err()
            .expect("stderr limit was ignored");
        assert_eq!(failure.kind, FailureKind::StderrLimit);
        assert_eq!(failure.child_state, ChildState::Reaped);
        assert!(started.elapsed() < Duration::from_secs(1));
    }

    #[test]
    fn completed_output_preserves_exit_status_and_both_bounded_streams() {
        let output = capture(&mut child_case("bounded"), CaptureLimits::QUERY).unwrap();
        assert_eq!(output.status.code(), Some(0));
        assert!(String::from_utf8_lossy(&output.stdout).contains("fixture-ready"));
        assert!(String::from_utf8_lossy(&output.stderr).contains("fixture-diagnostic"));
        assert!(output.stdout.len() < 4096 && output.stderr.len() < 4096);
    }

    #[test]
    fn candidate_fallback_is_only_for_proven_spawn_failure() {
        let missing = std::env::current_exe()
            .unwrap()
            .join("not-a-directory-or-runtime");
        let error = capture(&mut Command::new(&missing), short_limits())
            .err()
            .expect("invalid executable path started");
        assert_eq!(error.kind, FailureKind::Spawn);
        assert_eq!(error.child_state, ChildState::NotStarted);
        assert!(error.may_try_another_candidate());
        let output = capture_candidates(
            [Command::new(missing), child_case("bounded")],
            CaptureLimits::QUERY,
        )
        .unwrap();
        assert!(output.status.success());
        let output = capture_candidates(
            [child_case("exit-seven"), child_case("bounded")],
            CaptureLimits::QUERY,
        )
        .unwrap();
        assert_eq!(output.status.code(), Some(7));
        let failure =
            capture_candidates([child_case("wait"), child_case("bounded")], short_limits())
                .err()
                .expect("started effect was replayed");
        assert_eq!(failure.kind, FailureKind::Deadline);
    }

    #[test]
    fn inherited_pipe_does_not_hold_the_capture_or_an_orphan_reader_thread() {
        static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        let id = NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let done = std::env::temp_dir().join(format!(
            "simplicio-capture-{}-{id}.done",
            std::process::id()
        ));
        assert!(!done.exists(), "fixture completion path must be fresh");
        let mut command = child_case("inherit-pipe");
        command.env("SIMPLICIO_DESKTOP_CAPTURE_TEST_DONE", &done);
        let started = Instant::now();
        let result = capture(&mut command, short_limits());
        let elapsed = started.elapsed();
        // Wait for this bounded fixture's own completion before reporting, so
        // the test never leaves a long-lived pipe holder behind.
        let cleanup = Instant::now();
        while !done.exists() && cleanup.elapsed() < Duration::from_secs(3) {
            std::thread::sleep(Duration::from_millis(10));
        }
        let completed = std::fs::read(&done);
        if completed.is_ok() {
            std::fs::remove_file(&done).unwrap();
        }
        assert_eq!(completed.unwrap(), b"holder-finished");
        let failure = result
            .err()
            .expect("capture waited for an inherited pipe to close");
        assert_eq!(failure.kind, FailureKind::Deadline);
        assert_eq!(failure.child_state, ChildState::Reaped);
        assert!(elapsed < Duration::from_millis(550));
    }
}
