"""AIDA C1 task 9: the same data with en / th / legacy column names gives the same findings; name-based role
suggestion; 80k-row performance; Buddhist-Era and Thai-month dates. Every output goes to a temporary directory.

Role-suggestion tests: `test_suggest_roles_en_th_high_confidence` runs inspect WITHOUT the brief (name-based only),
and also WITH the variant's brief (variants/<v>/brief.json, whose keys are already that variant's column names).
"""
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _engine import engine  # noqa: E402
import sample_common as sc  # noqa: E402

ROOT = HERE.parent
SAMPLES = ROOT / "samples"
TABLES = {"C": ("payments", "contracts"), "A": ("payments",), "E": ("transactions", "accounts")}
VARIANTS = ("en", "th", "legacy")
_TMP = []


def tmp():
    d = tempfile.mkdtemp(prefix="aida-t9-")
    _TMP.append(d)
    return Path(d)


def tearDownModule():
    for d in _TMP:
        shutil.rmtree(d, True)


def vdir(ds, v):
    return SAMPLES / ds / "variants" / v


def vfiles(ds, v):
    return {t: str(vdir(ds, v) / f"{t}.csv") for t in TABLES[ds]}


def vroles(ds, v):
    return json.loads((SAMPLES / ds / "variants" / f"roles_{v}.json").read_text(encoding="utf-8"))


def vbrief(ds, v):
    return json.loads((vdir(ds, v) / "brief.json").read_text(encoding="utf-8"))


def key(ds):
    p = SAMPLES / "answer_key.json" if ds == "E" else SAMPLES / ds / "answer_key.json"
    return json.loads(p.read_text(encoding="utf-8"))


def key_set(ds):
    return {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key(ds)["findings"]}


def finding_set(f):
    return set(zip(f["entity_type"], f["entity_id"], f["risk"], f["period"]))


def answers(ds, v):
    """Same answers as test_orchestration.answers; only the column names (roles, filter column) follow the variant."""
    roles = vroles(ds, v)
    flt = []
    if ds == "C":
        col = next(c for c, r in roles["payments"].items() if r == "custom:status")
        flt = [{"column": col, "op": "!=", "value": "C"}]
    return {"roles": roles, "add_risks": [] if ds == "E" else key(ds)["intake"]["suggested_risks"],
            "filters": flt,
            "materiality": {"type": "ก", "amount": 1_000_000, "basis": "ทดสอบ"} if ds == "E" else {"type": "ไม่ระบุ"},
            "reviewer": "ผู้ตรวจสอบทดสอบ"}


def brief_for(ds, v):
    return sc.load_brief(SAMPLES / ds / "brief.md") if v == "en" else vbrief(ds, v)


def run_variant(ds, v, files=None, out=None):
    e = engine()
    files = files or vfiles(ds, v)
    out = out or tmp()
    ins = e.inspect(files, brief_for(ds, v))
    conf = e.confirm(ins["intake"], answers(ds, v), str(out / "intake.json"))
    return e.run(files, conf, str(out / "out"))


class Variants(unittest.TestCase):
    def test_variants_same_findings(self):
        for ds in ("C", "A", "E"):
            for v in VARIANTS:
                with self.subTest(dataset=ds, variant=v):
                    r = run_variant(ds, v)
                    self.assertEqual(finding_set(r["findings"]), key_set(ds))

    def test_suggest_roles_en_th_high_confidence(self):
        e = engine()
        for ds in ("C", "A", "E"):
            for v in ("en", "th"):
                for with_brief in (False, True):
                    with self.subTest(dataset=ds, variant=v, brief=with_brief):
                        ins = e.inspect(vfiles(ds, v), vbrief(ds, v) if with_brief else None)
                        sug = ins["intake"]["role_suggestions"] if "role_suggestions" in ins["intake"] else None
                        self.assertIsNotNone(sug, list(ins["intake"]))
                        level = {(s["table"], s["column"]): s["level"] for s in sug}
                        mapped = [(t, c) for t, m in vroles(ds, v).items() for c in m]
                        high = [k for k in mapped if level.get(k) == "สูง"]
                        self.assertGreaterEqual(len(high) / len(mapped), 0.8, (len(high), len(mapped),
                                                [k for k in mapped if k not in high]))

    def test_legacy_requires_confirmation(self):
        e = engine()
        for ds in ("C", "A", "E"):
            with self.subTest(dataset=ds):
                ins = e.inspect(vfiles(ds, "legacy"))
                level = {(s["table"], s["column"]): s for s in ins["intake"]["role_suggestions"]}
                cryptic = [(t, c) for t, m in vroles(ds, "legacy").items() for c in m
                           if c.startswith(("COL", "F0", "USR_", "AMT_", "LMT", "STS", "ACC_", "OPN_", "TRN_"))
                           and c not in ("ACC_FR", "ACC_TO", "TRN_NO", "TRN_DT", "ACC_ID", "OPN_DT", "AMT_X1")]
                self.assertTrue(cryptic, ds)
                for k in cryptic:
                    s = level[k]
                    self.assertTrue(s["role"] == "ไม่ทราบ" or s["level"] == "ต่ำ", (k, s))
                # at least one cryptic column per dataset needs the auditor (not all would be auto-accepted)
                self.assertTrue(any(s["role"] == "ไม่ทราบ" or s["level"] != "สูง" for s in level.values()))


