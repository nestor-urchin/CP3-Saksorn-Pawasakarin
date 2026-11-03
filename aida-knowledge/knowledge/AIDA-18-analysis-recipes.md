# AIDA-18 · Analysis Recipes (การ์ดวิเคราะห์ธุรกรรมระดับบัญชีและเครือข่าย)
> ไฟล์: AIDA-18 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: การ์ดวิเคราะห์ระดับบัญชี (STAT / BEH / TEMP / NET), Mule Account (MULE-DWELL / MULE-NEW-ACCT / MULE-PATTERN / MULE-CROSS-TX / MULE-NETWORK), คู่ค้า (CPTY-*) และเส้นทางเงิน (FLOW-TRACE / FLOW-LAYERING) คำนวณอะไร ใช้เกณฑ์ใดจาก AIDA-14 และให้ Evidence แบบไหน, ต้องโหลดอะไรและรันการ์ดตามลำดับใด

## สรุปสั้น
ไฟล์นี้เก็บการ์ดวิเคราะห์ (recipe) ที่ Code Interpreter รันตามที่เขียนไว้ทุกตัวอักษร การ์ดทุกใบรับ `(tables, cfg)` และคืน DataFrame ตาม Evidence schema ใน AIDA-17 (DataFrame ว่าง = ไม่พบสัญญาณ)
**ต้องรันการ์ด CORE-EVIDENCE และ CORE-BASELINE ใน AIDA-19 ก่อน** เพราะทุกการ์ดเรียก `clean_tx`, `one_per_month` และ `evidence_rows` จากการ์ดนั้น (และ BEH-VELOCITY / BEH-SPIKE เรียก `beyond_baseline`, `baseline_formula` จาก `CORE-BASELINE`)
ทุกการ์ดตัดรายการโอนเข้าบัญชีตัวเอง ยอด ≤ 0 และรายการที่ไม่มีวันเวลาออกก่อนวิเคราะห์, ใช้ period แบบ YYYY-MM (1 แถวต่อบัญชีต่อเดือน) และอ่านเกณฑ์จาก `cfg` (Machine Config ใน AIDA-14) เท่านั้น
ความเสี่ยง (AIDA-17): R1 = STAT-MAD, BEH-*, TEMP-OFFHOURS, NET-*, MULE-DWELL, MULE-NEW-ACCT, FLOW-LAYERING / R2 = MULE-PATTERN / R3 = MULE-CROSS-TX, MULE-NETWORK (entity_type network) / R4 = CPTY-*; FLOW-TRACE ไม่สร้าง Evidence แต่คืน Money Flow trail
การ์ด STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, CPTY-PROFILE, CPTY-NEW-LARGE ระบุบัญชีผู้โอน (from_acct); NET-CYCLE ระบุทุกบัญชีในวง; NET-FUNNEL และ MULE-DWELL ระบุบัญชีที่รับเงินแล้วส่งต่อ; FLOW-LAYERING ระบุทุกบัญชีบนเส้นทาง
**ลำดับการรัน:** การ์ด R1 ทั้งหมด → MULE-PATTERN (อ่าน Evidence R1 จาก `tables["evidence"]`) → MULE-CROSS-TX (อ่าน Evidence R2) → MULE-NETWORK (อ่าน Evidence R2 + MULE-CROSS-TX และใส่ตาราง Mule Network ใน `tables["_out"]["mule_networks"]`) — ต่อท้าย Evidence ของแต่ละขั้นเข้า `tables["evidence"]` ก่อนรันขั้นถัดไป

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
เป็นสัญญาณเมื่อจำนวนต่อวัน > ค่าเฉลี่ย + BEH.DEVIATION × max(SD, √ค่าเฉลี่ย) ตาม `BEH.VELOCITY.SD_FLOOR = sqrt(mean) (Poisson)` (ตั้ง Machine Config เป็น "none" = ใช้ SD อย่างเดียว); เกณฑ์อ้าง `BEH.DEVIATION = 3σ`

```python
# RECIPE BEH-VELOCITY v1.0 | Skill: 5.3 Behavioral | Risk: R1
# Registry: BEH.BASELINE.MIN_PERIODS, BEH.DEVIATION, BEH.VELOCITY.SD_FLOOR | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def beh_velocity(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    need = cfg["BEH.BASELINE.MIN_PERIODS"]["velocity_days"]
    k, floor = cfg["BEH.DEVIATION"], cfg["BEH.VELOCITY.SD_FLOOR"]
    d = (t.assign(day=t["ts"].dt.strftime("%Y-%m-%d"))
         .groupby(["from_acct", "day", "period"])
         .agg(n=("tx_id", "size"), refs=("tx_id", list)).reset_index())
    hit = beyond_baseline(d, "from_acct", "n", need, k, floor)
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "tx_per_day", "value": hit["n"], "threshold": hit["thr"].round(2),
        "explanation": [
            f"วันที่ {dy} มีรายการโอนออก {n} รายการ สูงกว่าเกณฑ์จาก baseline ของบัญชีเดียวกัน "
            f"({baseline_formula(mu, sd, k, th, floor)}; BEH.DEVIATION, BEH.VELOCITY.SD_FLOOR "
            f"และ BEH.BASELINE.MIN_PERIODS ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
            f"— ควรตรวจสอบเพิ่มเติม"
            for dy, n, mu, sd, th in zip(hit["day"], hit["n"], hit["mu"], hit["sd"], hit["thr"])],
        "record_refs": hit["refs"]})
    return evidence_rows("BEH-VELOCITY", "1.0", "5.3 Behavioral", "R1",
                         "BEH.DEVIATION", one_per_month(found), cfg)
```

