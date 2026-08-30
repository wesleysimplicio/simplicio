# Activity Center

`activity.center/v1` is the read-only history of bounded receipts. Filters,
pagination and exports operate on the projection; raw ledgers, prompts,
credentials and private detail are not sent to the Desktop.

Runtime-backed export returns an artifact handle. Preview mode keeps the export
button useful for local QA but does not claim a canonical report exists.
