"use strict";

const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const test = require("node:test");

const bootstrapPath = path.resolve(__dirname, "..", "bin", "simplicio-mcp-bootstrap.js");
const bootstrap = require(bootstrapPath);

test("version comparison is semantic and bounded", () => {
  assert.equal(bootstrap.versionAtLeast("3.8.35", "3.8.35"), true);
  assert.equal(bootstrap.versionAtLeast("v3.9.0", "3.8.35"), true);
  assert.equal(bootstrap.versionAtLeast("3.8.34", "3.8.35"), false);
  assert.equal(bootstrap.versionAtLeast("latest", "3.8.35"), false);
  assert.equal(bootstrap.supportedRuntimeVersion("3.9.0"), true);
  assert.equal(bootstrap.supportedRuntimeVersion("4.0.0"), false);
  assert.equal(bootstrap.versionAtLeast("3.8.35", "invalid"), false);
  assert.equal(bootstrap.runtimeVersion({
    runtime: { executable: { version: "3.8.36" } }
  }), "3.8.36");
  assert.equal(bootstrap.runtimeVersion({ version: "3.8.37" }), "3.8.37");
  assert.equal(bootstrap.runtimeVersion({}), null);
});

test("installer policy is pinned to immutable content", () => {
  assert.match(bootstrap.POLICY.installerCommit, /^[0-9a-f]{40}$/);
  assert.match(bootstrap.POLICY.installers.posix.sha256, /^[0-9a-f]{64}$/);
  assert.match(bootstrap.POLICY.installers.win32.sha256, /^[0-9a-f]{64}$/);
});

test("installer download follows redirects and fails closed on HTTP errors", async () => {
  await assert.rejects(
    bootstrap.download("https://example.test/installer", 6),
    /too many installer redirects/
  );

  const originalGet = https.get;
  let call = 0;
  https.get = (_url, _options, callback) => {
    call += 1;
    const request = new EventEmitter();
    request.destroy = (error) => request.emit("error", error);
    process.nextTick(() => {
      const response = new EventEmitter();
      response.headers = {};
      response.resume = () => {};
      if (call === 1) {
        response.statusCode = 302;
        response.headers.location = "/pinned-installer";
        callback(response);
        return;
      }
      response.statusCode = 200;
      callback(response);
      response.emit("data", Buffer.from("verified-installer"));
      response.emit("end");
    });
    return request;
  };

  try {
    const body = await bootstrap.download("https://example.test/installer");
    assert.equal(body.toString("utf8"), "verified-installer");

    https.get = (_url, _options, callback) => {
      const request = new EventEmitter();
      request.destroy = (error) => request.emit("error", error);
      process.nextTick(() => {
        const response = new EventEmitter();
        response.statusCode = 503;
        response.headers = {};
        response.resume = () => {};
        callback(response);
      });
      return request;
    };
    await assert.rejects(
      bootstrap.download("https://example.test/unavailable"),
      /HTTP 503/
    );

    https.get = (_url, _options, callback) => {
      const request = new EventEmitter();
      request.destroy = (error) => request.emit("error", error);
      process.nextTick(() => {
        const response = new EventEmitter();
        response.statusCode = 200;
        response.headers = {};
        callback(response);
        response.emit("data", Buffer.alloc((1024 * 1024) + 1));
      });
      return request;
    };
    await assert.rejects(
      bootstrap.download("https://example.test/oversized"),
      /exceeds the maximum expected size/
    );
  } finally {
    https.get = originalGet;
  }
});

test("runtime discovery ignores PATH and uses only managed locations", () => {
  const home = path.resolve(os.tmpdir(), "simplicio-test-home");
  assert.deepEqual(bootstrap.runtimeCandidates({ HOME: home, PATH: "/tmp/poisoned" }, home), [
    path.join(home, ".simplicio", "bin", bootstrap.executableName()),
    path.join(home, ".local", "bin", bootstrap.executableName())
  ]);
});

test("a self-declared product and version are not a full Runtime contract", () => {
  assert.equal(bootstrap.runtimeContractValid({
    product: "simplicio-runtime",
    runtime: { version: "3.8.35" }
  }, "/tmp/simplicio"), false);
});