### BEH-SPIKE
รวมยอดโอนออกต่อเดือนของแต่ละบัญชี แล้วเทียบกับ baseline ของบัญชีเดียวกัน (เดือนที่มีรายการก่อนหน้าทั้งหมด ต้องมีอย่างน้อย spike_months เดือน)
เป็นสัญญาณเมื่อยอดเดือนนั้น > ค่าเฉลี่ย + BEH.DEVIATION × SD ของ baseline (ไม่มีค่า SD ขั้นต่ำ); บัญชีที่ประวัติไม่ถึงเกณฑ์ไม่ถูกประเมิน

```python
# RECIPE BEH-SPIKE v1.0 | Skill: 5.3 Behavioral | Risk: R1
# Registry: BEH.BASELINE.MIN_PERIODS, BEH.DEVIATION | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def beh_spike(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    need = cfg["BEH.BASELINE.MIN_PERIODS"]["spike_months"]
    k = cfg["BEH.DEVIATION"]
    d = (t.groupby(["from_acct", "period"])
         .agg(amt=("amount", "sum"), refs=("tx_id", list)).reset_index())
    hit = beyond_baseline(d, "from_acct", "amt", need, k)
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "amount_per_month", "value": hit["amt"].round(2),
        "threshold": hit["thr"].round(2),
        "explanation": [
            f"ยอดโอนออกเดือน {p} รวม {a:,.2f} สูงกว่าเกณฑ์จาก baseline รายเดือนของบัญชีเดียวกัน "
            f"({baseline_formula(mu, sd, k, th)}; BEH.DEVIATION และ BEH.BASELINE.MIN_PERIODS "
            f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, a, mu, sd, th in zip(hit["period"], hit["amt"], hit["mu"], hit["sd"], hit["thr"])],
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
หาวงเงินหมุนวน (A→B→…→A) ยาว min_len–max_len ทอด ด้วย DFS แบบวนซ้ำ (ไม่ใช้ networkx) ทอดถัดไปต้องเกิดไม่ก่อนทอดก่อนหน้าและอยู่ภายใน days วันนับจากทอดแรก; ใช้รายการแรกต่อคู่บัญชีเท่านั้นและนับวงตามชุดบัญชี (ไม่นับซ้ำ)
แต่ละบัญชีในวงได้ 1 แถวต่อเดือน (เดือนของทอดแรก) โดย record_refs คือรายการของวงที่ระบุใน explanation เท่านั้น; ค้นหาไม่เกิน `NET.CYCLE.MAX_PATHS = 100,000` เส้นทาง; เกณฑ์อ้าง `NET.CYCLE = 2–5 ทอด ภายใน 30 วัน`

```python
# RECIPE NET-CYCLE v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.CYCLE, NET.CYCLE.MAX_PATHS | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def net_cycle(tables: dict, cfg: dict) -> pd.DataFrame:
    from bisect import bisect_left, bisect_right
    t = clean_tx(tables["transactions"])
    c, cap = cfg["NET.CYCLE"], cfg["NET.CYCLE.MAX_PATHS"]
    win = pd.Timedelta(days=c["days"])
    out = {a: (list(g["ts"]), list(g["to_acct"]), list(g["tx_id"])) for a, g in t.groupby("from_acct")}
    cycles, steps = {}, 0
    for t0, a0, b0, x0, p0 in zip(t["ts"], t["from_acct"], t["to_acct"], t["tx_id"], t["period"]):
        stack = [(b0, t0, (a0, b0), (x0,))]
        while stack and steps < cap:
            node, ts, path, refs = stack.pop()
            steps += 1
            tss, tos, txs = out.get(node, ([], [], []))
            seen = set()  # earliest edge per (node, next account) only
            for j in range(bisect_left(tss, ts), bisect_right(tss, t0 + win)):
                nxt = tos[j]
                if nxt in seen:
                    continue
                seen.add(nxt)
                if nxt == a0 and len(path) >= c["min_len"]:
                    i = path.index(min(path))  # same accounts in rotation = same cycle
                    cycles.setdefault((path[i:] + path[:i], p0), (path, refs + (txs[j],)))
                elif nxt not in path and len(path) < c["max_len"]:
                    stack.append((nxt, tss[j], path + (nxt,), refs + (txs[j],)))
    note = f" — ค้นหาถึงขีดจำกัด NET.CYCLE.MAX_PATHS ({cap:,} เส้นทาง) ผลอาจไม่ครบ" if steps >= cap else ""
    best = {}  # (account, month) -> [first cycle found, its refs, number of cycles]
    for (_, p0), (path, refs) in cycles.items():
        for a in path:
            best.setdefault((a, p0), [path, refs, 0])[2] += 1
    found = pd.DataFrame([{
        "entity_id": a, "period": p0, "metric": "cycle_length", "value": len(path),
        "threshold": c["max_len"], "record_refs": list(refs),
        "explanation": f"บัญชีอยู่ในวงเงินหมุนวน {' → '.join(path + (path[0],))} ({len(path)} ทอด "
        f"ภายใน {c['days']} วัน; พบ {n} วงในเดือนนี้ แสดงวงแรก; NET.CYCLE {c['min_len']}–{c['max_len']} "
        f"ทอด ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม{note}"}
        for (a, p0), (path, refs, n) in best.items()],
        columns=["entity_id", "period", "metric", "value", "threshold", "explanation", "record_refs"])
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

