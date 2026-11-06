"""Deterministic sample data for AIDA C1, data type A (accounts payable payments).

make(seed) returns (frames, key): frames = {"payments": ...}. Only `seed` changes the normal data; the planted
cases and the answer key are the same for every seed.

Normal data design (why no check fires on it):
- 123 vendors (V-200..V-319 plus V-031, V-045, V-150) are each paid 3 times a month Jan-Aug 2026 on distinct weekdays
  of day 6-24 (none falls in a period-end window). A vendor has a stable baseline amount (stratified Benford over
  10,000-39,999 for first digits 1-3 and 4,000-9,999 for 4-9, so the largest amount stays under 44,000 and no amount
  is a modified-z outlier of the whole file); its payments stay within +-10 % of it and its monthly total follows a
  small fixed pattern, so BEH-SPIKE / BEH-VELOCITY flag nothing. Every amount is unique and none is a multiple of 1,000.
- approval_limit is the smallest tier of 10k/50k/200k/1M/5M that is at least amount / 0.85: no normal payment is
  within 90-100 % of its limit.
- Makers U001..U030 and approvers M001..M010 are different people.

Planted cases (ids in the key):
- INV-7781 (V-031) paid twice, 2026-04-14 and 04-16, 36,420.50                 -> DUP-PAY, A-R1
- V-045: 3 x 48,000 against a 50,000 limit on 2026-06-16/17 (invoices INV-8801..8803) -> SPLIT-LIMIT, FOR-REPEAT, A-R2
- maker = approver U017 on 8 payments in 2026-08                               -> SOD-SAME-USER, A-R3
- V-077: 600 payments (75 a month, Benford digits) = 12.5 % of the total               -> GEN-CONC, A-R4
- V-099: 1,050 payments of 10-99, 60 % with uniform first digits (Benford MAD about 0.04; the whole file stays
  within "acceptable")                                    -> FOR-BENFORD, G-R4
- V-120: 40 distinct multiples of 1,000 in 2026-08                             -> FOR-ROUND, G-R4
- V-150: 12 payments on 2026-08-27/28/31 (last 3 weekdays), totalling about one normal month of that vendor                     -> GEN-PERIOD-END, G-R2
Known side effects: V-045's three 48,000 payments are also multiples of 1,000 (3 of its ~27 payments, so the round
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
            "FOR-ROUND": "V-120: 40 of 40 payments round. V-045 has 3 round payments of about 27 (11 %)",
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


# Normal data is stable per vendor (so the general checks STAT-MAD / BEH-VELOCITY / BEH-SPIKE flag nothing):
# a vendor has a baseline amount, its payments stay within +-10 % of it, it is paid 3 times a month on distinct
# weekdays, and its monthly total follows the small fixed pattern E_PATTERN (the last payment of the month is the
# remainder). Baselines are stratified Benford (first digit) over three decades, capped below 50,000 so that no
# amount is a modified-z outlier of the whole file.
E_PATTERN = [0.004, -0.004, 0.002, -0.002, 0.004, -0.004, 0.002, -0.002]
NOISE = 0.10
P_LOW, P_HIGH = [0.0, 0.0, 1.0], [0.0, 1.0]  # decade weights (10^2, 10^3, 10^4) for first digit 1-3; (10^2, 10^3) for 4-9
V150_BASE = 30_000.0
PER_MONTH = 3            # payments per normal vendor and month
V077_SHARE = 0.125       # share of the total amount paid to V-077
MAX_AMOUNT = 40_000.0


def _baselines(n, rng):
    """n stratified-Benford amounts: mantissa uniform in log10 (exact first-digit law), decade by weight."""
    lg = (np.arange(n) + 0.5) / n
    rng.shuffle(lg)
    out = []
    for g in lg:
        d = int(10 ** g)
        e = rng.choice([2, 3, 4], p=P_LOW) if d <= 3 else rng.choice([2, 3], p=P_HIGH)
        out.append(10 ** (e + g))
    return np.array(out)


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
    KEEP_ROUND = {48000.0}

    def fresh(x):
        x = round(float(x), 2)
        while x in used or x % sc.TH["FOR.ROUND.UNIT"] == 0 and x not in KEEP_ROUND:
            x = round(x + 0.01, 2)
        used.add(x)
        return x

    inv = iter(range(10001, 10001 + 3 * N_NORMAL))

    def add(date, vendor, amount, maker=None, approver=None, invoice=None, limit=None, category=None):
        rows.append({"pay_date": pd.Timestamp(date).strftime("%Y-%m-%d"), "amount": float(amount),
                     "vendor_id": vendor, "invoice_no": invoice or f"INV-{next(inv)}",
                     "created_by": maker or makers[int(rng.integers(30))],
                     "approved_by": approver or approvers[int(rng.integers(10))],
                     "approval_limit": float(limit or _tier(amount)),
                     "category": category or CATEGORIES[int(rng.integers(5))]})

    def month_amounts(base, n, target, r, noise=NOISE):
        """n payments around `base` (+-noise, centred) whose sum is `target`."""
        z = r.uniform(-noise, noise, n)
        a = base * (1 + z - z.mean())
        return list(a * (target / a.sum()))

    # normal vendors: stable baseline, 6 payments a month, monthly total follows E_PATTERN
    vendors = [v for v in NORMAL_VENDORS if v != "V-150"]
    base = _baselines(len(vendors), rng)
    for v, b in zip(vendors, base):
        for m in range(1, 9):
            amts = month_amounts(b, PER_MONTH, PER_MONTH * b * (1 + E_PATTERN[m - 1]), rng)
            days = sorted(rng.choice(len(_weekdays(m)), PER_MONTH, replace=False))
            for dix, a in zip(days, amts):
                add(_weekdays(m)[dix], v, fresh(a))
    # V-150: the same stable pattern in 2026-01..07 (fixed generator); its August is the period-end case below
    for m in range(1, 8):
        amts = month_amounts(V150_BASE, PER_MONTH, PER_MONTH * V150_BASE * (1 + E_PATTERN[m - 1]), prng)
        days = sorted(prng.choice(len(_weekdays(m)), PER_MONTH, replace=False))
        for dix, a in zip(days, amts):
            add(_weekdays(m)[dix], "V-150", fresh(a), "U020", "M005")
    # V-099: mostly uniform first digits (Benford anomaly), amounts 10-99, spread evenly over the weekdays
    seen = {m: 0 for m in range(1, 9)}
    for k in range(N_V099):
        m = k % 8 + 1
        if k % 5 < 3:        # 60 % of the payments have uniform first digits ...
            j = k // 5 * 3 + k % 5
            amount = (1 + j % 9 + ((j // 9) * GOLDEN) % 1.0) * 10
        else:                # ... 40 % follow Benford, so the whole file stays within the acceptable MAD
            amount = 10 * 10 ** (((k // 5 * 2 + k % 5 - 3) * GOLDEN) % 1.0)
        wd = _weekdays(m)
        add(wd[seen[m] % len(wd)], "V-099", fresh(amount))
        seen[m] += 1
    # SoD: 8 August payments by U017 as both maker and approver
    aug = [r for r in rows if r["pay_date"].startswith("2026-08") and r["vendor_id"] in vendors[:120]]
    for r in [aug[i] for i in sorted(rng.choice(len(aug), 8, replace=False))]:
        r["created_by"] = r["approved_by"] = "U017"

    # planted cases below use the fixed generator: identical for every seed
    def planted(amount):
        a = round(float(amount), 2)
        assert a not in used, a
        used.add(a)
        return a

    add("2026-04-14", "V-031", planted(36420.50), "U005", "M002", "INV-7781", 50000)
    add("2026-04-16", "V-031", 36420.50, "U009", "M004", "INV-7781", 50000)
    for d, no in [("2026-06-16", "INV-8801"), ("2026-06-16", "INV-8802"), ("2026-06-17", "INV-8803")]:
        add(d, "V-045", 48000.0, "U012", "M003", no, 50000, "บริการ")
    used.add(48000.0)
    wd8 = _weekdays(8)
    for k, a in enumerate(sorted(prng.choice(np.setdiff1d(np.arange(1, 42), [36, 48]), 40, replace=False))):
        add(wd8[k % len(wd8)], "V-120", planted(a * 1000.0))
    # V-150 period end: 12 payments on the last 3 weekdays; their total stays inside the vendor's monthly pattern
    shape = 0.8 + 0.4 * np.arange(12) / 11 + prng.uniform(0, 0.01, 12)
    amounts150 = np.round(shape / shape.sum() * PER_MONTH * V150_BASE * 0.998, 2)
    for k, a in enumerate(amounts150):
        add(["2026-08-27", "2026-08-28", "2026-08-31"][k % 3], "V-150", planted(a))

    # V-077: concentration (V077_SHARE of the total); 75 payments a month spread evenly over the weekdays. Amounts have
    # Benford first digits (stratified mantissa); a share p4 of the digit 1-3 amounts is in the 10^4 decade, the rest in
    # 10^3, so the mean reaches the target; each month is scaled to the E_PATTERN total.
    others = sum(r["amount"] for r in rows)
    target = V077_SHARE / (1 - V077_SHARE) * others
    per_month = N_V077 // 8
    lg = (np.arange(per_month) + 0.5) / per_month
    low = np.floor(10 ** lg) <= 3
    mant = 10 ** lg
    a0 = (mant[~low].sum() * 1e3 + mant[low].sum() * 1e3) / per_month        # all in 10^3
    b0 = mant[low].sum() * 9e3 / per_month                                    # extra when a digit 1-3 amount is in 10^4
    p4 = min(1.0, max(0.0, (target / N_V077 - a0) / b0))
    n4 = int(round(p4 * low.sum()))
    for m in range(1, 9):
        order = rng.permutation(per_month)
        pick = [i for i in order if low[i]][:n4]
        e = np.full(per_month, 3.0)
        e[pick] = 4.0
        raw = mant * 10 ** e
        amts = raw * (target / 8 * (1 + E_PATTERN[m - 1]) / raw.sum())
        wd = _weekdays(m)
        for k, a in enumerate(rng.permutation(amts)):
            add(wd[k % len(wd)], "V-077", fresh(a))

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
