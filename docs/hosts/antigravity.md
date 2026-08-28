# Google Antigravity status

Antigravity is represented in the compatibility matrix but remains
unsupported until its canonical executable and official extension/MCP
contract are verified. The installer intentionally does not guess a binary
name or configuration file and therefore cannot mutate a user's setup based
on a coincidental executable.

Enabling this row requires upstream documentation, an exact probe, an
atomic/idempotent fixture, and live Runtime handshake evidence. Until then,
the UI should surface the reason as unsupported rather than as an install
failure.
