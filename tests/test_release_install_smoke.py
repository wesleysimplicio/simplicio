import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "release_install_smoke.py"


def load_module():
    spec = importlib.util.spec_from_file_location("release_install_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_wheel_install_is_offline_and_exact():
    module = load_module()
    wheel = Path("/artifacts/simplicio_installer-3.8.30-py3-none-any.whl")
    command = module.package_install_command(
        Path("/venv/bin/python"), "3.8.30", "https://pypi.org/simple", wheel
    )
    assert "--no-index" in command
    assert "--index-url" not in command
    assert str(wheel) == command[-1]


def test_pypi_install_is_version_pinned():
    module = load_module()
    command = module.package_install_command(
        Path("/venv/bin/python"), "3.8.30", "https://pypi.org/simple", None
    )
    assert command[-1] == "simplicio-installer==3.8.30"
    assert command[command.index("--index-url") + 1] == "https://pypi.org/simple"