def tile_e(n_tiles, d):
    """samples/E tiled n_tiles times with unique ids and account ids (so about n_tiles x 5,159 rows)."""
    tx = pd.read_csv(SAMPLES / "transactions.csv", dtype=str)
    ac = pd.read_csv(SAMPLES / "accounts.csv", dtype=str)
    txs, acs = [], []
    for i in range(n_tiles):
        t, a = tx.copy(), ac.copy()
        sfx = f"-{i}" if i else ""
        t["tx_id"] += sfx
        t["from_acct"] += sfx
        t["to_acct"] += sfx
        a["acct_id"] += sfx
        txs.append(t)
        acs.append(a)
    p = {"transactions": str(d / "transactions.csv"), "accounts": str(d / "accounts.csv")}
    pd.concat(txs).to_csv(p["transactions"], index=False)
    pd.concat(acs).to_csv(p["accounts"], index=False)
    return p


class Perf(unittest.TestCase):
    def test_perf_80k_e_inspect_run(self):
        e = engine()
        d = tmp()
        files = tile_e(16, d)  # 16 x 5,159 = 82,544 rows
        n = len(pd.read_csv(files["transactions"], usecols=["tx_id"]))
        self.assertGreaterEqual(n, 80_000)
        brief = sc.load_brief(SAMPLES / "E" / "brief.md")
        t0 = time.perf_counter()
        ins = e.inspect(files, brief)
        t_inspect = time.perf_counter() - t0
        conf = e.confirm(ins["intake"], answers("E", "en"), str(d / "intake.json"))
        t0 = time.perf_counter()
        r = e.run(files, conf, str(d / "out"))
        t_run = time.perf_counter() - t0
        print(f"\n[perf] rows={n:,} inspect={t_inspect:.1f}s run={t_run:.1f}s findings={len(r['findings'])}")
        self.assertLessEqual(t_inspect, 30)
        self.assertLessEqual(t_run, 90)


def to_be_thai(ts: str, style: str) -> str:
    """'2026-03-07 09:18:00' -> BE dd/mm/yyyy or Thai-month text with BE year (time kept)."""
    ts = ts.strip()
    d, _, t = ts.partition(" ")
    y, m, dd = d.split("-")
    months = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    by = int(y) + 543
    head = f"{int(dd)} {months[int(m) - 1]} {by}" if style == "thai" else f"{dd}/{m}/{by}"
    return f"{head} {t}".strip()


class ThaiDates(unittest.TestCase):
    def test_thai_dates_be_variants_still_match(self):
        for style in ("be", "thai"):
            with self.subTest(dataset="E", style=style):
                d = tmp()
                tx = pd.read_csv(SAMPLES / "transactions.csv", dtype=str)
                tx["ts"] = tx["ts"].map(lambda x: to_be_thai(x, style))
                ac = pd.read_csv(SAMPLES / "accounts.csv", dtype=str)
                ac["opened_at"] = ac["opened_at"].map(lambda x: to_be_thai(x, style))
                files = {"transactions": str(d / "transactions.csv"), "accounts": str(d / "accounts.csv")}
                tx.to_csv(files["transactions"], index=False)
                ac.to_csv(files["accounts"], index=False)
                r = run_variant("E", "en", files=files, out=d)
                self.assertEqual(finding_set(r["findings"]), key_set("E"))
            with self.subTest(dataset="C", style=style):
                d = tmp()
                files = {}
                for t, cols in (("payments", ["pay_date", "due_date"]), ("contracts", ["opened_at"])):
                    df = pd.read_csv(SAMPLES / "C" / f"{t}.csv", dtype=str)
                    for c in cols:
                        if c in df:
                            df[c] = df[c].map(lambda x: to_be_thai(x, style) if isinstance(x, str) else x)
                    files[t] = str(d / f"{t}.csv")
                    df.to_csv(files[t], index=False)
                r = run_variant("C", "en", files=files, out=d)
                self.assertEqual(finding_set(r["findings"]), key_set("C"))


if __name__ == "__main__":
    unittest.main()
