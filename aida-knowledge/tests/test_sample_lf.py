"""Tests for the L (life insurance) and F (fund transactions) sample data, briefs and answer keys (AIDA C2 task 2).

test_planted_cases_grounded recomputes every planted case from the CSV frames with plain pandas, without the
engine and without reading the answer key; the key is then compared with what the data shows. Thresholds are the
AIDA-14 v1.3 values (sample_common.TH).
"""
import json
import re
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_sample_f as msf  # noqa: E402
import make_sample_l as msl  # noqa: E402
import sample_common as sc  # noqa: E402
from _engine import engine  # noqa: E402

TH = sc.TH
SAMPLES = sc.SAMPLES
_CACHE = {}
GENERAL = ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "GEN-CONC", "GEN-PERIOD-END", "FOR-BENFORD",
           "FOR-ROUND", "FOR-REPEAT"]


def built(mod):
    if mod.__name__ not in _CACHE:
        _CACHE[mod.__name__] = mod.make()
    return _CACHE[mod.__name__]


def month(s):
    return pd.to_datetime(s).dt.strftime("%Y-%m")


def roles_of(path):
    """(roles {table: {column: role}}, answers {"dataset_type": ...} or {}) from a roles_<variant>.json."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    answers = {"dataset_type": data["dataset_type"]} if "dataset_type" in data else {}
    return {t: m for t, m in data.items() if t != "dataset_type"}, answers


class Shared:
    mod = None
    name = None
    main = None
    CHECKS = []
    DTYPE = None

    def test_deterministic(self):
        f1, k1 = self.mod.make()
        f2, k2 = self.mod.make()
        for t in f1:
            pd.testing.assert_frame_equal(f1[t], f2[t])
        self.assertEqual(k1, k2)

    def test_seed_changes_only_normal_data(self):
        f1, k1 = self.mod.make()
        f2, k2 = self.mod.make(seed=7)
        self.assertEqual(k1, k2)
        self.assertFalse(f1[self.main].equals(f2[self.main]))

    def test_committed_files_match_generator(self):
        frames, key = built(self.mod)
        d = SAMPLES / self.name
        for t, df in frames.items():
            on_disk = pd.read_csv(d / f"{t}.csv", dtype=str, keep_default_na=False)
            pd.testing.assert_frame_equal(on_disk, df.astype(str).reset_index(drop=True), check_dtype=False)
        self.assertEqual(json.loads((d / "answer_key.json").read_text(encoding="utf-8")),
                         json.loads(json.dumps(key, ensure_ascii=False)))

    def test_key_shape(self):
        _, key = built(self.mod)
        for f in key["findings"]:
            self.assertEqual(set(f), {"entity_type", "entity_id", "risk", "period"})
            self.assertIn(f["entity_type"], self.ENTITY_TYPES)
        self.assertTrue(set(key["recipes"]) <= set(self.CHECKS) | set(GENERAL))
        for c in self.CHECKS:
            self.assertTrue(key["recipes"][c], c)  # every certified check has a planted entity
        for c in GENERAL:
            self.assertEqual(key["recipes"][c], [], c)  # the general cards find nothing
        intake = key["intake"]
        self.assertEqual(set(intake), {"sufficiency", "data_request", "suggested_risks", "description_conflicts"})
        self.assertTrue(set(intake["sufficiency"].values()) <= {"พร้อม", "บางส่วน", "ไม่พอ"})
        self.assertFalse(set(intake["suggested_risks"]) & set(intake["sufficiency"]))
        self.assertTrue(key["conventions"] and key["code_values"])
        self.assertEqual({f["risk"] for f in key["findings"]}, set(self.RISKS))

    def test_variants_same_content(self):
        frames, _ = built(self.mod)
        d = SAMPLES / self.name / "variants"
        e = engine()
        for v in sc.VARIANTS:
            roles, answers = roles_of(d / f"roles_{v}.json")
            names = self.mod.VARIANT_NAMES[v]
            disk = {}
            for t, df in frames.items():
                disk[t] = pd.read_csv(d / v / f"{t}.csv", dtype=str, keep_default_na=False)
                inv = {n: c for c, n in names.get(t, {}).items()}
                pd.testing.assert_frame_equal(disk[t].rename(columns=inv), df.astype(str).reset_index(drop=True),
                                              check_dtype=False)
                if v != "en":
                    self.assertTrue(set(names[t].values()).isdisjoint(set(self.mod.VARIANT_NAMES["en"][t].values())))
            internal = e.to_internal(disk, roles)
            self.assertTrue({"tx_id", "ts", "amount"} <= set(internal["transactions"].columns))
            self.assertEqual(len(internal["transactions"]), len(frames[self.main]))
            self.assertEqual(set(internal), set(self.INTERNAL))
            self.assertEqual(answers, {"dataset_type": self.DTYPE} if v == "legacy" else {})

    def test_en_variant_matches_presets(self):
        preset = engine().PRESETS[self.name]
        for rmap in self.mod.ROLES_EN.values():
            for col, role in rmap.items():
                self.assertEqual(preset.get(col), role, col)

    def test_brief_json_block_parses(self):
        brief = sc.load_brief(SAMPLES / self.name / "brief.md")
        self.assertEqual(set(brief), {"context", "columns", "conditions", "concerns"})
        self.assertTrue(brief["context"] and brief["concerns"])
        self.assertEqual(len(brief["concerns"]), self.N_CONCERNS)
        text = (SAMPLES / self.name / "brief.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"[฀-๿]{20,}")
        for t, cols in self.mod.TABLES.items():
            for c in cols:
                self.assertIn(c, brief["columns"])
        for v in sc.VARIANTS:
            vb = json.loads((SAMPLES / self.name / "variants" / v / "brief.json").read_text(encoding="utf-8"))
            self.assertEqual(len(vb["columns"]), len(brief["columns"]))
        e = engine()
        frames, key = built(self.mod)
        conflicts = e.check_descriptions(e.profile_columns(frames), brief["columns"])
        self.assertEqual(sorted({c["column"] for c in conflicts}), key["intake"]["description_conflicts"])

    def test_code_values_cover_all_codes(self):
        frames, key = built(self.mod)
        e = engine()
        self.assertEqual(set(key["code_values"]), {f"{self.main}.txn_type"})
        cv = key["code_values"][f"{self.main}.txn_type"]
        self.assertEqual(set(frames[self.main]["txn_type"]), set(cv))
        for code, text in cv.items():
            self.assertRegex(text, r"[฀-๿]{4,}")
            self.assertEqual(e.resolve_code_meaning(text), self.MEANINGS[code], f"{code}: {text}")
        # with these confirmed meanings, code_set finds the raw codes of every internal meaning
        roles, _ = roles_of(SAMPLES / self.name / "variants" / "roles_en.json")
        tables = e.to_internal(frames, roles)
        e.attach_meta(tables, {"roles": roles, "code_values": key["code_values"], "dataset_type": self.DTYPE})
        for code, meaning in self.MEANINGS.items():
            self.assertEqual(e.code_set(tables, meaning), {code})
        self.assertIsNone(e.require_codes(tables, sorted(set(self.MEANINGS.values()))))

    def test_general_cards_quiet_on_the_sample(self):
        """The nine general cards (and the certified-check-free general rules) report nothing on the whole sample."""
        frames, key = built(self.mod)
        e = engine()
        roles, _ = roles_of(SAMPLES / self.name / "variants" / "roles_en.json")
        cfg = {**e.load_registry(sc.REGISTRY_PATH), "_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}}
        tables = e._prep_internal(e.to_internal(frames, roles), cfg)
        for cid in GENERAL:
            ev = e.CHECKS[cid]["func"]({k: (v.copy() if hasattr(v, "copy") else v) for k, v in tables.items()}, cfg)
            self.assertEqual(len(ev), 0, f"{cid}: {ev['entity_id'].tolist() if len(ev) else ''}")


class TestL(Shared, unittest.TestCase):
    mod, name, main = msl, "L", "policy_txn"
    DTYPE = "L"
    INTERNAL = ("transactions", "accounts", "events")
    N_CONCERNS = 4
    ENTITY_TYPES = {"policy", "payee", "beneficiary", "staff", "insured"}
    RISKS = ["L-R1", "L-R2", "L-R3", "L-R4", "L-R5", "L-R6"]
    CHECKS = ["LIFE-EARLY-SURR", "LIFE-BENCHG-CASH", "LIFE-LOAN", "LIFE-THIRD-PAYEE", "LIFE-BENEF-MULTI",
              "LIFE-STAFF-CONC"]
    MEANINGS = {"SURR": "surrender", "LOAN": "loan", "CLM": "claim"}

    def frames(self):
        f = built(msl)[0]
        tx = f["policy_txn"].copy()
        tx["d"], tx["amt"], tx["cv"] = pd.to_datetime(tx["txn_date"]), tx["amount"].astype(float), tx["cash_value"].astype(float)
        pol = f["policies"].copy()
        pol["issue"] = pd.to_datetime(pol["issue_date"])
        ch = f["beneficiary_changes"].copy()
        ch["d"] = pd.to_datetime(ch["change_date"])
        return tx, pol, ch

    def test_planted_cases_grounded(self):
        _, key = built(msl)
        tx, pol, ch = self.frames()
        tx = tx.merge(pol[["policy_no", "issue"]], on="policy_no")
        surr, loan, clm = (tx[tx["txn_type"] == c] for c in ("SURR", "LOAN", "CLM"))
        # L-R1: surrender within EARLY_SURR.MONTHS of the issue date
        cutoff = surr["issue"] + surr["issue"].map(lambda _: pd.DateOffset(months=TH["LIFE.EARLY_SURR.MONTHS"]))
        early = surr[surr["d"] <= cutoff]
        self.assertEqual(early["policy_no"].tolist(), ["P-0101"])
        self.assertEqual(pol.set_index("policy_no").loc["P-0101", "premium_mode"], "single")
        months = (early["d"].iloc[0].year - early["issue"].iloc[0].year) * 12 + early["d"].iloc[0].month - early["issue"].iloc[0].month
        self.assertEqual(months, 4)
        rest = surr.drop(early.index)
        self.assertGreater((rest["d"] - rest["issue"]).min().days, 400)  # others: 13+ months
        # L-R2: beneficiary change followed by surrender / loan / claim on the policy within BENCHG_CASH.WINDOW_DAYS
        money = tx[tx["txn_type"].isin(["SURR", "LOAN", "CLM"])]
        j = ch.merge(money, on="policy_no", suffixes=("_c", ""))
        j["gap"] = (j["d"] - j["d_c"]).dt.days
        hit = j[(j["gap"] >= 0) & (j["gap"] <= TH["LIFE.BENCHG_CASH.WINDOW_DAYS"])]
        self.assertEqual(hit["policy_no"].tolist(), ["P-0202"])
        self.assertEqual(hit["gap"].tolist(), [10])
        self.assertEqual(hit["txn_type"].tolist(), ["SURR"])
        later = j[j["gap"] > TH["LIFE.BENCHG_CASH.WINDOW_DAYS"]]["gap"]
        self.assertGreaterEqual(later.min(), 45)  # normal: money follows a change by 45+ days
        # L-R3: (a) loan >= NEAR_PCT of cash value; (b) >= MIN_COUNT loans within COUNT_MONTHS; (c) loan then surrender
        ratio = loan["amt"] / loan["cv"]
        self.assertEqual(loan[ratio >= TH["LIFE.LOAN.NEAR_PCT"]]["policy_no"].tolist(), ["P-0303"])
        self.assertAlmostEqual(ratio[loan["policy_no"] == "P-0303"].iloc[0], 0.95, places=4)
        self.assertLess(ratio.drop(loan.index[loan["policy_no"] == "P-0303"]).max(), 0.75)
        per_pol = loan.groupby("policy_no").size()
        self.assertLessEqual(per_pol.max(), TH["LIFE.LOAN.MIN_COUNT"] - 1)  # nobody reaches 3 loans (b is not planted)
        self.assertGreater((per_pol == 2).sum(), 5)  # but several policies have 2: a clear near-miss
        ls = loan.merge(surr, on="policy_no", suffixes=("_l", "_s"))
        ls = ls[(ls["d_s"] - ls["d_l"]).dt.days.between(0, TH["LIFE.LOAN_SURR.WINDOW_DAYS"])]
        self.assertEqual(ls["policy_no"].tolist(), ["P-0304"])
        self.assertEqual((ls["d_s"] - ls["d_l"]).dt.days.tolist(), [42])
        # L-R4: (a) payee differs from the insured, comparable id format; (b) one payee from >= PAYEE.MIN_POLICIES policies
        other = money[money["payee"] != money["insured_id"]]
        by_payee = other.groupby("payee")["insured_id"].nunique()
        self.assertEqual(by_payee[by_payee >= TH["LIFE.PAYEE.MIN_POLICIES"]].index.tolist(), ["ACC-9001"])
        self.assertEqual(by_payee["ACC-9001"], 4)
        self.assertEqual(other[other["payee"] == "ACC-9001"]["txn_type"].unique().tolist(), ["SURR"])
        self.assertEqual(sorted(other[other["payee"] == "ACC-9001"]["policy_no"]), ["P-0401", "P-0402", "P-0403", "P-0404"])
        same_fmt = other[other["payee"].str.match(r"^I-\d+$")]
        self.assertEqual(same_fmt["policy_no"].tolist(), ["P-0505"])
        self.assertEqual(same_fmt["insured_id"].tolist(), ["I-0505"])
        self.assertEqual(same_fmt["payee"].tolist(), ["I-0999"])
        self.assertEqual(set(other["payee"]), {"ACC-9001", "I-0999"})  # every other payee is the insured
        self.assertFalse(tx["insured_id"].eq("I-0999").any())
        # L-R5: one beneficiary on >= BENEF.MIN_POLICIES policies of different insured; changes per policy / beneficiary
        cj = ch.merge(pol[["policy_no", "insured_id"]], on="policy_no")
        n_ins = cj.groupby("beneficiary")["insured_id"].nunique()
        self.assertEqual(n_ins[n_ins >= TH["LIFE.BENEF.MIN_POLICIES"]].index.tolist(), ["B-777"])
        self.assertEqual(n_ins["B-777"], 3)
        self.assertEqual(sorted(cj[cj["beneficiary"] == "B-777"]["policy_no"]), ["P-0601", "P-0602", "P-0603"])
        self.assertLess(ch.groupby("policy_no").size().max(), TH["LIFE.BENCHG.MIN_COUNT"])  # no policy changed twice
        self.assertTrue((n_ins.drop("B-777") == 1).all())
        # L-R6: a staff member's share of surrender + beneficiary-change records
        recs = pd.concat([surr[["staff_id"]], ch[["staff_id"]]])
        share = recs["staff_id"].value_counts(normalize=True)
        self.assertEqual(share[share >= sc.TH["CONC.SINGLE_ENTITY_SHARE"]].index.tolist(), ["S-07"])
        self.assertAlmostEqual(share["S-07"], 0.40, places=3)
        self.assertLess(share.drop("S-07").max(), 0.05)
        # every transaction policy is in the master and every change policy has transactions (the join is complete)
        self.assertTrue(set(tx["policy_no"]) <= set(pol["policy_no"]))
        self.assertTrue(set(ch["policy_no"]) <= set(tx["policy_no"]))
        self.assertTrue((tx.merge(pol, on="policy_no")["insured_id_x"] == tx.merge(pol, on="policy_no")["insured_id_y"]).all())
        # normal data: business-day style dates inside the month, steady monthly counts, amounts in one band
        normal = tx[~tx["policy_no"].isin(["P-0101", "P-0202", "P-0303", "P-0304", "P-0401", "P-0402", "P-0403",
                                           "P-0404", "P-0505", "P-0601", "P-0602", "P-0603"])]
        self.assertTrue(normal["d"].dt.day.between(5, 24).all())
        per_month = month(normal["txn_date"]).value_counts()
        self.assertEqual(len(per_month), 10)
        self.assertLess(per_month.max() / per_month.min(), 1.6)
        self.assertTrue(tx["amt"].between(1000, 39999.99).all())
        self.assertEqual((tx["amt"] % TH["FOR.ROUND.UNIT"] == 0).sum(), 0)
        self.assertTrue(tx["d"].min() >= pd.Timestamp("2026-01-01") and tx["d"].max() <= pd.Timestamp("2026-10-31"))
        self.assertTrue(ch["d"].min() >= pd.Timestamp("2026-01-01"))
        # the key says the same
        r = key["recipes"]
        self.assertEqual(r["LIFE-EARLY-SURR"], ["P-0101"])
        self.assertEqual(r["LIFE-BENCHG-CASH"], ["P-0202"])
        self.assertEqual(r["LIFE-LOAN"], ["P-0303", "P-0304"])
        self.assertEqual(r["LIFE-THIRD-PAYEE"], ["ACC-9001", "P-0505"])
        self.assertEqual(r["LIFE-BENEF-MULTI"], ["B-777"])
        self.assertEqual(r["LIFE-STAFF-CONC"], ["S-07"])
        got = {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key["findings"]}
        last_staff = max(month(surr[surr["staff_id"] == "S-07"]["txn_date"]).max(),
                         month(ch[ch["staff_id"] == "S-07"]["change_date"]).max())
        self.assertEqual(got, {("policy", "P-0101", "L-R1", "2026-06"), ("policy", "P-0202", "L-R2", "2026-07"),
                               ("policy", "P-0303", "L-R3", "2026-08"), ("policy", "P-0304", "L-R3", "2026-05"),
                               ("payee", "ACC-9001", "L-R4", "2026-09"), ("policy", "P-0505", "L-R4", "2026-05"),
                               ("beneficiary", "B-777", "L-R5", "2026-06"), ("staff", "S-07", "L-R6", last_staff)})
        self.assertEqual(last_staff, "2026-10")

    def test_intake_key(self):
        _, key = built(msl)
        it = key["intake"]
        self.assertEqual(it["sufficiency"], {"L-R1": "พร้อม", "L-R2": "พร้อม", "L-R4": "พร้อม"})
        self.assertEqual(len(it["data_request"]), 1)
        self.assertIn("เคลม", it["data_request"][0])
        self.assertEqual(it["suggested_risks"], ["L-R3", "L-R5", "L-R6"])
        self.assertEqual(it["description_conflicts"], [])
        brief = sc.load_brief(SAMPLES / "L" / "brief.md")
        self.assertTrue(any("เคลม" in c for c in brief["concerns"]))  # the concern the data cannot answer

    def test_brief_conditions_hold(self):
        brief = sc.load_brief(SAMPLES / "L" / "brief.md")
        self.assertTrue(any("2026" in c for c in brief["conditions"]))


class TestF(Shared, unittest.TestCase):
    mod, name, main = msf, "F", "fund_txn"
    DTYPE = "F"
    INTERNAL = ("transactions", "accounts")
    N_CONCERNS = 3
    ENTITY_TYPES = {"unitholder", "fund", "account", "agent"}
    RISKS = ["F-R1", "F-R2", "F-R3", "F-R4", "F-R5", "F-R6"]
    CHECKS = ["FUND-ROUNDTRIP", "FUND-THIRD-PARTY", "FUND-SHARED-ACCT", "FUND-FREQUENT", "FUND-CHURN",
              "FUND-LATE-TRADE"]
    MEANINGS = {"BUY": "buy", "SELL": "sell", "SWI": "switch_in", "SWO": "switch_out"}

    def tx(self):
        t = built(msf)[0]["fund_txn"].copy()
        t["dt"], t["nav"], t["amt"] = pd.to_datetime(t["order_datetime"]), pd.to_datetime(t["nav_date"]), t["amount"].astype(float)
        t["per"] = month(t["order_datetime"])
        return t

    def test_planted_cases_grounded(self):
        _, key = built(msf)
        t = self.tx()
        # F-R1: same unitholder + fund, a sale within ROUNDTRIP.DAYS of a purchase, sale 80-120 % of the purchase
        buys, sells = t[t["txn_type"] == "BUY"], t[t["txn_type"] == "SELL"]
        j = buys.merge(sells, on=["unitholder_id", "fund_code"], suffixes=("_b", "_s"))
        j["gap"] = (j["dt_s"] - j["dt_b"]).dt.days
        j["r"] = j["amt_s"] / j["amt_b"]
        lo, hi = TH["FUND.ROUNDTRIP.BAND"]
        rt = j[(j["gap"] >= 0) & (j["gap"] <= TH["FUND.ROUNDTRIP.DAYS"]) & (j["r"] >= lo) & (j["r"] <= hi)]
        self.assertEqual(rt["unitholder_id"].tolist(), ["U-0101"])
        self.assertEqual(rt["fund_code"].tolist(), ["FX1"])
        self.assertEqual(rt["gap"].tolist(), [9])
        self.assertAlmostEqual(rt["r"].iloc[0], 0.98, places=3)
        # near misses exist on both sides of the rule: slow sales with the same amount, quick sales with another amount
        self.assertTrue(((j["gap"] > TH["FUND.ROUNDTRIP.DAYS"]) & (j["r"] >= lo) & (j["r"] <= hi)).any())
        self.assertTrue(((j["gap"] <= TH["FUND.ROUNDTRIP.DAYS"]) & ((j["r"] < lo) | (j["r"] > hi))).any())
        self.assertGreater(j[(j["gap"] > TH["FUND.ROUNDTRIP.DAYS"]) & (j["r"] >= lo) & (j["r"] <= hi)]["gap"].min(), 50)
        self.assertLess(j[(j["gap"] <= TH["FUND.ROUNDTRIP.DAYS"]) & ((j["r"] < lo) | (j["r"] > hi))]["r"].max(), 0.6)
        # F-R2: the account owner (counterparty) is not the unitholder; only owner ids of the unitholder format compare
        third = t[t["bank_account"] != t["unitholder_id"]]
        comparable = third[third["bank_account"].str.match(r"^U-\d+$")]
        self.assertEqual(comparable["unitholder_id"].tolist(), ["U-0202"])
        self.assertEqual(comparable["bank_account"].tolist(), ["U-0999"])
        self.assertEqual(comparable["txn_type"].tolist(), ["SELL"])
        self.assertEqual(set(third["bank_account"]), {"U-0999", "BA-7000"})  # BA-7000 is an account number: not comparable
        self.assertFalse(t["unitholder_id"].eq("U-0999").any())
        # F-R3: one counterparty used by >= SHARED_ACCT.MIN_HOLDERS unitholders
        n_hold = t.groupby("bank_account")["unitholder_id"].nunique()
        self.assertEqual(n_hold[n_hold >= TH["FUND.SHARED_ACCT.MIN_HOLDERS"]].index.tolist(), ["BA-7000"])
        self.assertEqual(n_hold["BA-7000"], 4)
        self.assertEqual(sorted(t[t["bank_account"] == "BA-7000"]["unitholder_id"].unique()),
                         ["U-0301", "U-0302", "U-0303", "U-0304"])
        self.assertEqual((n_hold.drop(["BA-7000"]) == 1).all(), True)
        # F-R4: >= FREQ.MIN_TX_MONTH buy / sell / switch transactions per unitholder per month
        cnt = t.groupby(["unitholder_id", "per"]).size()
        freq = cnt[cnt >= TH["FUND.FREQ.MIN_TX_MONTH"]]
        hitters = sorted(freq.index.get_level_values(0).unique())
        self.assertEqual(hitters, ["U-0404", "U-0501", "U-0502", "U-0503", "U-0504", "U-0505", "U-0506"])
        self.assertEqual(int(cnt[("U-0404", "2026-07")]), 10)
        self.assertEqual([int(cnt[(u, "2026-08")]) for u in hitters[1:]], [8] * 6)
        self.assertLessEqual(cnt.drop(freq.index).max(), 2)  # normal: at most 2 in a month
        # F-R5: an agent with >= CHURN.MIN_CLIENT_SHARE of its clients (and >= CHURN.MIN_CLIENTS) hitting F-R4
        clients = t.groupby("agent")["unitholder_id"].nunique()
        hit_clients = t[t["unitholder_id"].isin(hitters)].groupby("agent")["unitholder_id"].nunique()
        share = (hit_clients / clients).dropna()
        churn = share[(share >= TH["FUND.CHURN.MIN_CLIENT_SHARE"]) & (hit_clients.reindex(share.index) >= TH["FUND.CHURN.MIN_CLIENTS"])]
        self.assertEqual(churn.index.tolist(), ["AG-05"])
        self.assertEqual(int(clients["AG-05"]), 15)
        self.assertEqual(int(hit_clients["AG-05"]), 6)
        self.assertAlmostEqual(share["AG-05"], 0.40, places=3)
        self.assertEqual(share.drop("AG-05").index.tolist(), ["AG-06"])  # U-0404's agent: 1 client of many
        self.assertLess(share["AG-06"], 0.15)
        # F-R6: order time after the cut-off with the NAV date equal to the order date
        hhmm = t["dt"].dt.strftime("%H:%M")
        late = t[(hhmm > TH["FUND.CUTOFF_TIME"]) & (t["nav"] == t["dt"].dt.normalize())]
        self.assertEqual(late["order_id"].tolist(), ["O-6006"])
        self.assertEqual(late["order_datetime"].tolist(), ["2026-09-16 16:10:00"])
        self.assertEqual(late["unitholder_id"].tolist(), ["U-0606"])
        decoys = t[(hhmm > TH["FUND.CUTOFF_TIME"]) & (t["nav"] > t["dt"].dt.normalize())]
        self.assertGreaterEqual(len(decoys), 5)  # late orders priced on the next business day are normal
        self.assertTrue((decoys["nav"] - decoys["dt"].dt.normalize()).dt.days.between(1, 3).all())
        # normal data: weekdays 09:00-15:00, steady, no period-end clustering
        normal = t[~t["unitholder_id"].isin(["U-0101", "U-0202", "U-0301", "U-0302", "U-0303", "U-0304", "U-0404",
                                             "U-0501", "U-0502", "U-0503", "U-0504", "U-0505", "U-0506", "U-0606"])
                   & ~t["order_id"].isin(decoys["order_id"])]
        self.assertTrue((normal["dt"].dt.dayofweek < 5).all())
        self.assertTrue((hhmm[normal.index] >= "09:00").all() and (hhmm[normal.index] <= "15:00").all())
        self.assertTrue((normal["nav"] == normal["dt"].dt.normalize()).all())
        per_month = normal.groupby("per").size()
        self.assertEqual(len(per_month), 10)
        self.assertLess(per_month.max() / per_month.min(), 1.15)
        self.assertEqual(sorted(t["txn_type"].unique()), ["BUY", "SELL", "SWI", "SWO"])
        self.assertEqual((t["amt"] % TH["FOR.ROUND.UNIT"] == 0).sum(), 0)
        self.assertTrue(t["amt"].between(1000, 39999.99).all())
        # the master has every unitholder (and the account owner U-0999)
        u = built(msf)[0]["unitholders"]
        self.assertTrue(set(t["unitholder_id"]) <= set(u["unitholder_id"]))
        self.assertIn("U-0999", set(u["unitholder_id"]))
        self.assertTrue(u["unitholder_id"].is_unique)
        first = t.groupby("unitholder_id")["dt"].min()
        opened = pd.to_datetime(u.set_index("unitholder_id")["open_date"])
        self.assertTrue((opened.reindex(first.index) < first).all())
        # the key says the same
        r = key["recipes"]
        self.assertEqual(r["FUND-ROUNDTRIP"], ["U-0101"])
        self.assertEqual(r["FUND-THIRD-PARTY"], ["U-0202"])
        self.assertEqual(r["FUND-SHARED-ACCT"], ["BA-7000"])
        self.assertEqual(r["FUND-FREQUENT"], hitters)
        self.assertEqual(r["FUND-CHURN"], ["AG-05"])
        self.assertEqual(r["FUND-LATE-TRADE"], ["O-6006"])
        got = {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key["findings"]}
        want = {("unitholder", "U-0101", "F-R1", "2026-05"), ("unitholder", "U-0202", "F-R2", "2026-06"),
                ("account", "BA-7000", "F-R3", "2026-09"), ("unitholder", "U-0404", "F-R4", "2026-07"),
                ("agent", "AG-05", "F-R5", "2026-08"), ("unitholder", "U-0606", "F-R6", "2026-09")} | \
               {("unitholder", u, "F-R4", "2026-08") for u in hitters[1:]}
        self.assertEqual(got, want)
        self.assertEqual(t[t["bank_account"] == "BA-7000"]["per"].max(), "2026-09")

    def test_intake_key(self):
        _, key = built(msf)
        it = key["intake"]
        self.assertEqual(it["sufficiency"], {"F-R1": "พร้อม", "F-R2": "พร้อม", "F-R6": "พร้อม"})
        self.assertEqual(it["data_request"], [])
        self.assertEqual(it["suggested_risks"], ["F-R3", "F-R4", "F-R5"])
        self.assertEqual(it["description_conflicts"], [])
        self.assertEqual(key["conventions"]["date_only"]["sufficiency"], {"F-R6": "บางส่วน"})
        self.assertTrue(key["conventions"]["date_only"]["data_request"])

    def test_brief_describes_time(self):
        brief = sc.load_brief(SAMPLES / "F" / "brief.md")
        self.assertIn("เวลา", brief["columns"]["order_datetime"])
        self.assertIn("NAV", brief["columns"]["nav_date"])

    def test_date_only_variant(self):
        frames, _ = built(msf)
        d = SAMPLES / "F" / "variants" / "date_only"
        on_disk = pd.read_csv(d / "fund_txn.csv", dtype=str, keep_default_na=False)
        full = frames["fund_txn"]
        self.assertEqual(len(on_disk), len(full))
        self.assertTrue(on_disk["order_datetime"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all())
        self.assertEqual(on_disk["order_datetime"].tolist(), full["order_datetime"].str[:10].tolist())
        pd.testing.assert_frame_equal(on_disk.drop(columns="order_datetime"), full.astype(str).drop(columns="order_datetime"),
                                      check_dtype=False)
        pd.testing.assert_frame_equal(pd.read_csv(d / "unitholders.csv", dtype=str, keep_default_na=False),
                                      frames["unitholders"].astype(str), check_dtype=False)
        roles, answers = roles_of(SAMPLES / "F" / "variants" / "roles_date_only.json")
        self.assertEqual(roles, roles_of(SAMPLES / "F" / "variants" / "roles_en.json")[0])
        self.assertEqual(answers, {})
        internal = engine().to_internal({t: pd.read_csv(d / f"{t}.csv", dtype=str, keep_default_na=False) for t in roles},
                                        roles)
        self.assertEqual(len(internal["transactions"]), len(full))


class TestPlanting(unittest.TestCase):
    def test_generators_share_no_planted_ids_with_normal_rows(self):
        for mod, col in ((msl, "policy_no"), (msf, "unitholder_id")):
            frames, _ = built(mod)
            main = frames["policy_txn" if mod is msl else "fund_txn"]
            self.assertTrue(main["txn_id" if mod is msl else "order_id"].is_unique)
            ids = main[col]
            self.assertFalse(ids.str.match(r"^\s|\s$").any())
            self.assertTrue(ids.map(lambda x: bool(re.match(r"^[A-Z]-\d{4}$", x))).all())


class TestEvalC2(unittest.TestCase):
    """eval-questions.md Q48-Q57 (C2): each item has the question, expected behaviour, pass criteria, a checklist tag
    and a 4-samples/ path that exists in the repo samples/ (the zip layout), and says to paste only the letter."""

    def test_q48_to_q57_complete(self):
        t = (HERE / "eval-questions.md").read_text(encoding="utf-8")
        section = t.split("## ระยะ C2", 1)[1].split("## ตารางผลทดสอบ", 1)[0]
        self.assertIn("เฉพาะส่วนหนังสือภาษาไทย", section)
        self.assertIn("```json", section)
        for q in range(48, 58):
            block = t.split(f"### Q{q} — ", 1)[1].split("\n### ", 1)[0].split("\n---", 1)[0]
            for part in ("- ต้องมี: ", "- ต้องไม่มี: ", "- ไฟล์ที่ควรถูกอ้าง: AIDA-", "- Checklist ข้อ "):
                self.assertIn(part, block, f"Q{q}: {part}")
            paths = re.findall(r"`4-samples/([^`]+)`", block)
            if q in (51, 55, 56):  # follow-ups of Q50 / Q53 / Q48 reuse those files
                continue
            self.assertTrue(paths, f"Q{q}: no 4-samples/ path")
            for rel in paths:
                self.assertTrue((SAMPLES / rel).exists(), f"Q{q}: samples/{rel} missing")
            self.assertIn(f"| Q{q} | ", t)


if __name__ == "__main__":
    unittest.main()
