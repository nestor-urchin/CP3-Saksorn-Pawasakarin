# AIDA Phase B1 — Spike kit (ทดสอบ Code Interpreter)

ชุดนี้ใช้ตรวจ assumption 4 ข้อก่อนสร้างงานจริงต่อ ถ้าข้อใดไม่ผ่าน ให้หยุดและแจ้งผล เพื่อปรับ design ก่อน

## เตรียมการ
1. อัปโหลด `AIDA-SPIKE-recipes.md` เข้า Knowledge ของ AIDA (ชั่วคราว) แล้วรอให้ index เสร็จ
2. อัปโหลด `spike-transactions.csv` (200 แถว: tx_id, ts, from_acct, to_acct, amount, channel) ไปที่ SharePoint หรือ OneDrive
3. เปิดแชตใหม่กับ AIDA ที่เปิดใช้ Code Interpreter

## Prompt 4 ข้อ (ส่งตามลำดับ ในแชตเดียวกัน)

**ข้อ 1 — ดึงการ์ดครบและรันได้**
```
ดึงการ์ด NET-FUNNEL จาก Knowledge มาแสดงโค้ดทั้งหมดแบบไม่ตัดทอน แล้วบอกจำนวนบรรทัด
จากนั้นรันด้วย Code Interpreter โดยกำหนด cfg = {"NET.FUNNEL": {"min_sources": 10, "out_ratio": 0.8, "days": 7}}
และ tables = {"transactions": <ข้อมูลที่ฉันแนบ/ชี้ให้ในข้อ 2>} แล้วแสดงผลลัพธ์ DataFrame
```

**ข้อ 2 — อ่านไฟล์จาก SharePoint**
```
อ่านไฟล์ spike-transactions.csv จาก SharePoint/OneDrive ที่ <ใส่ลิงก์ไฟล์> ด้วย Code Interpreter
แล้วแสดง 5 แถวแรก จำนวนแถว และ pandas version (pd.__version__)
```

**ข้อ 3 — สร้าง .xlsx ให้ดาวน์โหลด**
```
นำผลลัพธ์ NET-FUNNEL สร้างเป็นไฟล์ spike-result.xlsx 2 sheet (Summary, Findings)
ด้วย Code Interpreter แล้วให้ลิงก์ดาวน์โหลด
```

**ข้อ 4 — สร้าง .html จาก template ยาว**
```
ดึง template ใน code block ```html จาก Knowledge (AIDA-SPIKE-recipes) มาแสดงจำนวนบรรทัดและบรรทัดสุดท้าย
จากนั้นสร้างไฟล์ spike-dashboard.html จาก template นั้น โดยแทนข้อมูลใน DATA ด้วยผล NET-FUNNEL
แล้วให้ลิงก์ดาวน์โหลด ห้ามย่อหรือข้ามส่วนใดของ template
```

## ผลที่คาดหวัง (expected result)
- NET-FUNNEL ต้องพบบัญชี **F01 เพียงบัญชีเดียว**: sources = 12, total_in = 58700, out_ratio = 0.85
  (ตรวจในเครื่องแล้วด้วย `python3 -m unittest test_extract_recipes` ใน `aida-knowledge/tools`)
- การ์ดยาว 26 บรรทัดโค้ด; template ยาวประมาณ 118 บรรทัด และบรรทัดสุดท้ายต้องเป็น `<!-- END-OF-TEMPLATE -->`
  ถ้า Copilot แสดงบรรทัดสุดท้ายไม่ใช่ marker นี้ แปลว่า template ถูกตัด
- ไฟล์ .xlsx เปิดได้ และไฟล์ .html เปิดในเบราว์เซอร์ได้ มี 3 แท็บ (สรุป, Findings, Run Log) โดยไม่โหลดอะไรจากภายนอก

## ตารางผล (กรอกแล้วส่งกลับ)

| # | ทดสอบ | ผ่าน/ไม่ผ่าน | pandas version | ขนาดไฟล์ใหญ่สุดที่ลอง | หมายเหตุ |
|---|---|---|---|---|---|
| 1 | ดึงการ์ด NET-FUNNEL ครบ (26 บรรทัด) และรันพบ F01 | | | | |
| 2 | อ่านไฟล์จาก SharePoint/OneDrive | | | | |
| 3 | สร้าง .xlsx ดาวน์โหลดได้ | | | | |
| 4 | สร้าง .html และ template ครบ (เห็น END-OF-TEMPLATE) | | | | |

pandas ต้องเป็นเวอร์ชัน 1.5 ขึ้นไป ขนาดไฟล์ใหญ่สุด: ลองเพิ่มทีละขั้น (เช่น 1 MB, 5 MB, 20 MB) แล้วบันทึกขนาดสุดท้ายที่ยังอ่านได้

## ถ้าไม่ผ่าน
เขียน `Ruling:` ปรับ design ก่อนทำ Task 2 เช่น แยก template เป็นส่วนมีเลขลำดับ, ลดขนาดการ์ด หรือเปลี่ยนวิธีรับไฟล์

## หลัง spike เสร็จ (ขั้นตอนลบ)
1. ลบ `AIDA-SPIKE-recipes.md` ออกจาก Knowledge ของ AIDA (ไฟล์นี้ใช้ทดสอบเท่านั้น และไม่นับใน 20 ไฟล์ของ pack)
2. ลบไฟล์ `spike-transactions.csv` จาก SharePoint/OneDrive และลบไฟล์ผลลัพธ์ที่ Copilot สร้าง
3. เก็บโฟลเดอร์ `aida-knowledge/spike/` ใน repo ไว้เป็นหลักฐานผล spike
