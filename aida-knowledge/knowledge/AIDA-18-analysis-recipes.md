# AIDA-18 · Analysis Recipes (การ์ดวิเคราะห์ธุรกรรมระดับบัญชีและเครือข่าย)
> ไฟล์: AIDA-18 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: การ์ด STAT-MAD / BEH-VELOCITY / BEH-SPIKE / TEMP-OFFHOURS / NET-CYCLE / NET-FUNNEL คำนวณอะไร ใช้เกณฑ์ใดจาก AIDA-14 และให้ Evidence แบบไหน, ต้องโหลดอะไรก่อนรันการ์ด

## สรุปสั้น
ไฟล์นี้เก็บการ์ดวิเคราะห์ (recipe) ที่ Code Interpreter รันตามที่เขียนไว้ทุกตัวอักษร การ์ดทุกใบรับ `(tables, cfg)` และคืน DataFrame ตาม Evidence schema ใน AIDA-17 (DataFrame ว่าง = ไม่พบสัญญาณ)
**ต้องรันการ์ด CORE-EVIDENCE ใน AIDA-19 ก่อน** เพราะทุกการ์ดเรียก `clean_tx`, `one_per_month` และ `evidence_rows` จากการ์ดนั้น
ทุกการ์ดตัดรายการโอนเข้าบัญชีตัวเองและยอด ≤ 0 ออกก่อนวิเคราะห์, ใช้ period แบบ YYYY-MM (1 แถวต่อบัญชีต่อเดือน), อ่านเกณฑ์จาก `cfg` (Machine Config ใน AIDA-14) เท่านั้น และการ์ดในไฟล์นี้ทั้งหมดให้ Evidence ความเสี่ยง R1
การ์ด STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS ระบุบัญชีผู้โอน (from_acct); NET-CYCLE ระบุทุกบัญชีในวง; NET-FUNNEL ระบุบัญชีที่รับเงินแล้วส่งต่อ

## การ์ด Statistical (5.1)

### STAT-MAD
หารายการโอนที่ยอดเงินโดดเด่นจากรายการอื่นในช่องทาง (channel) เดียวกันด้วย Modified Z-Score (อิง Median/MAD) ถ้าไม่มีคอลัมน์ channel ใช้ทั้งชุด
กลุ่มที่มีรายการน้อยกว่า GATE.SAMPLE.MIN หรือ MAD = 0 จะไม่คำนวณ; เกณฑ์อ้าง `STAT.MAD.THRESHOLD = 3.5`

```python
# RECIPE STAT-MAD v1.0 | Skill: 5.1 Statistical | Risk: R1
# Registry: STAT.MAD.THRESHOLD, GATE.SAMPLE.MIN | Input: transactions(tx_id, ts, from_acct, to_acct, amount, channel)
def stat_mad(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    lim, n_min = cfg["STAT.MAD.THRESHOLD"], cfg["GATE.SAMPLE.MIN"]
    if "channel" in t.columns:
        t["grp"] = "ช่องทาง " + t["channel"].fillna("ไม่ระบุ").astype(str)
    else:
        t["grp"] = "ทั้งชุดข้อมูล"
    parts = []
    for _, g in t.groupby("grp"):
        med = g["amount"].median()
        mad = (g["amount"] - med).abs().median()
        if len(g) < n_min or mad == 0:
            continue
        z = (0.6745 * (g["amount"] - med) / mad).abs()  # 0.6745 = Modified Z constant
        parts.append(g.assign(z=z)[z > lim])
    hit = pd.concat(parts) if parts else t.iloc[0:0].assign(z=0.0)
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "modified_z_amount", "value": hit["z"].round(2), "threshold": lim,
        "explanation": [
            f"รายการ {i} ยอด {a:,.2f} มี Modified Z-Score {z:.2f} ใน{g} สูงกว่าเกณฑ์ {lim} "
            f"(STAT.MAD.THRESHOLD ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for i, a, z, g in zip(hit["tx_id"], hit["amount"], hit["z"], hit["grp"])],
        "record_refs": [[i] for i in hit["tx_id"]]})
    return evidence_rows("STAT-MAD", "1.0", "5.1 Statistical", "R1",
                         "STAT.MAD.THRESHOLD", one_per_month(found), cfg)
```

