# DeepSeek Harness status

DeepSeek Harness remains deliberately fail-closed. The repository does not
have a verified canonical executable name, configuration location, or
official MCP/plugin contract for this host, so the compatibility matrix does
not probe guessed commands and the installer makes no changes.

When an upstream contract is available, add its exact probe, scope, and
verification command to `host_integrations.py`, then add a clean-profile
fixture and live Runtime evidence before enabling automatic registration. A
detected-looking binary must not be enough to opt into the integration.
