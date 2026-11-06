"""Deterministic sample data for AIDA C1, data type C (loan instalment payments).

make(seed) returns (frames, key): frames = {"payments": ..., "contracts": ...}. Only `seed` changes the normal
data; the planted cases and the answer key are the same for every seed.

Normal data design (why no check fires on it):
- 200 contracts HP-0001..HP-0200, one borrower each, 8 months (2026-01..08), one instalment a month. Instalments are
  stratified Benford (1,000-39,999, see _instalments), so the first digits follow Benford's law and no amount is
  a modified-z outlier; an instalment is the same every month, so the monthly total of a borrower is flat (no
  spike), and no amount is round or repeats three times for the same borrower in a month.
- Due day 10-14. A normal payment is made 4-6 days before or 4-8 days after the due day (never 0-2 days before),
  so every payment date falls on day 4-24 of its month: outside every period-end window.
- The payer is the borrower, except 10 contracts paid by their own third party (TP01..TP10): one contract each.
- Refunds (33 rows = 2 % of the rows) are negative partial amounts (30 % of the instalment) 9-10 days after the due
  day, so they never equal a payment. Cancelled rows (status C, 24) are single rows of their contract-month.

Planted cases (ids in the key):
- PY01 pays 6 contracts of other borrowers (HP-0101..0106) in 2026-08            -> PAYER-MULTI, C-R1
- HP-0042 is paid 1-2 days before due in all 8 periods                           -> DUE-NEAR, C-R2
- HP-0150 is paid twice for 2026-05 (4 and 5 days before due, same amount)       -> DUP-PAY, C-R3
- negative refunds and status C rows are in the data to be understood (conflict with "ยอดชำระสุทธิ"), not findings
"""
import numpy as np
import pandas as pd

import sample_common as sc

SEED = 20261106
PLANT_SEED = 1106
N = 200
MONTHS = range(1, 9)
PERIOD = "2026-08"
N_CANCEL, N_REFUND = 24, 33
THIRD_PARTY = [11, 23, 37, 51, 64, 78, 89, 120, 133, 177]
SPECIAL = {42, 150, *range(101, 107)}

TABLES = {"payments": ["payment_id", "pay_date", "pay_amount", "borrower_id", "payer_id", "contract_id",
                       "due_date", "status"],
          "contracts": ["contract_id", "borrower_id", "opened_at", "product"]}
ROLES_EN = {"payments": {"payment_id": "record_id", "pay_date": "date", "pay_amount": "amount",
                         "borrower_id": "entity", "payer_id": "counterparty", "contract_id": "contract",
                         "due_date": "due_date", "status": "custom:status"},
            "contracts": {"borrower_id": "entity", "opened_at": "opened_at", "product": "custom:product"}}
VARIANT_NAMES = {
    "en": {"payments": {}, "contracts": {}},
    "th": {"payments": {"payment_id": "รหัสรายการชำระ", "pay_date": "วันที่ชำระ", "pay_amount": "ยอดชำระ",
                        "borrower_id": "รหัสผู้กู้", "payer_id": "รหัสผู้ชำระ", "contract_id": "เลขที่สัญญา",
                        "due_date": "วันครบกำหนด", "status": "สถานะ"},
           "contracts": {"contract_id": "เลขที่สัญญา", "borrower_id": "รหัสผู้กู้", "opened_at": "วันที่ทำสัญญา",
                         "product": "ประเภทสินเชื่อ"}},
    "legacy": {"payments": {"payment_id": "COL1", "pay_date": "COL2", "pay_amount": "AMT_X1", "borrower_id": "COL4",
                            "payer_id": "COL5", "contract_id": "COL6", "due_date": "COL7", "status": "STS"},
               "contracts": {"contract_id": "COL6", "borrower_id": "COL4", "opened_at": "COL9",
                             "product": "COL10"}},
}

