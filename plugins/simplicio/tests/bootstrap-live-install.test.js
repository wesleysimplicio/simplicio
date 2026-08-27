"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const test = require("node:test");

const bootstrapPath = path.resolve(__dirname, "..", "bin", "simplicio-mcp-bootstrap.js");
const bootstrap = require(bootstrapPath);

test("missing Runtime is installed in isolation before the MCP handshake", {
  skip: process.env.SIMPLICIO_PLUGIN_LIVE_INSTALL_TEST !== "1" || process.platform === "win32",
  timeout: 10 * 60 * 1000
}, async () => {
  const tempHome = fs.mkdtempSync(path.join(os.tmpdir(), "simplicio-plugin-live-install-"));
  const env = {
    ...process.env,
    HOME: tempHome,
    PATH: "/usr/bin:/bin:/usr/sbin:/sbin"
  };
  delete env.SIMPLICIO_BIN;
  delete env.SIMPLICIO_ALLOW_UNVERIFIED;
  delete env.SIMPLICIO_CHANNEL;

  const installed = await bootstrap.installRuntime(env, tempHome);
  assert.equal(installed.version, bootstrap.POLICY.runtimeVersion);
  assert.equal(
    installed.binary,
    path.join(tempHome, ".simplicio", "bin", bootstrap.executableName())
  );
  const reused = await bootstrap.installRuntime(env, tempHome);
  assert.equal(reused.binary, installed.binary);

  const child = spawn(process.execPath, [bootstrapPath], {
    env,
    stdio: ["pipe", "pipe", "pipe"]
  });
  const responses = new Map();
  const waiters = new Map();
  let buffer = "";
  let stderr = "";

  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr = `${stderr}${chunk}`.slice(-12000); });
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
      const waiter = waiters.get(message.id);
      if (waiter) {
        waiters.delete(message.id);
        waiter.resolve(message);
      }
    }
  });

  function waitFor(id, timeoutMs = 9 * 60 * 1000) {
    if (responses.has(id)) return Promise.resolve(responses.get(id));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        waiters.delete(id);
        reject(new Error(`timeout waiting for MCP response ${id}: ${stderr}`));
      }, timeoutMs);
      waiters.set(id, {
        resolve(message) {
          clearTimeout(timer);
          resolve(message);
        }
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
        clientInfo: { name: "simplicio-plugin-live-install-test", version: "0.2.0" }
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
    const listed = await waitFor(2, 30000);
    assert.ok(listed.result.tools.length >= 44);
    assert.ok(listed.result.tools.some((tool) => tool.name === "simplicio_exec"));
    assert.ok(fs.existsSync(path.join(tempHome, ".simplicio", "bin", "simplicio")));
  } finally {
    child.stdin.end();
    child.kill("SIGTERM");
    await new Promise((resolve) => {
      if (child.exitCode !== null) return resolve();
      const timer = setTimeout(resolve, 5000);
      child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
    });
    fs.rmSync(tempHome, { recursive: true, force: true });
  }
});
