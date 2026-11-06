"""Tests for the C (loan payments) and A (accounts payable) sample data, briefs and answer keys (AIDA C1 task 4).

test_planted_cases_grounded recomputes every planted case from the CSV frames with plain pandas, without the
engine and without reading the answer key; the key is then compared with what the data shows. Thresholds are
the AIDA-14 v1.2 values (sample_common.TH).
"""
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_sample_a as msa  # noqa: E402
import make_sample_c as msc  # noqa: E402
import make_sample_data as mse  # noqa: E402
import sample_common as sc  # noqa: E402
from _engine import engine  # noqa: E402

TH = sc.TH
SAMPLES = sc.SAMPLES
_CACHE = {}


def built(mod):
    if mod.__name__ not in _CACHE:
        _CACHE[mod.__name__] = mod.make()
    return _CACHE[mod.__name__]


def benford_mad(amounts):
    a = pd.Series(amounts).abs()
    a = a[a >= 10]
    first = a.map(lambda x: int(f"{x:.10e}"[0]))
    obs = first.value_counts(normalize=True).reindex(range(1, 10), fill_value=0.0)
    exp = pd.Series({d: np.log10(1 + 1 / d) for d in range(1, 10)})
    return float((obs - exp).abs().mean()), len(a)


def month(s):
    return pd.to_datetime(s).dt.strftime("%Y-%m")