BRIEF_MD = """# หนังสือขอให้ตรวจสอบ: การรับชำระค่างวดสินเชื่อเช่าซื้อ

เรียน ทีมวิเคราะห์ข้อมูล

ขอให้ช่วยตรวจสอบข้อมูลการรับชำระค่างวดของสินเชื่อเช่าซื้อ ช่วงเดือนมกราคมถึงสิงหาคม 2026 ไฟล์ที่ส่งมามี 2 ตาราง
คือ payments (รายการรับชำระ 1 แถวต่อ 1 การชำระ) และ contracts (ข้อมูลสัญญาและผู้กู้) เชื่อมกันด้วยเลขที่สัญญา

ความหมายของคอลัมน์ที่ผมทราบ: payment_id คือรหัสรายการชำระ ไม่ซ้ำกัน, pay_date คือวันที่รับชำระ, pay_amount
คือยอดชำระสุทธิ ของรายการนั้น, borrower_id คือรหัสผู้กู้ตามสัญญา, payer_id คือรหัสของผู้ชำระเงินจริง ซึ่งส่วนใหญ่คือผู้กู้เอง,
contract_id คือเลขที่สัญญา, due_date คือวันครบกำหนดชำระของงวดนั้น, status คือสถานะรายการ P = บันทึกแล้ว และ C = ยกเลิก
ส่วนตาราง contracts มี opened_at คือวันที่ทำสัญญา ส่วนคอลัมน์ product ผมยังไม่แน่ใจความหมาย

เงื่อนไข: ให้ตัดรายการที่ status = C (ยกเลิก) ออกก่อนวิเคราะห์ทุกครั้ง และดูเฉพาะรายการระหว่าง 1 ม.ค. ถึง 31 ส.ค. 2026

สิ่งที่กังวล:
1. มีผู้ชำระรายเดียวที่ชำระแทนผู้กู้หลายสัญญา ซึ่งอาจเป็นการชำระแทนที่ไม่ได้เปิดเผยความสัมพันธ์
2. ลูกหนี้บางรายชำระก่อนวันครบกำหนดเพียง 1-2 วันแทบทุกงวด ซึ่งอาจเป็นการตกแต่งสถานะค้างชำระ
3. บัญชีผู้ชำระอาจถูกใช้รับโอนเงินผิดปกติ

```json
{
  "context": "สินเชื่อเช่าซื้อ — ข้อมูลรับชำระค่างวด ม.ค.–ส.ค. 2026 (payments และ contracts เชื่อมด้วยเลขที่สัญญา)",
  "columns": {
    "payment_id": "รหัสรายการชำระ ไม่ซ้ำกัน",
    "pay_date": "วันที่รับชำระ",
    "pay_amount": "ยอดชำระสุทธิ ของรายการนั้น",
    "borrower_id": "รหัสผู้กู้ตามสัญญา",
    "payer_id": "รหัสผู้ชำระเงินจริง ส่วนใหญ่คือผู้กู้เอง",
    "contract_id": "เลขที่สัญญา",
    "due_date": "วันครบกำหนดชำระของงวดนั้น",
    "status": "สถานะรายการ P = บันทึกแล้ว, C = ยกเลิก",
    "opened_at": "วันที่ทำสัญญา"
  },
  "conditions": [
    "ตัดรายการ status = C (ยกเลิก) ออกก่อนวิเคราะห์",
    "ดูเฉพาะรายการ 1 ม.ค. – 31 ส.ค. 2026"
  ],
  "concerns": [
    "มีผู้ชำระรายเดียวที่ชำระแทนผู้กู้หลายสัญญา ซึ่งอาจเป็นการชำระแทนที่ไม่ได้เปิดเผยความสัมพันธ์",
    "ลูกหนี้บางรายชำระก่อนวันครบกำหนดเพียง 1-2 วันแทบทุกงวด ซึ่งอาจเป็นการตกแต่งสถานะค้างชำระ",
    "บัญชีผู้ชำระอาจถูกใช้รับโอนเงินผิดปกติ"
  ]
}
```
"""


def _answer_key():
    recipes = {"GEN-CONC": [], "GEN-PERIOD-END": [], "DUP-PAY": ["HP-0150"], "FOR-BENFORD": [], "FOR-ROUND": [],
               "FOR-REPEAT": [], "DUE-NEAR": ["HP-0042"], "PAYER-MULTI": ["PY01"]}
    findings = [("payer", "PY01", "C-R1", PERIOD), ("contract", "HP-0042", "C-R2", PERIOD),
                ("contract", "HP-0150", "C-R3", "2026-05")]
    return {
        "recipes": recipes,
        "findings": [{"entity_type": t, "entity_id": e, "risk": r, "period": p} for t, e, r, p in findings],
        "concern_risks": ["C-R1", "C-R2", "R1"],
        "intake": {
            "sufficiency": {"C-R1": "พร้อม", "C-R2": "พร้อม", "R1": "ไม่พอ"},
            "data_request": ["รายการเงินฝากและโอนเงินของบัญชีผู้ชำระ (รหัสรายการ, วันเวลา, บัญชีต้นทาง, บัญชีปลายทาง, "
                             "ยอดเงิน) เพื่อดูการรับโอนและส่งต่อเงิน"],
            "suggested_risks": ["C-R3"],
            "description_conflicts": ["pay_amount"],
        },
        "conventions": {
            "entities": "DUP-PAY and DUE-NEAR name the contract (contract_id), PAYER-MULTI the payer (payer_id)",
            "period": "findings of a pattern over several periods carry the latest period of the data, 2026-08; "
                      "the duplicate payment carries its own month, 2026-05",
            "status": "rows with status C are cancelled and are excluded by the brief (conditions); "
                      "none of them takes part in a planted case",
            "refunds": "negative pay_amount rows are refunds (about 2 % of the rows); they are not findings, "
                       "they are why \"ยอดชำระสุทธิ\" conflicts with the data",
            "suggested_risks": "C-R3 is the only library risk with a planted case that the auditor did not request "
                               "(duplicate payment + refunds); G-R3 would need time of day, which payments lack; "
                               "G-R1/G-R2/G-R4 have no planted case in C",
            "concern_risks": "concern 3 (payer accounts receiving unusual transfers) is a data type E risk, R1; it "
                             "needs deposit/transfer transactions the file does not have, hence \"ไม่พอ\" and a data "
                             "request",
            "benford": "the instalments are stratified Benford (1,000-39,999) so first digits follow Benford (MAD < 0.006) and no amount is a modified-z outlier",
        },
        "tables": {"payments": TABLES["payments"], "contracts": TABLES["contracts"]},
    }


