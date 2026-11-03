# AIDA-19 · Pipeline Recipes (การ์ดเตรียมข้อมูล, Evidence builder, รวมผล และ Output)
> ไฟล์: AIDA-19 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: การ์ด CORE-EVIDENCE สร้างแถว Evidence อย่างไร, กฎกลางที่ทุกการ์ดวิเคราะห์ใช้ร่วมกันคืออะไร (ตัดรายการโอนเข้าบัญชีตัวเอง / ยอด ≤ 0), ต้องรันการ์ดในไฟล์นี้ก่อนการ์ดใน AIDA-18 หรือไม่

## สรุปสั้น
ไฟล์นี้เก็บการ์ด (recipe) ระดับ pipeline ที่ Code Interpreter รันตามลำดับในข้อ 7 ของ Instructions — **ต้องรันการ์ดในไฟล์นี้ก่อนการ์ดวิเคราะห์ใน AIDA-18** เพราะการ์ดวิเคราะห์ทุกใบเรียกใช้ฟังก์ชันจาก `CORE-EVIDENCE`
ตอนนี้มีเฉพาะ `CORE-EVIDENCE`; การ์ด PREP-MAP, PROF-PROFILE, GATE-CAPABILITY, UNIFY-FINDINGS, ASSESS-CMP, OUT-WORKBOOK, OUT-NETWORK-CSV, OUT-DASHBOARD และ LOG-RUN จะเพิ่มต่อท้ายไฟล์นี้
คอลัมน์ Evidence เป็นไปตาม Schema ใน AIDA-17 และทุกแถวบันทึก Registry version จาก AIDA-14

## การ์ด Evidence builder

### CORE-EVIDENCE
ฟังก์ชันกลางที่การ์ดวิเคราะห์ทุกใบใช้: `clean_tx` (ตัดรายการโอนเข้าบัญชีตัวเองและยอด ≤ 0, แปลง ts, เพิ่ม period YYYY-MM), `beyond_baseline` (เทียบกับ baseline ของบัญชีเดียวกัน), `one_per_month` (1 แถวต่อบัญชีต่อเดือน) และ `evidence_rows` (สร้างแถวตาม Evidence schema)
baseline ที่คงที่ (std = 0) ใช้ค่า √mean เป็นค่าเบี่ยงเบนขั้นต่ำ เพื่อไม่ให้การเพิ่มขึ้นเล็กน้อยกลายเป็นสัญญาณ

```python
# RECIPE CORE-EVIDENCE v1.0 | Skill: - | Risk: -
# Registry: REGISTRY.VERSION | Input: found(entity_id, period, metric, value, threshold, explanation, record_refs)
EVIDENCE_COLUMNS = ["evidence_id", "run_id", "recipe_id", "recipe_version", "skill_family",
                    "entity_type", "entity_id", "risk", "period", "metric", "value", "threshold",
                    "registry_key", "registry_version", "explanation", "record_refs", "data_ref"]
def clean_tx(tx: pd.DataFrame) -> pd.DataFrame:
    t = tx.copy()
    t["ts"] = pd.to_datetime(t["ts"])
    t["amount"] = pd.to_numeric(t["amount"], errors="coerce")
    t["tx_id"] = t["tx_id"].astype(str)
    t = t[(t["from_acct"] != t["to_acct"]) & (t["amount"] > 0)]
    return t.assign(period=t["ts"].dt.strftime("%Y-%m")).sort_values("ts", kind="mergesort")
def beyond_baseline(d: pd.DataFrame, acct: str, col: str, need: int, k: float):
    # d sorted by time within acct; baseline = this account's earlier rows only
    by = d.groupby(acct)[col].shift().groupby(d[acct])
    n = by.transform(lambda s: s.expanding().count())
    mu = by.transform(lambda s: s.expanding().mean())
    sd = by.transform(lambda s: s.expanding().std()).fillna(0)
    thr = mu + k * np.maximum(sd, np.sqrt(mu))
    return (n >= need) & (d[col] > thr), thr
def one_per_month(f: pd.DataFrame) -> pd.DataFrame:
    if f.empty:
        return f
    keys = ["entity_id", "period"]
    refs = f.groupby(keys)["record_refs"].agg(lambda s: sorted({str(x) for r in s for x in r}))
    top = f.sort_values("value", ascending=False, kind="mergesort").drop_duplicates(keys)
    return top.drop(columns="record_refs").merge(refs.reset_index(), on=keys)
def evidence_rows(recipe_id: str, version: str, skill_family: str, risk: str,
                  registry_key: str, found: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if found is None or len(found) == 0:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    run, f = cfg["_RUN"], found.reset_index(drop=True)
    etype = f["entity_type"].fillna("account") if "entity_type" in f.columns else "account"
    return f.assign(
        evidence_id=[f"{recipe_id}-{run['run_id']}-{i + 1}" for i in range(len(f))],
        run_id=run["run_id"], recipe_id=recipe_id, recipe_version=version,
        skill_family=skill_family, entity_type=etype, risk=risk, registry_key=registry_key,
        registry_version=cfg["REGISTRY.VERSION"], data_ref=run["data_ref"],
        record_refs=[[str(x) for x in r] for r in f["record_refs"]])[EVIDENCE_COLUMNS]
def core_evidence(tables: dict = None, cfg: dict = None) -> pd.DataFrame:
    return pd.DataFrame(columns=EVIDENCE_COLUMNS)  # empty Evidence frame
```

## ข้อห้าม (Guardrails)
- รันการ์ดตามที่เขียนไว้ทุกตัวอักษร (verbatim) ห้ามแก้โค้ด ห้ามเขียนการ์ดขึ้นเอง และต้องรัน CORE-EVIDENCE ก่อนการ์ดใน AIDA-18
- ถ้าดึงการ์ดมาไม่ครบ (โค้ดถูกตัด, ไม่มีบรรทัดปิด) ห้ามรันส่วนที่ได้มา — Skip การ์ดนั้นพร้อม reason "ดึง recipe ไม่ครบ"
- ผลของการ์ดเป็นสัญญาณให้ตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุปว่าบัญชีหรือบุคคลกระทำผิด — ใช้ถ้อยคำตาม AIDA-11
- ห้ามแต่งค่า `tx_id` หรือ `data_ref` ที่ไม่มีในข้อมูลจริง และห้ามเปลี่ยนคอลัมน์ Evidence นอก Schema ใน AIDA-17

## ไฟล์ที่เกี่ยวข้อง
- AIDA-18 Analysis Recipes (การ์ดวิเคราะห์ที่เรียกใช้ CORE-EVIDENCE)
- AIDA-17 Data & Evidence Schema (คอลัมน์ Evidence)
- AIDA-14 Configuration Registry (Machine Config, `REGISTRY.VERSION = 1.1`)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ใช้)
- AIDA-13 Traceability & Governance (record_refs + data_ref)