class Shared:
    mod = None
    name = None

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
        self.assertTrue(set(key["recipes"]) <= set(self.CHECKS))
        intake = key["intake"]
        self.assertEqual(set(intake), {"sufficiency", "data_request", "suggested_risks", "description_conflicts"})
        self.assertTrue(set(intake["sufficiency"].values()) <= {"พร้อม", "บางส่วน", "ไม่พอ"})
        self.assertFalse(set(intake["suggested_risks"]) & set(intake["sufficiency"]))

    def test_variants_same_content(self):
        frames, key = built(self.mod)
        d = SAMPLES / self.name / "variants"
        e = engine()
        for v in sc.VARIANTS:
            roles = json.loads((d / f"roles_{v}.json").read_text(encoding="utf-8"))
            names = self.mod.VARIANT_NAMES[v]
            back = {}
            for t, df in frames.items():
                on_disk = pd.read_csv(d / v / f"{t}.csv", dtype=str, keep_default_na=False)
                inv = {n: c for c, n in names.get(t, {}).items()}
                back[t] = on_disk.rename(columns=inv)
                pd.testing.assert_frame_equal(back[t], df.astype(str).reset_index(drop=True), check_dtype=False)
                if v != "en":
                    self.assertTrue(set(names[t].values()).isdisjoint(set(self.mod.VARIANT_NAMES["en"][t].values())))
            disk = {t: pd.read_csv(d / v / f"{t}.csv", dtype=str, keep_default_na=False) for t in frames}
            internal = e.to_internal(disk, roles)
            self.assertTrue({"tx_id", "ts", "amount"} <= set(internal["transactions"].columns))
            self.assertEqual(len(internal["transactions"]), len(frames[self.main]))

    def test_en_variant_matches_presets(self):
        preset = engine().PRESETS[self.name]
        roles_en = {c: r for rmap in self.mod.ROLES_EN.values() for c, r in rmap.items()}
        for col, role in roles_en.items():
            if role == "custom:product":  # deliberately not in the preset: the brief leaves it undescribed
                continue
            self.assertEqual(preset.get(col), role, col)

    def test_brief_block(self):
        brief = sc.load_brief(SAMPLES / self.name / "brief.md")
        self.assertEqual(set(brief), {"context", "columns", "conditions", "concerns"})
        self.assertTrue(brief["context"] and brief["concerns"])
        text = (SAMPLES / self.name / "brief.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"[฀-๿]{20,}")
        for v in sc.VARIANTS:
            vb = json.loads((SAMPLES / self.name / "variants" / v / "brief.json").read_text(encoding="utf-8"))
            self.assertEqual(len(vb["columns"]), len(brief["columns"]))


class TestC(Shared, unittest.TestCase):
    mod, name, main = msc, "C", "payments"
    CHECKS = ["GEN-CONC", "GEN-PERIOD-END", "DUP-PAY", "FOR-BENFORD", "FOR-ROUND", "FOR-REPEAT", "DUE-NEAR",
              "PAYER-MULTI"]

    def pay(self):
        p = built(msc)[0]["payments"].copy()
        p["d"], p["due"] = pd.to_datetime(p["pay_date"]), pd.to_datetime(p["due_date"])
        p["amt"] = p["pay_amount"].astype(float)
        return p

    def test_planted_cases_grounded(self):
        frames, key = built(msc)
        p = self.pay()
        live = p[p["status"] != "C"]
        # payer paying several contracts of other borrowers
        other = live[live["payer_id"] != live["borrower_id"]]
        n_contracts = other.groupby("payer_id")["contract_id"].nunique()
        multi = sorted(n_contracts[n_contracts >= TH["PAYER.MIN_CONTRACTS"]].index)
        self.assertEqual(multi, ["PY01"])
        self.assertEqual(n_contracts["PY01"], 6)
        self.assertEqual(set(other["payer_id"]) - {"PY01"}, {x for x in other["payer_id"] if x.startswith("TP")})
        self.assertTrue((n_contracts.drop("PY01") == 1).all())
        # paying 1-2 days before due in (nearly) every period
        live = live.assign(per=month(live["pay_date"]), lead=(live["due"] - live["d"]).dt.days)
        live = live.assign(is_near=(live["lead"] >= 0) & (live["lead"] <= TH["DUE.NEAR_DAYS"]))
        per_period = live.groupby(["contract_id", "per"])["is_near"].any()
        g = pd.DataFrame({"periods": per_period.groupby("contract_id").size(),
                          "near": per_period.groupby("contract_id").mean()})
        near = sorted(g[(g["periods"] >= TH["DUE.MIN_PERIODS"]) & (g["near"] >= TH["DUE.MIN_SHARE"])].index)
        self.assertEqual(near, ["HP-0042"])
        self.assertEqual(g.loc["HP-0042", "periods"], 8)
        self.assertTrue(live[live["contract_id"] == "HP-0042"]["lead"].isin([1, 2]).all())
        self.assertLess(g.drop("HP-0042")["near"].max(), 0.2)
        # duplicate payments: same contract + payer + amount within DUP.WINDOW_DAYS
        pos = live[live["amt"] > 0].sort_values(["contract_id", "payer_id", "amt", "d"])
        gap = pos.groupby(["contract_id", "payer_id", "amt"])["d"].diff().dt.days
        dup = pos[gap.le(TH["DUP.WINDOW_DAYS"])]
        self.assertEqual(sorted(dup["contract_id"].unique()), ["HP-0150"])
        self.assertEqual(len(dup), 1)
        # refunds about 2 % of rows; cancelled rows exist and are not duplicates of anything
        self.assertTrue(0.015 <= (p["amt"] < 0).mean() <= 0.025)
        self.assertTrue((p["status"] == "C").sum() > 0)
        self.assertTrue((p[p["status"] == "C"]["amt"] > 0).all())
        # normal data triggers no general check
        self.assertEqual((live["amt"].abs() % TH["FOR.ROUND.UNIT"] == 0).sum(), 0)
        rep = live.groupby(["borrower_id", "per", "amt"]).size()
        self.assertTrue((rep < TH["FOR.REPEAT.MIN_COUNT"]).all())
        mad, n = benford_mad(live["amt"])
        self.assertGreaterEqual(n, TH["FOR.BENFORD.MIN_N"])
        self.assertLess(mad, TH["FOR.BENFORD.MAD_OK"])
        tot = live[live["amt"] > 0].groupby("borrower_id")["amt"].sum()
        self.assertLess(tot.max() / tot.sum(), TH["CONC.SINGLE_ENTITY_SHARE"])
        # no payment inside the period-end window (last 3 weekdays / first 3 days)
        dd = live["d"]
        eom = dd + pd.offsets.MonthEnd(0)
        self.assertTrue((dd.dt.day >= 4).all() and (dd.dt.day <= 24).all())
        self.assertTrue((dd < (eom - pd.offsets.BDay(2)).dt.normalize()).all())
        # contracts table joins to payments
        c = frames["contracts"]
        self.assertEqual(set(p["contract_id"]), set(c["contract_id"]))
        j = p.merge(c, on="contract_id", suffixes=("", "_c"))
        self.assertTrue((j["borrower_id"] == j["borrower_id_c"]).all())
        # the key says the same
        r = key["recipes"]
        self.assertEqual(r["PAYER-MULTI"], ["PY01"])
        self.assertEqual(r["DUE-NEAR"], ["HP-0042"])
        self.assertEqual(r["DUP-PAY"], ["HP-0150"])
        for cid in ("GEN-CONC", "GEN-PERIOD-END", "FOR-BENFORD", "FOR-ROUND", "FOR-REPEAT"):
            self.assertEqual(r[cid], [])
        got = {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key["findings"]}
        self.assertEqual(got, {("payer", "PY01", "C-R1", "2026-08"), ("contract", "HP-0042", "C-R2", "2026-08"),
                               ("contract", "HP-0150", "C-R3", "2026-05")})
        self.assertEqual(dup["pay_date"].map(lambda s: s[:7]).iloc[0], "2026-05")
        self.assertEqual(month(live[live["payer_id"] == "PY01"]["pay_date"]).unique().tolist(), ["2026-08"])

    def test_intake_key(self):
        _, key = built(msc)
        it = key["intake"]
        self.assertEqual(it["sufficiency"], {"C-R1": "พร้อม", "C-R2": "พร้อม", "R1": "ไม่พอ"})
        self.assertEqual(len(it["data_request"]), 1)
        self.assertIn("เงินฝาก", it["data_request"][0])
        self.assertEqual(it["suggested_risks"], ["C-R3"])
        self.assertEqual(it["description_conflicts"], ["pay_amount"])

    def test_brief_mentions_conflict_column(self):
        brief = sc.load_brief(SAMPLES / "C" / "brief.md")
        self.assertIn("ยอดชำระสุทธิ", brief["columns"]["pay_amount"])
        self.assertEqual(len(brief["concerns"]), 3)
        self.assertTrue(any("C" in c and "ยกเลิก" in c for c in brief["conditions"]))
        e = engine()
        frames, key = built(msc)
        prof = e.profile_columns(frames)
        conflicts = e.check_descriptions(prof, brief["columns"])
        self.assertEqual(sorted({c["column"] for c in conflicts if c["table"] == "payments"}),
                         key["intake"]["description_conflicts"])
        for v in ("th", "legacy"):
            vb = json.loads((SAMPLES / "C" / "variants" / v / "brief.json").read_text(encoding="utf-8"))
            vframes = {t: pd.read_csv(SAMPLES / "C" / "variants" / v / f"{t}.csv", dtype=str, keep_default_na=False)
                       for t in frames}
            vc = e.check_descriptions(e.profile_columns(vframes), vb["columns"])
            amt = msc.VARIANT_NAMES[v]["payments"]["pay_amount"]
            self.assertEqual(sorted({c["column"] for c in vc if c["table"] == "payments"}), [amt])


class TestA(Shared, unittest.TestCase):
    mod, name, main = msa, "A", "payments"
    CHECKS = ["GEN-CONC", "GEN-PERIOD-END", "DUP-PAY", "SPLIT-LIMIT", "FOR-BENFORD", "FOR-ROUND", "FOR-REPEAT",
              "SOD-SAME-USER"]

    def pay(self):
        p = built(msa)[0]["payments"].copy()
        p["d"] = pd.to_datetime(p["pay_date"])
        p["amt"] = p["amount"].astype(float)
        p["lim"] = p["approval_limit"].astype(float)
        p["per"] = month(p["pay_date"])
        return p

    def test_planted_cases_grounded(self):
        _, key = built(msa)
        p = self.pay()
        # duplicate invoice: same vendor + invoice + amount, paid again within DUP.WINDOW_DAYS
        s = p.sort_values(["vendor_id", "invoice_no", "amt", "d"])
        gap = s.groupby(["vendor_id", "invoice_no", "amt"])["d"].diff().dt.days
        dup = s[gap.le(TH["DUP.WINDOW_DAYS"])]
        self.assertEqual(dup["invoice_no"].tolist(), ["INV-7781"])
        self.assertEqual(gap[dup.index].tolist(), [2])
        # same vendor + amount within the window even without the invoice number: only the split vendor besides
        s2 = p.sort_values(["vendor_id", "amt", "d"])
        gap2 = s2.groupby(["vendor_id", "amt"])["d"].diff().dt.days
        self.assertEqual(sorted(s2[gap2.le(TH["DUP.WINDOW_DAYS"])]["vendor_id"].unique()), ["V-031", "V-045"])
        # split payments: >= SPLIT.MIN_TX payments in the band under the limit within SPLIT.WINDOW_DAYS
        ratio = p["amt"] / p["lim"]
        band = p[(ratio >= TH["SPLIT.BAND"][0]) & (ratio < TH["SPLIT.BAND"][1])].sort_values(["vendor_id", "d"])
        self.assertEqual(sorted(band["vendor_id"].unique()), ["V-045"])
        self.assertEqual(band["amt"].tolist(), [48000.0] * 3)
        self.assertEqual(band["lim"].tolist(), [50000.0] * 3)
        self.assertLessEqual((band["d"].max() - band["d"].min()).days, TH["SPLIT.WINDOW_DAYS"])
        self.assertEqual(band["per"].unique().tolist(), ["2026-06"])
        # maker = checker
        same = p[p["created_by"] == p["approved_by"]]
        self.assertEqual(same["created_by"].unique().tolist(), ["U017"])
        self.assertGreaterEqual(len(same), 5)
        self.assertEqual(same["per"].unique().tolist(), ["2026-08"])
        self.assertTrue((p[p["created_by"] != "U017"]["created_by"] != p[p["created_by"] != "U017"]["approved_by"]).all())
        # Benford: vendors with >= MIN_N payments; V-099 deviates, nobody else does; the whole file is fine
        counts = p.groupby("vendor_id")["amt"].apply(lambda x: (x >= 10).sum())
        big = counts[counts >= TH["FOR.BENFORD.MIN_N"]].index.tolist()
        self.assertEqual(big, ["V-099"])
        mad99, _ = benford_mad(p[p["vendor_id"] == "V-099"]["amt"])
        self.assertGreater(mad99, TH["FOR.BENFORD.MAD_BAD"])
        mad_all, n_all = benford_mad(p["amt"])
        self.assertLess(mad_all, TH["FOR.BENFORD.MAD_OK"])
        mad_rest, _ = benford_mad(p[p["vendor_id"] != "V-099"]["amt"])
        self.assertLess(mad_rest, 0.006)
        # round amounts clustered at V-120
        rnd = (p["amt"] % TH["FOR.ROUND.UNIT"] == 0)
        share = rnd.groupby(p["vendor_id"]).mean()
        cnt = rnd.groupby(p["vendor_id"]).sum()
        self.assertEqual((share[cnt >= 10] >= 0.5).index[(share[cnt >= 10] >= 0.5)].tolist(), ["V-120"])
        self.assertEqual(int(cnt["V-120"]), 40)
        self.assertEqual(float(share["V-120"]), 1.0)
        self.assertEqual(sorted(cnt[(cnt > 0) & (cnt.index != "V-120")].index), ["V-045"])
        self.assertLess(share["V-045"], 0.2)
        # repeated amounts: same vendor + amount >= FOR.REPEAT.MIN_COUNT times in a period
        rep = p.groupby(["vendor_id", "per", "amt"]).size()
        self.assertEqual(sorted(rep[rep >= TH["FOR.REPEAT.MIN_COUNT"]].index.get_level_values(0).unique()), ["V-045"])
        # concentration: one vendor >= CONC.SINGLE_ENTITY_SHARE of the total
        sh = p.groupby("vendor_id")["amt"].sum() / p["amt"].sum()
        self.assertEqual(sh[sh >= TH["CONC.SINGLE_ENTITY_SHARE"]].index.tolist(), ["V-077"])
        self.assertLess(sh.drop("V-077").max(), 0.05)
        # period end: last 3 weekdays of the month, only V-150
        eom = p["d"] + pd.offsets.MonthEnd(0)
        last3 = p["d"] >= (eom - pd.offsets.BDay(2)).dt.normalize()
        first3 = p["d"].dt.day <= 3
        window = last3 | first3
        self.assertEqual(sorted(p[window]["vendor_id"].unique()), ["V-150"])
        self.assertEqual(p[window]["per"].unique().tolist(), ["2026-08"])
        self.assertGreaterEqual(window.sum(), 10)
        # nothing else: normal rows have distinct amounts per vendor and unique invoice numbers
        self.assertEqual(p["invoice_no"].duplicated().sum(), 1)
        self.assertTrue(p["payment_id"].is_unique)
        # the key says the same
        r = key["recipes"]
        self.assertEqual(r["DUP-PAY"], ["V-031"])
        self.assertEqual(r["SPLIT-LIMIT"], ["V-045"])
        self.assertEqual(r["SOD-SAME-USER"], ["U017"])
        self.assertEqual(r["FOR-BENFORD"], ["V-099"])
        self.assertEqual(r["FOR-ROUND"], ["V-120"])
        self.assertEqual(r["FOR-REPEAT"], ["V-045"])
        self.assertEqual(r["GEN-CONC"], ["V-077"])
        self.assertEqual(r["GEN-PERIOD-END"], ["V-150"])
        got = {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key["findings"]}
        self.assertEqual(got, {("document", "INV-7781", "A-R1", "2026-04"), ("vendor", "V-045", "A-R2", "2026-06"),
                               ("user", "U017", "A-R3", "2026-08"), ("vendor", "V-077", "A-R4", "2026-08"),
                               ("vendor", "V-099", "G-R4", "2026-08"), ("vendor", "V-120", "G-R4", "2026-08"),
                               ("vendor", "V-150", "G-R2", "2026-08")})

    def test_intake_key(self):
        _, key = built(msa)
        it = key["intake"]
        self.assertEqual(it["sufficiency"], {"A-R1": "พร้อม", "A-R2": "พร้อม"})
        self.assertEqual(it["data_request"], [])
        self.assertTrue({"A-R3", "G-R4", "A-R4"} <= set(it["suggested_risks"]))
        self.assertEqual(it["suggested_risks"], ["A-R3", "A-R4", "G-R2", "G-R4"])
        self.assertEqual(it["description_conflicts"], [])

    def test_brief_concerns(self):
        brief = sc.load_brief(SAMPLES / "A" / "brief.md")
        self.assertEqual(len(brief["concerns"]), 2)
        e = engine()
        frames, key = built(msa)
        self.assertEqual(e.check_descriptions(e.profile_columns(frames), brief["columns"]), [])


class TestEBrief(unittest.TestCase):
    def test_e_brief(self):
        brief = sc.load_brief(SAMPLES / "E" / "brief.md")
        self.assertEqual(len(brief["concerns"]), 4)
        tx = pd.read_csv(SAMPLES / "transactions.csv", nrows=1)
        self.assertTrue({c for c in brief["columns"]} <= set(tx.columns) | {"acct_id", "opened_at", "account_type"})

    def test_e_variants(self):
        e = engine()
        frames = {"transactions": pd.read_csv(SAMPLES / "transactions.csv", dtype=str, keep_default_na=False),
                  "accounts": pd.read_csv(SAMPLES / "accounts.csv", dtype=str, keep_default_na=False)}
        for v in sc.VARIANTS:
            roles = json.loads((SAMPLES / "E" / "variants" / f"roles_{v}.json").read_text(encoding="utf-8"))
            names = mse_names(v)
            disk = {t: pd.read_csv(SAMPLES / "E" / "variants" / v / f"{t}.csv", dtype=str, keep_default_na=False)
                    for t in frames}
            for t, df in frames.items():
                pd.testing.assert_frame_equal(disk[t].rename(columns={n: c for c, n in names[t].items()}), df)
            internal = e.to_internal(disk, roles)
            self.assertEqual(set(internal), {"transactions", "accounts"})


def mse_names(v):
    import make_sample_e_variants as mev
    return mev.VARIANT_NAMES[v]


if __name__ == "__main__":
    unittest.main()
