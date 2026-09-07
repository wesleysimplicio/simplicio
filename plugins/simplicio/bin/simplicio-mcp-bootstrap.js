#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

const POLICY = Object.freeze({
  runtimeVersion: "3.8.47",
  minimumRuntimeVersion: "3.8.40",
  unifiedSurfaceMinimumVersion: "3.8.40",
  installerCommit: "0fab19520aa2e5430aa682ec414cf5a41bb79b09",
  installers: Object.freeze({
    posix: Object.freeze({
      filename: "install.sh",
      sha256: "3ce5c4a81a545b4608c95dcbd6a41e42858e62384397e06703b4d6746e65e535"
    }),
    win32: Object.freeze({
      filename: "install.ps1",
      sha256: "2056f5128e4754c45d10e42ddffdbbb646d194536bb4e3e99f11552710fdba06"
    })
  })
});

const INSTALL_TIMEOUT_MS = 9 * 60 * 1000;
const LOCK_TIMEOUT_MS = 9 * 60 * 1000;
const LOCK_STALE_MS = 12 * 60 * 1000;
const MAX_INSTALLER_BYTES = 1024 * 1024;

function stderr(message) {
  process.stderr.write(`[simplicio-plugin] ${message}\n`);
}

function resolveHome(env = process.env) {
  const candidate = process.platform === "win32"
    ? env.USERPROFILE || env.HOME
    : env.HOME || env.USERPROFILE;
  const resolved = candidate || os.homedir();
  if (!resolved || !path.isAbsolute(resolved)) {
    throw new Error("cannot resolve an absolute user home directory");
  }
  return path.resolve(resolved);
}

function executableName(platform = process.platform) {
  return platform === "win32" ? "simplicio.exe" : "simplicio";
}

function parseVersion(value) {
  const match = String(value || "").trim().match(/^v?(\d+)\.(\d+)\.(\d+)/);
  return match ? match.slice(1, 4).map(Number) : null;
}

function versionAtLeast(actual, minimum) {
  const left = parseVersion(actual);
  const right = parseVersion(minimum);
  if (!left || !right) return false;
  for (let index = 0; index < 3; index += 1) {
    if (left[index] > right[index]) return true;
    if (left[index] < right[index]) return false;
  }
  return true;
}

function supportedRuntimeVersion(actual, minimum = POLICY.minimumRuntimeVersion) {
  const parsed = parseVersion(actual);
  return Boolean(parsed && parsed[0] === 3 && versionAtLeast(actual, minimum));
}

const MAPPER_ONLY_TOOLS = Object.freeze([
  "simplicio_map",
  "simplicio_context",
  "simplicio_memory",
  "simplicio_read",
  "simplicio_search",
  "simplicio_symbol"
]);
const FULL_MODE_CANONICAL_TOOLS = Object.freeze([
  "simplicio_map",
  "simplicio_context",
  "simplicio_memory",
  "simplicio_edit",
  "simplicio_run"
]);
const RETIRED_ALIAS_TOOLS = Object.freeze([
  "mapper",
  "index",
  "code-graph",
  "codegraph",
  "mapper-memory",
  "mapper-foreground",
  "mapper-cutover",
  "simplicio_mapper",
  "simplicio_index",
  "simplicio_code_graph"
]);
const MAPPER_ONLY_FORBIDDEN_TOOLS = Object.freeze([
  "simplicio_edit",
  "simplicio_run",
  "simplicio_loop",
  "simplicio_exec"
]);

function advertisedHostSurface(version, mode = "full") {
  const unified = Boolean(
    version && versionAtLeast(version, POLICY.unifiedSurfaceMinimumVersion)
  );
  if (!unified) {
    return Object.freeze({
      schema: "simplicio.host-surface/v1",
      unified: false,
      mode,
      tools: [],
      retiredAliases: [...RETIRED_ALIAS_TOOLS],
      reason: "runtime_below_unified_surface"
    });
  }
  const mapperOnly = mode === "mapper-only";
  return Object.freeze({
    schema: "simplicio.host-surface/v1",
    unified: true,
    mode: mapperOnly ? "mapper-only" : "full",
    tools: mapperOnly ? [...MAPPER_ONLY_TOOLS] : [...FULL_MODE_CANONICAL_TOOLS],
    forbidden: mapperOnly ? [...MAPPER_ONLY_FORBIDDEN_TOOLS] : [],
    retiredAliases: [...RETIRED_ALIAS_TOOLS]
  });
}

function runtimeVersion(payload) {
  return payload?.runtime?.version
    || payload?.runtime?.executable?.version
    || payload?.version
    || null;
}

