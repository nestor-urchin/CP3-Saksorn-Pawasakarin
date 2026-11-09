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

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "AIDA-14-configuration-registry.md"


# AIDA-14 v1.3 keys the L / F samples are designed against (FUND.ROUNDTRIP.AMOUNT_BAND is exposed as FUND.ROUNDTRIP.BAND)
LF_KEYS = ("LIFE.EARLY_SURR.MONTHS", "LIFE.BENCHG_CASH.WINDOW_DAYS", "LIFE.LOAN.NEAR_PCT", "LIFE.LOAN.MIN_COUNT",
           "LIFE.LOAN.COUNT_MONTHS", "LIFE.LOAN_SURR.WINDOW_DAYS", "LIFE.PAYEE.MIN_POLICIES", "LIFE.BENEF.MIN_POLICIES",
           "LIFE.BENCHG.MIN_COUNT", "LIFE.BENCHG.COUNT_MONTHS", "FUND.ROUNDTRIP.DAYS", "FUND.SHARED_ACCT.MIN_HOLDERS",
           "FUND.FREQ.MIN_TX_MONTH", "FUND.CHURN.MIN_CLIENT_SHARE", "FUND.CHURN.MIN_CLIENTS", "FUND.CUTOFF_TIME")


def _thresholds():
    """The thresholds the planted cases are designed against, read from the AIDA-14 Machine Config
    (through the engine's load_registry) so the samples and the registry cannot drift apart."""
    from _engine import engine
    cfg = engine().load_registry(REGISTRY_PATH)
    band, mad = cfg["FOR.THRESHOLD_AVOID.BAND"], cfg["FOR.BENFORD.MAD_1ST"]
    th = {k: cfg[k] for k in ("DUP.WINDOW_DAYS", "SPLIT.WINDOW_DAYS", "SPLIT.MIN_TX", "DUE.NEAR_DAYS",
                              "DUE.MIN_SHARE", "DUE.MIN_PERIODS", "PAYER.MIN_CONTRACTS", "FOR.BENFORD.MIN_N",
                              "FOR.ROUND.UNIT", "FOR.REPEAT.MIN_COUNT", "CONC.SINGLE_ENTITY_SHARE")}
    th.update({k: cfg[k] for k in LF_KEYS})
    rt = cfg["FUND.ROUNDTRIP.AMOUNT_BAND"]
    th.update({"FUND.ROUNDTRIP.BAND": (rt["low"], rt["high"])})
    th.update({"SPLIT.BAND": (band["low"], band["high"]),
               "FOR.BENFORD.MAD_OK": mad["acceptable"], "FOR.BENFORD.MAD_BAD": mad["marginal"]})
    return th


TH = _thresholds()


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


def write_dataset(out_dir, frames, key, brief_md, variant_names, roles_en, legacy_dataset_type=None):
    """Write frames as <table>.csv, answer_key.json, brief.md and the three naming variants.

    legacy_dataset_type (L / F samples): stored in roles_legacy.json as the top-level key "dataset_type", next to the
    {table: {column: role}} mapping, because cryptic legacy names cannot be recognised as L / F from the columns."""
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
        roles = variant_roles(roles_en, names)
        if v == "legacy" and legacy_dataset_type:
            roles = {**roles, "dataset_type": legacy_dataset_type}
        (vdir / f"roles_{v}.json").write_text(json.dumps(roles, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
