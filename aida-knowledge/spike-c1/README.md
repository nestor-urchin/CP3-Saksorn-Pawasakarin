# AIDA Phase C1 — Spike kit (ทดสอบการโหลด engine ใน Copilot)

ชุดนี้ตอบคำถามเดียวก่อนสร้าง engine จริง (spec ข้อ 7.1): Code Interpreter ของ AIDA โหลดไฟล์ `.py` หรือ `.txt` จาก Knowledge ได้หรือไม่
ผลจะตัดสินว่า engine ของ C1 จะส่งมาในรูป **แนวทาง 3** (ไฟล์ใน Knowledge) หรือ **แนวทาง 2** (ติดตั้งจาก SharePoint หรือไฟล์แนบ)

ไฟล์ในชุดนี้
- `aida_engine_probe.py` และ `aida_engine_probe.txt` (เนื้อหาเหมือนกันทุกไบต์) มี `__version__ = "probe-1"`, `hello()` และ `summarize(path)`
- `probe-data.csv` ข้อมูลทดสอบ 50 แถว มีคอลัมน์ `amount` ผลรวมที่ถูกต้องคือ 1090927

## เตรียมการ
1. อัปโหลด `aida_engine_probe.py` และ `probe-data.csv` เข้า Knowledge ของ AIDA (ชั่วคราว) แล้วรอให้ index เสร็จ
   (ทดสอบข้อ 5 ไปพร้อมกัน: ถ้าอัปโหลด `.py` ไม่ได้ ให้บันทึกข้อความที่ระบบแสดงและลองอัปโหลด `aida_engine_probe.txt` แทน)
2. อัปโหลด `aida_engine_probe.py` ไปที่ SharePoint หรือ OneDrive และคัดลอกลิงก์ไฟล์ไว้ (ใช้ในข้อ 3)
3. เปิดแชตใหม่กับ AIDA ที่เปิดใช้ Code Interpreter

## Prompt 5 ข้อ (ส่งตามลำดับ ในแชตเดียวกัน)

**ข้อ 1 — Code Interpreter เห็นไฟล์ใน Knowledge ไหม**
```
ใช้ Code Interpreter แสดงรายการไฟล์ทั้งหมดที่มองเห็นได้ (ใช้ os.listdir หรือ glob กับโฟลเดอร์ทำงานและ /mnt ถ้ามี)
แล้วบอกว่า aida_engine_probe.py, aida_engine_probe.txt และ probe-data.csv อยู่ที่ path ใดบ้าง ให้แสดง path เต็มทุกไฟล์
ถ้าไม่เห็นไฟล์ใดเลย ให้บอกชัด ๆ ว่าไม่เห็น
```

**ข้อ 2 — import engine จาก Knowledge ได้ไหม (.py / .txt)**
```
ใช้ Code Interpreter ทดสอบสองวิธีกับ path ที่เห็นในข้อ 1 (ถ้ามีทั้ง .py และ .txt ให้ทำทั้งสองไฟล์):
วิธี A (สำหรับ .py): sys.path.insert(0, <โฟลเดอร์ที่มีไฟล์ .py>) แล้ว import aida_engine_probe จากนั้นเรียก hello()
        และ summarize(<path ของ probe-data.csv>) แสดงผลลัพธ์ทั้ง dict
วิธี A (สำหรับ .txt): คัดลอกไฟล์ .txt เป็น aida_engine_probe.py ในโฟลเดอร์ทำงาน (ไม่ใช่โฟลเดอร์ Knowledge)
        แล้วทำเหมือนวิธี A สำหรับ .py ข้างบน (import ไฟล์ .txt โดยตรงไม่ได้)
วิธี B (ทั้ง .py และ .txt): exec(open(<path ของไฟล์>, encoding="utf-8").read()) แล้วเรียก hello()
รายงานแยกทีละวิธีและทีละไฟล์ว่า ผ่าน หรือ ไม่ผ่าน พร้อม __version__ และข้อความ error เต็ม (ถ้ามี)
ระบุด้วยว่าผ่านด้วยไฟล์ .py หรือ .txt
```

**ข้อ 3 — ทางสำรอง: อ่าน engine จาก SharePoint/ไฟล์แนบแล้ว import ได้ไหม**
```
อ่านไฟล์ aida_engine_probe.py จาก <ใส่ลิงก์ SharePoint/OneDrive หรือแนบไฟล์> ด้วย Code Interpreter
เขียนลงโฟลเดอร์ทำงานชั่วคราว แล้ว import aida_engine_probe และเรียก hello()
รายงานว่า ผ่าน หรือ ไม่ผ่าน พร้อม __version__ และข้อความ error เต็ม (ถ้ามี)
```
ก่อนส่ง ให้แทนที่ `<ใส่ลิงก์ SharePoint/OneDrive หรือแนบไฟล์>` ด้วยลิงก์หรือไฟล์จริงทุกครั้ง ห้ามส่งข้อความที่ยังมี placeholder

