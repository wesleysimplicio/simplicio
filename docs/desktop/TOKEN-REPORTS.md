# Token Reports

The Runtime navigation entry **Relatório de tokens** queries the Runtime's
SQLite ledger through the bounded `desktop_token_report` IPC command. The
Desktop does not aggregate SQL or read raw usage samples itself.

The bridge accepts an optional absolute project directory and session ID,
a timezone offset, and paired custom start/end epochs. It invokes
`simplicio tokens report --json` with individual arguments and accepts only
`workspace.token-analytics-report/v1` with `generated_by: sqlite_ledger`.
Today, 7-day, 1/3/6/12-month and custom windows come from that report. The
default project is `SIMPLICIO_DESKTOP_REPO` or the user's home directory.

An existing `.simplicio/token-usage.sqlite3` must resolve inside the selected
project. A query never creates an empty ledger to make missing telemetry look
like zero consumption. Missing usage is shown as a dash; errors and changed
filters clear stale totals and exports. Reports are limited to seven unique
windows, bounded strings and coherent non-negative, JavaScript-safe counts.

JSON and CSV exports use the native `desktop_export_token_report` command,
not WebView Blob downloads. Only the digest and format cross IPC: the native
bridge retains at most eight validated Runtime reports and exports the exact
queried snapshot. An expired digest requires a new query. JavaScript cannot
provide a file body or destination. The destination is the OS Downloads folder;
exclusive file creation adds a suffix on collision and never follows an existing
filename symlink or overwrites an export. OS permission errors stay visible,
and success is shown only after the native write and flush complete. No OS
permission or security setting is changed by the Desktop.

The files contain validated aggregate fields only. JSON includes
the report digest and the qualification that recorded usage is not verified
billing or savings. CSV includes the same qualification as a fixed label,
the report digest, timezone offset and whether a session filter was used;
it excludes user-controlled text and raw samples. The
current Runtime report does not expose per-sample provenance, model/harness
breakdowns or costs; the Desktop does not invent them. Browser preview has
no real usage report. Access must be active in the Runtime snapshot.

The separate `insights.tokens/v1` summary preserves savings/cache evidence
labels. Only `measured` savings with a valid ledger reference may populate its
saved-token counter; `mixed`, `estimated`, `replayed` and missing receipts do
not become measured usage. Neither surface calculates provider cache hits.

## All-project consolidated report

The top section consolidates discovered projects, saved project shortcuts and
manually selected projects (up to 96 distinct absolute paths). It reuses the
project discovery already performed for the individual report. Discovery is
bounded, not a claim to have searched every folder on the computer; partial
discovery and excluded paths remain explicit.

The five filters are **7 days, 30 days, 3 months, 6 months and 12 months**.
Days are rolling 24-hour intervals. Months use the local calendar and clamp
month-end dates, including leap years. Start and exclusive end are fixed once
before the batch, with one timezone offset and no session filter. In particular,
30 days is not the Runtime's calendar `1m` window. Every Runtime query uses the
same explicit custom interval and its echoed bounds are checked.

`desktop_consolidated_token_report` returns
`simplicio.desktop-consolidated-tokens/v1`. Each requested path has a status:
`ready`, `missing`, `invalid`, `timeout`, `skipped` or `duplicate`. Native code
adds only validated `ready` aggregates using checked JavaScript-safe integers;
the WebView independently validates that sum and the exact requested scope.
Unknown usage stays unknown, not zero. Canonical ledger paths (and device/inode
identity on Unix) exclude aliases of the same database. Copies in independent
databases cannot be event-deduplicated by this aggregate-only contract.

The report has accessible project bars, an input/output/reasoning composition
chart and a table containing every project/status. Bars show the eight largest
projects plus a sum of the remainder; totals always include all valid reports.
Cached input is a subset of input and is not added twice. No daily time series,
model split, financial cost or measured savings is fabricated. Individual JSON
and CSV exports below still refer only to the selected project's report, not
the consolidated view.

Filesystem preflight runs in a bounded pre-Tauri worker, without starting a
Runtime grandchild. The parent starts fixed Runtime argv directly. A single
native batch has a 90-second budget, each filesystem preflight at most 2 seconds,
and each Runtime query at most 5 seconds, plus bounded process cleanup. Fresh
read authorization is performed once. Completed project results survive the
deadline, while remaining projects are explicitly skipped. The frontend's
observer timeout does not release the native read slot or trigger a retry.

The separate context-savings panel is the selected project's **all-history**
report. Its values are not mixed into this time-filtered usage consolidation.
