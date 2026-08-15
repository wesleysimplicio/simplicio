#!/usr/bin/env node
/**
 * Claude Code UserPromptSubmit hook — thin Plugin v1 adapter.
 *
 * Formats/transports only. Runtime/Loop owns RouteDecision. The hook never
 * authorizes writes or effects and never silently opts out in mandatory.
 *
 * stdin  -> JSON { prompt, cwd, session_id, hook_event_name, ... }
 * stdout -> JSON { hookSpecificOutput: { hookEventName, additionalContext } }
 * exit 0 always (host contract). Fallback is visible in additionalContext.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { runHook } from "./plugin-runtime-adapter/adapter.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..", "..");

function readStdin() {
  try {
    return readFileSync(0, "utf-8");
  } catch {
    return "";
  }
}

function main() {
  const result = runHook(readStdin(), { root: REPO_ROOT, env: process.env });
  process.stdout.write(JSON.stringify(result.hookSpecificOutput ? {
    hookSpecificOutput: result.hookSpecificOutput,
  } : result));
  process.exit(0);
}

main();
