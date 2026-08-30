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
