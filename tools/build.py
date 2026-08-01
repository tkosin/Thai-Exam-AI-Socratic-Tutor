#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ประกอบคลังข้อสอบเข้า index.html

อ่าน  questions/units/unit-*.json  (ข้อสอบ แยกตามหน่วย)
  +   questions/figures.json       (คลังรูป SVG ใช้ซ้ำได้)
เขียน index.html                   (แทนที่ค่าของ const QUESTIONS)
  +   ข้อสอบคณิตศาสตร์_ม1.html      (สำเนาชื่อภาษาไทย)

ในฟิลด์ `text` ใช้ตัวคั่น [[fig]] เป็นตำแหน่งที่จะแทรกรูปที่อ้างด้วยฟิลด์ `figure`
ถ้ามี `figure` แต่ไม่มี [[fig]] จะต่อรูปไว้ท้ายโจทย์

รัน:  python3 tools/build.py [--check]
      --check = ตรวจอย่างเดียว ไม่เขียนไฟล์ (ออกด้วยรหัส 1 ถ้าไฟล์ไม่ตรง)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNITS_DIR = os.path.join(ROOT, "questions", "units")
FIGURES = os.path.join(ROOT, "questions", "figures.json")
HTML = os.path.join(ROOT, "index.html")
COPY = os.path.join(ROOT, "ข้อสอบคณิตศาสตร์_ม1.html")

PLACEHOLDER = "[[fig]]"
FIELD_ORDER = ["unit", "uname", "sub", "text", "answer", "level", "std", "tag"]


def load():
    figures = json.load(open(FIGURES, encoding="utf-8"))
    files = sorted(glob.glob(os.path.join(UNITS_DIR, "unit-*.json")))
    if not files:
        raise SystemExit(f"ไม่พบไฟล์ข้อสอบใน {UNITS_DIR}")

    questions, used = [], set()
    for path in files:
        data = json.load(open(path, encoding="utf-8"))
        name = os.path.basename(path)
        for i, q in enumerate(data["questions"], 1):
            where = f"{name} ข้อที่ {i}"
            text = q["text"]
            if "figure" in q:
                key = q["figure"]
                if key not in figures:
                    raise SystemExit(f"{where}: ไม่พบรูปชื่อ '{key}' ใน figures.json")
                used.add(key)
                text = (text.replace(PLACEHOLDER, figures[key])
                        if PLACEHOLDER in text else text + figures[key])
            elif PLACEHOLDER in text:
                raise SystemExit(f"{where}: มี {PLACEHOLDER} แต่ไม่ได้ระบุฟิลด์ figure")
            merged = dict(q, unit=data["unit"], uname=data["uname"], text=text)
            questions.append({k: merged[k] for k in FIELD_ORDER})

    unused = sorted(set(figures) - used)
    return questions, unused


def main(check_only):
    questions, unused = load()
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"(const QUESTIONS = )(\[.*?\]);", html, re.S)
    if not m:
        raise SystemExit("ไม่พบ const QUESTIONS ใน index.html")

    payload = json.dumps(questions, ensure_ascii=False, separators=(", ", ": "))
    rebuilt = html[:m.start(2)] + payload + html[m.end(2):]
    same = rebuilt == html
    copy_same = os.path.exists(COPY) and open(COPY, encoding="utf-8").read() == rebuilt

    per_unit = {}
    for q in questions:
        per_unit[q["unit"]] = per_unit.get(q["unit"], 0) + 1
    print(f"ข้อสอบ {len(questions)} ข้อ · " +
          " · ".join(f"{u}:{c}" for u, c in sorted(per_unit.items())))
    if unused:
        print(f"⚠️  รูปที่ไม่ได้ถูกใช้: {', '.join(unused)}")

    if check_only:
        if same and copy_same:
            print("✅ index.html และสำเนาตรงกับคลังข้อสอบแล้ว")
            return 0
        print("❌ ไฟล์ไม่ตรงกับคลังข้อสอบ — รัน: python3 tools/build.py")
        return 1

    open(HTML, "w", encoding="utf-8").write(rebuilt)
    open(COPY, "w", encoding="utf-8").write(rebuilt)
    print("ไม่มีการเปลี่ยนแปลง" if same else "เขียน index.html ใหม่แล้ว"
          + " (เลขข้อเปลี่ยน — อย่าลืมเพิ่มเลขเวอร์ชันของ STORE_KEY ถ้าลำดับข้อขยับ)")
    print("ซิงค์สำเนา ข้อสอบคณิตศาสตร์_ม1.html แล้ว")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
