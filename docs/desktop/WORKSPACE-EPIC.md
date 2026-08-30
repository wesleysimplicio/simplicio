# Workspace OS program

The Workspace OS is one Desktop experience spanning Spaces, Teams, Chats, Work
Items, Live, Apps and Library. Its primary navigation stays limited to Today,
Chats, Teams, Automations and Apps; Settings and technical inspectors are
contextual.

The repository now has versioned projection boundaries for workspace identity,
resources, sessions, Rooms, Work Items, Live, capabilities, search, artifacts,
reports and optional widgets. The Runtime remains the only authority for
membership, policy, effects, scheduling, sessions and durable state.

The remaining epic acceptance is integration/E2E against the Runtime contracts;
the Desktop standalone fixture deliberately renders unavailable states instead
of pretending those cross-repository effects exist.
