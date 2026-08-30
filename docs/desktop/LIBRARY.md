# Library artifact graph

`library.artifacts/v1` indexes artifact handles, versions and provenance from
the Runtime graph. It is a view over canonical artifacts, not a hidden local
copy or a second file store.

Recent, favorite, Space/Team, project and type views can be built on the same
projection. Opening or reusing an artifact navigates by handle and preserves
the originating session/Work Item lineage.
