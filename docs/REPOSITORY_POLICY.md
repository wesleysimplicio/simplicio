# Public repository policy

The repository stores reproducible source, manifests, documentation, tests,
and release metadata. It does not store local Runtime state, generated maps,
dependency trees, build products, logs, databases, model weights, or compiled
executables.

`scripts/repository_policy.py` checks the tracked tree in CI and fails closed
for those classes, secret-like material, and personal absolute paths outside
documentation examples. The `.gitignore` mirrors the policy for local work;
the CI check remains authoritative because ignored files can still be forced
into Git.
