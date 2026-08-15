# agentsview source_adapter — session analytics & cost observability

A concrete binding of the `source_adapter` extension point for the **agentsview** local-first
session search / analytics system. Connects to agentsview's SQLite database (or HTTP API) to
discover stalled/incomplete agent sessions, report aggregate token-cost data, and track
orchestrator effectiveness over time.

**agentsview** (kenn-io) supports 20+ coding agents: Claude Code, Codex, Aider, Cursor, Gemini,
Copilot, OpenCode, and more. See https://agentsview.io and https://github.com/kenn-io/agentsview.

## Purpose

| Use case | What it enables |
|---|---|
| **Discover abandoned work** | Find sessions that were started but never completed by any agent, convert to simplicio-loop items |
| **Cost observability** | Report real historical cost per session for dashboards and billing rollups |
| **Fleet observability** | Monitor fleet use (which agents, which projects, which patterns) to inform autoscale |
| **Effectiveness tracking** | Compare token spend, session count, completion rate before vs after simplicio-loop adoption |

## Architecture: two modes

The adapter supports two connection strategies. One must be active.

### Mode A — Direct SQLite read (recommended)

Reads agentsview's local SQLite database directly. No agentsview server needed.

```bash
# Default path (platform-specific)
AGENTSVIEW_DB="${AGENTSVIEW_DB:-$HOME/.agentsview/data.db}"
AGENTSVIEW_DB="${AGENTSVIEW_DB:-$HOME/Library/Application Support/agentsview/data.db}"
```

Queries use SQLite FTS5 for session search and the main `sessions` + `messages` tables for
analytics. This mode is faster and requires zero external process, but may conflict with a
concurrent agentsview `serve` process (SQLite WAL handles concurrent readers).

### Mode B — HTTP API

Hits the agentsview REST API at `http://127.0.0.1:8080`. Requires `agentsview serve` to be
running. Cleaner abstraction; respects agentsview's process lifecycle.

```bash
AGENTSVIEW_API="${AGENTSVIEW_API:-http://127.0.0.1:8080}"
```

## The six verbs (uniform source_adapter contract)

| Verb | Implementation | Notes |
|---|---|---|
| `list_ready` | `sqlite3 "$AGENTSVIEW_DB" "SELECT id, agent, project, started_at FROM sessions WHERE status != 'completed' ORDER BY started_at DESC LIMIT 50"` — or `curl -s "$AGENTSVIEW_API/api/v1/sessions" \| jq '.[] \| select(.status != "completed")'` | metadata-only; returns session id, agent name, project, start time, duration |
| `get_details` | Read full session from SQLite by ID — joins `sessions` + `messages` tables; extracts last user prompt, tool calls, error logs | full details for Step 2b intake |
| `claim` | Tag the session in agentsview as `in-progress` via API `PATCH /api/v1/sessions/<id>` with `{"status": "in-progress"}` — or write a sidecar `.simplicio-claimed` file next to the session data | cross-session claim marker |
| `update_status` | `PATCH /api/v1/sessions/<id>` with `{"status": "<state>"}` — states: `stalled` (no progress), `resumed` (adopted by loop), `completed` (merged+closed) | |
| `attach_evidence` | Add a note/tag to the agentsview session record — store the PR URL, loop run ID, outcome summary | evidence = the `evidence.md` sidecar path |
| `close` | Mark the session as `completed` — `PATCH /api/v1/sessions/<id> {"status": "completed", "outcome": "merged"}` | |

## SQL queries (Direct SQLite — Mode A)

### Discover stalled sessions (sessions older than 1h with no close)

```sql
SELECT s.id, s.agent, s.project, s.started_at, s.updated_at,
       CAST((julianday('now') - julianday(s.updated_at)) * 24 AS INTEGER) AS hours_stalled,
       (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count,
       (SELECT SUM(m.cost_estimate) FROM messages m WHERE m.session_id = s.id) AS total_cost_estimate
FROM sessions s
WHERE s.status != 'completed'
  AND s.updated_at < datetime('now', '-1 hour')
ORDER BY hours_stalled DESC
LIMIT 30;
```

### Get full session detail

```sql
SELECT s.*, m.role, m.content_preview, m.cost_estimate, m.duration_ms
FROM sessions s
LEFT JOIN messages m ON m.session_id = s.id
WHERE s.id = '<session-id>'
ORDER BY m.created_at ASC;
```