test("the release contract accepts the signed-security fallback", () => {
  const binary = path.join(os.tmpdir(), "simplicio-contract-only");
  assert.equal(bootstrap.runtimeContractValid({
    schema: "simplicio.release-manifest/v1",
    product: "simplicio-runtime",
    runtime: {
      name: "simplicio-runtime",
      version: "3.8.35",
      executable: { path: binary, version: "3.8.35" }
    },
    auto_update: {
      distribution: { source_code_distributed: true },
      security: {
        signature_required: true,
        public_key_configured: true,
        refuse_unsigned: true,
        refuse_invalid_signature: true
      }
    },
    identity: { enabled: true, login_enabled: true }
  }, binary), true);
});

test("invalid homes, paths, and binaries fail closed", () => {
  assert.throws(
    () => bootstrap.resolveHome({ HOME: "relative", USERPROFILE: "" }),
    /absolute user home/
  );
  assert.equal(
    bootstrap.resolveHome({ HOME: "", USERPROFILE: os.tmpdir() }),
    path.resolve(os.tmpdir())
  );
  assert.equal(bootstrap.resolveHome({ HOME: "", USERPROFILE: "" }), os.homedir());
  assert.equal(bootstrap.validateRuntime(null), null);
  assert.equal(bootstrap.validateRuntime("relative/simplicio"), null);
  assert.equal(bootstrap.validateRuntime(path.join(os.tmpdir(), "missing-simplicio")), null);
  assert.equal(bootstrap.runtimeContractValid({
    runtime: { executable: { path: {} } }
  }, "/tmp/simplicio"), false);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-invalid-runtime-"));
  const invalidBinary = path.join(tempDir, "simplicio");
  try {
    fs.writeFileSync(invalidBinary, "not executable", { mode: 0o600 });
    assert.equal(bootstrap.validateRuntime(invalidBinary), null);
    fs.writeFileSync(invalidBinary, "#!/bin/sh\nprintf 'not-json'\n", { mode: 0o700 });
    assert.equal(bootstrap.validateRuntime(invalidBinary), null);
    assert.equal(bootstrap.findRuntime({ HOME: tempDir }, tempDir), null);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("install lock release cannot delete a replacement owner's lock", async () => {
  const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-lock-owner-test-"));
  const stateDir = path.join(tempHome, ".simplicio", "codex-plugin-bootstrap");
  const lockPath = path.join(stateDir, "install.lock");
  fs.mkdirSync(stateDir, { recursive: true });
  try {
    const lock = await bootstrap.acquireInstallLock(lockPath, { HOME: tempHome, PATH: "" }, tempHome);
    const replacement = JSON.stringify({ token: "replacement", pid: process.pid, createdAt: new Date().toISOString() });
    fs.writeFileSync(lockPath, replacement);
    lock.release();
    assert.equal(fs.readFileSync(lockPath, "utf8"), replacement);
  } finally {
    fs.rmSync(tempHome, { recursive: true, force: true });
  }
});

test("a dead stale install lock is reclaimed", async () => {
  const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-stale-lock-test-"));
  const stateDir = path.join(tempHome, ".simplicio", "codex-plugin-bootstrap");
  const lockPath = path.join(stateDir, "install.lock");
  fs.mkdirSync(stateDir, { recursive: true });
  fs.writeFileSync(lockPath, JSON.stringify({
    token: "stale",
    pid: 99999999,
    createdAt: new Date(0).toISOString()
  }));
  const staleTime = new Date(Date.now() - 6000);
  fs.utimesSync(lockPath, staleTime, staleTime);

  try {
    const lock = await bootstrap.acquireInstallLock(
      lockPath,
      { HOME: tempHome, PATH: "" },
      tempHome
    );
    lock.release();
    assert.equal(fs.existsSync(lockPath), false);
  } finally {
    fs.rmSync(tempHome, { recursive: true, force: true });
  }
});

test("an expired malformed install lock is reclaimed", async () => {
  const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-expired-lock-test-"));
  const stateDir = path.join(tempHome, ".simplicio", "codex-plugin-bootstrap");
  const lockPath = path.join(stateDir, "install.lock");
  fs.mkdirSync(stateDir, { recursive: true });
  fs.writeFileSync(lockPath, "malformed");
  const expiredTime = new Date(Date.now() - (13 * 60 * 1000));
  fs.utimesSync(lockPath, expiredTime, expiredTime);

  try {
    const lock = await bootstrap.acquireInstallLock(
      lockPath,
      { HOME: tempHome, PATH: "" },
      tempHome
    );
    lock.release();
    assert.equal(fs.existsSync(lockPath), false);
  } finally {
    fs.rmSync(tempHome, { recursive: true, force: true });
  }
});

test("bootstrap selects a valid Runtime and keeps pre-server stdout empty", { skip: process.platform === "win32" }, () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-bootstrap-test-"));
  const fakeRuntime = path.join(tempDir, ".simplicio", "bin", "simplicio");
  const argsFile = path.join(tempDir, "args.txt");
  fs.mkdirSync(path.dirname(fakeRuntime), { recursive: true });
  fs.writeFileSync(fakeRuntime, `#!/bin/sh
if [ "$1" = "version" ]; then
  printf '{"schema":"simplicio.release-manifest/v1","product":"simplicio-runtime","runtime":{"name":"simplicio-runtime","version":"3.8.35","executable":{"path":"%s","version":"3.8.35"}},"auto_update":{"distribution":{"source_code_distributed":true}},"identity":{"enabled":true,"login_enabled":true},"security":{"signature_required":true,"public_key_configured":true,"refuse_unsigned":true,"refuse_invalid_signature":true}}' "$0"
  exit 0
fi
printf '%s' "$*" > "$SIMPLICIO_TEST_ARGS_FILE"
`, { mode: 0o700 });

  try {
    const result = spawnSync(process.execPath, [bootstrapPath], {
      encoding: "utf8",
      env: {
        ...process.env,
        HOME: tempDir,
        SIMPLICIO_TEST_ARGS_FILE: argsFile
      },
      timeout: 15000
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(fs.readFileSync(argsFile, "utf8"), "serve --mcp --stdio --no-facade-mode");
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test("real bootstrap completes an MCP handshake and exposes governed tools", { timeout: 30000 }, async (context) => {
  const installed = bootstrap.findRuntime();
  if (!installed) {
    context.skip("no compatible Runtime is installed for the live handshake");
    return;
  }

  const child = spawn(process.execPath, [bootstrapPath], {
    env: { ...process.env },
    stdio: ["pipe", "pipe", "pipe"]
  });
  const responses = new Map();
  const waiters = new Map();
  let buffer = "";
  let stderr = "";

  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    buffer += chunk;
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      const message = JSON.parse(line);
      if (message.id === undefined) continue;
      responses.set(message.id, message);
      const resolve = waiters.get(message.id);
      if (resolve) {
        waiters.delete(message.id);
        resolve(message);
      }
    }
  });

  function waitFor(id) {
    if (responses.has(id)) return Promise.resolve(responses.get(id));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`timeout waiting for MCP response ${id}: ${stderr}`)), 15000);
      waiters.set(id, (message) => {
        clearTimeout(timer);
        resolve(message);
      });
    });
  }

  try {
    child.stdin.write(`${JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "simplicio-plugin-test", version: "0.2.0" }
      }
    })}\n`);
    const initialized = await waitFor(1);
    assert.equal(initialized.result.serverInfo.name, "simplicio");

    child.stdin.write(`${JSON.stringify({
      jsonrpc: "2.0",
      method: "notifications/initialized",
      params: {}
    })}\n`);
    child.stdin.write(`${JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list",
      params: {}
    })}\n`);
    const listed = await waitFor(2);
    const tools = listed.result.tools;
    const names = tools.map((tool) => tool.name);
    assert.ok(names.length > 0, "expected a non-empty governed tool surface");
    assert.equal(new Set(names).size, names.length, "tool names must be unique");
    assert.ok(names.includes("simplicio_context"));
    assert.ok(names.includes("simplicio_edit"));
  } finally {
    child.stdin.end();
    child.kill("SIGTERM");
  }
});
