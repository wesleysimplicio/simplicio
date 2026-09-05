#!/usr/bin/env node
"use strict";

const bootstrap = require("./simplicio-mcp-bootstrap.js");

// Claude Code owns native editing and terminal tools. Keep this selection
// process-local so an ambient full Runtime configuration is not changed for
// the user's other hosts.
process.env.SIMPLICIO_RUNTIME_MODE = "mapper-only";

bootstrap.main().catch((error) => {
  process.stderr.write(`[simplicio-plugin] ${error.message}. See ~/.simplicio/logs/codex-plugin-bootstrap.log\n`);
  process.exitCode = 1;
});
