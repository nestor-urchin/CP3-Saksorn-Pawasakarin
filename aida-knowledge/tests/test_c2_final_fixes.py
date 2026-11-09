"""AIDA C2 final whole-branch review fixes (I1-I6, M1-M4).

I1 two L/F anchors decide the type, so one stray anchor column (policy_no as the contract, fund_code in AP) keeps the
C1 rules; I2 confirm re-derives a detected type from the confirmed roles; I3 FUND.CUTOFF_TIME / AMOUNT_BAND are
validated and a crashing card is never silent; I4 run_id covers code_values and dataset_type; I5 confirm validates
code_values; I6 L-R4 reads only payout rows when the codes are confirmed; M1 registry_key of no-threshold rules;
M2 a tampered dataset_type in intake.json; M4 LIFE-STAFF-CONC at exactly CONC.SINGLE_ENTITY_SHARE.
Every output goes to a temporary directory.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _engine import engine  # noqa: E402
import sample_common as sc  # noqa: E402

ROOT = HERE.parent
SAMPLES = ROOT / "samples"
C1_TABLES = {"C": ("payments", "contracts"), "A": ("payments",)}
LF_TABLES = {"L": ("policy_txn", "policies", "beneficiary_changes"), "F": ("fund_txn", "unitholders")}
_TMP = []
_CACHE = {}


def tmp():
    d = tempfile.mkdtemp(prefix="aida-c2fix-")
    _TMP.append(d)
    return Path(d)


def tearDownModule():
    for d in _TMP:
        shutil.rmtree(d, True)


def files(ds, folder=None):
    tables = C1_TABLES.get(ds) or LF_TABLES[ds]
    return {t: str(Path(folder or SAMPLES / ds) / f"{t}.csv") for t in tables}


def brief(ds):
    return sc.load_brief(SAMPLES / ds / "brief.md")


def key(ds):
    return json.loads((SAMPLES / ds / "answer_key.json").read_text(encoding="utf-8"))


def key_set(ds, risks=None):
    return {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key(ds)["findings"]
            if risks is None or f["risk"] in risks}


def finding_set(f):
    return set(zip(f["entity_type"], f["entity_id"], f["risk"], f["period"]))


def flow(fs, br, answers=None, d=None):
    """inspect -> confirm(answers) -> run in one temp dir: (inspect result, intake, run result)."""
    e = engine()
    d = d or tmp()
    ins = e.inspect(fs, br, draft_path=str(d / "intake_draft.json"))
    it = e.confirm(ins["intake"], answers or {}, str(d / "intake.json"))
    return ins, it, e.run(fs, it, str(d / "out"))


def copy_tables(ds, edit):
    """The sample tables of `ds` written to a temp dir after edit(table, df) -> df; returns (folder, files)."""
    d = tmp()
    for t, p in files(ds).items():
        edit(t, pd.read_csv(p, dtype=str, keep_default_na=False)).to_csv(d / f"{t}.csv", index=False)
    return d, files(ds, d)


def a_with(cols):
    """The A sample with extra columns {name: function(df) -> values}."""
    def edit(t, df):
        for c, f in cols.items():
            df[c] = f(df)
        return df
    return copy_tables("A", edit)[1]


class I1Anchors(unittest.TestCase):
    def test_c_with_policy_no_contract_stays_C(self):
        fs = copy_tables("C", lambda t, df: df.rename(columns={"contract_id": "policy_no"}))[1]
        br = brief("C")
        br["columns"]["policy_no"] = br["columns"].pop("contract_id")
        ins, it, r = flow(fs, br)
        self.assertEqual(ins["intake"]["dataset_type"], "C")
        self.assertEqual(it["dataset_type"], "C")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(finding_set(r["findings"]), key_set("C", set(key("C")["concern_risks"])))

    def test_a_with_extra_fund_code_stays_A(self):
        fs = a_with({"fund_code": lambda df: [f"F{i % 5:02d}" for i in range(len(df))]})
        br = brief("A")
        br["columns"]["fund_code"] = "รหัสแหล่งเงิน"
        ins, it, r = flow(fs, br)
        self.assertEqual(ins["intake"]["dataset_type"], "A")
        self.assertEqual(it["dataset_type"], "A")
        self.assertEqual(finding_set(r["findings"]), key_set("A", set(key("A")["concern_risks"])))

    def test_two_anchors_needed(self):
        e = engine()
        self.assertEqual(e.LF_MIN_ANCHORS, 2)
        one = {"o": pd.DataFrame({"order_id": ["O1", "O2"], "fund_code": ["F1", "F2"], "amount": ["1", "2"],
                                  "pay_date": ["2026-01-05", "2026-01-06"]})}
        self.assertIsNone(e._lf_type(e.profile_columns(one)))
        two = {"o": one["o"].assign(unitholder_id=["U1", "U2"])}
        self.assertEqual(e._lf_type(e.profile_columns(two)), "F")

    def test_lf_samples_still_detect(self):
        for ds in ("L", "F"):
            with self.subTest(dataset=ds):
                frames = {t: pd.read_csv(p, dtype=str) for t, p in files(ds).items()}
                self.assertEqual(engine().detect_dataset_type(engine().profile_columns(frames)), ds)

    def test_type_gate_reason_points_to_dataset_type(self):
        """C data asked about R1 (a transfer risk): the reason names dataset_type before asking for more data."""
        ins = engine().inspect(files("C"), brief("C"), draft_path=str(tmp() / "d.json"))
        rows = [p for p in ins["intake"]["plan"] if p["decision"] == "Skip" and p["missing"] == "ประเภทข้อมูล"]
        self.assertTrue(rows)
        for p in rows:
            self.assertIn("dataset_type", p["reason"])
            self.assertIn("ถ้าข้อมูลนี้เป็นประเภท", p["reason"])
        self.assertIn("dataset_type", ins["review_th"])
        # the C key's Data Request (transfer data for R1) is unchanged
        self.assertEqual(ins["intake"]["data_request"], key("C")["intake"]["data_request"])


class I2Rederive(unittest.TestCase):
    def _two_anchor_a(self):
        fs = a_with({"fund_code": lambda df: [f"F{i % 5:02d}" for i in range(len(df))],
                     "nav_date": lambda df: df["pay_date"]})
        br = brief("A")
        br["columns"]["fund_code"] = "รหัสแหล่งเงิน"
        return fs, br

    def test_detected_type_rederived_from_confirmed_roles(self):
        fs, br = self._two_anchor_a()
        ins, it, r = flow(fs, br, {"roles": {"fund_code": "ไม่ใช้", "nav_date": "ไม่ใช้"}})
        self.assertEqual(ins["intake"]["dataset_type"], "F")  # two anchors on role columns: detected as F
        self.assertEqual(ins["intake"]["dataset_type_source"], "detected")
        self.assertEqual(it["dataset_type"], "A")
        self.assertEqual(it["dataset_type_source"], "detected")
        self.assertEqual(finding_set(r["findings"]), key_set("A", set(key("A")["concern_risks"])))

    def test_confirmed_type_is_kept(self):
        fs, br = self._two_anchor_a()
        d = tmp()
        e = engine()
        ins = e.inspect(fs, br, draft_path=str(d / "d.json"))
        it = e.confirm(ins["intake"], {"roles": {"fund_code": "ไม่ใช้", "nav_date": "ไม่ใช้"}, "dataset_type": "F"},
                       str(d / "i.json"))
        self.assertEqual(it["dataset_type"], "F")
        self.assertEqual(it["dataset_type_source"], "confirmed")
        again = e.confirm(it, {}, str(d / "i2.json"))  # a confirmed type stays on a later confirm
        self.assertEqual(again["dataset_type"], "F")
        self.assertEqual(again["dataset_type_source"], "confirmed")

    def test_lf_samples_bare_confirm_detected(self):
        for ds in ("L", "F"):
            with self.subTest(dataset=ds):
                _, it, _ = flow(files(ds), brief(ds))
                self.assertEqual(it["dataset_type"], ds)
                self.assertEqual(it["dataset_type_source"], "detected")


class I3OrgValues(unittest.TestCase):
    def _ins(self):
        if "F" not in _CACHE:
            _CACHE["F"] = engine().inspect(files("F"), brief("F"), draft_path=str(tmp() / "d.json"))
        return _CACHE["F"]

    def test_confirm_rejects_bad_cutoff(self):
        e = engine()
        for v in ("25:00", "4pm", "15:60", "1530"):
            with self.subTest(value=v):
                with self.assertRaises(e.AidaError) as cm:
                    e.confirm(self._ins()["intake"], {"org_values": {"FUND.CUTOFF_TIME": v}}, str(tmp() / "i.json"))
                msg = str(cm.exception)
                self.assertIn("FUND.CUTOFF_TIME", msg)
                self.assertIn("HH:MM", msg)
                self.assertRegex(msg, "[ก-๙]")
        it = e.confirm(self._ins()["intake"], {"org_values": {"FUND.CUTOFF_TIME": "16:00"}}, str(tmp() / "i.json"))
        self.assertEqual(it["org_values"]["FUND.CUTOFF_TIME"], "16:00")

    def test_tampered_intake_cutoff_rejected_at_run(self):
        e = engine()
        d = tmp()
        it = e.confirm(self._ins()["intake"], {}, str(d / "intake.json"))
        it["org_values"] = {"FUND.CUTOFF_TIME": "25:00"}
        (d / "intake.json").write_text(json.dumps(it, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(e.AidaError) as cm:
            e.run(files("F"), str(d / "intake.json"), str(d / "out"))
        self.assertIn("FUND.CUTOFF_TIME", str(cm.exception))

    def test_amount_band_low_above_high_rejected(self):
        e = engine()
        with self.assertRaises(e.AidaError) as cm:
            e.confirm(self._ins()["intake"], {"org_values": {"FUND.ROUNDTRIP.AMOUNT_BAND": {"low": 1.3, "high": 0.9}}},
                      str(tmp() / "i.json"))
        self.assertIn("low", str(cm.exception))
        self.assertRegex(str(cm.exception), "[ก-๙]")
        it = e.confirm(self._ins()["intake"], {"org_values": {"FUND.ROUNDTRIP.AMOUNT_BAND": {"low": 0.9, "high": 0.9}}},
                       str(tmp() / "i.json"))
        self.assertEqual(it["org_values"]["FUND.ROUNDTRIP.AMOUNT_BAND"], {"low": 0.9, "high": 0.9})

    def test_card_crash_shows_in_warnings(self):
        e = engine()
        d = tmp()
        it = e.confirm(self._ins()["intake"], {}, str(d / "intake.json"))
        spec = e.CHECKS["FUND-LATE-TRADE"]
        orig = spec["func"]

        def boom(tables, cfg):
            raise ValueError("ทดสอบ")
        spec["func"] = boom
        try:
            r = e.run(files("F"), it, str(d / "out"))
        finally:
            spec["func"] = orig
        self.assertTrue(any("FUND-LATE-TRADE" in w and "รันไม่สำเร็จ" in w for w in r["warnings"]), r["warnings"])
        self.assertIn("FUND-LATE-TRADE", r["summary_th"])
        self.assertIn("รันไม่สำเร็จ", r["summary_th"])


class I4RunId(unittest.TestCase):
    def test_run_id_covers_dataset_type_and_code_values(self):
        e = engine()
        d = tmp()
        ins = e.inspect(files("L"), brief("L"), draft_path=str(d / "d.json"))
        ids = {}
        for name, ans in (("bare", {}), ("typeC", {"dataset_type": "C"}),
                          ("codes", {"code_values": {"policy_txn.txn_type": {"SURR": "เวนคืนกรมธรรม์"}}})):
            it = e.confirm(ins["intake"], ans, str(d / f"{name}.json"))
            ids[name] = e.run(files("L"), it, str(d / name))["run_id"]
        self.assertNotEqual(ids["bare"], ids["typeC"])
        self.assertNotEqual(ids["bare"], ids["codes"])
        it = e.confirm(ins["intake"], {}, str(d / "again.json"))
        self.assertEqual(e.run(files("L"), it, str(d / "again"))["run_id"], ids["bare"])  # still deterministic


class I5CodeValues(unittest.TestCase):
    def _ins(self):
        if "Lnocode" not in _CACHE:
            br = brief("L")
            br["columns"]["txn_type"] = "ประเภทรายการ"  # no code list: inspect proposes no code values
            _CACHE["Lnocode"] = engine().inspect(files("L"), br, draft_path=str(tmp() / "d.json"))
        return _CACHE["Lnocode"]

    def test_bare_column_key_resolves(self):
        e = engine()
        d = tmp()
        codes = key("L")["code_values"]["policy_txn.txn_type"]
        it = e.confirm(self._ins()["intake"], {"code_values": {"txn_type": codes}}, str(d / "i.json"))
        self.assertEqual(it["code_values"].get("policy_txn.txn_type"), codes)
        self.assertNotIn("txn_type", it["code_values"])
        r = e.run(files("L"), it, str(d / "out"))
        plan = r["plan"].set_index("recipe_id")
        for cid in ("LIFE-EARLY-SURR", "LIFE-BENCHG-CASH", "LIFE-LOAN"):
            self.assertEqual(plan.loc[cid, "decision"], "Run", cid)
        self.assertEqual(finding_set(r["findings"]), key_set("L", set(key("L")["concern_risks"])))

    def test_non_dict_rejected(self):
        e = engine()
        for bad in ({"txn_type": "SURR"}, ["SURR"], {"txn_type": {"SURR": ["เวนคืน"]}}):
            with self.subTest(value=bad):
                with self.assertRaises(e.AidaError) as cm:
                    e.confirm(self._ins()["intake"], {"code_values": bad}, str(tmp() / "i.json"))
                self.assertRegex(str(cm.exception), "[ก-๙]")
                self.assertIn("policy_txn.txn_type", str(cm.exception))

    def test_unknown_key_rejected(self):
        e = engine()
        with self.assertRaises(e.AidaError) as cm:
            e.confirm(self._ins()["intake"], {"code_values": {"no_such_col": {"SURR": "เวนคืน"}}}, str(tmp() / "i.json"))
        msg = str(cm.exception)
        self.assertIn("no_such_col", msg)
        self.assertIn("policy_txn.txn_type", msg)
        self.assertRegex(msg, "[ก-๙]")


class I6ThirdPayee(unittest.TestCase):
    def _fixture(self):
        def edit(t, df):
            if t != "policy_txn":
                return df
            base = df[df["txn_type"] == "LOAN"].drop_duplicates("insured_id").head(6)
            add = base.assign(txn_id=[f"T-R{i}" for i in range(len(base))], txn_type="RPY", payee="COMPANY-BANK",
                              txn_date="2026-10-20")
            return pd.concat([df, add], ignore_index=True)
        fs = copy_tables("L", edit)[1]
        br = brief("L")
        br["columns"]["txn_type"] += ", RPY = ชำระคืนเงินกู้"
        return fs, br

    def test_repayments_to_company_account_not_flagged(self):
        fs, br = self._fixture()
        ins, it, r = flow(fs, br, {"add_risks": key("L")["intake"]["suggested_risks"]})
        self.assertEqual(it["code_values"]["policy_txn.txn_type"].get("RPY"), "ชำระคืนเงินกู้")
        ev = r["evidence"]
        self.assertNotIn("COMPANY-BANK", set(ev["entity_id"].astype(str)))
        refs = {x for rr in ev["record_refs"] for x in rr}
        self.assertFalse({x for x in refs if x.startswith("T-R")})
        self.assertEqual(finding_set(r["findings"]), key_set("L"))

    def test_without_codes_runs_with_note(self):
        """No confirmed codes: L-R4 still reads every row (C2 behaviour) and says so in a card note."""
        e = engine()
        tables = e.to_internal({"t": pd.DataFrame({
            "id": ["T1", "T2"], "pol": ["P-1", "P-2"], "ins": ["I-1", "I-2"], "d": ["2026-01-05", "2026-01-06"],
            "amt": ["10", "20"], "payee": ["I-9", "I-2"]})},
            {"t": {"id": "record_id", "pol": "contract", "ins": "entity", "d": "date", "amt": "amount",
                   "payee": "counterparty"}})
        e.attach_meta(tables, {"dataset_type": "L"})
        cfg = {**e.load_registry(sc.REGISTRY_PATH), "_RUN": {"run_id": "T", "data_ref": "t"}}
        ev = e.CHECKS["LIFE-THIRD-PAYEE"]["func"](tables, cfg)
        self.assertEqual(list(ev["entity_id"]), ["P-1"])
        notes = " ".join(n["detail"] for n in tables["_out"]["notes"])
        self.assertIn("ยังไม่ได้ยืนยันความหมายรหัสประเภทรายการ", notes)


class M1RegistryKey(unittest.TestCase):
    def test_no_threshold_rules_cite_dash(self):
        e = engine()
        for ds, cid in (("L", "LIFE-THIRD-PAYEE"), ("F", "FUND-THIRD-PARTY")):
            with self.subTest(check=cid):
                _, _, r = flow(files(ds), brief(ds), {"add_risks": key(ds)["intake"]["suggested_risks"]})
                ev = r["evidence"][r["evidence"]["recipe_id"] == cid]
                self.assertGreater(len(ev), 0)
                if cid == "FUND-THIRD-PARTY":
                    self.assertEqual(set(ev["registry_key"]), {"-"})
                else:
                    a = ev[ev["metric"] == "payee_differs_count"]
                    b = ev[ev["metric"] == "insured_count"]
                    self.assertGreater(len(a), 0)
                    self.assertEqual(set(a["registry_key"]), {"-"})
                    self.assertTrue(set(b["registry_key"]) <= {"LIFE.PAYEE.MIN_POLICIES"})
        self.assertIsNotNone(e)


class M2IntakeType(unittest.TestCase):
    def test_tampered_dataset_type_rejected(self):
        e = engine()
        d = tmp()
        ins = e.inspect(files("L"), brief("L"), draft_path=str(d / "d.json"))
        it = e.confirm(ins["intake"], {}, str(d / "intake.json"))
        for bad in ("Z", ["L"], 5):
            with self.subTest(value=bad):
                it2 = {**it, "dataset_type": bad}
                p = d / "bad.json"
                p.write_text(json.dumps(it2, ensure_ascii=False), encoding="utf-8")
                with self.assertRaises(e.AidaError) as cm:
                    e.run(files("L"), str(p), str(d / "out"))
                self.assertIn("dataset_type", str(cm.exception))
                self.assertRegex(str(cm.exception), "[ก-๙]")
        it3 = {**it, "dataset_type": None}  # no type recorded: detected again from the roles
        p = d / "none.json"
        p.write_text(json.dumps(it3, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(e.run(files("L"), str(p), str(d / "out2"))["status"], "OK")


class M4StaffConcBoundary(unittest.TestCase):
    def _call(self, n_other, n_top):
        e = engine()
        rows = [(f"T{i}", f"P-{i}", f"I-{i}", "2026-01-10", "S", 100.0, f"I-{i}", 1000.0, f"S-{i}") for i in range(n_other)]
        rows += [(f"X{i}", f"P-X{i}", f"I-X{i}", "2026-02-10", "S", 100.0, f"I-X{i}", 1000.0, "S-TOP") for i in range(n_top)]
        cols = ["tx_id", "contract", "from_acct", "ts", "category", "amount", "to_acct", "limit", "created_by"]
        t = {"transactions": pd.DataFrame(rows, columns=cols),
             "meta": {"code_values": {"t.type": {"S": "เวนคืนกรมธรรม์"}}, "category_key": "t.type", "dtype": "L",
                      "tx_table": "t", "events_table": None}}
        cfg = {**e.load_registry(sc.REGISTRY_PATH), "_RUN": {"run_id": "T", "data_ref": "t"}}
        return e.CHECKS["LIFE-STAFF-CONC"]["func"](t, cfg), cfg

    def test_exactly_at_threshold_is_reported(self):
        ev, cfg = self._call(18, 2)  # S-TOP has 2 of 20 records = exactly CONC.SINGLE_ENTITY_SHARE (10%)
        self.assertEqual(cfg["CONC.SINGLE_ENTITY_SHARE"], 0.1)
        self.assertEqual(list(ev["entity_id"]), ["S-TOP"])
        self.assertEqual(ev["value"].iloc[0], 0.1)
        self.assertEqual(ev["threshold"].iloc[0], 0.1)

    def test_just_below_threshold_is_not_reported(self):
        ev, _ = self._call(19, 2)  # 2 of 21 records = 9.5%
        self.assertEqual(len(ev), 0)


if __name__ == "__main__":
    unittest.main()
