"""Deterministic sample data for AIDA C1, data type A (accounts payable payments).

make(seed) returns (frames, key): frames = {"payments": ...}. Only `seed` changes the normal data; the planted
cases and the answer key are the same for every seed.

Normal data design (why no check fires on it):
- 6,000 payments Jan-Aug 2026 to 123 vendors (V-200..V-319 plus V-031, V-045, V-150), on weekdays of day 6-24 of
  the month: none falls in a period-end window. Amounts are stratified log-uniform over 1,000-100,000 (two whole
  decades) so first digits follow Benford's law; every amount is unique and none is a multiple of 1,000.
- approval_limit is the smallest tier of 10k/50k/200k/1M/5M that is at least amount / 0.85: no normal payment is
  within 90-100 % of its limit.
- Makers U001..U030 and approvers M001..M010 are different people.

Planted cases (ids in the key):
- INV-7781 (V-031) paid twice, 2026-04-14 and 04-16, 36,420.50                 -> DUP-PAY, A-R1
- V-045: 3 x 48,000 against a 50,000 limit on 2026-06-16/17 (invoices INV-8801..8803) -> SPLIT-LIMIT, FOR-REPEAT, A-R2
- maker = approver U017 on 8 payments in 2026-08                               -> SOD-SAME-USER, A-R3
- V-077: 600 payments of 10,000-100,000 = about 15 % of the total               -> GEN-CONC, A-R4
- V-099: 1,050 payments of 100-999 with uniform first digits (Benford MAD about 0.06; about 13 % of the rows, so
  the whole file stays within "acceptable")                                    -> FOR-BENFORD, G-R4
- V-120: 40 distinct multiples of 1,000 in 2026-08                             -> FOR-ROUND, G-R4
- V-150: 12 payments on 2026-08-27/28/31 (last 3 weekdays)                     -> GEN-PERIOD-END, G-R2
Known side effects: V-045's three 48,000 payments are also multiples of 1,000 (3 of its ~50 payments, so the round
share is small) and carry distinct invoice numbers (not a duplicate by invoice).
"""
import numpy as np
import pandas as pd

import sample_common as sc

SEED = 20261106
PLANT_SEED = 1106
PERIOD = "2026-08"
N_NORMAL, N_V077, N_V099 = 6000, 600, 1050
NORMAL_VENDORS = [f"V-{i}" for i in range(200, 320)] + ["V-031", "V-045", "V-150"]
CATEGORIES = ["วัสดุสำนักงาน", "บริการ", "ซ่อมบำรุง", "ไอที", "สาธารณูปโภค"]
TIERS = [10_000, 50_000, 200_000, 1_000_000, 5_000_000]
GOLDEN = 0.6180339887498949

TABLES = {"payments": ["payment_id", "pay_date", "amount", "vendor_id", "invoice_no", "created_by", "approved_by",
                       "approval_limit", "category"]}
ROLES_EN = {"payments": {"payment_id": "record_id", "pay_date": "date", "amount": "amount", "vendor_id": "entity",
                         "invoice_no": "document_no", "created_by": "created_by", "approved_by": "approved_by",
                         "approval_limit": "limit", "category": "category"}}
VARIANT_NAMES = {
    "en": {"payments": {}},
    "th": {"payments": {"payment_id": "เลขที่รายการจ่าย", "pay_date": "วันที่จ่าย", "amount": "จำนวนเงิน",
                        "vendor_id": "รหัสผู้ขาย", "invoice_no": "เลขที่ใบแจ้งหนี้", "created_by": "ผู้บันทึก",
                        "approved_by": "ผู้อนุมัติ", "approval_limit": "วงเงินอนุมัติ", "category": "หมวดค่าใช้จ่าย"}},
    "legacy": {"payments": {"payment_id": "F01", "pay_date": "F02", "amount": "AMT_X1", "vendor_id": "F04",
                            "invoice_no": "F05", "created_by": "USR_A", "approved_by": "USR_B", "approval_limit": "LMT",
                            "category": "COL3"}},
}

