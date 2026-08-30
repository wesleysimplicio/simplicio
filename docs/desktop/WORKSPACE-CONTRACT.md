# Workspace projection

`workspace/v1` binds Spaces, Teams, Rooms and shared-memory scopes without
duplicating Session Service or Bot membership in the Desktop. A Team and its
Room keep stable IDs so Chat, Work Items, Live and Library can link to the
same object.

The preview can render structure for layout review, but membership, invites,
reassignments and shared-memory writes remain disabled until the Runtime
publishes a verified Workspace projection.
