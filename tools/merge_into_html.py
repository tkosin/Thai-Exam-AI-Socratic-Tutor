#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""รวมข้อสอบชุดใหม่เข้า index.html

- แทรกข้อสอบต่อท้ายบล็อกของหน่วยเดียวกัน (คลังข้อสอบเรียงตามหน่วย 1-9)
- เติมฟิลด์ std / tag / level ให้ข้อสอบเดิมที่ยังไม่มี
- ข้ามข้อที่ซ้ำ (เทียบจาก text) จึงรันซ้ำได้อย่างปลอดภัย

รัน:  python3 tools/merge_into_html.py questions/phase1.json
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")

# ตัวชี้วัดตามหน่วย (ค่าเริ่มต้น)
STD_BY_UNIT = {
    1: "ค 1.1 ม.1/1", 2: "ค 1.1 ม.1/2", 3: "ค 1.1 ม.1/1", 4: "ค 2.2 ม.1/1",
    5: "ค 2.2 ม.1/2", 6: "ค 1.3 ม.1/1", 7: "ค 1.1 ม.1/3", 8: "ค 1.3 ม.1/2",
    9: "ค 3.1 ม.1/1",
    10: "-",          # โจทย์ประยุกต์ข้ามหน่วย — ไม่ผูกกับตัวชี้วัดใดตัวเดียว
}

# ประเภทข้อสอบที่ไม่ใช่ตัวชี้วัด ม.1 -> (ตัวชี้วัด, ขอบเขต)
SCOPE_BY_SUB = {
    "เส้นรอบรูป":                    ("-",            "ทบทวน ป.6"),
    "พื้นที่รูปสองมิติ":              ("-",            "ทบทวน ป.6"),
    "พื้นที่ผิว":                     ("ค 2.1 ม.2/1",  "ต่อยอด ม.2"),
    "ปริมาตร":                       ("ค 2.1 ม.2/2",  "ต่อยอด ม.2"),
    "ค่าเฉลี่ยเลขคณิต":               ("ค 3.1 ม.2/1",  "ต่อยอด ม.2"),
    "มัธยฐาน":                       ("ค 3.1 ม.2/1",  "ต่อยอด ม.2"),
    "ฐานนิยม":                       ("ค 3.1 ม.2/1",  "ต่อยอด ม.2"),
    "ค่ากลางของข้อมูล":               ("ค 3.1 ม.2/1",  "ต่อยอด ม.2"),
    "พิสัย":                         ("ค 3.1 ม.2/1",  "ต่อยอด ม.2"),
    "สมการเส้นตรง":                  ("ค 1.3 ม.1/3",  "ม.1"),
    "โจทย์ปัญหาความสัมพันธ์เชิงเส้น":  ("ค 1.3 ม.1/3",  "ม.1"),
}