## การ์ด Mule Account (สัญญาณ R1 → รูปแบบ R2 → เครือข่าย R3)

### MULE-DWELL
จับคู่เงินเข้าแต่ละรายการกับเงินออกรายการถัดไปของบัญชีเดียวกันตามลำดับเวลา (เงินออก 1 รายการจับคู่กับเงินเข้าล่าสุดก่อนหน้าเพียงรายการเดียว) แล้วนับคู่ที่เงินอยู่ในบัญชีไม่เกิน `MULE.DWELL_HOURS = 24` ชั่วโมง ต่อบัญชีต่อเดือน
เป็นสัญญาณ R1 เมื่อจำนวนคู่ ≥ `MULE.DWELL_MIN_PAIRS = 3`; บัญชีที่ไม่มีเงินออกเลยไม่ได้สัญญาณ — เป็น 1 ใน 5 สัญญาณที่ MULE-PATTERN นับ

```python
# RECIPE MULE-DWELL v1.0 | Skill: 5.4 Temporal | Risk: R1
# Registry: MULE.DWELL_HOURS, MULE.DWELL_MIN_PAIRS | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def mule_dwell(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    hrs, need = cfg["MULE.DWELL_HOURS"], cfg["MULE.DWELL_MIN_PAIRS"]
    outs_by = {a: g for a, g in t.groupby("from_acct")}
    rows = []
    for acct, ins in t.groupby("to_acct"):
        outs = outs_by.get(acct)
        if outs is None:
            continue  # no outflow at all: no pair, no signal
        j = np.searchsorted(outs["ts"].to_numpy(), ins["ts"].to_numpy(), side="left")
        ok = j < len(outs)  # inflows followed by an outflow
        p = pd.DataFrame({"in_tx": ins["tx_id"].to_numpy()[ok], "in_ts": ins["ts"].to_numpy()[ok],
                          "period": ins["period"].to_numpy()[ok],
                          "out_tx": outs["tx_id"].to_numpy()[j[ok]],
                          "out_ts": outs["ts"].to_numpy()[j[ok]]})
        p = p.drop_duplicates("out_tx", keep="last")  # one outflow pairs with its latest inflow only
        p["hours"] = (p["out_ts"] - p["in_ts"]) / pd.Timedelta(hours=1)
        for per, g in p[p["hours"] <= hrs].groupby("period"):
            if len(g) < need:
                continue
            rows.append({"entity_id": acct, "period": per, "metric": "short_dwell_pairs",
                         "value": len(g), "threshold": need,
                         "explanation": f"เดือน {per} มีเงินเข้าแล้วโอนออกต่อภายใน {hrs} ชั่วโมง "
                         f"{len(g)} คู่ (median {g['hours'].median():.1f} ชั่วโมง; MULE.DWELL_HOURS และ "
                         f"MULE.DWELL_MIN_PAIRS ≥ {need} คู่ ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
                         f"— ควรตรวจสอบเพิ่มเติม",
                         "record_refs": list(g["in_tx"]) + list(g["out_tx"])})
    return evidence_rows("MULE-DWELL", "1.0", "5.4 Temporal", "R1", "MULE.DWELL_HOURS",
                         pd.DataFrame(rows), cfg)
```

### MULE-NEW-ACCT
นับรายการ (ทั้งรับและโอน) ของบัญชีภายใน `MULE.NEW_ACCT_DAYS = 30` วันนับจากวันเริ่มต้นบัญชี เป็นสัญญาณ R1 เมื่อ ≥ `MULE.NEW_ACCT_MIN_TX = 20` รายการ; period = เดือนที่มีรายการครบเกณฑ์
basis = `opened_at` เมื่อมีตาราง accounts ที่มีคอลัมน์ opened_at (รายบัญชี) มิฉะนั้น basis = `first_seen` (วันที่พบรายการแรกในไฟล์) และไม่ประเมินบัญชีที่พบใน MULE.NEW_ACCT_DAYS วันแรกของไฟล์ เพราะอาจเปิดก่อนช่วงข้อมูล; explanation ระบุ basis=opened_at|first_seen

```python
# RECIPE MULE-NEW-ACCT v1.0 | Skill: 5.7 Rule-Based | Risk: R1
# Registry: MULE.NEW_ACCT_DAYS, MULE.NEW_ACCT_MIN_TX | Input: transactions(tx_id, ts, from_acct, to_acct), accounts(acct_id, opened_at) ถ้ามี
def mule_new_acct(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    days, need = cfg["MULE.NEW_ACCT_DAYS"], cfg["MULE.NEW_ACCT_MIN_TX"]
    win = pd.Timedelta(days=days)
    inv = pd.concat([t[["tx_id", "ts", "period", s]].rename(columns={s: "acct"})
                     for s in ("from_acct", "to_acct")]).sort_values("ts", kind="mergesort")
    seen = inv.groupby("acct")["ts"].min()
    start = seen.where(seen > t["ts"].min() + win)  # first_seen: skip accounts seen at the file start
    basis = pd.Series("first_seen", index=seen.index)
    acc = tables.get("accounts")
    if acc is not None and "opened_at" in acc.columns:
        opened = (pd.to_datetime(acc["opened_at"], errors="coerce")
                  .groupby(acc["acct_id"]).min().reindex(seen.index))
        basis = basis.where(opened.isna(), "opened_at")
        start = opened.fillna(start)
    inv = inv.assign(start=inv["acct"].map(start)).dropna(subset=["start"])
    inv = inv[(inv["ts"] >= inv["start"]) & (inv["ts"] <= inv["start"] + win)]
    rows = []
    for acct, g in inv.groupby("acct"):
        if len(g) < need:
            continue
        hit, s0, b = g.iloc[need - 1], g["start"].iloc[0], basis[acct]
        note = "" if b == "opened_at" else (" — ไม่มี opened_at จึงใช้วันที่พบรายการแรกในไฟล์ "
                                            "ซึ่งอาจไม่ใช่วันเปิดบัญชีจริง")
        rows.append({"entity_id": acct, "period": hit["period"], "metric": "tx_within_new_acct_days",
                     "value": len(g), "threshold": need,
                     "explanation": f"บัญชีมี {len(g)} รายการ (รับและโอน) ภายใน {days} วันนับจาก "
                     f"{s0:%Y-%m-%d} (basis={b}{note}) และมีครบ {need} รายการเมื่ออายุบัญชี "
                     f"{(hit['ts'] - s0).days} วัน (MULE.NEW_ACCT_DAYS และ MULE.NEW_ACCT_MIN_TX "
                     f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม",
                     "record_refs": list(g["tx_id"])})
    return evidence_rows("MULE-NEW-ACCT", "1.0", "5.7 Rule-Based", "R1", "MULE.NEW_ACCT_DAYS",
                         pd.DataFrame(rows), cfg)
```

