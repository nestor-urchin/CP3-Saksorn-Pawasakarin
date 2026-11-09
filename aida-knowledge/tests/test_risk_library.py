"""Tests for AIDA C1 task 6: RISK_LIBRARY, match_concerns, assess_sufficiency, suggest_risks, plan."""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _engine import engine  # noqa: E402
import sample_common as sc  # noqa: E402

ROOT = HERE.parent
REGISTRY = ROOT / "knowledge" / "AIDA-14-configuration-registry.md"
ALL_IDS = ["R1", "R2", "R3", "R4", "G-R1", "G-R2", "G-R3", "G-R4", "C-R1", "C-R2", "C-R3", "L-R1", "L-R2", "L-R3", "L-R4", "L-R5", "L-R6",
           "A-R1", "A-R2", "A-R3", "A-R4"]
TABLES = {"C": ("payments", "contracts"), "A": ("payments",), "E": ("transactions", "accounts")}
_CACHE = {}


def cfg():
    return {**engine().load_registry(REGISTRY), "_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}}


def load(name):
    """(raw frames, roles, key, internal tables, profile) of sample C, A or E."""
    if name not in _CACHE:
        d = ROOT / "samples" / name
        if name == "E":
            frames = {"transactions": pd.read_csv(ROOT / "samples" / "transactions.csv"),
                      "accounts": pd.read_csv(ROOT / "samples" / "accounts.csv")}
            key = None
        else:
            frames = {t: pd.read_csv(d / f"{t}.csv") for t in TABLES[name]}
            key = json.loads((d / "answer_key.json").read_text(encoding="utf-8"))
        roles = json.loads((d / "variants" / "roles_en.json").read_text(encoding="utf-8"))
        e = engine()
        _CACHE[name] = (frames, roles, key, e.to_internal(frames, roles), e.profile_columns(frames))
    frames, roles, key, tables, profile = _CACHE[name]
    return ({k: v.copy() for k, v in frames.items()}, roles, key, {k: v.copy() for k, v in tables.items()}, profile)


def brief_concerns(name):
    return sc.load_brief(ROOT / "samples" / name / "brief.md")["concerns"]


class Library(unittest.TestCase):
    def test_library_covers_all_ids(self):
        lib = engine().RISK_LIBRARY
        self.assertEqual(sorted(lib), sorted(ALL_IDS))
        for rid, r in lib.items():
            for f in ("name_th", "description_th", "synonyms", "data_types", "checks", "min_roles", "min_data",
                      "request_if_missing"):
                self.assertIn(f, r, f"{rid}.{f}")
            self.assertTrue(r["synonyms"] and r["checks"] and r["min_roles"], rid)
            self.assertEqual(set(r["min_data"]), {"months", "rows"}, rid)
            for bad in ("บัญชีม้า", "ทุจริต"):
                self.assertNotIn(bad, r["name_th"] + r["description_th"])
        names = {"G-R1": "ยอดโดดเด่น", "G-R2": "ช่วงสิ้นงวด", "G-R3": "นอกเวลาทำการ", "G-R4": "ตัวเลขผิดธรรมชาติ",
                 "C-R1": "ผู้ชำระคนเดียวหลายสัญญา", "C-R3": "ชำระซ้ำ/คืนเงินผิดปกติ", "A-R1": "จ่ายซ้ำ",
                 "A-R2": "แบ่งรายการต่ำกว่าวงเงิน", "A-R3": "ผู้บันทึกและผู้อนุมัติเป็นคนเดียวกัน",
                 "A-R4": "ผู้ขายกระจุกตัว"}
        for rid, n in names.items():
            self.assertEqual(lib[rid]["name_th"], n)
        self.assertIn("ชำระใกล้วันครบกำหนดซ้ำ ๆ", lib["C-R2"]["name_th"])
        self.assertIn("ปิดบัญชีก่อนกำหนดจากผู้ชำระอื่น", lib["C-R1"]["description_th"])
        self.assertNotIn("C-R4", lib)

    def test_library_checks_exist_in_CHECKS(self):
        e = engine()
        for rid, r in e.RISK_LIBRARY.items():
            expected = {c for c, s in e.CHECKS.items() if s["risk"] == rid or rid in s["risk_alt"]}
            self.assertEqual(set(r["checks"]), expected, rid)
            for c in r["checks"]:
                self.assertIn(c, e.CHECKS)
            for role in r["min_roles"]:
                self.assertIn(role, e.ROLES)
            for role in r["request_if_missing"]:
                self.assertTrue(role in e.ROLES or role.startswith("_"), role)


class Concerns(unittest.TestCase):
    def ids(self, name):
        return [m["risk_id"] for m in engine().match_concerns(brief_concerns(name))]

    def test_match_concerns_synonyms_and_unmatched(self):
        e = engine()
        self.assertEqual(self.ids("C"), ["C-R1", "C-R2", "R1"])
        self.assertEqual(self.ids("A"), ["A-R1", "A-R2"])
        self.assertEqual(self.ids("E"), ["R1", "R2", "R3", "R4"])
        m = e.match_concerns(["Duplicate  PAYMENT of the same invoice", "จ่ายเงินซ้ำซ้อน", "split below limit",
                              "พนักงานลาออกบ่อย"])
        self.assertEqual([x["risk_id"] for x in m], ["A-R1", "A-R1", "A-R2", None])
        self.assertTrue(m[0]["matched_by"] and m[3]["matched_by"] is None)
        self.assertEqual(m[3]["mode"], "สำรวจ")
        self.assertEqual(m[3]["concern"], "พนักงานลาออกบ่อย")
        self.assertEqual(m[0]["mode"], "รับรอง")

    def test_ascii_synonyms_match_whole_words(self):
        m = engine().match_concerns(["an episode of sleep", "SoD conflict", "possible sod issue", "period-end spike"])
        self.assertEqual([x["risk_id"] for x in m], [None, "A-R3", "A-R3", "G-R2"])

    def test_match_never_drops_and_is_deterministic(self):
        e = engine()
        cs = ["x", "", "  ", "ผู้ขายกระจุกตัว", "unknown thing"] * 3
        a, b = e.match_concerns(cs), e.match_concerns(cs)
        self.assertEqual(a, b)
        self.assertEqual(len(a), len(cs))
        self.assertEqual([x["concern"] for x in a], cs)


class Sufficiency(unittest.TestCase):
    def assess(self, name, ids):
        _, roles, key, tables, profile = load(name)
        df = engine().assess_sufficiency(ids, roles, profile, cfg())
        return df.set_index("risk_id"), key

    def test_sufficiency_c_matches_key(self):
        df, key = self.assess("C", ["C-R1", "C-R2", "R1"])
        self.assertEqual(df["status"].to_dict(), key["intake"]["sufficiency"])
        for col in ("runnable_checks", "skipped_checks", "data_request"):
            self.assertIn(col, df.columns)
        self.assertEqual(df.loc["C-R1", "runnable_checks"], ["PAYER-MULTI"])
        self.assertEqual(df.loc["C-R2", "data_request"], [])
        self.assertEqual(df.loc["R1", "runnable_checks"], [])
        self.assertTrue(df.loc["R1", "skipped_checks"])

    def test_data_request_c_matches_key(self):
        df, key = self.assess("C", ["C-R1", "C-R2", "R1"])
        req = [t for lst in df["data_request"] for t in lst]
        self.assertEqual(req, key["intake"]["data_request"])
        self.assertIn("เงินฝาก", req[0])

    def test_sufficiency_a_matches_key(self):
        df, key = self.assess("A", ["A-R1", "A-R2"])
        self.assertEqual(df["status"].to_dict(), key["intake"]["sufficiency"])
        self.assertEqual([t for lst in df["data_request"] for t in lst], key["intake"]["data_request"])

    def test_sufficiency_e_ready_and_missing_roles(self):
        df, _ = self.assess("E", ["R1", "R2", "R3", "R4"])
        self.assertEqual(set(df["status"]), {"พร้อม"})
        _, roles, _, _, profile = load("A")
        df = engine().assess_sufficiency(["C-R1", "A-R3"], roles, profile, cfg()).set_index("risk_id")
        self.assertEqual(df.loc["C-R1", "status"], "ไม่พอ")
        self.assertTrue(df.loc["C-R1", "data_request"])
        self.assertIn("contract", " ".join(df.loc["C-R1", "skipped_checks"].values()))
        self.assertEqual(df.loc["A-R3", "status"], "พร้อม")

    def test_sufficiency_partial_on_poor_join(self):
        e = engine()
        frames, roles, _, _, _ = load("E")
        ok = e.assess_sufficiency(["R1"], roles, e.profile_columns(frames), cfg()).iloc[0]
        self.assertEqual(ok["status"], "พร้อม")
        acc = frames["accounts"].copy()
        n = len(acc)
        acc["acct_id"] = [f"Z{i:05d}" if i % 3 else a for i, a in enumerate(acc["acct_id"])]
        poor = e.profile_columns({"transactions": frames["transactions"], "accounts": acc})
        jm = poor[(poor.table == "transactions") & (poor.column == "from_acct")]["join_match"].iloc[0]
        rate = jm["normalized"] if jm else 0.0
        self.assertLess(rate, 90)
        r = e.assess_sufficiency(["R1"], roles, poor, cfg()).iloc[0]
        self.assertEqual(r["status"], "บางส่วน")
        self.assertIn(f"{rate:.1f}%", r["reason"])
        self.assertIn("opened_at", r["reason"])
        self.assertTrue(r["runnable_checks"])
        self.assertGreater(n, 0)

    def test_join_threshold_comes_from_cfg(self):
        e = engine()
        frames, roles, _, _, _ = load("E")
        acc = frames["accounts"].copy()
        acc["acct_id"] = [f"Z{i:05d}" if i % 10 == 0 else a for i, a in enumerate(acc["acct_id"])]  # ~90% match
        prof = e.profile_columns({"transactions": frames["transactions"], "accounts": acc})
        jm = prof[(prof.table == "transactions") & (prof.column == "from_acct")]["join_match"].iloc[0]
        rate = jm["normalized"]
        self.assertTrue(70 < rate < 99, rate)
        lenient = {**cfg(), "INTAKE.JOIN_MIN_PCT": (rate - 1) / 100}
        strict = {**cfg(), "INTAKE.JOIN_MIN_PCT": (rate + 1) / 100}
        self.assertEqual(e.assess_sufficiency(["R1"], roles, prof, lenient).iloc[0]["status"], "พร้อม")
        self.assertEqual(e.assess_sufficiency(["R1"], roles, prof, strict).iloc[0]["status"], "บางส่วน")
        self.assertIn("INTAKE.JOIN_MIN_PCT", cfg())

    def test_time_of_day_needed_for_offhours(self):
        e = engine()
        frames, roles, _, _, _ = load("E")
        tx = frames["transactions"].copy()
        tx["ts"] = pd.to_datetime(tx["ts"]).dt.strftime("%Y-%m-%d")
        prof = e.profile_columns({"transactions": tx, "accounts": frames["accounts"]})
        df = e.assess_sufficiency(["G-R3", "R1"], roles, prof, cfg()).set_index("risk_id")
        self.assertEqual(df.loc["G-R3", "status"], "ไม่พอ")
        self.assertIn("TEMP-OFFHOURS", df.loc["G-R3", "skipped_checks"])
        self.assertEqual(df.loc["R1", "status"], "บางส่วน")

    def test_min_data(self):
        e = engine()
        frames, roles, _, _, _ = load("A")
        small = {"payments": frames["payments"].head(5)}
        df = e.assess_sufficiency(["A-R1"], roles, e.profile_columns(small), cfg()).iloc[0]
        self.assertEqual(df["status"], "ไม่พอ")
        self.assertTrue(df["data_request"])


class Suggest(unittest.TestCase):
    def suggest(self, name, requested):
        _, roles, key, tables, _ = load(name)
        return engine().suggest_risks(requested, roles, tables, cfg()), key, tables

    def test_suggest_risks_a_matches_key(self):
        df, key, _ = self.suggest("A", ["A-R1", "A-R2"])
        self.assertEqual(sorted(df["risk_id"]), sorted(key["intake"]["suggested_risks"]))
        self.assertEqual(list(df.columns), ["risk_id", "name_th", "why_th", "preview"])
        self.assertTrue((df["preview"] > 0).all())

    def test_suggest_risks_c_matches_key(self):
        df, key, _ = self.suggest("C", ["C-R1", "C-R2", "R1"])
        self.assertEqual(sorted(df["risk_id"]), key["intake"]["suggested_risks"])

    def test_suggest_preview_comes_from_running_checks(self):
        e = engine()
        df, _, tables = self.suggest("A", [])
        self.assertTrue({"A-R1", "A-R3"} <= set(df["risk_id"]))
        row = df.set_index("risk_id").loc["A-R3"]
        ev = e.CHECKS["SOD-SAME-USER"]["func"](tables, cfg())
        self.assertEqual(row["preview"], ev[["entity_type", "entity_id"]].drop_duplicates().shape[0])
        self.assertIn(str(row["preview"]), row["why_th"])
        # sorted by preview desc then risk id; requested are excluded
        self.assertEqual(list(df["preview"]), sorted(df["preview"], reverse=True))
        self.assertNotIn("A-R1", self.suggest("A", ["A-R1"])[0]["risk_id"].tolist())

    def test_suggest_deterministic(self):
        a = self.suggest("A", ["A-R1"])[0]
        b = self.suggest("A", ["A-R1"])[0]
        pd.testing.assert_frame_equal(a, b)

    def test_g_r3_excluded_without_time_of_day(self):
        e = engine()
        _, roles, _, tables, _ = load("E")
        tx = tables["transactions"].copy()
        tx["ts"] = pd.to_datetime(tx["ts"]).dt.normalize()
        out = e.suggest_risks([], roles, {**tables, "transactions": tx}, cfg())
        self.assertNotIn("G-R3", list(out["risk_id"]))


class Plan(unittest.TestCase):
    def test_plan_carries_data_volume_skips(self):
        e = engine()
        frames, roles, _, tables, profile = load("E")
        p = e.plan(["R1", "R4"], roles, profile, cfg(), tables).set_index("check_id")
        self.assertEqual(p.loc["STAT-MAD", "decision"], "Run")
        # STAT-MAD: every group smaller than GATE.SAMPLE.MIN
        c = {**cfg(), "GATE.SAMPLE.MIN": 10 ** 6}
        p = e.plan(["R1"], roles, profile, c, tables).set_index("check_id")
        self.assertEqual(p.loc["STAT-MAD", "decision"], "Skip")
        self.assertIn("GATE.SAMPLE.MIN", p.loc["STAT-MAD", "reason"])
        # the same wording as gate_volume
        self.assertEqual(p.loc["STAT-MAD", "reason"], e.gate_volume(tables, c)["STAT-MAD"])
        # a one-month file has no baseline for BEH-SPIKE / CPTY-NEW-LARGE
        tx = tables["transactions"].copy()
        tx = tx[pd.to_datetime(tx["ts"]).dt.strftime("%Y-%m") == "2026-01"]
        p = e.plan(["R1", "R4"], roles, profile, cfg(), {**tables, "transactions": tx}).set_index("check_id")
        self.assertEqual(p.loc["BEH-SPIKE", "decision"], "Skip")
        self.assertEqual(p.loc["CPTY-NEW-LARGE", "decision"], "Skip")
        df = e.assess_sufficiency(["R1"], roles, profile, cfg(), {**tables, "transactions": tx}).iloc[0]
        self.assertEqual(df["status"], "บางส่วน")
        self.assertIn("BEH-SPIKE", df["skipped_checks"])
        # loan / AP data uses the same rules
        _, roles_a, _, tab_a, prof_a = load("A")
        p = e.plan(["G-R1"], roles_a, prof_a, {**cfg(), "GATE.SAMPLE.MIN": 10 ** 7}, tab_a).set_index("check_id")
        self.assertNotIn("STAT-MAD", p.index[p.decision == "Run"])

    def test_general_checks_run_on_c_and_a(self):
        e = engine()
        for n in "CA":
            _, roles, _, tab, prof = load(n)
            p = e.plan_checks(tab, cfg()).set_index("recipe_id")
            for cid in ("STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS"):
                self.assertEqual(p.loc[cid, "decision"], "Run", (n, cid))
            # date-only data: G-R3 needs a time of day
            self.assertEqual(e.assess_sufficiency(["G-R3"], roles, prof, cfg()).iloc[0]["status"], "ไม่พอ")
        self.assertEqual(engine().RISK_LIBRARY["G-R3"]["data_types"], ["E", "C", "A", "L", "F"])
        self.assertEqual(engine().RISK_LIBRARY["G-R1"]["data_types"], ["E", "C", "A", "L", "F"])
        for n in "CA":
            _, roles, _, tab, prof = load(n)
            r = e.assess_sufficiency(["G-R1"], roles, prof, cfg(), tab).iloc[0]
            self.assertEqual(r["status"], "พร้อม", (n, r["reason"]))

    def test_plan_run_skip_reasons(self):
        e = engine()
        _, roles, _, _, profile = load("C")
        p = e.plan(["C-R1", "C-R2", "R1"], roles, profile, cfg())
        self.assertEqual(list(p.columns), ["check_id", "decision", "reason", "missing"])
        d = p.set_index("check_id")
        self.assertEqual(d.loc["PAYER-MULTI", "decision"], "Run")
        self.assertEqual(d.loc["DUE-NEAR", "decision"], "Run")
        self.assertEqual(d.loc["STAT-MAD", "decision"], "Skip")
        self.assertTrue(p["check_id"].is_unique)
        _, roles_a, _, _, prof_a = load("A")
        p = e.plan(["C-R2"], roles_a, prof_a, cfg()).iloc[0]
        self.assertEqual(p["decision"], "Skip")
        self.assertIn("contract", p["missing"])
        self.assertIn("บทบาท", p["reason"])
        self.assertTrue(all(isinstance(x, str) and x for x in (p["reason"], p["missing"])))


if __name__ == "__main__":
    unittest.main()
