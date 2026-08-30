# Workspace resources

`workspace.resources/v1` represents projects, worktrees, files and profiles by
safe handles. The Desktop can render previews and permissions, but it never
accepts arbitrary filesystem paths or writes directly to disk.

Read/write operations must be action descriptors from the Runtime, scoped to a
project/worktree/profile and carrying the canonical revision.
