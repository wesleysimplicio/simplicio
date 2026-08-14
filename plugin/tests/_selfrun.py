"""Zero-dependency test runner — lets the test files run under plain `python3`.

The suite is written as ordinary pytest tests (functions named `test_*`, plain `assert`). When
pytest is installed it discovers and runs them normally. When it is NOT (the project's only hard
requirement is python3), each test module's `__main__` block calls `run_module(globals())` here,
which executes every `test_*` callable and reports PASS/FAIL with a non-zero exit on failure.

This keeps the headline claim honest: the tests run on a bare python3, no pip needed.
"""
import inspect
import pathlib
import sys
import tempfile
import traceback


def run_module(ns, name=None):
    """Run every test_* function in namespace `ns`. Exit non-zero on any failure.

    The only pytest fixture the fallback supplies is `tmp_path` (a fresh temp dir per test);
    tests here use no other fixtures.
    """
    name = name or ns.get("__name__", "tests")
    tests = sorted((k, v) for k, v in ns.items()
                   if k.startswith("test_") and callable(v))
    passed = failed = 0
    for tname, fn in tests:
        wants_tmp = "tmp_path" in inspect.signature(fn).parameters
        try:
            if wants_tmp:
                with tempfile.TemporaryDirectory() as d:
                    fn(pathlib.Path(d))
            else:
                fn()
            print("  [ok] %s" % tname)
            passed += 1
        except AssertionError as e:
            print("  [XX] %s — %s" % (tname, e))
            failed += 1
        except Exception as e:  # noqa
            print("  [ER] %s — %s" % (tname, e))
            traceback.print_exc()
            failed += 1
    print("%s: %s (%d passed, %d failed)" % (name, "PASS" if not failed else "FAIL",
                                             passed, failed))
    sys.exit(1 if failed else 0)