### MULE-PATTERN
อ่าน Evidence ที่ได้แล้วจาก `tables["evidence"]` และนับสัญญาณ 5 แบบ (NET-FUNNEL, MULE-DWELL, MULE-NEW-ACCT, BEH-VELOCITY, TEMP-OFFHOURS) ต่อบัญชีต่อเดือน เป็น Evidence R2 เมื่อ ≥ `MULE.MIN_SIGNALS = 3 (จาก 5 สัญญาณ)`
value = จำนวนสัญญาณ, explanation ระบุสัญญาณที่พบครบทุกตัว และใช้ถ้อยคำ "สอดคล้องกับ Mule Account pattern" (ข้อสังเกต ไม่ใช่ข้อสรุป)

```python
# RECIPE MULE-PATTERN v1.0 | Skill: 5.10 Hybrid | Risk: R2
# Registry: MULE.MIN_SIGNALS | Input: evidence(recipe_id, entity_type, entity_id, period, record_refs)
MULE_SIGNALS = {"NET-FUNNEL": "รับเงินหลายแหล่งแล้วโอนออกเกือบหมด",
                "MULE-DWELL": "เงินอยู่ในบัญชีช่วงสั้น",
                "MULE-NEW-ACCT": "บัญชีใหม่แล้วมีรายการมากทันที",
                "BEH-VELOCITY": "โอนถี่กว่า baseline ของบัญชี",
                "TEMP-OFFHOURS": "ทำรายการนอกเวลาทำการ"}
def mule_pattern(tables: dict, cfg: dict) -> pd.DataFrame:
    ev, need = tables.get("evidence"), cfg["MULE.MIN_SIGNALS"]
    rows = []
    if ev is not None and len(ev) > 0:
        s = ev[ev["recipe_id"].isin(list(MULE_SIGNALS)) & (ev["entity_type"] == "account")]
        for (acct, per), g in s.groupby(["entity_id", "period"]):
            sig = [r for r in MULE_SIGNALS if r in set(g["recipe_id"])]
            if len(sig) < need:
                continue
            rows.append({"entity_id": acct, "period": per, "metric": "mule_signal_count",
                         "value": len(sig), "threshold": need,
                         "explanation": f"เดือน {per} บัญชีมีสัญญาณ {len(sig)} จาก {len(MULE_SIGNALS)} "
                         "สัญญาณ: " + ", ".join(f"{r} ({MULE_SIGNALS[r]})" for r in sig)
                         + f" — สอดคล้องกับ Mule Account pattern (MULE.MIN_SIGNALS ≥ {need} สัญญาณ "
                         "ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) เป็นข้อสังเกตที่ควรตรวจสอบเพิ่มเติม "
                         "ไม่ใช่ข้อสรุปเกี่ยวกับเจ้าของบัญชี",
                         "record_refs": sorted({str(x) for r in g["record_refs"] for x in r})})
    return evidence_rows("MULE-PATTERN", "1.0", "5.10 Hybrid", "R2", "MULE.MIN_SIGNALS",
                         pd.DataFrame(rows), cfg)
```

### MULE-CROSS-TX
ใช้บัญชีที่มี Evidence R2 (MULE-PATTERN) ใน `tables["evidence"]` เป็นชุดบัญชีที่สอดคล้องกับ Mule Account pattern แล้วหาธุรกรรมข้ามบัญชี 3 บทบาท: mule_to_mule (ผู้โอนและผู้รับอยู่ในชุดทั้งคู่ — ระบุทั้ง 2 บัญชี), collector (บัญชีนอกชุดที่รับเงินจากบัญชีในชุด) และ feeder (บัญชีนอกชุดที่โอนเงินให้บัญชีในชุด)
collector / feeder ต้องเชื่อมกับบัญชีในชุด ≥ `MULE.CROSS.MIN_LINKS = 2` บัญชี ภายใน `FLOW.WINDOW_DAYS = 7` วัน; metric = role, value = บทบาท — บทบาทอธิบายตำแหน่งในเครือข่าย ไม่ใช่ข้อสรุป