function runtimeContractValid(payload, binary, minimum = POLICY.minimumRuntimeVersion) {
  const version = runtimeVersion(payload);
  const executable = payload?.runtime?.executable || {};
  const distribution = payload?.auto_update?.distribution || {};
  const identity = payload?.identity || {};
  const security = payload?.security || payload?.auto_update?.security || {};
  let reportedPath;
  try {
    reportedPath = executable.path ? path.resolve(executable.path) : null;
  } catch (_error) {
    reportedPath = null;
  }
  return payload?.schema === "simplicio.release-manifest/v1"
    && payload?.product === "simplicio-runtime"
    && payload?.runtime?.name === "simplicio-runtime"
    && supportedRuntimeVersion(version, minimum)
    && reportedPath === path.resolve(binary)
    && distribution.source_code_distributed === true
    && identity.enabled === true
    && identity.login_enabled === true
    && security.signature_required === true
    && security.public_key_configured === true
    && security.refuse_unsigned === true
    && security.refuse_invalid_signature === true;
}

function validateRuntime(binary, minimum = POLICY.minimumRuntimeVersion) {
  if (!binary || !path.isAbsolute(binary) || !fs.existsSync(binary)) return null;
  const result = spawnSync(binary, ["version", "--json"], {
    encoding: "utf8",
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 15000,
    windowsHide: true
  });
  if (result.error || result.status !== 0 || !result.stdout) return null;
  try {
    const payload = JSON.parse(result.stdout);
    const version = runtimeVersion(payload);
    if (!runtimeContractValid(payload, binary, minimum)) {
      return null;
    }
    return { binary: path.resolve(binary), version, payload };
  } catch (_error) {
    return null;
  }
}

function runtimeCandidates(env = process.env, home = resolveHome(env)) {
  const name = executableName();
  return [
    path.join(home, ".simplicio", "bin", name),
    path.join(home, ".local", "bin", name)
  ];
}

function findRuntime(env = process.env, home = resolveHome(env)) {
  for (const candidate of runtimeCandidates(env, home)) {
    const validated = validateRuntime(candidate);
    if (validated) return validated;
  }
  return null;
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function download(url, redirects = 0) {
  if (redirects > 5) return Promise.reject(new Error("too many installer redirects"));
  return new Promise((resolve, reject) => {
    const request = https.get(url, {
      headers: { "User-Agent": "simplicio-codex-plugin/0.2.0" },
      timeout: 30000
    }, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        response.resume();
        resolve(download(new URL(response.headers.location, url).toString(), redirects + 1));
        return;
      }
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`installer download returned HTTP ${response.statusCode}`));
        return;
      }
      const chunks = [];
      let total = 0;
      response.on("data", (chunk) => {
        total += chunk.length;
        if (total > MAX_INSTALLER_BYTES) {
          request.destroy(new Error("installer exceeds the maximum expected size"));
          return;
        }
        chunks.push(chunk);
      });
      response.on("end", () => resolve(Buffer.concat(chunks)));
      response.on("error", reject);
    });
    request.on("timeout", () => request.destroy(new Error("installer download timed out")));
    request.on("error", reject);
  });
}

