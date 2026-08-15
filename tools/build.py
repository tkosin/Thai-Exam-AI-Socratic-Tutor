#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ประกอบคลังข้อสอบเข้า index.html

อ่าน  questions/courses.json          (รายวิชา — ลำดับในไฟล์นี้คือลำดับที่ประกอบ)
  +   questions/<slug>/unit-*.json    (ข้อสอบ แยกตามหน่วยของแต่ละวิชา)
  +   questions/figures.json          (คลังรูป SVG ใช้ซ้ำได้)
เขียน index.html                      (แทนที่ค่าของ const QUESTIONS)
  +   ข้อสอบคณิตศาสตร์_ม1.html         (สำเนาชื่อภาษาไทย)

ในฟิลด์ `text` ใช้ตัวคั่น [[fig]] เป็นตำแหน่งที่จะแทรกรูปที่อ้างด้วยฟิลด์ `figure`
ถ้ามี `figure` แต่ไม่มี [[fig]] จะต่อรูปไว้ท้ายโจทย์

ทุกข้อได้ฟิลด์ `id` ที่คงที่ (ดู qid) ความก้าวหน้าของผู้เรียนอ้างด้วย id ไม่ใช่ลำดับ
จึงแทรกข้อใหม่ไว้ตรงไหนก็ได้โดยไม่ทำให้ของเดิมหาย · questions/legacy-order.json คือ
ลำดับเดิมก่อนเปลี่ยนมาใช้ id ใช้ย้ายข้อมูลของผู้เรียนที่บันทึกไว้แบบเก่าเท่านั้น ห้ามแก้

รัน:  python3 tools/build.py [--check]
      --check = ตรวจอย่างเดียว ไม่เขียนไฟล์ (ออกด้วยรหัส 1 ถ้าไฟล์ไม่ตรง)
"""
import glob
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "questions")
COURSES = os.path.join(QDIR, "courses.json")
FIGURES = os.path.join(QDIR, "figures.json")
LEGACY = os.path.join(QDIR, "legacy-order.json")
HTML = os.path.join(ROOT, "index.html")
COPY = os.path.join(ROOT, "ข้อสอบคณิตศาสตร์_ม1.html")

PLACEHOLDER = "[[fig]]"
FIELD_ORDER = ["id", "subject", "grade", "unit", "uname", "sub",
               "text", "answer", "level", "std", "tag"]


def qid(slug, unit, q):
    """รหัสประจำข้อที่คงที่ ไม่ผูกกับลำดับในอาร์เรย์

    คิดจากโจทย์ต้นทาง (ก่อนแทรกรูป) + ชื่อรูป + เฉลย — การแก้รูปใน figures.json
    จึงไม่ทำให้รหัสเปลี่ยน และความก้าวหน้าของผู้เรียนไม่หายเวลาแทรกข้อใหม่ไว้กลางคลัง
    ใส่ชื่อรูปกับเฉลยไว้ด้วย เพราะมีข้อที่ใช้ข้อความโจทย์เดียวกันแต่คนละรูป
    """
    raw = "␟".join([q["text"], q.get("figure", ""), str(q["answer"])])
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{unit:02d}-{h}"


def load():
    figures = json.load(open(FIGURES, encoding="utf-8"))
    courses = json.load(open(COURSES, encoding="utf-8"))

    questions, used, per_course = [], set(), []
    for course in courses:
        cdir = os.path.join(QDIR, course["slug"])
        files = sorted(glob.glob(os.path.join(cdir, "unit-*.json")))
        if not files:
            raise SystemExit(f"ไม่พบไฟล์ข้อสอบใน questions/{course['slug']}/")

        start = len(questions)
        for path in files:
            data = json.load(open(path, encoding="utf-8"))
            name = f"{course['slug']}/{os.path.basename(path)}"
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
                merged = dict(q, subject=course["subject"], grade=course["grade"],
                              unit=data["unit"], uname=data["uname"], text=text,
                              id=qid(course["slug"], data["unit"], q))
                missing = [k for k in FIELD_ORDER if k not in merged]
                if missing:
                    raise SystemExit(f"{where}: ไม่มีฟิลด์ {', '.join(missing)}")
                questions.append({k: merged[k] for k in FIELD_ORDER})
        per_course.append((course, len(questions) - start))

    seen = {}
    for q in questions:
        if q["id"] in seen:
            raise SystemExit(f"รหัสข้อซ้ำ {q['id']}: '{seen[q['id']][:40]}' กับ '{q['text'][:40]}'")
        seen[q["id"]] = q["text"]

    unused = sorted(set(figures) - used)
    return questions, per_course, unused


def main(check_only):
    questions, per_course, unused = load()
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"(const QUESTIONS = )(\[.*?\]);", html, re.S)
    if not m:
        raise SystemExit("ไม่พบ const QUESTIONS ใน index.html")

    payload = json.dumps(questions, ensure_ascii=False, separators=(", ", ": "))
    rebuilt = html[:m.start(2)] + payload + html[m.end(2):]

    # ตารางแปลง "ลำดับข้อแบบเก่า -> id" สำหรับผู้เรียนที่บันทึกไว้ก่อนเปลี่ยนมาใช้ id
    legacy = json.load(open(LEGACY, encoding="utf-8"))
    known = {q["id"] for q in questions}
    gone = [i for i in legacy if i not in known]
    if gone:
        print(f"⚠️  มี {len(gone)} ข้อในลำดับเดิมที่ถูกลบ/แก้โจทย์ไปแล้ว "
              f"ความก้าวหน้าของข้อเหล่านั้นจะย้ายไม่ได้ (เช่น {gone[0]})")
    ml = re.search(r"(const LEGACY_IDS = )(\[.*?\]);", rebuilt, re.S)
    if not ml:
        raise SystemExit("ไม่พบ const LEGACY_IDS ใน index.html")
    rebuilt = (rebuilt[:ml.start(2)]
               + json.dumps(legacy, ensure_ascii=False, separators=(",", ":"))
               + rebuilt[ml.end(2):])
    same = rebuilt == html
    copy_same = os.path.exists(COPY) and open(COPY, encoding="utf-8").read() == rebuilt

    print(f"ข้อสอบรวม {len(questions)} ข้อ · {len(per_course)} วิชา")
    for course, n in per_course:
        units = {}
        for q in questions:
            if q["subject"] == course["subject"] and q["grade"] == course["grade"]:
                units[q["unit"]] = units.get(q["unit"], 0) + 1
        print(f"  {course['subject']} {course['grade']}: {n} ข้อ · " +
              " · ".join(f"{u}:{c}" for u, c in sorted(units.items())))
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
          + " (ถ้าลำดับข้อของวิชาเดิมขยับ อย่าลืมเพิ่มเลขเวอร์ชันของ STORE_KEY)")
    print("ซิงค์สำเนา ข้อสอบคณิตศาสตร์_ม1.html แล้ว")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