```python
# RECIPE MULE-CROSS-TX v1.0 | Skill: 5.9 Network | Risk: R3
# Registry: MULE.CROSS.MIN_LINKS, FLOW.WINDOW_DAYS | Input: transactions(tx_id, ts, from_acct, to_acct, amount), evidence(MULE-PATTERN)
def mule_cross_tx(tables: dict, cfg: dict) -> pd.DataFrame:
    t, ev = clean_tx(tables["transactions"]), tables.get("evidence")
    has = ev is not None and len(ev) > 0
    mules = set(ev.loc[ev["recipe_id"] == "MULE-PATTERN", "entity_id"]) if has else set()
    need, days = cfg["MULE.CROSS.MIN_LINKS"], cfg["FLOW.WINDOW_DAYS"]
    fm, tm = t["from_acct"].isin(mules), t["to_acct"].isin(mules)
    roles = [("mule_to_mule", t[fm & tm], "from_acct", "to_acct"),
             ("mule_to_mule", t[fm & tm], "to_acct", "from_acct"),
             ("collector", t[fm & ~tm], "to_acct", "from_acct"),
             ("feeder", t[~fm & tm], "from_acct", "to_acct")]
    rows = []
    for role, e, side, other in roles:
        for acct, g in e.groupby(side):
            for t0, p0 in zip(g["ts"], g["period"]):
                w = g[(g["ts"] >= t0) & (g["ts"] <= t0 + pd.Timedelta(days=days))]
                if role == "mule_to_mule" or w[other].nunique() >= need:
                    rows.append((acct, p0, role, w[other].nunique(), list(w["tx_id"])))
    if not rows:
        return evidence_rows("MULE-CROSS-TX", "1.0", "5.9 Network", "R3", "MULE.CROSS.MIN_LINKS",
                             pd.DataFrame(), cfg)
    f = (pd.DataFrame(rows, columns=["entity_id", "period", "value", "n", "refs"])
         .groupby(["entity_id", "period", "value"], as_index=False)
         .agg(n=("n", "max"), record_refs=("refs", lambda s: sorted({x for r in s for x in r}))))
    text = {"mule_to_mule": "มีธุรกรรมกับบัญชีอื่น {n} บัญชีที่สอดคล้องกับ Mule Account pattern "
                            "เช่นเดียวกับบัญชีนี้ (บทบาท mule_to_mule ในเครือข่าย)",
            "collector": "รับเงินจากบัญชีที่สอดคล้องกับ Mule Account pattern {n} บัญชีภายใน {d} วัน "
                         "(บทบาทผู้รับรวม collector ในเครือข่าย)",
            "feeder": "โอนเงินให้บัญชีที่สอดคล้องกับ Mule Account pattern {n} บัญชีภายใน {d} วัน "
                      "(บทบาทผู้ส่งเงินเข้า feeder ในเครือข่าย)"}
    found = f.assign(metric="role", threshold=need, explanation=[
        f"เดือน {p} " + text[v].format(n=n, d=days) + " — บทบาทอธิบายตำแหน่งในเครือข่าย ไม่ใช่ข้อสรุป "
        f"(MULE.CROSS.MIN_LINKS ≥ {need} บัญชี และ FLOW.WINDOW_DAYS ค่ามาตรฐานจาก AIDA-14 "
        "ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม" for p, v, n in zip(f["period"], f["value"], f["n"])])
    return evidence_rows("MULE-CROSS-TX", "1.0", "5.9 Network", "R3", "MULE.CROSS.MIN_LINKS", found, cfg)
```

### MULE-NETWORK
รวมบัญชีที่เชื่อมกันด้วยธุรกรรมใน record_refs ของ MULE-CROSS-TX (mule_to_mule, collector, feeder) เป็นกลุ่มด้วย union-find (เขียนเอง ไม่ใช้ networkx); กลุ่มที่มีสมาชิก ≥ `MULE.NETWORK.MIN_SIZE = 3` บัญชี → Evidence R3 1 แถวต่อกลุ่ม (entity_type = network, entity_id = NET-<n> เรียงตามขนาดกลุ่มจากมากไปน้อย แล้วตามรหัสสมาชิกที่น้อยที่สุด)
คืนตาราง Mule Network (AIDA-17) ใน `tables["_out"]["mule_networks"]` ด้วย: บทบาทต่อบัญชี (mule / collector / feeder) และธุรกรรมภายในกลุ่ม = ทุกรายการที่ผู้โอนและผู้รับเป็นสมาชิกกลุ่ม

