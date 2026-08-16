#!/usr/bin/env bash
# Optional authenticated npm-registry probe. It is a no-op unless the caller
# explicitly provides NPM_TOKEN; no token is committed to this repository.
set -euo pipefail

if [[ -z "${NPM_TOKEN:-}" ]]; then
  echo "NPM_TOKEN is not configured; skipping authenticated registry probe."
  exit 0
fi

curl --silent --show-error --fail --output /dev/null \
  --write-out "HTTP_CODE:%{http_code}\n" \
  -H "Authorization: Bearer ${NPM_TOKEN}" \
  https://registry.npmjs.org/-/whoami
