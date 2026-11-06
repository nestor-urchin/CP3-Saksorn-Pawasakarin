"""Shared helpers for the C and A sample generators (AIDA C1): output, column-naming variants, brief loading.

A dataset module defines TABLES (the en column names), VARIANT_NAMES ({variant: {table: {en col: name}}}),
ROLES_EN ({table: {en col: role}}), BRIEF_MD (Thai prose + one ```json block) and make(seed) -> (frames, key).
"""
import json
import re
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
VARIANTS = ("en", "th", "legacy")
JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.S)

# Thresholds the planted cases are designed against (AIDA-14 v1.2 / spec 4.7). Kept here, not read from the
# registry, because the Machine Config of the registry does not hold the FOR/CONC keys as numbers yet.
TH = {
    "DUP.WINDOW_DAYS": 3, "SPLIT.WINDOW_DAYS": 1, "SPLIT.MIN_TX": 2, "SPLIT.BAND": (0.90, 1.0),
    "DUE.NEAR_DAYS": 2, "DUE.MIN_SHARE": 0.8, "DUE.MIN_PERIODS": 3, "PAYER.MIN_CONTRACTS": 3,
    "FOR.BENFORD.MIN_N": 1000, "FOR.BENFORD.MAD_OK": 0.012, "FOR.BENFORD.MAD_BAD": 0.015,
    "FOR.ROUND.UNIT": 1000, "FOR.REPEAT.MIN_COUNT": 3, "CONC.SINGLE_ENTITY_SHARE": 0.10,
}


def load_brief(path) -> dict:
    """The machine-readable ```json block of a brief.md: {context, columns, conditions, concerns}."""
    text = Path(path).read_text(encoding="utf-8")
    m = JSON_BLOCK.search(text)
    if not m:
        raise ValueError(f"ไม่พบบล็อก ```json ใน {path}")
    return json.loads(m.group(1))


def rename_frames(frames, names):
    """frames {table: df} with columns renamed through names {table: {from: to}}."""
    return {t: df.rename(columns=names.get(t, {})) for t, df in frames.items()}


def variant_roles(roles_en, names):
    """{table: {column in the variant: role}} from the en roles and a variant's naming."""
    return {t: {names.get(t, {}).get(c, c): r for c, r in rmap.items()} for t, rmap in roles_en.items()}


def variant_brief(brief, names):
    """The brief with its column descriptions keyed by the variant's column names (same meaning)."""
    flat = {}
    for tmap in names.values():
        flat.update(tmap)
    return {**brief, "columns": {flat.get(c, c): m for c, m in brief["columns"].items()}}


def write_dataset(out_dir, frames, key, brief_md, variant_names, roles_en):
    """Write frames as <table>.csv, answer_key.json, brief.md and the three naming variants."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for t, df in frames.items():
        df.to_csv(out_dir / f"{t}.csv", index=False)
    (out_dir / "answer_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "brief.md").write_text(brief_md, encoding="utf-8")
    brief = load_brief(out_dir / "brief.md")
    vdir = out_dir / "variants"
    for v in VARIANTS:
        names = variant_names[v]
        (vdir / v).mkdir(parents=True, exist_ok=True)
        for t, df in rename_frames(frames, names).items():
            df.to_csv(vdir / v / f"{t}.csv", index=False)
        (vdir / v / "brief.json").write_text(json.dumps(variant_brief(brief, names), ensure_ascii=False, indent=2)
                                             + "\n", encoding="utf-8")
        (vdir / f"roles_{v}.json").write_text(json.dumps(variant_roles(roles_en, names), ensure_ascii=False,
                                                         indent=2) + "\n", encoding="utf-8")