```python
# RECIPE MULE-NETWORK v1.0 | Skill: 5.9 Network | Risk: R3
# Registry: MULE.NETWORK.MIN_SIZE | Input: transactions(tx_id, ts, from_acct, to_acct, amount), evidence(MULE-PATTERN, MULE-CROSS-TX)
def mule_network(tables: dict, cfg: dict) -> pd.DataFrame:
    t, ev = clean_tx(tables["transactions"]), tables.get("evidence")
    ev = ev if ev is not None and len(ev) > 0 else pd.DataFrame(columns=EVIDENCE_COLUMNS)
    size, x = cfg["MULE.NETWORK.MIN_SIZE"], ev[ev["recipe_id"] == "MULE-CROSS-TX"]
    mules = set(ev.loc[ev["recipe_id"] == "MULE-PATTERN", "entity_id"])
    roles, parent = {}, {}
    for a, v in zip(x["entity_id"], x["value"]):
        roles.setdefault(a, set()).add("mule" if a in mules else v)
    def root(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    links = t[t["tx_id"].isin({r for refs in x["record_refs"] for r in refs})]
    for a, b in zip(links["from_acct"], links["to_acct"]):
        parent[root(a)] = root(b)
    groups = {}
    for a in list(parent):
        groups.setdefault(root(a), []).append(a)
    groups = sorted((sorted(g) for g in groups.values() if len(g) >= size), key=lambda g: (-len(g), g[0]))
    nets, rows = [], []
    for n, members in enumerate(groups, 1):
        inner = t[t["from_acct"].isin(members) & t["to_acct"].isin(members)]
        role = {a: "/".join(sorted(roles.get(a, {"mule"}))) for a in members}
        k = {r: sum(r in v for v in role.values()) for r in ("mule", "collector", "feeder")}
        d0, d1 = inner["ts"].min().strftime("%Y-%m-%d"), inner["ts"].max().strftime("%Y-%m-%d")
        nets.append([f"NET-{n}", members, role, len(inner), round(float(inner["amount"].sum()), 2), d0, d1])
        rows.append({"entity_type": "network", "entity_id": f"NET-{n}", "period": inner["period"].iloc[0],
                     "metric": "network_size", "value": len(members), "threshold": size,
                     "explanation": f"กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern: "
                     f"สมาชิก {len(members)} บัญชี (mule {k['mule']}, collector {k['collector']}, feeder "
                     f"{k['feeder']}) ธุรกรรมภายในกลุ่ม {len(inner)} รายการ รวม {inner['amount'].sum():,.2f} "
                     f"ระหว่าง {d0} ถึง {d1} — collector/feeder เป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป "
                     f"(MULE.NETWORK.MIN_SIZE ≥ {size} บัญชี ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
                     f"— ควรตรวจสอบเพิ่มเติม", "record_refs": list(inner["tx_id"])})
    tables.setdefault("_out", {})["mule_networks"] = pd.DataFrame(nets, columns=[
        "network_id", "member_accts", "roles", "internal_tx_count", "internal_amount",
        "period_start", "period_end"])
    return evidence_rows("MULE-NETWORK", "1.0", "5.9 Network", "R3", "MULE.NETWORK.MIN_SIZE",
                         pd.DataFrame(rows), cfg)
```

## การ์ด Counterparty (5.2 / 5.3)

### CPTY-PROFILE
ต่อบัญชีผู้โอน (from_acct) ต่อเดือน: จำนวนคู่ค้า, สัดส่วนคู่ค้าใหม่ (คู่ค้าที่บัญชีไม่เคยโอนให้ในเดือนก่อนหน้า) และส่วนแบ่งยอดของคู่ค้าสูงสุด
เป็นสัญญาณ R4 เมื่อสัดส่วนคู่ค้าใหม่ ≥ `CPTY.NEW_RATIO = 50%` และบัญชีมีเดือนที่มีรายการก่อนหน้า ≥ spike_months ของ BEH.BASELINE.MIN_PERIODS; record_refs = รายการที่โอนให้คู่ค้าใหม่

```python
# RECIPE CPTY-PROFILE v1.0 | Skill: 5.2 Concentration | Risk: R4
# Registry: CPTY.NEW_RATIO, BEH.BASELINE.MIN_PERIODS | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def cpty_profile(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    need, lim = cfg["BEH.BASELINE.MIN_PERIODS"]["spike_months"], cfg["CPTY.NEW_RATIO"]
    t["new"] = t["period"] == t.groupby(["from_acct", "to_acct"])["period"].transform("min")
    pair = (t.groupby(["from_acct", "period", "to_acct"])
            .agg(amt=("amount", "sum"), new=("new", "first"), refs=("tx_id", list)).reset_index())
    m = (pair.groupby(["from_acct", "period"])
         .agg(n=("to_acct", "size"), n_new=("new", "sum"), amt=("amt", "sum"), top=("amt", "max"))
         .reset_index())
    m["prior"] = m.groupby("from_acct").cumcount()  # earlier active months of this account
    m["ratio"] = m["n_new"] / m["n"]
    hit = m[(m["prior"] >= need) & (m["ratio"] >= lim)]
    refs = pair[pair["new"]].groupby(["from_acct", "period"])["refs"].agg(lambda s: [x for r in s for x in r])
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "new_counterparty_ratio", "value": hit["ratio"].round(4), "threshold": lim,
        "explanation": [
            f"เดือน {p} โอนให้คู่ค้า {n} ราย เป็นคู่ค้าใหม่ {k} ราย ({r:.0%}) และคู่ค้าสูงสุดได้รับ "
            f"{top / amt:.0%} ของยอดโอนเดือนนั้น (บัญชีมีประวัติ {pr} เดือนก่อนหน้า; CPTY.NEW_RATIO "
            f"≥ {lim:.0%} และ BEH.BASELINE.MIN_PERIODS ≥ {need} เดือน ค่ามาตรฐานจาก AIDA-14 "
            f"ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, n, k, r, top, amt, pr in zip(hit["period"], hit["n"], hit["n_new"], hit["ratio"],
                                               hit["top"], hit["amt"], hit["prior"])],
        "record_refs": [refs[(a, p)] for a, p in zip(hit["from_acct"], hit["period"])]})
    return evidence_rows("CPTY-PROFILE", "1.0", "5.2 Concentration", "R4", "CPTY.NEW_RATIO",
                         found, cfg)
```

