"""AIDA C1: brief and column-naming variants for the existing B1 data type E sample (samples/transactions.csv,
samples/accounts.csv, answer_key.json). The E data itself is produced by make_sample_data.py and is not touched."""
import json

import pandas as pd

import sample_common as sc

ROLES_EN = {"transactions": {"tx_id": "record_id", "ts": "date", "from_acct": "entity", "to_acct": "counterparty",
                             "amount": "amount", "channel": "channel", "currency": "custom:currency"},
            "accounts": {"acct_id": "entity", "opened_at": "opened_at", "account_type": "custom:account_type"}}
VARIANT_NAMES = {
    "en": {"transactions": {}, "accounts": {}},
    "th": {"transactions": {"tx_id": "รหัสรายการ", "ts": "วันเวลาทำรายการ", "from_acct": "บัญชีต้นทาง",
                            "to_acct": "บัญชีปลายทาง", "amount": "จำนวนเงิน", "currency": "สกุลเงิน",
                            "channel": "ช่องทาง"},
           "accounts": {"acct_id": "เลขที่บัญชี", "opened_at": "วันที่เปิดบัญชี", "account_type": "ประเภทบัญชี"}},
    "legacy": {"transactions": {"tx_id": "TRN_NO", "ts": "TRN_DT", "from_acct": "ACC_FR", "to_acct": "ACC_TO",
                                "amount": "AMT_X1", "currency": "CCY", "channel": "CHNL"},
               "accounts": {"acct_id": "ACC_ID", "opened_at": "OPN_DT", "account_type": "ACC_TY"}},
}

BRIEF_MD = """# หนังสือขอให้ตรวจสอบ: ธุรกรรมโอนเงินระหว่างบัญชี

เรียน ทีมวิเคราะห์ข้อมูล

ขอให้ช่วยตรวจสอบธุรกรรมโอนเงินระหว่างบัญชีของธนาคาร ช่วงเดือนมกราคมถึงสิงหาคม 2026 ไฟล์ที่ส่งมามี 2 ตาราง
คือ transactions (การโอนเงิน 1 แถวต่อ 1 รายการ) และ accounts (ข้อมูลบัญชี)

ความหมายของคอลัมน์: tx_id คือรหัสรายการ ไม่ซ้ำกัน, ts คือวันเวลาที่ทำรายการ, from_acct คือบัญชีต้นทาง (ผู้โอน),
to_acct คือบัญชีปลายทาง (ผู้รับ), amount คือจำนวนเงินที่โอน (บาท), currency คือสกุลเงิน, channel คือช่องทางทำรายการ
ส่วนตาราง accounts มี acct_id คือเลขที่บัญชี, opened_at คือวันที่เปิดบัญชี และ account_type คือประเภทบัญชี

เงื่อนไข: ทุกรายการเป็นการโอนที่สำเร็จแล้ว ไม่ต้องตัดรายการใดออก

สิ่งที่กังวล:
1. การเคลื่อนย้ายเงินผิดปกติ เช่น ยอดโดดเด่น ธุรกรรมถี่ผิดปกติ นอกเวลาทำการ เงินวนกลับหรือส่งต่อเป็นทอด ๆ
2. บัญชีที่มีรูปแบบรับแล้วส่งต่อเงินอย่างรวดเร็ว โดยเฉพาะบัญชีที่เปิดใหม่
3. ธุรกรรมระหว่างกลุ่มบัญชีที่เชื่อมโยงกันเป็นเครือข่าย
4. ความผิดปกติของคู่ค้า เช่น โอนไปบัญชีใหม่ด้วยยอดสูงผิดปกติ

```json
{
  "context": "ธุรกรรมโอนเงินระหว่างบัญชี ม.ค.–ส.ค. 2026 (transactions และ accounts เชื่อมด้วยเลขที่บัญชี)",
  "columns": {
    "tx_id": "รหัสรายการ ไม่ซ้ำกัน",
    "ts": "วันเวลาที่ทำรายการ",
    "from_acct": "บัญชีต้นทาง (ผู้โอน)",
    "to_acct": "บัญชีปลายทาง (ผู้รับ)",
    "amount": "จำนวนเงินที่โอน (บาท)",
    "currency": "สกุลเงิน",
    "channel": "ช่องทางทำรายการ",
    "acct_id": "เลขที่บัญชี",
    "opened_at": "วันที่เปิดบัญชี",
    "account_type": "ประเภทบัญชี"
  },
  "conditions": [
    "ทุกรายการเป็นการโอนที่สำเร็จแล้ว ไม่ต้องตัดรายการใดออก"
  ],
  "concerns": [
    "การเคลื่อนย้ายเงินผิดปกติ เช่น ยอดโดดเด่น ธุรกรรมถี่ผิดปกติ นอกเวลาทำการ เงินวนกลับหรือส่งต่อเป็นทอด ๆ",
    "บัญชีที่มีรูปแบบรับแล้วส่งต่อเงินอย่างรวดเร็ว โดยเฉพาะบัญชีที่เปิดใหม่",
    "ธุรกรรมระหว่างกลุ่มบัญชีที่เชื่อมโยงกันเป็นเครือข่าย",
    "ความผิดปกติของคู่ค้า เช่น โอนไปบัญชีใหม่ด้วยยอดสูงผิดปกติ"
  ]
}
```

หมายเหตุสำหรับผู้พัฒนา (ไม่ใช่ส่วนของ brief): ความกังวล 1-4 ตรงกับความเสี่ยง R1-R4 ของ B1 ตามลำดับ
"""


def main():
    out = sc.SAMPLES / "E"
    frames = {t: pd.read_csv(sc.SAMPLES / f"{t}.csv", dtype=str, keep_default_na=False)
              for t in ("transactions", "accounts")}
    out.mkdir(parents=True, exist_ok=True)
    (out / "brief.md").write_text(BRIEF_MD, encoding="utf-8")
    brief = sc.load_brief(out / "brief.md")
    vdir = out / "variants"
    for v in sc.VARIANTS:
        names = VARIANT_NAMES[v]
        (vdir / v).mkdir(parents=True, exist_ok=True)
        for t, df in sc.rename_frames(frames, names).items():
            df.to_csv(vdir / v / f"{t}.csv", index=False)
        (vdir / v / "brief.json").write_text(json.dumps(sc.variant_brief(brief, names), ensure_ascii=False, indent=2)
                                             + "\n", encoding="utf-8")
        (vdir / f"roles_{v}.json").write_text(json.dumps(sc.variant_roles(ROLES_EN, names), ensure_ascii=False,
                                                         indent=2) + "\n", encoding="utf-8")
    print(f"wrote E brief and {len(sc.VARIANTS)} variants to {out}")


if __name__ == "__main__":
    main()