## การ์ด Behavioral (5.3) และ Temporal (5.4)

### BEH-VELOCITY
นับจำนวนรายการโอนออกต่อวันของแต่ละบัญชี แล้วเทียบกับ baseline ของบัญชีเดียวกัน (วันที่มีรายการก่อนหน้าทั้งหมด ต้องมีอย่างน้อย velocity_days วัน)
เป็นสัญญาณเมื่อจำนวนต่อวัน > mean + BEH.DEVIATION × max(std, √mean) ของ baseline (√mean กันกรณี baseline คงที่); เกณฑ์อ้าง `BEH.DEVIATION = 3σ`

```python
# RECIPE BEH-VELOCITY v1.0 | Skill: 5.3 Behavioral | Risk: R1
# Registry: BEH.BASELINE.MIN_PERIODS, BEH.DEVIATION | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def beh_velocity(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    need = cfg["BEH.BASELINE.MIN_PERIODS"]["velocity_days"]
    k = cfg["BEH.DEVIATION"]
    d = (t.assign(day=t["ts"].dt.strftime("%Y-%m-%d"))
         .groupby(["from_acct", "day", "period"])
         .agg(n=("tx_id", "size"), refs=("tx_id", list)).reset_index())
    flag, thr = beyond_baseline(d, "from_acct", "n", need, k)
    hit = d.assign(thr=thr)[flag]
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "tx_per_day", "value": hit["n"], "threshold": hit["thr"].round(2),
        "explanation": [
            f"วันที่ {dy} มีรายการโอนออก {n} รายการ สูงกว่า baseline ของบัญชีเดียวกัน "
            f"(mean + {k} × std = {th:.2f}; BEH.DEVIATION และ BEH.BASELINE.MIN_PERIODS "
            f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for dy, n, th in zip(hit["day"], hit["n"], hit["thr"])],
        "record_refs": hit["refs"]})
    return evidence_rows("BEH-VELOCITY", "1.0", "5.3 Behavioral", "R1",
                         "BEH.DEVIATION", one_per_month(found), cfg)
```

### BEH-SPIKE
รวมยอดโอนออกต่อเดือนของแต่ละบัญชี แล้วเทียบกับ baseline ของบัญชีเดียวกัน (เดือนที่มีรายการก่อนหน้าทั้งหมด ต้องมีอย่างน้อย spike_months เดือน)
เป็นสัญญาณเมื่อยอดเดือนนั้น > mean + BEH.DEVIATION × max(std, √mean) ของ baseline; บัญชีที่ประวัติไม่ถึงเกณฑ์ไม่ถูกประเมิน

```python
# RECIPE BEH-SPIKE v1.0 | Skill: 5.3 Behavioral | Risk: R1
# Registry: BEH.BASELINE.MIN_PERIODS, BEH.DEVIATION | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def beh_spike(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    need = cfg["BEH.BASELINE.MIN_PERIODS"]["spike_months"]
    k = cfg["BEH.DEVIATION"]
    d = (t.groupby(["from_acct", "period"])
         .agg(amt=("amount", "sum"), refs=("tx_id", list)).reset_index())
    flag, thr = beyond_baseline(d, "from_acct", "amt", need, k)
    hit = d.assign(thr=thr)[flag]
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "amount_per_month", "value": hit["amt"].round(2),
        "threshold": hit["thr"].round(2),
        "explanation": [
            f"ยอดโอนออกเดือน {p} รวม {a:,.2f} สูงกว่า baseline รายเดือนของบัญชีเดียวกัน "
            f"(mean + {k} × std = {th:,.2f}; BEH.DEVIATION และ BEH.BASELINE.MIN_PERIODS "
            f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, a, th in zip(hit["period"], hit["amt"], hit["thr"])],
        "record_refs": hit["refs"]})
    return evidence_rows("BEH-SPIKE", "1.0", "5.3 Behavioral", "R1",
                         "BEH.DEVIATION", one_per_month(found), cfg)
```

