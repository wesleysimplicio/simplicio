# Public repository policy

The repository stores reproducible source, manifests, documentation, tests, and release metadata. It does not store local Runtime state, generated maps, dependency trees, build products, logs, databases, model weights, or compiled executables.

scripts/repository_policy.py is the local policy check. Run it from the checkout before delivery; it fails closed for those classes, secret-like material, and personal absolute paths outside documentation examples. The .gitignore mirrors the policy for local work, but ignored files can still be forced into Git.

There is no checked-in GitHub Actions workflow for this repository. Local policy output, the exact command, exit code, and any pre-existing fixture-only findings are the authoritative evidence record.
