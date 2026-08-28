# Desktop release and updater contract

Desktop artifacts are published only through the closed-world release
workflow. A release is eligible when the signed manifest, SHA256 digests,
SBOM, provenance records, and component lock all match the immutable staged
bytes. The workflow refuses a remote release whose tag or asset digests have
drifted.

The updater follows a stage-before-swap transaction:

1. download into an isolated staging directory;
2. verify signature, checksum, provenance, and component membership;
3. retain the current sidecar as the single rollback candidate;
4. atomically switch the active sidecar;
5. start the sidecar and restore the previous candidate if startup fails.

The release acceptance suite must exercise both a successful fresh start and
a failed-start rollback. The Desktop UI never presents an update as complete
until the Runtime returns a healthy receipt.
