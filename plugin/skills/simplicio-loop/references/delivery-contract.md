# Delivery contract — `delivery.json` (issue #526 Etapa 4)

Client delivery restrictions said in natural language ("don't open a PR", "don't commit tests", "no
comments in the code") become a **frozen contract** living next to the task anchor, with mechanical
gates that enforce each clause — instead of prose the agent can forget mid-run. Worker:
`scripts/delivery_contract.py`; frozen into the anchor by `task_anchor.py set --delivery
delivery.json`.

## Schema (`simplicio.delivery-contract/v1`)

Exactly these 5 fields, ALL required. **An unknown field is a hard error** — `set --delivery`
refuses to freeze it (exit 2), never silently drops or ignores it.

```json
{
  "open_pr": false,
  "push_branch": true,
  "allow_new_files_in_repo": false,
  "allow_comments_in_code": false,
  "commit_message_convention": "#<issue> - <type>: <desc>"
}
```

| Field | Type | Meaning |
|---|---|---|
| `open_pr` | bool | `false` → the loop must not open a PR; evidence is a **local report file** instead. |
| `push_branch` | bool | `true` → the branch is expected to be pushed (informational; not independently observed by this worker — see "Observability" below). |
| `allow_new_files_in_repo` | bool | `false` → no file may appear in the repo (tracked or untracked) beyond what already existed when the contract was frozen. |
| `allow_comments_in_code` | bool | `false` → the diff must not add comment lines (any language the linter covers). |
| `commit_message_convention` | non-empty string | A template with `<issue>`/`<type>`/`<desc>` placeholders the commit subject must match. |

`commit_message_convention` placeholders: `<issue>` → digits, `<type>` → a bare word
(`feat`/`fix`/...), `<desc>` → any non-empty remainder. Example
`"#<issue> - <type>: <desc>"` matches `"#526 - feat: add delivery contract"`.

## Freezing (`task_anchor.py set --delivery FILE`)

```bash
python3 scripts/task_anchor.py set --item 526 --goal "Ship the TFS_326750 fix" \
    --ac "Cap mirrored in the UHE block" --delivery delivery.json
```

1. The LLM proposes the contract from the user's request; the **user confirms**; only then is
   `set --delivery` run.
2. The worker validates the file against the schema above — any error (unknown field, missing
   field, wrong type, blank `commit_message_convention`) BLOCKS the freeze (exit 2), it never
   silently accepts a partial/typo'd contract.
3. The validated contract is written into `anchor.json`'s `"delivery"` key.
4. **Re-anchor semantics**: if a delivery contract is already frozen and the new one differs,
   `set --delivery` is BLOCKED (exit 12) unless `--force` — identical to the goal re-anchor
   contract already in `task_anchor.py`. A silent contract swap mid-run is exactly the drift this
   guards against.
5. When `allow_new_files_in_repo: false` is (re-)frozen, the worker also (re-)captures the
   **new-file baseline** (`scripts/delivery_contract.py capture-baseline`) — every file untracked
   or newly-staged AT THAT MOMENT is treated as pre-existing/authorized for the rest of the
   contract's life; anything that appears after is a violation.

## Mechanical gates

### `open_pr: false` → `pr_evidence.py --local-report`

`pr_evidence.py build` reads the anchor's `delivery` clause; when `open_pr` is `false` it
automatically runs in **local-report mode**: the evidence body (checklist + prints + delivery
compliance section) is written to a local file
(`.simplicio/orchestrator/loop/delivery_report.md` by default) instead of being handed to any PR-opening
flow. `--local-report` can also be passed explicitly. The PR API is never called in this mode.

### `allow_new_files_in_repo: false` → stop-hook new-file guard

Every turn, `hooks/loop_stop.py` calls `scripts/delivery_contract.new_file_guard(anchor)`:

1. Read the frozen baseline (`.simplicio/orchestrator/loop/delivery_baseline.json`).
2. Compute the CURRENT untracked/staged-new files (`git status --porcelain=v1
   --untracked-files=all`).
3. Any file present now but ABSENT from the baseline is an unauthorized new file → the turn is
   **blocked**: a handoff is written, the reason names every offending path, and a journal record
   is appended (`loop_journal.py record --gate blocked`).

An absent baseline is treated as EMPTY — i.e. every currently-untracked/staged file is a
violation — so a guard that runs before `capture-baseline` ever ran fails CLOSED, never open.

### `allow_comments_in_code: false` → diff comment linter

`scripts/delivery_contract.py lint-comments` (staged diff by default; `--working-tree` for the
unstaged diff) parses the unified `git diff` output per-file and flags ADDED lines that are
comments in that file's language:

| Language | Extensions | Detected |
|---|---|---|
| C# | `.cs` | `//` line comments, `/* ... */` blocks (open/continuation/close) |
| TypeScript/JavaScript | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` | same as C# |
| Python | `.py` | `#` line comments, **new docstrings** (`"""..."""` / `'''...'''`, including multi-line open/close) |

A non-empty violation list fails the gate (exit 1) — run before commit; a delivery contract with
`allow_comments_in_code: false` makes this mandatory in that turn's flow.

### `commit_message_convention` → subject check

`scripts/delivery_contract.py check-commit-message --message "<subject>" --convention
"<template>"` derives a regex from the template's `<issue>`/`<type>`/`<desc>` placeholders and
checks the commit subject (first line) against it.

## Final report — clause-by-clause compliance (MEASURED)

`scripts/delivery_contract.py report` (also folded into `pr_evidence.py build`'s local-report
body when a delivery contract is anchored) renders:

```
### Delivery contract compliance

- [MEASURED] open_pr: false — compliant (pr_evidence.py runs in --local-report mode; no PR API call)
- [MEASURED] push_branch: true — declared clause (not independently observed by this worker)
- [MEASURED] allow_new_files_in_repo: false — compliant
- [MEASURED] allow_comments_in_code: false — compliant
- [MEASURED] commit_message_convention: '#<issue> - <type>: <desc>' — compliant
```

Every clause appears, always, tagged `MEASURED` — the report never omits a clause, and a
violation is spelled out (`VIOLATION — ...`) rather than silently passed over.

### Observability caveat — `push_branch`

`push_branch` is a **declared** clause: nothing in this repo (the loop's own process) can
independently observe whether the branch was actually pushed to the remote from inside a stop-hook
turn — that is an out-of-process fact. The report always names the clause and its declared value;
it is not (yet) mechanically verified the way the other four clauses are.

## Fixture (reproduces the real-world case)

`tests/test_delivery_contract_526_unit.py` freezes the exact 3-restriction contract from the
issue's motivating session (`open_pr: false`, `allow_new_files_in_repo: false`,
`allow_comments_in_code: false`) and then simulates a turn that creates `FooTests.cs` — the guard
blocks with a reason naming `FooTests.cs` explicitly.