**ข้อ 4 — ตัวแปรของ Code Interpreter อยู่ข้ามข้อความไหม**
ส่งเป็นสองข้อความ (ข้อความที่ 4a และ 4b ต้องส่งแยกกัน)
```
(4a) ใช้ Code Interpreter รัน: probe_marker = "persist-check-1" แล้วพิมพ์ค่าที่ตั้งไว้
```
```
(4b) ใช้ Code Interpreter พิมพ์ค่า probe_marker โดยไม่ตั้งค่าใหม่
ถ้ายังมีค่าอยู่ ให้ตอบค่านั้น ถ้าไม่มี ให้ตอบข้อความ error เต็ม (เช่น NameError)
```

**ข้อ 5 — Knowledge รับไฟล์ .py ไหม (ทำโดยการอัปโหลด ไม่ใช่ prompt)**
อัปโหลด `aida_engine_probe.py` เข้า Knowledge แล้วบันทึกว่า อัปโหลดสำเร็จหรือไม่ และข้อความที่ระบบแสดง
ถ้าไม่สำเร็จ ให้ลอง `aida_engine_probe.txt` และบันทึกผลแยกกัน

## กติกาตัดสิน (decision rule)
ข้อ 2 **ผ่าน** หมายถึง ข้อ 2A (import .py) **หรือ** ข้อ 2B (exec ทั้ง .py และ .txt) ได้ผล `hello()` เป็น `"AIDA engine probe OK"` อย่างน้อยหนึ่งแถว
1. ข้อ 2 **ผ่าน** → ใช้ **แนวทาง 3** (engine อยู่ใน Knowledge เป็น `aida_engine.py` หรือ `.txt` ตามไฟล์ที่ผ่าน)
2. ข้อ 2 **ไม่ผ่าน** แต่ข้อ 3 **ผ่าน** → ใช้ **แนวทาง 2** (engine ติดตั้งจาก `AIDA-16-engine-install.md`)
3. ข้อ 2 และข้อ 3 **ไม่ผ่านทั้งคู่** → **หยุด** และปรึกษาผู้ใช้ก่อนทำ Task 2 ต่อ

ข้อ 1, 4 และ 5 ไม่ใช่เงื่อนไขตัดสิน แต่ใช้ปรับรายละเอียดการออกแบบ (เช่น ข้อ 4 ไม่ผ่าน ให้ทุก Intake ส่งค่ากลับเป็น state ที่ engine รับได้เอง; ข้อ 5 ไม่ผ่าน ให้ใช้ `.txt` และเก็บ `.py` ไว้ใน repo)

## ตารางผล (กรอกแล้วส่งกลับ)

| # | ทดสอบ | ผ่าน/ไม่ผ่าน | ประเภทไฟล์ที่ผ่าน (.py / .txt) | __version__ / pandas version | ข้อความ error (ถ้ามี) | หมายเหตุ |
|---|---|---|---|---|---|---|
| 1 | Code Interpreter เห็นไฟล์ใน Knowledge (path ที่เห็น) | | | | | |
| 2A | import aida_engine_probe จาก Knowledge แล้ว hello() และ summarize() ได้ (.py; .txt ผ่านการคัดลอกเป็น .py) | | | | | |
| 2B | exec(open(...).read()) จาก Knowledge แล้ว hello() ได้ | | | | | |
| 3 | อ่านจาก SharePoint/ไฟล์แนบ แล้ว import และ hello() ได้ | | | | | |
| 4 | probe_marker ยังอยู่ในข้อความถัดไป | | | | | |
| 5 | Knowledge รับ .py (หรือ .txt) ได้ | | | | | |

## ถ้าไม่ผ่าน
เขียน `Ruling:` ในแชตนี้ แล้วปรึกษาก่อนทำ Task 2 ต่อ อย่าเดาวิธีแก้เอง

## หลัง spike เสร็จ (ขั้นตอนลบ)
1. ลบ `aida_engine_probe.py`, `aida_engine_probe.txt` และ `probe-data.csv` ออกจาก Knowledge ของ AIDA
2. ลบไฟล์ `aida_engine_probe.py` ที่อัปโหลดไว้ใน SharePoint/OneDrive และลบไฟล์ที่ Copilot สร้างระหว่างทดสอบ
3. เก็บโฟลเดอร์ `aida-knowledge/spike-c1/` ใน repo ไว้เป็นหลักฐานผล spike และบันทึกผลตารางข้างบนลงใน Task 10
