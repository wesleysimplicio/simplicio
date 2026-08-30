# Settings and onboarding projection

`settings.projection/v1` groups providers, models, tools and skills while
keeping authentication and secrets write-only. The Desktop can show state and
remediation, but never exposes secret bodies or exports raw credentials.

Selecting a provider/model/tool/skill is a Runtime action descriptor. Unknown
or stale registry entries are read-only until a fresh probe succeeds.
