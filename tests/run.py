"""Dependency-free test runner: python3 tests/run.py [module ...]"""
import importlib
import sys
import traceback

sys.path.insert(0, ".")
mods = sys.argv[1:] or ["test_stage1"]
bad = 0
for m in mods:
    mod = importlib.import_module(f"tests.{m}")
    for n in sorted(dir(mod)):
        if n.startswith("test_"):
            try:
                getattr(mod, n)()
                print("PASS", m, n)
            except Exception:
                bad += 1
                print("FAIL", m, n)
                traceback.print_exc(limit=4)
sys.exit(1 if bad else 0)
