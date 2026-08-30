# Capability Center

`capability.registry/v1` is the single discovery surface for Desktop Apps and
the `+ New` launcher. Each entry has a stable capability ID, human category,
approval requirement and probe reason code. The UI does not infer availability
from an installed icon or provider configuration.

The five categories are Create, Explore, Act, Build and Learn. A capability is
actionable only after a healthy Runtime probe; otherwise the card remains
disabled with the returned reason code. Executing a capability is a Runtime
action descriptor and produces the same Work Item, Live, Chat and artifact
receipts used elsewhere in the app.
