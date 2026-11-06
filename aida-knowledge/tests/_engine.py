"""Test loader for the AIDA engine (aida-knowledge/engine/aida_engine.py), imported by path."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent.parent / "engine" / "aida_engine.py"
_MOD = {}


def engine():
    """The engine module, imported once by file path."""
    if "m" not in _MOD:
        spec = importlib.util.spec_from_file_location("aida_engine", ENGINE_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["aida_engine"] = mod
        spec.loader.exec_module(mod)
        _MOD["m"] = mod
    return _MOD["m"]


def recipes():
    """{name: function} for every public callable defined in the engine (drop-in for load_recipes)."""
    mod = engine()
    return {n: f for n, f in vars(mod).items()
            if not n.startswith("_") and callable(f) and getattr(f, "__module__", None) == mod.__name__
            and getattr(f, "__code__", None) is not None}
