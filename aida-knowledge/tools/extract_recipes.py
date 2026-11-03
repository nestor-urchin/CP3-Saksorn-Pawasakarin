"""Extract and execute AIDA recipe cards (```python blocks) from Markdown."""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


class RecipeError(Exception):
    pass


@dataclass
class Recipe:
    id: str
    version: str
    skill: str
    risk: str
    registry_keys: list
    inputs: str
    code: str
    func_name: str


_H1 = re.compile(r"^#\s*RECIPE\s+(\S+)\s+v(\d+\.\d+)\s*\|\s*Skill:\s*(.*?)\s*\|\s*Risk:\s*(\S+)\s*$")
_H2 = re.compile(r"^#\s*Registry:\s*(.*?)\s*\|\s*Input:\s*(.*?)\s*$")
_FENCE_OPEN = re.compile(r"^```python\s*$")
_FENCE_CLOSE = re.compile(r"^```\s*$")


def _build(lines: list, where: str) -> Recipe:
    if len(lines) < 2:
        raise RecipeError(f"{where}: recipe block too short for a header")
    m1, m2 = _H1.match(lines[0]), _H2.match(lines[1])
    if not m1 or not m2:
        raise RecipeError(f"{where}: malformed recipe header")
    rid = m1.group(1)
    keys = [k.strip() for k in m2.group(1).split(",") if k.strip() not in ("", "-")]
    return Recipe(rid, m1.group(2), m1.group(3), m1.group(4), keys, m2.group(2),
                  "\n".join(lines), rid.lower().replace("-", "_"))


def parse_recipes(md_text: str) -> list:
    recipes, lines, i = [], md_text.splitlines(), 0
    while i < len(lines):
        if _FENCE_OPEN.match(lines[i]):
            start = i + 1
            j = start
            while j < len(lines) and not _FENCE_CLOSE.match(lines[j]):
                j += 1
            block = lines[start:j]
            if block and block[0].startswith("# RECIPE"):
                r = _build(block, f"line {start + 1}")
                if j >= len(lines):
                    raise RecipeError(f"{r.id}: code fence never closed (truncated block)")
                recipes.append(r)
            i = j + 1
        else:
            i += 1
    return recipes


def load_recipes(paths: list) -> dict:
    ns = {"pd": pd, "np": np, "json": json}
    funcs = {}
    for path in paths:
        for r in parse_recipes(Path(path).read_text(encoding="utf-8")):
            try:
                code = compile(r.code, f"<{r.id}>", "exec")
            except SyntaxError as e:
                raise RecipeError(f"{r.id}: does not compile ({e.msg}, line {e.lineno})") from e
            exec(code, ns)
            fn = ns.get(r.func_name)
            if not callable(fn):
                raise RecipeError(f"{r.id}: expected function {r.func_name} not defined")
            funcs[r.func_name] = fn
    return funcs