def _fix_round(values):
    values = np.array(values, dtype=float)
    while (values % 1000 == 0).any():
        values[values % 1000 == 0] += 0.37
    return values


def _instalments(n, rng):
    """Stratified-Benford instalments (first digit follows the law exactly): digits 1-3 in 10,000-39,999, digits
    4-9 in 1,000-9,999. The largest is under 40,000, so no instalment is a modified-z outlier of the whole file."""
    lg = (np.arange(n) + 0.5) / n
    rng.shuffle(lg)
    return np.array([10 ** ((4 if int(10 ** g) <= 3 else 3) + g) for g in lg])


def make(seed: int = SEED):
    """Return (frames, answer_key)."""
    rng = np.random.default_rng(seed)
    inst = _fix_round(np.round(_instalments(N, rng), 2))
    due_day = rng.integers(10, 15, N)
    cids = [f"HP-{i:04d}" for i in range(1, N + 1)]
    third = {f"HP-{i:04d}": f"TP{k:02d}" for k, i in enumerate(THIRD_PARTY, start=1)}
    cells = [(i, m) for i in range(1, N + 1) for m in MONTHS]
    eligible = [c for c in cells if c[0] not in SPECIAL]
    pick = rng.permutation(len(eligible))
    cancelled = {eligible[k] for k in pick[:N_CANCEL]}
    refunded = [eligible[k] for k in pick[N_CANCEL:N_CANCEL + N_REFUND]]

    rows = []

    def add(i, m, pay, amount, status="P", payer=None):
        cid = cids[i - 1]
        due = pd.Timestamp(2026, m, int(due_day[i - 1]))
        rows.append({"pay_date": pay.strftime("%Y-%m-%d"), "pay_amount": round(float(amount), 2),
                     "borrower_id": f"B{i:04d}", "payer_id": payer or third.get(cid, f"B{i:04d}"),
                     "contract_id": cid, "due_date": due.strftime("%Y-%m-%d"), "status": status})

    for i, m in cells:
        due = pd.Timestamp(2026, m, int(due_day[i - 1]))
        amount = inst[i - 1]
        if i == 42:                                          # paid 1-2 days before due in every period
            add(i, m, due - pd.Timedelta(days=int(rng.integers(1, 3))), amount)
        elif i == 150 and m == 5:                            # paid twice, 5 and 4 days before due
            add(i, m, due - pd.Timedelta(days=5), amount)
            add(i, m, due - pd.Timedelta(days=4), amount)
        else:
            if rng.random() < 0.5:
                pay = due - pd.Timedelta(days=int(rng.integers(4, 7)))
            else:
                pay = due + pd.Timedelta(days=int(rng.integers(4, 9)))
            payer = "PY01" if (101 <= i <= 106 and m == 8) else None
            add(i, m, pay, amount, "C" if (i, m) in cancelled else "P", payer)
    for i, m in refunded:
        due = pd.Timestamp(2026, m, int(due_day[i - 1]))
        add(i, m, due + pd.Timedelta(days=int(rng.integers(9, 11))), -0.3 * inst[i - 1])

    pay = pd.DataFrame(rows).sort_values(["pay_date", "contract_id", "pay_amount"], kind="stable")
    pay = pay.reset_index(drop=True)
    pay.insert(0, "payment_id", [f"PM-{k:06d}" for k in range(1, len(pay) + 1)])
    pay = pay[TABLES["payments"]]

    crng = np.random.default_rng(PLANT_SEED)
    contracts = pd.DataFrame({
        "contract_id": cids, "borrower_id": [f"B{i:04d}" for i in range(1, N + 1)],
        "opened_at": [(pd.Timestamp("2023-01-01") + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d")
                      for d in crng.integers(0, 1095, N)],
        "product": crng.choice(["HP", "PL", "CR"], N, p=[0.6, 0.25, 0.15])})
    return {"payments": pay, "contracts": contracts[TABLES["contracts"]]}, _answer_key()


def main():
    frames, key = make()
    sc.write_dataset(sc.SAMPLES / "C", frames, key, BRIEF_MD, VARIANT_NAMES, ROLES_EN)
    p = frames["payments"]
    print(f"wrote {len(p)} payments ({(p['pay_amount'] < 0).sum()} refunds, {(p['status'] == 'C').sum()} cancelled), "
          f"{len(frames['contracts'])} contracts, {len(key['findings'])} expected findings to {sc.SAMPLES / 'C'}")


if __name__ == "__main__":
    main()
