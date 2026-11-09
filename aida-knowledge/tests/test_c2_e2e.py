"""AIDA C2 task 5: the end-to-end gate for data types L (life insurance) and F (funds).

Intake and sufficiency, the realistic path (brief -> inspect -> "ยืนยัน" -> run), naming variants, regression and
performance. Every output (intake_draft.json, intake.json, Workbook, Dashboard, explore_log.json) goes to a temporary
directory; inspect is always given draft_path.

What each realistic-path test passes to confirm (only what an auditor would type):
* test_realistic_path_L / _F: confirm(draft, {}) (a bare "ยืนยัน") must give the key Findings of the concerns the letter
  asked about (key "concern_risks"); confirm(draft, {"add_risks": <the D suggestions>}) gives the whole key.
* test_confirm_with_code_values_only: the brief without the code list of txn_type, so inspect proposes no code values;
  confirm(draft, {"code_values": <key code_values>}) then gives the key Findings of the concerns.
"""
import json
import re
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
TABLES = {"L": ("policy_txn", "policies", "beneficiary_changes"), "F": ("fund_txn", "unitholders")}
TX = {"L": "policy_txn", "F": "fund_txn"}
VARIANTS = ("en", "th", "legacy")
ICON = {"พร้อม": "✅", "บางส่วน": "🟡", "ไม่พอ": "❌"}
ACCUSE = ("บัญชีม้า", "ทุจริต")
_TMP = []
_CACHE = {}


def tmp():
    d = tempfile.mkdtemp(prefix="aida-c2e2e-")
    _TMP.append(d)
    return Path(d)


def tearDownModule():
    for d in _TMP:
        shutil.rmtree(d, True)


def files(ds, v=None, tables=None):
    d = SAMPLES / ds if v is None else SAMPLES / ds / "variants" / v
    return {t: str(d / f"{t}.csv") for t in (tables or TABLES[ds])}


def brief(ds, v=None):
    if v is None:
        return sc.load_brief(SAMPLES / ds / "brief.md")
    return json.loads((SAMPLES / ds / "variants" / v / "brief.json").read_text(encoding="utf-8"))


def roles_of(ds, v):
    """(roles {table: {column: role}}, extra answers): legacy carries a top-level dataset_type, popped before use."""
    data = json.loads((SAMPLES / ds / "variants" / f"roles_{v}.json").read_text(encoding="utf-8"))
    extra = {"dataset_type": data.pop("dataset_type")} if "dataset_type" in data else {}
    return data, extra


def key(ds):
    return json.loads((SAMPLES / ds / "answer_key.json").read_text(encoding="utf-8"))


def key_set(ds, risks=None):
    return {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key(ds)["findings"]
            if risks is None or f["risk"] in risks}


def finding_set(f):
    return set(zip(f["entity_type"], f["entity_id"], f["risk"], f["period"]))


