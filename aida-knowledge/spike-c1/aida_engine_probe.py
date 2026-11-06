"""AIDA phase C1 engine probe (Copilot spike, spec 7.1).

Standard library + pandas only. No network imports. Used only to check whether
Code Interpreter can load a module from the Knowledge folder; it is not the engine.
"""
import pandas as pd

__version__ = "probe-1"


def hello() -> str:
    return "AIDA engine probe OK"


def summarize(path: str) -> dict:
    df = pd.read_csv(path)
    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "sum": int(df["amount"].sum()),
    }