### CPTY-NEW-LARGE
หารายการโอนครั้งแรกจากบัญชีผู้โอน (from_acct) ไปยังคู่ค้าที่ไม่เคยโอนให้มาก่อน ซึ่งยอด ≥ `CPTY.NEW_LARGE.MULTIPLIER = 5` × median ยอดโอนของบัญชีนั้น
ไม่นับเดือนแรกที่บัญชีมีรายการในไฟล์ เพราะยังไม่มีประวัติให้รู้ว่าคู่ค้าใดเป็นคู่ค้าใหม่จริง; 1 แถวต่อบัญชีต่อเดือน

```python
# RECIPE CPTY-NEW-LARGE v1.0 | Skill: 5.3 Behavioral | Risk: R4
# Registry: CPTY.NEW_LARGE.MULTIPLIER | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def cpty_new_large(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    k = cfg["CPTY.NEW_LARGE.MULTIPLIER"]
    t["med"] = t.groupby("from_acct")["amount"].transform("median")
    t["first_month"] = t.groupby("from_acct")["period"].transform("min")
    first = t.drop_duplicates(["from_acct", "to_acct"])  # time-sorted: first transfer per pair
    hit = first[(first["period"] > first["first_month"]) & (first["amount"] >= k * first["med"])]
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "new_counterparty_amount_x_median", "value": (hit["amount"] / hit["med"]).round(2),
        "threshold": k,
        "explanation": [
            f"รายการ {i} เป็นการโอนครั้งแรกให้คู่ค้าใหม่ {to} ยอด {a:,.2f} = {a / md:.1f} เท่าของ "
            f"median ยอดโอนของบัญชี ({md:,.2f}; CPTY.NEW_LARGE.MULTIPLIER ≥ {k} เท่า ค่ามาตรฐานจาก "
            f"AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for i, to, a, md in zip(hit["tx_id"], hit["to_acct"], hit["amount"], hit["med"])],
        "record_refs": [[i] for i in hit["tx_id"]]})
    return evidence_rows("CPTY-NEW-LARGE", "1.0", "5.3 Behavioral", "R4",
                         "CPTY.NEW_LARGE.MULTIPLIER", one_per_month(found), cfg)
```

## การ์ด Money Flow (5.9)

### FLOW-TRACE
ไล่เส้นทางเงินจากบัญชีที่ระบุ ไปข้างหน้า (`direction="forward"` = เงินไปที่ใด) หรือย้อนกลับ (`"backward"` = เงินมาจากที่ใด) แบบ BFS ตามลำดับเวลา ไม่เกิน `FLOW.MAX_HOPS = 4` ทอด และอยู่ภายใน `FLOW.WINDOW_DAYS = 7` วันนับจากทอดแรกของเส้นทาง; แต่ละรายการถูกไล่ต่อเพียงครั้งเดียว
ไม่ใช่การ์ดวิเคราะห์และไม่สร้าง Evidence — signature `flow_trace(tables, cfg, start_acct, direction)` คืน Money Flow trail ตาม AIDA-17 (ใช้อัตโนมัติกับบัญชี Priority สูงสุดไม่เกิน `FLOW.AUTO_MAX_ENTITIES = 10` บัญชี หรือเมื่อผู้ใช้สั่ง)

```python
# RECIPE FLOW-TRACE v1.0 | Skill: 5.9 Network | Risk: -
# Registry: FLOW.MAX_HOPS, FLOW.WINDOW_DAYS | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
TRAIL_COLUMNS = ["trace_id", "start_acct", "direction", "hop", "from_acct", "to_acct", "amount",
                 "ts", "tx_id"]
def flow_trace(tables: dict, cfg: dict, start_acct: str, direction: str) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    fwd = direction == "forward"  # "backward" = where the money came from
    side, nxt = ("from_acct", "to_acct") if fwd else ("to_acct", "from_acct")
    win, by = pd.Timedelta(days=cfg["FLOW.WINDOW_DAYS"]), {a: g for a, g in t.groupby(side)}
    rows, seen, frontier = [], set(), [(start_acct, None, None)]
    for hop in range(1, cfg["FLOW.MAX_HOPS"] + 1):
        later = []
        for acct, last, first in frontier:
            g = by.get(acct)
            if g is None:
                continue
            if last is not None:  # keep time order, within FLOW.WINDOW_DAYS of the first hop
                g = (g[(g["ts"] >= last) & (g["ts"] <= first + win)] if fwd
                     else g[(g["ts"] <= last) & (g["ts"] >= first - win)])
            for r in g[~g["tx_id"].isin(seen)].itertuples(index=False):
                seen.add(r.tx_id)  # each transfer is followed once
                rows.append((hop, r.from_acct, r.to_acct, r.amount, r.ts, r.tx_id))
                later.append((getattr(r, nxt), r.ts, r.ts if first is None else first))
        frontier = later
    trail = pd.DataFrame(rows, columns=["hop", "from_acct", "to_acct", "amount", "ts", "tx_id"])
    return trail.assign(trace_id=f"TRACE-{cfg['_RUN']['run_id']}-{start_acct}-{direction}",
                        start_acct=start_acct, direction=direction)[TRAIL_COLUMNS]
```

### FLOW-LAYERING
หาเส้นทางเงินต่อเนื่อง ≥ 3 ทอด (A → B → C → D) ที่แต่ละทอดเกิดไม่ก่อนทอดก่อนหน้า อยู่ภายใน `FLOW.WINDOW_DAYS = 7` วันนับจากทอดแรก และส่งต่อ ≥ `FLOW.MIN_PASS_RATIO = 90%` ของยอดที่รับในทอดก่อนหน้า; บัญชีในเส้นทางต้องไม่ซ้ำกัน
ทุกบัญชีบนเส้นทางได้ Evidence R1 (1 แถวต่อบัญชีต่อเดือนของทอดแรก แสดงเส้นทางแรกที่พบ) — ค้นหาด้วยทอดกลางของเส้นทาง 3 ทอด (เส้นทางที่ยาวกว่าประกอบด้วยเส้นทาง 3 ทอดเสมอ) จึงไม่ต้องไล่ทุกเส้นทางและรันเร็วแม้ข้อมูลหนาแน่น