BRIEF_MD = """# หนังสือขอให้ตรวจสอบ: การจ่ายเงินให้ผู้ขาย

เรียน ทีมวิเคราะห์ข้อมูล

ขอให้ช่วยตรวจสอบรายการจ่ายเงินให้ผู้ขาย (เจ้าหนี้การค้า) ช่วงเดือนมกราคมถึงสิงหาคม 2026 ไฟล์ payments มี 1 แถวต่อ 1 การจ่ายเงิน

ความหมายของคอลัมน์: payment_id คือเลขที่รายการจ่าย, pay_date คือวันที่จ่ายเงิน, amount คือจำนวนเงินที่จ่ายจริงต่อใบแจ้งหนี้,
vendor_id คือรหัสผู้ขาย, invoice_no คือเลขที่ใบแจ้งหนี้ของผู้ขาย, created_by คือผู้บันทึกรายการจ่าย,
approved_by คือผู้อนุมัติรายการจ่าย, approval_limit คือวงเงินอนุมัติของรายการนั้น และ category คือหมวดค่าใช้จ่าย

เงื่อนไข: ทุกรายการเป็นการจ่ายเงินจริงแล้ว ไม่มีรายการที่ต้องตัดออก

สิ่งที่กังวล:
1. มีการจ่ายเงินซ้ำสำหรับใบแจ้งหนี้เดียวกัน
2. มีการแบ่งจ่ายเป็นหลายรายการเพื่อให้ต่ำกว่าวงเงินอนุมัติ

```json
{
  "context": "เจ้าหนี้การค้า — รายการจ่ายเงินให้ผู้ขาย ม.ค.–ส.ค. 2026 (ตารางเดียว payments)",
  "columns": {
    "payment_id": "เลขที่รายการจ่าย",
    "pay_date": "วันที่จ่ายเงิน",
    "amount": "จำนวนเงินที่จ่ายจริงต่อใบแจ้งหนี้",
    "vendor_id": "รหัสผู้ขาย",
    "invoice_no": "เลขที่ใบแจ้งหนี้ของผู้ขาย",
    "created_by": "ผู้บันทึกรายการจ่าย",
    "approved_by": "ผู้อนุมัติรายการจ่าย",
    "approval_limit": "วงเงินอนุมัติของรายการนั้น",
    "category": "หมวดค่าใช้จ่าย"
  },
  "conditions": [
    "ทุกรายการเป็นการจ่ายเงินจริงแล้ว ไม่ต้องตัดรายการใดออก"
  ],
  "concerns": [
    "มีการจ่ายเงินซ้ำสำหรับใบแจ้งหนี้เดียวกัน",
    "มีการแบ่งจ่ายเป็นหลายรายการเพื่อให้ต่ำกว่าวงเงินอนุมัติ"
  ]
}
```
"""


def _answer_key():
    recipes = {"GEN-CONC": ["V-077"], "GEN-PERIOD-END": ["V-150"], "DUP-PAY": ["V-031"], "SPLIT-LIMIT": ["V-045"],
               "FOR-BENFORD": ["V-099"], "FOR-ROUND": ["V-120"], "FOR-REPEAT": ["V-045"],
               "SOD-SAME-USER": ["U017"]}
    findings = [("document", "INV-7781", "A-R1", "2026-04"), ("vendor", "V-045", "A-R2", "2026-06"),
                ("user", "U017", "A-R3", PERIOD), ("vendor", "V-077", "A-R4", PERIOD),
                ("vendor", "V-099", "G-R4", PERIOD), ("vendor", "V-120", "G-R4", PERIOD),
                ("vendor", "V-150", "G-R2", PERIOD)]
    return {
        "recipes": recipes,
        "findings": [{"entity_type": t, "entity_id": e, "risk": r, "period": p} for t, e, r, p in findings],
        "concern_risks": ["A-R1", "A-R2"],
        "intake": {
            "sufficiency": {"A-R1": "พร้อม", "A-R2": "พร้อม"},
            "data_request": [],
            "suggested_risks": ["A-R3", "A-R4", "G-R2", "G-R4"],
            "description_conflicts": [],
        },
        "conventions": {
            "entities": "DUP-PAY and SPLIT-LIMIT / FOR-* / GEN-* name the vendor (vendor_id); SOD-SAME-USER the user "
                        "(created_by = approved_by); the duplicate finding is keyed by invoice number",
            "period": "findings of a pattern over several periods carry the latest period of the data, 2026-08; "
                      "INV-7781 carries 2026-04 and the split payments 2026-06",
            "DUP-PAY": "V-031 only: same vendor, invoice and amount within DUP.WINDOW_DAYS. V-045's 3 x 48,000 have "
                       "the same vendor and amount within the window but different invoice numbers (not a duplicate)",
            "FOR-ROUND": "V-120: 40 of 40 payments round. V-045 has 3 round payments of about 50 (6 %)",
            "FOR-BENFORD": "V-099 is the only vendor with >= FOR.BENFORD.MIN_N (1,000) payments; the whole file is "
                           "within the acceptable MAD (< 0.012)",
            "suggested_risks": "library risks the data supports (roles present) and that have a planted case, minus "
                               "the two the auditor asked for: A-R3, A-R4, G-R2, G-R4. G-R3 would need time of day "
                               "(date only), G-R1 has no planted case",
        },
        "tables": {"payments": TABLES["payments"]},
    }


def _tier(amount):
    return next(t for t in TIERS if amount <= 0.85 * t)


def _log_uniform(lo, hi, n, rng):
    v = lo * (hi / lo) ** ((np.arange(n) + 0.5) / n)
    rng.shuffle(v)
    return v


