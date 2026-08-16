#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ประกอบคลังข้อสอบเข้า index.html

อ่าน  questions/courses.json          (รายวิชา — ลำดับในไฟล์นี้คือลำดับที่ประกอบ)
  +   questions/<slug>/unit-*.json    (ข้อสอบ แยกตามหน่วยของแต่ละวิชา)
  +   questions/figures.json          (คลังรูป SVG ใช้ซ้ำได้)
เขียน index.html                      (โค้ด + MANIFEST · ไม่มีตัวข้อสอบ)
  +   data/<slug>.json                  (ข้อสอบรายวิชา หน้าเว็บโหลดตอนกดเข้าวิชา)
  +   ข้อสอบคณิตศาสตร์_ม1.html         (สำเนาชื่อไทย รวมทุกอย่างไว้ในไฟล์เดียว เปิดออฟไลน์ได้)

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
DATA = os.path.join(ROOT, "data")
HTML = os.path.join(ROOT, "index.html")
COPY = os.path.join(ROOT, "ข้อสอบคณิตศาสตร์_ม1.html")
FONT_CSS = os.path.join(ROOT, "questions", "font-embed.css")

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


def build_texts(questions, per_course):
    """คืน (เนื้อ index.html แบบแยกข้อมูล, เนื้อสำเนาออฟไลน์แบบรวมไฟล์เดียว, ไฟล์ข้อมูลรายวิชา)

    หน้าเว็บออนไลน์โหลดข้อสอบเฉพาะวิชาที่กด — index.html จึงมีแต่โค้ดกับ MANIFEST
    (รายชื่อวิชา ชื่อหน่วย จำนวนข้อ) ที่พอให้หน้าแรกวาดได้โดยไม่ต้องโหลดข้อสอบเลย

    ส่วนสำเนาชื่อไทยยังรวมทุกอย่างไว้ในไฟล์เดียวเหมือนเดิม เพราะเปิดจาก file://
    แล้ว fetch() ถูก CORS บล็อก จะโหลดไฟล์ข้อมูลแยกไม่ได้
    """
    html = open(HTML, encoding="utf-8").read()

    def put(text, name, value):
        m = re.search(r"(const %s = )(\[.*?\]);" % name, text, re.S)
        if not m:
            raise SystemExit(f"ไม่พบ const {name} ใน index.html")
        return text[:m.start(2)] + value + text[m.end(2):]

    # MANIFEST — พอสำหรับหน้าแรก: ชื่อวิชา จำนวนข้อ ชื่อหน่วยและจำนวนข้อรายหน่วย
    manifest, data_files = [], {}
    for course, _ in per_course:
        mine = [q for q in questions
                if q["subject"] == course["subject"] and q["grade"] == course["grade"]]
        units, names = {}, {}
        for q in mine:
            units[q["unit"]] = units.get(q["unit"], 0) + 1
            names[q["unit"]] = q["uname"]
        manifest.append({
            "slug": course["slug"], "subject": course["subject"], "grade": course["grade"],
            "count": len(mine),
            "units": [{"unit": u, "uname": names[u], "count": units[u]}
                      for u in sorted(units)],
        })
        data_files[course["slug"]] = mine

    legacy = json.load(open(LEGACY, encoding="utf-8"))
    known = {q["id"] for q in questions}
    gone = [i for i in legacy if i not in known]
    if gone:
        print(f"⚠️  มี {len(gone)} ข้อในลำดับเดิมที่ถูกลบ/แก้โจทย์ไปแล้ว "
              f"ความก้าวหน้าของข้อเหล่านั้นจะย้ายไม่ได้ (เช่น {gone[0]})")

    dump = lambda v: json.dumps(v, ensure_ascii=False, separators=(", ", ": "))
    tight = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))

    shell = put(html, "LEGACY_IDS", tight(legacy))
    shell = put(shell, "MANIFEST", dump(manifest))
    split = put(shell, "QUESTIONS", "[]")            # ออนไลน์: โหลดข้อสอบทีหลัง
    bundled = embed_font(put(shell, "QUESTIONS", dump(questions)))   # ออฟไลน์: ไฟล์เดียว
    return split, bundled, data_files