### TEMP-OFFHOURS
นับรายการโอนออกนอกเวลาทำการ (ก่อนเวลา start หรือตั้งแต่เวลา end) และวันเสาร์-อาทิตย์ (ถ้า weekend = true) ต่อบัญชีต่อเดือน
ไม่มีปฏิทินวันหยุดนักขัตฤกษ์ในข้อมูล จึงนับเฉพาะวันเสาร์-อาทิตย์; เกณฑ์อ้าง `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด`

```python
# RECIPE TEMP-OFFHOURS v1.0 | Skill: 5.4 Temporal | Risk: R1
# Registry: TEMP.OFF_HOURS | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def temp_offhours(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    oh = cfg["TEMP.OFF_HOURS"]
    hhmm = t["ts"].dt.strftime("%H:%M")
    off = (hhmm < oh["start"]) | (hhmm >= oh["end"])
    rule = f"นอกเวลา {oh['start']}–{oh['end']}"
    if oh["weekend"]:
        off = off | (t["ts"].dt.dayofweek >= 5)  # 5, 6 = Saturday, Sunday
        rule += " หรือวันเสาร์-อาทิตย์"
    d = (t[off].groupby(["from_acct", "period"])
         .agg(n=("tx_id", "size"), refs=("tx_id", list)).reset_index())
    found = pd.DataFrame({
        "entity_id": d["from_acct"], "period": d["period"],
        "metric": "offhours_tx_count", "value": d["n"], "threshold": rule,
        "explanation": [
            f"เดือน {p} มีรายการโอนออก {n} รายการ{rule} "
            f"(TEMP.OFF_HOURS ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, n in zip(d["period"], d["n"])],
        "record_refs": d["refs"]})
    return evidence_rows("TEMP-OFFHOURS", "1.0", "5.4 Temporal", "R1",
                         "TEMP.OFF_HOURS", found, cfg)
```

## การ์ด Network (5.9)

### NET-CYCLE
หาวงเงินหมุนวน (A→B→…→A) ยาว min_len–max_len ทอด ด้วย DFS แบบวนซ้ำ (ไม่ใช้ networkx) โดยแต่ละทอดต้องเกิดไม่ก่อนทอดก่อนหน้า และทุกทอดอยู่ภายใน days วันนับจากทอดแรก
ทุกบัญชีในวงได้ Evidence 1 แถวต่อเดือน (เดือนของทอดแรก); เกณฑ์อ้าง `NET.CYCLE = 2–5 ทอด ภายใน 30 วัน`

```python
# RECIPE NET-CYCLE v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.CYCLE | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def net_cycle(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    c = cfg["NET.CYCLE"]
    win = pd.Timedelta(days=c["days"])
    out = {a: list(zip(g["ts"], g["to_acct"], g["tx_id"])) for a, g in t.groupby("from_acct")}
    rows = []
    for t0, a0, b0, x0, p0 in zip(t["ts"], t["from_acct"], t["to_acct"], t["tx_id"], t["period"]):
        stack = [(b0, t0, [a0, b0], [x0])]
        while stack:
            node, ts, path, refs = stack.pop()
            for nts, nxt, ntx in out.get(node, []):
                if nts < ts or nts - t0 > win:
                    continue
                if nxt == path[0] and len(path) >= c["min_len"]:
                    loop = " → ".join(path + [nxt])
                    rows += [{"entity_id": a, "period": p0, "metric": "cycle_length",
                              "value": len(path), "threshold": c["max_len"],
                              "explanation": f"บัญชีอยู่ในวงเงินหมุนวน {loop} ({len(path)} ทอด "
                              f"ภายใน {c['days']} วัน; NET.CYCLE {c['min_len']}–{c['max_len']} ทอด "
                              f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม",
                              "record_refs": refs + [ntx]} for a in path]
                elif nxt not in path and len(path) < c["max_len"]:
                    stack.append((nxt, nts, path + [nxt], refs + [ntx]))
    found = one_per_month(pd.DataFrame(rows, columns=["entity_id", "period", "metric", "value",
                                                      "threshold", "explanation", "record_refs"]))
    return evidence_rows("NET-CYCLE", "1.0", "5.9 Network", "R1", "NET.CYCLE", found, cfg)
```

