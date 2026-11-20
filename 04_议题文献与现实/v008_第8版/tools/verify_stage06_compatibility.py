"""Run unchanged current06 tests with the current04 synthetic fixture.

The historical06 tests hardcode the old04 fixture, which omits mandatory new05
research-link fields. Only redirect that fixture import; keep every06 assertion.
"""
from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import ROOT, registry_module

def main():
    old = ROOT / "04_议题文献与现实/v004_第4版/tests/test_workflow.py"
    current = registry_module("04") / "tests/test_workflow.py"
    original = importlib.util.spec_from_file_location
    def versioned(name, location, *args, **kwargs):
        location = current if Path(location).resolve() == old.resolve() else location
        return original(name, location, *args, **kwargs)
    with patch.object(importlib.util, "spec_from_file_location", side_effect=versioned):
        suite = unittest.defaultTestLoader.discover(str(registry_module("06") / "tests"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__": raise SystemExit(main())