def _weekdays(month):
    days = pd.date_range(f"2026-{month:02d}-06", f"2026-{month:02d}-24", freq="D")
    return [d for d in days if d.dayofweek < 5]


def make(seed: int = SEED):
    """Return (frames, answer_key)."""
    rng = np.random.default_rng(seed)
    prng = np.random.default_rng(PLANT_SEED)
    makers = [f"U{i:03d}" for i in range(1, 31)]
    approvers = [f"M{i:03d}" for i in range(1, 11)]
    rows, used = [], set()

    def fresh(x):
        x = round(float(x), 2)
        while x in used or x % sc.TH["FOR.ROUND.UNIT"] == 0 and x not in KEEP_ROUND:
            x = round(x + 0.01, 2)
        used.add(x)
        return x

    KEEP_ROUND = set()
    inv = iter(range(10001, 10001 + N_NORMAL + N_V077 + N_V099 + 100))

    def day_in(month):
        wd = _weekdays(month)
        return wd[int(rng.integers(len(wd)))]

    def add(date, vendor, amount, maker=None, approver=None, invoice=None, limit=None, category=None):
        rows.append({"pay_date": pd.Timestamp(date).strftime("%Y-%m-%d"), "amount": float(amount),
                     "vendor_id": vendor, "invoice_no": invoice or f"INV-{next(inv)}",
                     "created_by": maker or makers[int(rng.integers(30))],
                     "approved_by": approver or approvers[int(rng.integers(10))],
                     "approval_limit": float(limit or _tier(amount)),
                     "category": category or CATEGORIES[int(rng.integers(5))]})

    # normal payments
    base = _log_uniform(1000, 100000, N_NORMAL, rng)
    for k, a in enumerate(base):
        add(day_in(k % 8 + 1), NORMAL_VENDORS[int(rng.integers(len(NORMAL_VENDORS)))], fresh(a))
    # V-077: concentration (a normal-looking vendor with many payments)
    for k, a in enumerate(_log_uniform(10000, 100000, N_V077, rng)):
        add(day_in(k % 8 + 1), "V-077", fresh(a))
    # V-099: uniform first digits (Benford anomaly), amounts 100-999
    for k in range(N_V099):
        d, u = 1 + k % 9, ((k // 9) * GOLDEN) % 1.0
        add(day_in(k % 8 + 1), "V-099", fresh((d + u) * 100))
    # SoD: 8 August payments by U017 as both maker and approver
    aug = [r for r in rows if r["pay_date"].startswith("2026-08") and r["vendor_id"] in NORMAL_VENDORS[:120]]
    for r in [aug[i] for i in sorted(rng.choice(len(aug), 8, replace=False))]:
        r["created_by"] = r["approved_by"] = "U017"

    # planted cases below use the fixed generator: identical for every seed
    def planted(amount):
        a = round(float(amount), 2)
        assert a not in used, a
        used.add(a)
        return a

    KEEP_ROUND.update({48000.0})
    add("2026-04-14", "V-031", planted(36420.50), "U005", "M002", "INV-7781", 50000)
    add("2026-04-16", "V-031", 36420.50, "U009", "M004", "INV-7781", 50000)
    for d, no in [("2026-06-16", "INV-8801"), ("2026-06-16", "INV-8802"), ("2026-06-17", "INV-8803")]:
        add(d, "V-045", 48000.0, "U012", "M003", no, 50000, "บริการ")
    used.add(48000.0)
    for a in sorted(prng.choice(np.setdiff1d(np.arange(5, 96), [48]), 40, replace=False)):
        wd = _weekdays(8)
        add(wd[int(prng.integers(len(wd)))], "V-120", planted(a * 1000.0))
    amounts150 = np.round(20000 + 3250 * np.arange(12) + prng.uniform(0, 900, 12), 2)
    for k, a in enumerate(amounts150):
        add(["2026-08-27", "2026-08-28", "2026-08-31"][k % 3], "V-150", planted(a))

    df = pd.DataFrame(rows).sort_values(["pay_date", "vendor_id", "amount", "invoice_no"], kind="stable")
    df = df.reset_index(drop=True)
    df.insert(0, "payment_id", [f"PAY-{k:06d}" for k in range(1, len(df) + 1)])
    return {"payments": df[TABLES["payments"]]}, _answer_key()


def main():
    frames, key = make()
    sc.write_dataset(sc.SAMPLES / "A", frames, key, BRIEF_MD, VARIANT_NAMES, ROLES_EN)
    p = frames["payments"]
    print(f"wrote {len(p)} payments, {p['vendor_id'].nunique()} vendors, {len(key['findings'])} expected findings "
          f"to {sc.SAMPLES / 'A'}")


if __name__ == "__main__":
    main()
