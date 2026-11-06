"""Tests for the phase C1 Copilot spike kit (aida-knowledge/spike-c1/).

The probe is the file Code Interpreter must load from Knowledge (.py or .txt) in the
spike (spec 7.1). It must stay stdlib + pandas only, with no network imports, and the
.py and .txt copies must be byte-identical.
"""
import ast
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPIKE = HERE.parent / "spike-c1"
PY_PATH = SPIKE / "aida_engine_probe.py"
TXT_PATH = SPIKE / "aida_engine_probe.txt"
CSV_PATH = SPIKE / "probe-data.csv"
README_PATH = SPIKE / "README.md"

PROBE_ROWS = 50
PROBE_AMOUNT_SUM = 1090927

FORBIDDEN_IMPORTS = {
    "requests", "urllib", "http", "socket", "ssl", "ftplib", "smtplib",
    "telnetlib", "xmlrpc", "httpx", "aiohttp", "websocket", "websockets",
}


def _load_probe():
    sys.path.insert(0, str(SPIKE))
    try:
        import importlib
        import aida_engine_probe
        return importlib.reload(aida_engine_probe)
    finally:
        sys.path.remove(str(SPIKE))


class TestProbeKit(unittest.TestCase):

    def test_probe_identical_py_txt(self):
        self.assertTrue(PY_PATH.is_file(), f"missing {PY_PATH}")
        self.assertTrue(TXT_PATH.is_file(), f"missing {TXT_PATH}")
        self.assertEqual(PY_PATH.read_bytes(), TXT_PATH.read_bytes())

    def test_probe_hello(self):
        probe = _load_probe()
        self.assertEqual(probe.__version__, "probe-1")
        self.assertEqual(probe.hello(), "AIDA engine probe OK")

    def test_probe_summarize(self):
        probe = _load_probe()
        self.assertTrue(CSV_PATH.is_file(), f"missing {CSV_PATH}")
        result = probe.summarize(str(CSV_PATH))
        self.assertEqual(result["rows"], PROBE_ROWS)
        self.assertEqual(result["sum"], PROBE_AMOUNT_SUM)
        self.assertIn("amount", result["columns"])
        self.assertEqual(
            sorted(result["columns"]),
            sorted(["record_id", "date", "amount", "channel", "category", "entity"]),
        )

    def test_probe_no_network_imports(self):
        self.assertTrue(PY_PATH.is_file(), f"missing {PY_PATH}")
        tree = ast.parse(PY_PATH.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & FORBIDDEN_IMPORTS, f"network import found: {names}")
        allowed = set(sys.stdlib_module_names) | {"pandas"}
        self.assertTrue(names <= allowed, f"non-allowed import(s): {names - allowed}")


if __name__ == "__main__":
    unittest.main()