### NET-FUNNEL
หาบัญชีที่รับเงินจากหลายแหล่งแล้วส่งต่อออกไปเกือบทั้งหมด: ในช่วง days วันนับจากเงินเข้าแต่ละรายการ ต้องมีแหล่งเงินเข้า ≥ min_sources บัญชี และยอดออก/ยอดเข้า ≥ out_ratio
บัญชีที่ไม่มีเงินออกเลยไม่ได้สัญญาณ (ไม่มีการหารด้วยศูนย์); เกณฑ์อ้าง `NET.FUNNEL = รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน`

```python
# RECIPE NET-FUNNEL v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.FUNNEL | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def net_funnel(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    f = cfg["NET.FUNNEL"]
    win = pd.Timedelta(days=f["days"])
    outs_by = {a: g for a, g in t.groupby("from_acct")}
    rows = []
    for acct, ins in t.groupby("to_acct"):
        outs = outs_by.get(acct)
        if outs is None or ins["from_acct"].nunique() < f["min_sources"]:
            continue  # no outflow at all, or too few sources: no signal
        for t0, p0 in zip(ins["ts"], ins["period"]):
            wi = ins[(ins["ts"] >= t0) & (ins["ts"] < t0 + win)]
            wo = outs[(outs["ts"] >= t0) & (outs["ts"] < t0 + win)]
            n_src, amt_in = wi["from_acct"].nunique(), wi["amount"].sum()
            if n_src < f["min_sources"] or wo.empty or amt_in <= 0:
                continue
            ratio = wo["amount"].sum() / amt_in
            if ratio >= f["out_ratio"]:
                rows.append({"entity_id": acct, "period": p0, "metric": "out_in_ratio",
                             "value": round(ratio, 4), "threshold": f["out_ratio"],
                             "explanation": f"รับเงินจาก {n_src} แหล่ง รวม {amt_in:,.2f} แล้วส่งต่อ "
                             f"{ratio:.0%} ภายใน {f['days']} วัน (NET.FUNNEL ≥ {f['min_sources']} แหล่ง "
                             f"และ ≥ {f['out_ratio']:.0%} ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
                             f"— ควรตรวจสอบเพิ่มเติม",
                             "record_refs": list(wi["tx_id"]) + list(wo["tx_id"])})
    found = one_per_month(pd.DataFrame(rows, columns=["entity_id", "period", "metric", "value",
                                                      "threshold", "explanation", "record_refs"]))
    return evidence_rows("NET-FUNNEL", "1.0", "5.9 Network", "R1", "NET.FUNNEL", found, cfg)
```

## ข้อห้าม (Guardrails)
- รันการ์ดตามที่เขียนไว้ทุกตัวอักษร (verbatim) ห้ามแก้โค้ด ห้ามเปลี่ยนเกณฑ์ในโค้ด และห้ามเขียนการ์ดขึ้นเองแทนการ์ดที่หาไม่พบ
- ถ้าดึงการ์ดมาไม่ครบ (โค้ดถูกตัด, ไม่มีบรรทัดปิด) ห้ามรันส่วนที่ได้มา — Skip การ์ดนั้นพร้อม reason "ดึง recipe ไม่ครบ"
- ผลของการ์ดเป็นสัญญาณให้ตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุปว่าบัญชีหรือบุคคลกระทำผิดหรือเป็นบัญชีม้า — ใช้ถ้อยคำตาม AIDA-11 เช่น "สอดคล้องกับ Mule Account pattern"
- ห้ามรายงานเกณฑ์โดยไม่อ้าง key ใน AIDA-14 และต้องแจ้งว่าเป็นค่ามาตรฐานที่ปรับได้

## ไฟล์ที่เกี่ยวข้อง
- AIDA-19 Pipeline Recipes (CORE-EVIDENCE ต้องรันก่อน)
- AIDA-17 Data & Evidence Schema (คอลัมน์ input และ Evidence)
- AIDA-14 Configuration Registry (Machine Config)
- AIDA-04 Statistical, AIDA-05 Behavioral / Temporal, AIDA-08 Network (หลักการของแต่ละ skill)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ใช้)