# ระดับความยากของข้อสอบชุดเดิม (ประมาณจากประเภทข้อสอบ)
LEVEL_BY_SUB = {
    "บวกลบจำนวนเต็ม": "ง่าย", "คูณหารจำนวนเต็ม": "ง่าย", "โจทย์ผสมจำนวนเต็ม": "กลาง",
    "ค่าของเลขยกกำลัง": "ง่าย", "คูณเลขยกกำลัง": "ง่าย", "หารเลขยกกำลัง": "ง่าย",
    "เลขยกกำลังซ้อน": "กลาง",
    "บวกลบเศษส่วน": "ง่าย", "คูณหารเศษส่วน": "ง่าย", "บวกลบทศนิยม": "ง่าย",
    "คูณหารทศนิยม": "ง่าย", "แปลงเศษส่วนทศนิยม": "ง่าย",
    "การสร้างทางเรขาคณิต": "กลาง",
    "เส้นรอบรูป": "ง่าย", "พื้นที่รูปสองมิติ": "กลาง", "พื้นที่ผิว": "กลาง",
    "ปริมาตร": "กลาง", "มโนทัศน์รูปทรงสามมิติ": "ง่าย", "มโนทัศน์รูปคลี่": "ง่าย",
    "สมการพื้นฐาน": "ง่าย", "สมการตัวแปรสองข้าง": "กลาง", "โจทย์ปัญหาสมการ": "ยาก",
    "อัตราส่วนอย่างต่ำ": "ง่าย", "สัดส่วน": "กลาง", "ร้อยละ - หาร้อยละ": "กลาง",
    "ร้อยละ - หาส่วน": "กลาง", "ร้อยละ - หาจำนวนเต็ม": "กลาง", "โจทย์ปัญหาร้อยละ": "ยาก",
    "พิกัดและจตุภาค": "ง่าย", "อัตราการเปลี่ยนแปลง": "กลาง", "สมการเส้นตรง": "กลาง",
    "โจทย์ปัญหาความสัมพันธ์เชิงเส้น": "ยาก",
    "ค่าเฉลี่ยเลขคณิต": "ง่าย", "มัธยฐาน": "ง่าย", "ฐานนิยม": "ง่าย",
    "ค่ากลางของข้อมูล": "กลาง", "พิสัย": "ง่าย", "การอ่านข้อมูลจากตาราง": "ง่าย",
}

FIELD_ORDER = ["unit", "uname", "sub", "text", "answer", "level", "std", "tag"]


def backfill(q):
    sub = q.get("sub") or q.get("uname")
    std, tag = SCOPE_BY_SUB.get(sub, (STD_BY_UNIT[q["unit"]], "ม.1"))
    q.setdefault("std", std)
    q.setdefault("tag", tag)
    if "level" not in q:
        if sub not in LEVEL_BY_SUB:
            raise SystemExit(f"ไม่พบระดับความยากของประเภท '{sub}' — เพิ่มใน LEVEL_BY_SUB ก่อน")
        q["level"] = LEVEL_BY_SUB[sub]
    return {k: q[k] for k in FIELD_ORDER if k in q}


def main(batch_path):
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"(const QUESTIONS = )(\[.*?\]);", html, re.S)
    if not m:
        raise SystemExit("ไม่พบ const QUESTIONS ใน index.html")
    existing = json.loads(m.group(2))
    new = json.load(open(batch_path, encoding="utf-8"))

    # คลังข้อสอบต้องเรียงตามหน่วยอยู่แล้ว จึงรวมแบบต่อท้ายบล็อกของหน่วยได้
    units_seen = [q["unit"] for q in existing]
    assert units_seen == sorted(units_seen), "ข้อสอบเดิมไม่ได้เรียงตามหน่วย — ตรวจสอบก่อนรวม"

    have = {q["text"] for q in existing}
    groups = {}
    for q in existing:
        groups.setdefault(q["unit"], []).append(backfill(q))

    added = skipped = 0
    for q in new:
        if q["text"] in have:
            skipped += 1
            continue
        groups.setdefault(q["unit"], []).append(backfill(dict(q)))
        have.add(q["text"])
        added += 1

    merged = [q for u in sorted(groups) for q in groups[u]]
    payload = json.dumps(merged, ensure_ascii=False, separators=(", ", ": "))
    html = html[:m.start(2)] + payload + html[m.end(2):]
    open(HTML, "w", encoding="utf-8").write(html)

    print(f"เพิ่ม {added} ข้อ (ข้ามที่ซ้ำ {skipped} ข้อ) — คลังข้อสอบมี {len(merged)} ข้อ")
    for u in sorted(groups):
        by_tag = {}
        for q in groups[u]:
            by_tag[q["tag"]] = by_tag.get(q["tag"], 0) + 1
        detail = " · ".join(f"{k} {v}" for k, v in sorted(by_tag.items()))
        print(f"  หน่วย {u}: {len(groups[u]):>3} ข้อ   ({detail})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("ใช้: python3 tools/merge_into_html.py <batch.json>")
    main(sys.argv[1])