def section(text, letter):
    m = re.search(rf"^{letter}\. .*?(?=^[A-E]\. |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


def inspect_(fs, br, d=None):
    d = d or tmp()
    return engine().inspect(fs, br, draft_path=str(d / "intake_draft.json")), d


def realistic(ds, answers, fs=None, br=None):
    """inspect(files, brief) -> confirm(draft, answers) -> run, all in one temp dir."""
    e = engine()
    fs = fs or files(ds)
    ins, d = inspect_(fs, br if br is not None else brief(ds))
    it = e.confirm(ins["intake"], answers, str(d / "intake.json"))
    return e.run(fs, it, str(d / "out")), it, ins


def inspected(ds):
    if ("i", ds) not in _CACHE:
        _CACHE[("i", ds)] = inspect_(files(ds), brief(ds))[0]
    return _CACHE[("i", ds)]


class RealisticPath(unittest.TestCase):
    def _check(self, ds):
        k = key(ds)
        r, it, _ = realistic(ds, {})
        self.assertEqual(r["status"], "OK")
        self.assertEqual(it["dataset_type"], ds)
        self.assertEqual(finding_set(r["findings"]), key_set(ds, set(k["concern_risks"])))
        r2, _, _ = realistic(ds, {"add_risks": k["intake"]["suggested_risks"]})
        self.assertEqual(finding_set(r2["findings"]), key_set(ds))

    def test_realistic_path_L(self):
        self._check("L")

    def test_realistic_path_F(self):
        self._check("F")

    def test_confirm_with_code_values_only(self):
        e = engine()
        for ds in ("L", "F"):
            with self.subTest(dataset=ds):
                k = key(ds)
                br = brief(ds)
                br["columns"]["txn_type"] = "ประเภทรายการ"  # no code list: inspect proposes no code values
                ins, d = inspect_(files(ds), br)
                self.assertNotIn(f"{TX[ds]}.txn_type", ins["intake"]["code_values"])
                a = section(ins["review_th"], "A")
                self.assertTrue(any(ln.startswith("❓") and "txn_type" in ln and "ค่ารหัส" in ln for ln in a.splitlines()), a)
                # a bare "ยืนยัน" now Skips the checks that need the codes, with a Thai reason
                bare = e.run(files(ds), e.confirm(ins["intake"], {}, str(d / "bare.json")), str(d / "bare"))
                skip = bare["plan"][bare["plan"]["decision"] == "Skip"]
                self.assertTrue(skip["reason"].str.contains("ยังไม่ได้ยืนยันความหมายรหัสประเภทรายการ").any())
                it = e.confirm(ins["intake"], {"code_values": k["code_values"]}, str(d / "intake.json"))
                r = e.run(files(ds), it, str(d / "out"))
                self.assertEqual(finding_set(r["findings"]), key_set(ds, set(k["concern_risks"])))


class Intake(unittest.TestCase):
    def _check(self, ds, ins, want):
        it = ins["intake"]
        self.assertEqual({s["risk_id"]: s["status"] for s in it["sufficiency"]}, want["sufficiency"])
        self.assertEqual(it["data_request"], want["data_request"])
        b = section(ins["review_th"], "B")
        for rid, st in want["sufficiency"].items():
            self.assertTrue(any(rid in ln and ICON[st] in ln for ln in b.splitlines()), (rid, b))
        for r in want["data_request"]:
            self.assertIn(r, b)
        if not want["data_request"]:
            self.assertIn("Data Request: ไม่มี", b)
        for w in ACCUSE:
            self.assertNotIn(w, ins["review_th"])
        return it

    def _check_full(self, ds):
        k = key(ds)
        ins = inspected(ds)
        it = self._check(ds, ins, k["intake"])
        self.assertEqual(sorted(s["risk_id"] for s in it["suggested_risks"]), k["intake"]["suggested_risks"])
        self.assertEqual([c["column"] for c in it["description_conflicts"]], k["intake"]["description_conflicts"])
        self.assertEqual(it["risks"]["requested"], k["concern_risks"])
        self.assertEqual(it["dataset_type"], ds)
        for t, m in roles_of(ds, "en")[0].items():  # the brief's descriptions map every column to its role
            self.assertEqual(it["roles"][t], m, t)
        cat = f"{TX[ds]}.txn_type"  # the transaction-type column; premium_mode words are described, not coded
        self.assertEqual({cat: it["code_values"][cat]}, k["code_values"])

    def test_intake_L_matches_key(self):
        self._check_full("L")

    def test_intake_F_matches_key(self):
        self._check_full("F")

    def test_event_table_absent_gives_request(self):
        e = engine()
        br = brief("L")
        br["concerns"] = br["concerns"] + ["ผู้รับผลประโยชน์รายเดียวหลายกรมธรรม์"]
        ins, d = inspect_(files("L", tables=("policy_txn", "policies")), br)
        it = ins["intake"]
        suff = {s["risk_id"]: s for s in it["sufficiency"]}
        req = e.REQ_BENEF_HISTORY
        for rid in ("L-R2", "L-R5"):
            self.assertNotEqual(suff[rid]["status"], "พร้อม", suff[rid])
            self.assertIn(req, suff[rid]["data_request"])
        self.assertEqual(suff["L-R1"]["status"], "พร้อม")
        self.assertIn(req, it["data_request"])
        b = section(ins["review_th"], "B")
        self.assertIn(req, b)
        self.assertFalse(any("L-R2" in ln and "✅" in ln for ln in b.splitlines()), b)
        r = e.run(files("L", tables=("policy_txn", "policies")), e.confirm(it, {}, str(d / "intake.json")), str(d / "out"))
        plan = r["plan"].set_index("recipe_id")
        self.assertEqual(plan.loc["LIFE-BENEF-MULTI", "decision"], "Skip")
        self.assertEqual(plan.loc["LIFE-BENCHG-CASH", "decision"], "Skip")

    def test_event_table_poor_join_partial(self):
        d = tmp()
        ev = pd.read_csv(SAMPLES / "L" / "beneficiary_changes.csv", dtype=str, keep_default_na=False)
        half = ev.index[: len(ev) // 2]
        ev.loc[half, "policy_no"] = ["Q-" + str(9000 + i) for i in range(len(half))]  # not in policy_txn
        fs = files("L")
        fs["beneficiary_changes"] = str(d / "beneficiary_changes.csv")
        ev.to_csv(fs["beneficiary_changes"], index=False)
        ins, _ = inspect_(fs, brief("L"), d)
        suff = {s["risk_id"]: s for s in ins["intake"]["sufficiency"]}
        tx_ids = set(pd.read_csv(SAMPLES / "L" / "policy_txn.csv", dtype=str)["policy_no"])
        ev_ids = set(ev["policy_no"])  # share of the event table's policy numbers found in the transactions
        rate = f"{100.0 * len(ev_ids & tx_ids) / len(ev_ids):.1f}%"
        self.assertLess(len(ev_ids & tx_ids) / len(ev_ids), 0.9)
        self.assertEqual(suff["L-R2"]["status"], "บางส่วน", suff["L-R2"])
        self.assertIn(rate, suff["L-R2"]["reason"])
        self.assertEqual(suff["L-R1"]["status"], "พร้อม")
        b = section(ins["review_th"], "B")
        self.assertTrue(any("L-R2" in ln and "🟡" in ln and rate in ln for ln in b.splitlines()), b)

    def test_date_only_variant_f_r6_partial(self):
        e = engine()
        k = key("F")
        want = {"sufficiency": {**k["intake"]["sufficiency"], **k["conventions"]["date_only"]["sufficiency"]},
                "data_request": k["conventions"]["date_only"]["data_request"]}
        fs = files("F", "date_only")
        ins, d = inspect_(fs, brief("F", "date_only"))
        it = self._check("F", ins, want)
        self.assertEqual(it["roles"], roles_of("F", "date_only")[0])
        conf = e.confirm(it, {}, str(d / "intake.json"))  # a bare "ยืนยัน" works: no duplicate role
        r = e.run(fs, conf, str(d / "out"))
        plan = r["plan"].set_index("recipe_id")
        self.assertEqual(plan.loc["FUND-LATE-TRADE", "decision"], "Skip")
        self.assertIn("เวลา", plan.loc["FUND-LATE-TRADE", "reason"])
        self.assertEqual(finding_set(r["findings"]), key_set("F", {"F-R1", "F-R2"}))


class Variants(unittest.TestCase):
    def test_variants_same_findings_L_F(self):
        e = engine()
        for ds in ("L", "F"):
            for v in VARIANTS:
                with self.subTest(dataset=ds, variant=v):
                    roles, extra = roles_of(ds, v)
                    fs = files(ds, v)
                    ins, d = inspect_(fs, brief(ds, v))
                    ans = {"roles": roles, "add_risks": key(ds)["intake"]["suggested_risks"], **extra}
                    it = e.confirm(ins["intake"], ans, str(d / "intake.json"))
                    self.assertEqual(it["dataset_type"], ds)
                    r = e.run(fs, it, str(d / "out"))
                    self.assertEqual(finding_set(r["findings"]), key_set(ds))

    def test_suggest_roles_en_th_high_confidence_L_F(self):
        for ds in ("L", "F"):
            for v in ("en", "th"):
                for with_brief in (False, True):
                    with self.subTest(dataset=ds, variant=v, brief=with_brief):
                        ins, _ = inspect_(files(ds, v), brief(ds, v) if with_brief else None)
                        sug = {(s["table"], s["column"]): s for s in ins["intake"]["role_suggestions"]}
                        roles = roles_of(ds, v)[0]
                        mapped = [(t, c) for t, m in roles.items() for c in m]
                        high = [x for x in mapped if sug[x]["level"] == "สูง" and sug[x]["role"] == roles[x[0]][x[1]]]
                        self.assertGreaterEqual(len(high) / len(mapped), 0.8,
                                                [(x, sug[x]["role"], sug[x]["level"]) for x in mapped if x not in high])


class Regression(unittest.TestCase):
    def test_every_runnable_check_flags_only_key_ids_L_F(self):
        e = engine()
        for ds in ("L", "F"):
            with self.subTest(dataset=ds):
                k = key(ds)
                r, it, _ = realistic(ds, {"add_risks": sorted(set(e.RISK_LIBRARY) - set(k["concern_risks"]))})
                ran = set(r["plan"].loc[r["plan"]["decision"] == "Run", "recipe_id"])
                planted = {c for c, ids in k["recipes"].items() if ids}
                self.assertTrue(planted <= ran, sorted(planted - ran))
                self.assertGreaterEqual(len(ran & set(k["recipes"])), len(planted) + 5)  # general cards run too
                ev = r["evidence"]
                for cid in ran:
                    got = set(ev.loc[ev["recipe_id"] == cid, "entity_id"].astype(str))
                    self.assertTrue(got <= set(k["recipes"].get(cid, [])), (cid, sorted(got)))
                    if k["recipes"].get(cid):
                        self.assertEqual(got, set(k["recipes"][cid]), cid)
                self.assertEqual(finding_set(r["findings"]), key_set(ds))

    def test_e_c_a_regression(self):
        import test_orchestration as to
        e = engine()
        for ds in ("E", "C", "A"):
            with self.subTest(dataset=ds):
                d = tmp()
                ins = e.inspect(to.files(ds), to.brief(ds), draft_path=str(d / "intake_draft.json"))
                it = e.confirm(ins["intake"], to.answers(ds), str(d / "intake.json"))
                r = e.run(to.files(ds), it, str(d / "out"))
                self.assertEqual(to.finding_set(r["findings"]), to.key_set(ds))
                if ds != "E":
                    k = to.key(ds)["intake"]
                    self.assertEqual({s["risk_id"]: s["status"] for s in ins["intake"]["sufficiency"]}, k["sufficiency"])
                    self.assertEqual(sorted(s["risk_id"] for s in ins["intake"]["suggested_risks"]),
                                     sorted(k["suggested_risks"]))
                    self.assertEqual(ins["intake"]["data_request"], k["data_request"])


def tile(ds, n_rows, d):
    """samples/<ds> tiled with unique ids until the transactions table has at least n_rows rows."""
    frames = {t: pd.read_csv(p, dtype=str, keep_default_na=False) for t, p in files(ds).items()}
    n = -(-n_rows // len(frames[TX[ds]]))
    ids = {"L": {"policy_txn": ["txn_id", "policy_no", "insured_id", "payee"], "policies": ["policy_no", "insured_id"],
                 "beneficiary_changes": ["change_id", "policy_no", "beneficiary"]},
           "F": {"fund_txn": ["order_id", "unitholder_id", "bank_account"], "unitholders": ["unitholder_id"]}}[ds]
    out = {}
    for t, df in frames.items():
        parts = []
        for i in range(n):
            p = df.copy()
            if i:
                for c in ids[t]:
                    p[c] = p[c] + f"-{i}"
            parts.append(p)
        out[t] = str(d / f"{t}.csv")
        pd.concat(parts).to_csv(out[t], index=False)
    return out


class Perf(unittest.TestCase):
    def test_perf_80k_L_and_F(self):
        e = engine()
        for ds in ("L", "F"):
            with self.subTest(dataset=ds):
                d = tmp()
                fs = tile(ds, 80_000, d)
                n = len(pd.read_csv(fs[TX[ds]], usecols=[0]))
                self.assertGreaterEqual(n, 80_000)
                t0 = time.perf_counter()
                ins = e.inspect(fs, brief(ds), draft_path=str(d / "intake_draft.json"))
                t_inspect = time.perf_counter() - t0
                it = e.confirm(ins["intake"], {"add_risks": key(ds)["intake"]["suggested_risks"]}, str(d / "intake.json"))
                t0 = time.perf_counter()
                r = e.run(fs, it, str(d / "out"))
                t_run = time.perf_counter() - t0
                print(f"\n[perf {ds}] rows={n:,} inspect={t_inspect:.1f}s run={t_run:.1f}s findings={len(r['findings'])}")
                self.assertEqual(r["status"], "OK")
                self.assertLessEqual(t_inspect, 30)
                self.assertLessEqual(t_run, 90)


class Explore(unittest.TestCase):
    def test_explore_promote_on_L(self):
        e = engine()
        d = tmp()
        ins, _ = inspect_(files("L"), brief("L"), d)
        it = e.confirm(ins["intake"], {}, str(d / "intake.json"))
        ip = str(d / "intake.json")
        dd = e.data(files("L"), ip)
        self.assertIn("events", dd)
        eid = e.explore_log("กรมธรรม์ใดมีการเคลมเร็วหลังทำกรมธรรม์", "d['transactions'].head()", "P-0101 1 รายการ", intake=ip)
        e.promote(eid, "P-0101", "RX", "2026-06", "ควรทบทวนการเคลมหลังออกกรมธรรม์", "ผู้ทบทวนทดสอบ", "สูง", intake=ip)
        r = e.run(files("L"), ip, str(d / "out"))
        f = r["findings"]
        row = f[f["source"] == "exploratory"].iloc[0]
        self.assertEqual(row["source_label"], e.EXPLORE_LABEL)
        self.assertIn(row["confidence"], ("กลาง", "ต่ำ"))
        self.assertEqual(row["entity_id"], "P-0101")
        self.assertEqual(finding_set(f[f["source"] == "card"]), key_set("L", set(key("L")["concern_risks"])))


if __name__ == "__main__":
    unittest.main()
