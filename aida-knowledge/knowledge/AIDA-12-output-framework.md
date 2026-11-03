# AIDA-12 · Output Framework, Reporting และ Intelligence
> ไฟล์: AIDA-12 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: AIDA ส่ง Output อะไรได้บ้าง, แต่ละ Output ใช้ทำอะไรและใครใช้, Executive Summary ต้องเขียนอย่างไร, Early Warning Alert ต่างจาก Finding อย่างไร

## สรุปสั้น
ทุก Output ต้อง Drill Down ไปยัง Finding และ Evidence ได้
AIDA มี Output 16 แบบ ออกตามลำดับ workflow (AIDA-01)
Layer 8 Reporting และ Layer 9 Intelligence เปลี่ยนผลเชิงเทคนิคเป็นภาษาที่ผู้ตรวจสอบและผู้บริหารนำไปใช้ได้

## Output 16 แบบ
| # | Output | หน้าที่ | ผู้ใช้หลัก | Drill down ไปยัง |
|---|---|---|---|---|
| 01 | Dataset Profile | สรุปโครงสร้าง คุณภาพ และขอบเขตข้อมูล | ผู้ตรวจสอบ / นักวิเคราะห์ | dataset, table, field |
| 02 | Risk Context | ความเสี่ยงที่เกี่ยวข้องจาก Risk Library | ผู้ตรวจสอบ | risk ID |
| 03 | Analysis Plan | skill ที่เลือก/ข้าม พร้อมเหตุผล | ผู้ตรวจสอบ | Selection / Skip Reason |
| 04 | Evidence Package | Evidence จากทุก skill | ผู้ตรวจสอบ | record, Data Reference |
| 05 | Unified Findings | Finding ที่ลบซ้ำและเชื่อมหลักฐาน | ผู้ตรวจสอบ | Evidence ที่เชื่อม |
| 06 | Confidence Assessment | ระดับความมั่นใจต่อ Finding | ผู้ตรวจสอบ | Evidence quality |
| 07 | Materiality Assessment | ระดับนัยสำคัญต่อ Finding | ผู้ตรวจสอบ / หัวหน้างาน | exposure |
| 08 | Priority Assessment | ลำดับความสำคัญ | หัวหน้างาน | C, M, criteria |
| 09 | Interpreted Findings | Finding ในภาษาผู้ตรวจสอบ | ผู้ตรวจสอบ | Finding, Evidence |
| 10 | Recommended Audit Procedures | ขั้นตอนหาหลักฐานเพิ่ม | ผู้ตรวจสอบ | Finding |
| 11 | Audit Workbook | เอกสารทำงานรวมทุก Finding | ทีมตรวจสอบ | ทุก Output ข้างต้น |
| 12 | Executive Summary | สรุปสำหรับผู้บริหาร | ผู้บริหาร / คณะกรรมการตรวจสอบ | Finding สำคัญ |
| 13 | Executive Dashboard | ภาพรวมเชิงตัวชี้วัด | ผู้บริหาร | Finding, Priority |
| 14 | Network Investigation Package | ชุดข้อมูลเครือข่ายเพื่อการตรวจสอบเชิงลึก | ผู้ตรวจสอบ | subgraph, Evidence (AIDA-08) |
| 15 | Early Warning Alert | สัญญาณเตือนล่วงหน้า (แยกจาก Finding) | ผู้ตรวจสอบ | Evidence, Alert rule |
| 16 | Audit Trail Report | บันทึกการทำงานทุก Stage | ผู้ตรวจสอบ / QA | Lineage 7 ระดับ (AIDA-13) |

## Layer 8 · Reporting
- Audit Workbook
- Executive Summary
- Executive Dashboard
- Network Dashboard
- Investigation Package
- Management Action Summary

## Layer 9 · Intelligence
- Natural-language query
- Network exploration
- Money Flow / Network Evolution
- Emerging Risk
- Early Warning Alert
- Alert ต้องผ่าน Human Review

Alert ≠ Finding: Alert เป็นสัญญาณให้ทบทวน ยังไม่ผ่านการประเมินครบ จึงต้องแยกจาก Finding และผ่าน Human Review ก่อนเผยแพร่

## Executive Output: กฎการเขียน 7 ข้อ
1. ภาษาผู้บริหาร
2. ประเด็นสำคัญ
3. ความเสี่ยง
4. ผลกระทบทางธุรกิจ
5. สิ่งที่ควรดำเนินการ
6. ไม่เน้นค่าทางเทคนิคเกินจำเป็น
7. ไม่กล่าวหา

## ข้อห้าม (Guardrails)
- ห้ามออก Output ที่ Drill Down ไปยัง Finding และ Evidence ไม่ได้
- ห้ามเผยแพร่ Alert หรือ Output ใดก่อน Human Review
- ห้ามใส่ค่าทางเทคนิค (z, HHI, Anomaly Score) ใน Executive Output โดยไม่อธิบายความหมายทางธุรกิจ

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Stage 18, AIDA-02 Human Review, AIDA-08 Network, AIDA-11 Interpretation, AIDA-13 Audit Trail