function appendLog(logPath, message) {
  fs.appendFileSync(logPath, `${new Date().toISOString()} ${message}\n`, { encoding: "utf8" });
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function acquireInstallLock(lockPath, env, home) {
  const started = Date.now();
  while (Date.now() - started < LOCK_TIMEOUT_MS) {
    try {
      const token = crypto.randomUUID();
      const record = JSON.stringify({ token, pid: process.pid, createdAt: new Date().toISOString() });
      const fd = fs.openSync(lockPath, "wx", 0o600);
      fs.writeFileSync(fd, record);
      fs.closeSync(fd);
      return {
        runtime: null,
        release() {
          try {
            if (fs.readFileSync(lockPath, "utf8") === record) fs.unlinkSync(lockPath);
          } catch (error) {
            if (error.code !== "ENOENT") throw error;
          }
        }
      };
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      const runtime = findRuntime(env, home);
      if (runtime) return { runtime, release() {} };
      try {
        const raw = fs.readFileSync(lockPath, "utf8");
        const stat = fs.statSync(lockPath);
        const age = Date.now() - stat.mtimeMs;
        let owner = null;
        try { owner = JSON.parse(raw); } catch (_parseError) {}
        let ownerAlive = false;
        if (Number.isInteger(owner?.pid) && owner.pid > 0) {
          try {
            process.kill(owner.pid, 0);
            ownerAlive = true;
          } catch (killError) {
            ownerAlive = killError.code === "EPERM";
          }
        }
        const deadOwner = owner && !ownerAlive && age > 5000;
        const expiredOwner = age > LOCK_STALE_MS;
        if (deadOwner || expiredOwner) {
          if (fs.readFileSync(lockPath, "utf8") === raw) fs.unlinkSync(lockPath);
          continue;
        }
      } catch (statError) {
        if (statError.code !== "ENOENT") throw statError;
      }
      await sleep(500);
    }
  }
  throw new Error("timed out waiting for another Simplicio installation");
}

function runOfficialInstaller(installerPath, home, logPath) {
  const isolatedHome = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-plugin-home-"));
  const managedBinDir = path.join(home, ".simplicio", "bin");
  const logFd = fs.openSync(logPath, "a", 0o600);
  const env = {
    ...process.env,
    HOME: isolatedHome,
    USERPROFILE: isolatedHome,
    SIMPLICIO_BIN_DIR: managedBinDir,
    SIMPLICIO_BUNDLE_DIR: path.join(isolatedHome, ".simplicio"),
    SIMPLICIO_INSTALL_CODEX: "0",
    SIMPLICIO_INSTALL_HOST_PLUGINS: "0",
    SIMPLICIO_VERSION: POLICY.runtimeVersion
  };
  delete env.SIMPLICIO_ALLOW_UNVERIFIED;
  delete env.SIMPLICIO_CHANNEL;

  const command = process.platform === "win32" ? "powershell.exe" : "/bin/sh";
  const args = process.platform === "win32"
    ? ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", installerPath]
    : [installerPath];
  try {
    appendLog(logPath, `running pinned official ${path.basename(installerPath)} for Runtime ${POLICY.runtimeVersion}`);
    const result = spawnSync(command, args, {
      env,
      stdio: ["ignore", logFd, logFd],
      timeout: INSTALL_TIMEOUT_MS,
      windowsHide: true
    });
    if (result.error) throw result.error;
    if (result.status !== 0) {
      throw new Error(`official installer exited with status ${result.status}`);
    }
  } finally {
    fs.closeSync(logFd);
    fs.rmSync(isolatedHome, { recursive: true, force: true });
  }
}

async function installRuntime(env = process.env, home = resolveHome(env)) {
  const stateDir = path.join(home, ".simplicio", "codex-plugin-bootstrap");
  const logDir = path.join(home, ".simplicio", "logs");
  const logPath = path.join(logDir, "codex-plugin-bootstrap.log");
  fs.mkdirSync(stateDir, { recursive: true, mode: 0o700 });
  fs.mkdirSync(logDir, { recursive: true, mode: 0o700 });

  const lock = await acquireInstallLock(path.join(stateDir, "install.lock"), env, home);
  if (lock.runtime) return lock.runtime;
  let tempDir = null;
  try {
    const existing = findRuntime(env, home);
    if (existing) return existing;

    const installer = process.platform === "win32"
      ? POLICY.installers.win32
      : POLICY.installers.posix;
    const url = `https://raw.githubusercontent.com/wesleysimplicio/simplicio/${POLICY.installerCommit}/${installer.filename}`;
    appendLog(logPath, `downloading ${url}`);
    const body = await download(url);
    const actualDigest = sha256(body);
    if (actualDigest !== installer.sha256) {
      throw new Error(`official installer digest mismatch: expected ${installer.sha256}, got ${actualDigest}`);
    }

    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-plugin-installer-"));
    const installerPath = path.join(tempDir, installer.filename);
    fs.writeFileSync(installerPath, body, { flag: "wx", mode: 0o700 });
    runOfficialInstaller(installerPath, home, logPath);

    const installed = validateRuntime(path.join(home, ".simplicio", "bin", executableName()));
    if (!installed) throw new Error("the installed Runtime failed its version contract check");
    appendLog(logPath, `Runtime ${installed.version} ready at ${installed.binary}`);
    return installed;
  } finally {
    if (tempDir) fs.rmSync(tempDir, { recursive: true, force: true });
    lock.release();
  }
}

function launchRuntime(runtime, environment = process.env) {
  const args = ["serve", "--mcp", "--stdio", "--no-facade-mode"];
  const child = spawn(runtime.binary, args, {
    env: environment,
    stdio: "inherit",
    windowsHide: true
  });
  child.on("error", (error) => {
    stderr(`failed to start Runtime: ${error.message}`);
    process.exitCode = 1;
  });
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.on(signal, () => {
      if (!child.killed) child.kill(signal);
    });
  }
  child.on("exit", (code, signal) => {
    process.exitCode = Number.isInteger(code) ? code : (signal ? 1 : 0);
  });
}

async function main(environment = process.env) {
  const home = resolveHome(environment);
  const runtime = findRuntime(environment, home) || await installRuntime(environment, home);
  launchRuntime(runtime, environment);
}

if (require.main === module) {
  main().catch((error) => {
    stderr(`${error.message}. See ~/.simplicio/logs/codex-plugin-bootstrap.log`);
    process.exitCode = 1;
  });
}

module.exports = {
  POLICY,
  advertisedHostSurface,
  MAPPER_ONLY_FORBIDDEN_TOOLS,
  MAPPER_ONLY_TOOLS,
  RETIRED_ALIAS_TOOLS,
  acquireInstallLock,
  download,
  executableName,
  findRuntime,
  installRuntime,
  launchRuntime,
  main,
  parseVersion,
  resolveHome,
  runtimeCandidates,
  runtimeContractValid,
  runtimeVersion,
  sha256,
  supportedRuntimeVersion,
  validateRuntime,
  versionAtLeast
};