```python
# RECIPE FLOW-LAYERING v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: FLOW.MIN_PASS_RATIO, FLOW.WINDOW_DAYS | Input: transactions(tx_id, ts, from_acct, to_acct, amount)
def flow_layering(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"]).reset_index(drop=True)
    r, w = cfg["FLOW.MIN_PASS_RATIO"], cfg["FLOW.WINDOW_DAYS"]
    day = ((t["ts"] - t["ts"].min()) / pd.Timedelta(days=1)).to_numpy()
    amt, src, dst, per, txid = (t[c].to_numpy() for c in ("amount", "from_acct", "to_acct", "period", "tx_id"))
    ins = {a: g.index.to_numpy() for a, g in t.groupby("to_acct")}
    outs = {a: g.index.to_numpy() for a, g in t.groupby("from_acct")}
    best = {}  # (account, month) -> first path (e1, m, e3) found
    for m in range(len(t)):  # m = middle hop of a 3-hop path e1 -> m -> e3
        p, s = ins.get(src[m]), outs.get(dst[m])
        if p is None or s is None:
            continue
        p = p[(day[p] <= day[m]) & (day[p] >= day[m] - w) & (amt[m] >= r * amt[p]) & (src[p] != dst[m])]
        s = s[(day[s] >= day[m]) & (day[s] <= day[m] + w) & (amt[s] >= r * amt[m]) & (dst[s] != src[m])]
        if len(p) == 0 or len(s) == 0:
            continue
        ok = (day[s][None, :] <= day[p][:, None] + w) & (dst[s][None, :] != src[p][:, None])
        paths = [(p[i], m, s[ok[i].argmax()]) for i in np.flatnonzero(ok.any(axis=1))]
        paths += [(p[ok[:, j].argmax()], m, s[j]) for j in np.flatnonzero(ok.any(axis=0))]
        for e1, e2, e3 in paths:
            for a in (src[e1], src[e2], dst[e2], dst[e3]):
                best.setdefault((a, per[e1]), (e1, e2, e3))
    found = pd.DataFrame([{
        "entity_id": a, "period": p0, "metric": "min_pass_ratio",
        "value": round(min(amt[e2] / amt[e1], amt[e3] / amt[e2]), 4), "threshold": r,
        "explanation": f"บัญชีอยู่บนเส้นทางเงิน {src[e1]} → {src[e2]} → {dst[e2]} → {dst[e3]} (3 ทอด "
        f"ภายใน {w} วัน แต่ละทอดส่งต่อ {amt[e2] / amt[e1]:.0%} และ {amt[e3] / amt[e2]:.0%} ของยอดที่รับ; "
        f"FLOW.MIN_PASS_RATIO ≥ {r:.0%} และ FLOW.WINDOW_DAYS ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร; "
        f"แสดงเส้นทางแรกที่พบ) — ควรตรวจสอบเพิ่มเติม", "record_refs": [txid[e1], txid[e2], txid[e3]]}
        for (a, p0), (e1, e2, e3) in best.items()])
    return evidence_rows("FLOW-LAYERING", "1.0", "5.9 Network", "R1", "FLOW.MIN_PASS_RATIO", found, cfg)
```

## ข้อห้าม (Guardrails)
- รันการ์ดตามที่เขียนไว้ทุกตัวอักษร (verbatim) ห้ามแก้โค้ด ห้ามเปลี่ยนเกณฑ์ในโค้ด และห้ามเขียนการ์ดขึ้นเองแทนการ์ดที่หาไม่พบ
- ถ้าดึงการ์ดมาไม่ครบ (โค้ดถูกตัด, ไม่มีบรรทัดปิด) ห้ามรันส่วนที่ได้มา — Skip การ์ดนั้นพร้อม reason "ดึง recipe ไม่ครบ"
- ผลของการ์ดเป็นสัญญาณให้ตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุปว่าบัญชีหรือบุคคลกระทำผิดหรือเป็นบัญชีม้า — ใช้ถ้อยคำตาม AIDA-11 เช่น "สอดคล้องกับ Mule Account pattern"
- ห้ามรายงานเกณฑ์โดยไม่อ้าง key ใน AIDA-14 และต้องแจ้งว่าเป็นค่ามาตรฐานที่ปรับได้
- MULE-PATTERN / MULE-CROSS-TX / MULE-NETWORK ใช้ถ้อยคำ "สอดคล้องกับ Mule Account pattern" และ "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern" เท่านั้น — ห้ามเรียกว่า "บัญชีม้า" / "แก๊งบัญชีม้า"; collector / feeder เป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป

## ไฟล์ที่เกี่ยวข้อง
- AIDA-19 Pipeline Recipes (CORE-EVIDENCE ต้องรันก่อน)
- AIDA-17 Data & Evidence Schema (คอลัมน์ input, Evidence, Mule Network และ Money Flow trail)
- AIDA-14 Configuration Registry (Machine Config)
- AIDA-04 Statistical, AIDA-05 Behavioral / Temporal, AIDA-08 Network (หลักการของแต่ละ skill)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ใช้)