# บรรทัดที่ดึงฟอนต์จาก Google Fonts — สำเนาออฟไลน์ไม่ต้องใช้ และเรียกไปก็ล้มเปล่า ๆ
CDN_FONT = re.compile(
    r'^<link rel="preconnect" href="https://fonts\.(?:googleapis|gstatic)\.com".*?\n'
    r'|^<link href="https://fonts\.googleapis\.com/css2\?family=.*?\n', re.M)


def embed_font(bundled):
    """ฝังฟอนต์ลงในสำเนาออฟไลน์ แล้วตัดลิงก์ CDN ทิ้ง

    ฝังเฉพาะสำเนาออฟไลน์ ไม่ฝังใน index.html — base64 ราว 152 KB จะดันหน้าแรก
    จาก 218 KB เป็น 370 KB ซึ่งกินผลของการแยกข้อมูลออกจาก index.html ไปเกือบหมด
    ส่วนสำเนาออฟไลน์ใหญ่ 4.4 MB อยู่แล้ว เพิ่ม 3% ไม่มีผล
    """
    if not os.path.exists(FONT_CSS):
        print("⚠️  ไม่พบ questions/font-embed.css — สำเนาออฟไลน์จะยังไม่มีฟอนต์ฝังไว้ "
              "(รัน: python3 tools/build_font.py)")
        return bundled
    css = open(FONT_CSS, encoding="utf-8").read().rstrip()
    out = CDN_FONT.sub("", bundled)
    if "<style>" not in out:
        raise SystemExit("ไม่พบแท็ก <style> ในหน้าเว็บ ฝังฟอนต์ไม่ได้")
    return out.replace("<style>", "<style>\n" + css, 1)


def main(check_only):
    questions, per_course, unused = load()
    split, bundled, data_files = build_texts(questions, per_course)

    same = split == open(HTML, encoding="utf-8").read()
    copy_same = os.path.exists(COPY) and open(COPY, encoding="utf-8").read() == bundled
    data_same = True
    for slug, qs in data_files.items():
        path = os.path.join(DATA, slug + ".json")
        want = json.dumps(qs, ensure_ascii=False, separators=(",", ":"))
        if not os.path.exists(path) or open(path, encoding="utf-8").read() != want:
            data_same = False
    # ไฟล์ข้อมูลของวิชาที่ถูกลบไปแล้วต้องไม่ค้างอยู่ ไม่งั้นเสิร์ฟของเก่าให้ผู้เรียน
    stale = ([] if not os.path.isdir(DATA) else
             sorted(set(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(DATA, "*.json")))
                    - set(data_files)))
    if stale:
        data_same = False

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
    if stale:
        print(f"⚠️  ไฟล์ข้อมูลที่ไม่มีวิชารองรับแล้ว: {', '.join(stale)}")

    if check_only:
        if same and copy_same and data_same:
            print("✅ index.html · data/*.json และสำเนาตรงกับคลังข้อสอบแล้ว")
            return 0
        print("❌ ไฟล์ไม่ตรงกับคลังข้อสอบ — รัน: python3 tools/build.py")
        return 1

    os.makedirs(DATA, exist_ok=True)
    for slug in stale:
        os.remove(os.path.join(DATA, slug + ".json"))
    for slug, qs in data_files.items():
        with open(os.path.join(DATA, slug + ".json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(qs, ensure_ascii=False, separators=(",", ":")))
    open(HTML, "w", encoding="utf-8").write(split)
    open(COPY, "w", encoding="utf-8").write(bundled)
    print("ไม่มีการเปลี่ยนแปลง" if same and copy_same and data_same
          else f"เขียน index.html + data/*.json ({len(data_files)} ไฟล์) ใหม่แล้ว")
    print("ซิงค์สำเนา ข้อสอบคณิตศาสตร์_ม1.html (รวมไฟล์เดียว เปิดออฟไลน์ได้) แล้ว")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