### Daily cost summary (for billing/observability)

```sql
SELECT DATE(m.created_at) AS day,
       COUNT(DISTINCT m.session_id) AS sessions,
       SUM(m.cost_estimate) AS total_cost,
       SUM(m.duration_ms) / 60000.0 AS total_minutes
FROM messages m
WHERE m.created_at > datetime('now', '-30 days')
GROUP BY DATE(m.created_at)
ORDER BY day DESC;
```

### Agent usage breakdown

```sql
SELECT s.agent, COUNT(*) AS session_count,
       AVG(CAST((julianday('now') - julianday(s.started_at)) * 24 AS REAL)) AS avg_hours,
       SUM(m.cost_estimate) AS total_cost
FROM sessions s
LEFT JOIN messages m ON m.session_id = s.id
WHERE s.started_at > datetime('now', '-7 days')
GROUP BY s.agent
ORDER BY total_cost DESC;
```

## API endpoints (HTTP — Mode B)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/sessions` | GET | List all sessions (paginated, filterable by `?status=`) |
| `/api/v1/sessions/<id>` | GET | Full session detail with messages |
| `/api/v1/sessions/<id>` | PATCH | Update session metadata (status, tags) |
| `/api/v1/usage/daily` | GET | Daily cost/session summaries |
| `/api/v1/agents` | GET | Agent inventory |

## Integration points in simplicio-loop

### 1. Cost observability (`pre-flight` / dashboard)

Before each loop iteration, run:

```bash
# Mode A: Direct SQLite
agentsview_daily_cost=$(sqlite3 "$AGENTSVIEW_DB" "
  SELECT COALESCE(SUM(m.cost_estimate), 0)
  FROM messages m
  WHERE m.created_at > datetime('now', 'start of day')
")

# Mode B: HTTP API
agentsview_daily_cost=$(curl -s "$AGENTSVIEW_API/api/v1/usage/daily" | jq '.[0].total_cost // 0')
```

Use this value only for reporting, billing rollups, or operator dashboards. It does not stop or
gate the loop.

### 2. Demand discovery (Step 3 — Discover + normalize)

```text
/simplicio-tasks resume stalled sessions
```

→ Adapter queries agentsview for sessions running >1h with no completion
→ Normalizes each into a canonical work-item:
  - `id`: `agentsview/<agent>/<session-uuid>`
  - `title`: `[agentsview] <agent> — <project> session <started_at>`
  - `description`: session context, last prompt, error summary
  - `priority`: stall_time (longer = higher)
  - `source`: `agentsview`

### 3. Observability dashboard readout

At the end of each loop cycle, read agentsview's metrics to include in the savings report:

```text
┌─────────────────────────────────────────────┐
│ agentsview observability                    │
├─────────────────────────────────────────────┤
│ Sessions tracked today: 12                  │
│ Total agent cost today: $0.87               │
│ Stalled sessions recovered: 3               │
│ Loop adoption impact: -34% token spend      │
└─────────────────────────────────────────────┘
```

## Prerequisites

- **agentsview** binary installed (`curl -fsSL https://agentsview.io/install.sh | bash`)
- For Mode A: `sqlite3` on PATH
- For Mode B: `agentsview serve` running (or `agentsview serve --background`)
- API access requires loopback binding (agentsview binds `127.0.0.1:8080` by default)
- PostgreSQL mode: agentsview may push to PG; the adapter reads from PG via `AGENTSVIEW_PG_DSN`

## Token economy

- `list_ready` returns metadata only (session id, agent, project, duration) — no message bodies
- `get_details` is the only verb that fetches full transcript, and only for the session about to be acted upon
- `cost_summary` queries are aggregate SQL — cost estimates already numeric, no LLM parsing
- Large transcript bodies are truncated to first+N tokens through SQL `substr()` or API `?truncate=2000`
- All output flows through `orient_clamp.py` for final clamping

## Testing (no agentsview needed)

Each verb supports `--dry-run`:

```bash
# Dry-run the adapter without a real agentsview DB
python3 scripts/agentsview_adapter.py list_ready --dry-run
python3 scripts/agentsview_adapter.py get_details --id test-session-uuid --dry-run
python3 scripts/agentsview_adapter.py cost_summary --days 7 --dry-run
```

In dry-run mode, the adapter prints the exact SQL queries or curl commands it would execute,
plus the expected normalization schema — verifiable in CI without agentsview installed.
