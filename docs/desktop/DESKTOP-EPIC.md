# Desktop Epic architecture

The public Desktop is a Tauri/React projection client with five primary
surfaces: Today, Chats, Teams, Automations and Apps. Settings is secondary.
The Runtime remains authority for Agent API, sessions, policies, approvals,
capabilities, Work Items, receipts, artifacts and Computer leases.

Every visible surface has a versioned projection and an explicit unavailable
reason when its backend contract is not verified. The Desktop never starts a
second agent loop, scheduler, session store or permission engine.

The implementation order is shell → projections → Runtime bindings → installed
E2E. This keeps layout and accessibility testable while the cross-repository
Runtime dependencies remain open.
