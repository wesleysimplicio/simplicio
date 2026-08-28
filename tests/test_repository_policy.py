from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("repository_policy", ROOT / "scripts/repository_policy.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_policy_rejects_generated_binaries_secrets_and_personal_paths(tmp_path: Path) -> None:
    (tmp_path / ".simplicio/cache").mkdir(parents=True)
    (tmp_path / ".simplicio/cache/map.json").write_text("{}", encoding="utf-8")
    (tmp_path / "simplicio.exe").write_bytes(b"binary")
    (tmp_path / "config.txt").write_bytes(b"token=ghp_123456789012345678901234567890")
    (tmp_path / "source.py").write_bytes(b"path=/home/alice/private")
    paths = [
        tmp_path / ".simplicio/cache/map.json",
        tmp_path / "simplicio.exe",
        tmp_path / "config.txt",
        tmp_path / "source.py",
    ]

    findings = MODULE.path_findings(tmp_path, paths)

    assert len(findings) == 4


def test_policy_allows_documentation_path_examples(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    example = docs / "example.md"
    example.write_bytes(b"Install at /home/your-name/.simplicio/bin/simplicio")

    assert MODULE.path_findings(tmp_path, [example]) == []
