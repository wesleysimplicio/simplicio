# Multi-chat workspace

`chat.workspace/v1` is a bounded session index. It links each chat to the
canonical `session_id`, Bot ID and Runtime revision, so switching or reopening
a chat never creates a local duplicate session.

New, resume, rename and branch are Runtime operations. The preview renders the
index and keeps those controls disabled until Session Service authority is
verified.
