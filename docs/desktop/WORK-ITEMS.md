# Work Item projection

`work.item/v1` is the shared identity that connects a task to its Space/Team,
Room, Bot, session and approval. The Desktop renders progress from Runtime
state; it does not run a local queue or infer completion from a button click.

The Work Item card exposes only the action permitted by the Runtime action
descriptor. Preview and stale projections show the item and its reason code,
but keep Approve/Resume/Assume unavailable.
