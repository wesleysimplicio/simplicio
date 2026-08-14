# Azure DevOps source_adapter (`az boards` / `az repos` / `az pipelines`)

A concrete binding of the `source_adapter` extension point for repos whose work lives in **Azure
DevOps Boards** rather than GitHub Issues. Step 2 of the orchestrator resolves the source adapter
FIRST and never assumes GitHub — when the source is Azure Boards, it drives the six uniform verbs
below. The runnable form is `scripts/az_boards_adapter.py`; this file is the contract + the exact
commands it wraps. Evidence/facts come from the terminal (JSON), never from the LLM.

Credit: Azure CLI (`az`) + the `azure-devops` extension (`az extension add --name azure-devops`).

## Auth + defaults (resolve once)
```bash
az login
az extension add --name azure-devops          # one-time
az devops configure --defaults organization=https://dev.azure.com/<org> project=<project>
# CI / non-interactive: export AZURE_DEVOPS_EXT_PAT=<pat>   (scopes: Work Items R/W, Code R/W)
```
Override per call with `--org` / `--project`, or env `AZURE_DEVOPS_ORG` / `AZURE_DEVOPS_PROJECT`.
On auth failure the adapter STOPS (never proceeds on broken auth — Step 1a).

## The six verbs (uniform source_adapter contract)

| Verb | Azure CLI | Notes |
|---|---|---|
| `list_ready` | `az boards query --wiql "<WIQL>"` | metadata-only; states `New,Active` by default; optional `--area` (AreaPath UNDER) |
| `get_details` | `az boards work-item show --id <id>` + `az devops invoke --area wit --resource comments` | full fields + comments for Step 2b intake; reads `Microsoft.VSTS.Common.AcceptanceCriteria` |
| `claim` | `az boards work-item update --id <id> --assigned-to <me> --fields System.Tags=in-progress` | cross-session claim marker (assignee + tag) |
| `update_status` | `az boards work-item update --id <id> --state <State>` | e.g. `Active`, `Resolved` |
| `attach_evidence` | `az boards work-item update --id <id> --discussion "<note>"` | PR link + verification note into the discussion |
| `close` | `az boards work-item update --id <id> --state Closed` | `--state Resolved` where the process requires a resolve step first |

WIQL used by `list_ready` (newest first, metadata fields only):
```sql
SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType], [System.Tags]
FROM workitems
WHERE ([System.State] = 'New' OR [System.State] = 'Active') [AND [System.AreaPath] UNDER '<area>']
ORDER BY [System.ChangedDate] DESC
```

## Code review + CI (deliver, Step 6)
The Boards adapter pairs with Repos + Pipelines for the full demand-to-delivery loop:
```bash
az repos pr create   --repository <repo> --source-branch <branch> --target-branch main \
                     --title "<conv-commit title>" --work-items <id>        # links PR ↔ work-item
az repos pr show     --id <pr> --output json                                # poll status (Step 6b)
az pipelines run     --name <pipeline> --branch <branch>                    # trigger CI
az pipelines runs show --id <run> --output json                            # gate on result
```
Linking the PR with `--work-items <id>` lets Azure auto-transition the item on merge; the adapter's
`attach_evidence` still records the PR URL + verification so the close is evidence-backed.

## Claim atomicity (cross-session safety)
`az boards` has no compare-and-swap, so the claim is assignee + `in-progress` tag, then a re-read
to confirm we won the race (another instance that also claimed → back off, Step 3b idempotency).
For hard atomicity, gate on a State transition the process allows only from the unclaimed state.

## Token economy
- `list_ready` returns metadata only — never pull every body during triage (Step 2).
- `get_details` is the only verb that fetches bodies + comments, and only for the item about to be
  implemented (Step 2b).
- All output is JSON parsed by the orchestrator deterministically; clamp large query results
  through the orient catalog (tee to file, surface count + first N) exactly like build/test output.

## Test offline (no org needed)
Every verb supports `--dry-run`, which prints the resolved `az` argv without executing — so the
command construction is verifiable in CI without an Azure organization or PAT:
```bash
python3 scripts/az_boards_adapter.py list_ready --state New,Active --area "Web\UI" --dry-run
```
