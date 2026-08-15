#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ตรวจความถูกต้องของ index.html และคลังข้อสอบ — ใช้เป็นด่านตรวจใน CI

รัน:  python3 tools/validate.py
ออกด้วยรหัส 1 ถ้าพบข้อผิดพลาด
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
COPY = os.path.join(ROOT, "ข้อสอบคณิตศาสตร์_ม1.html")
COURSES = os.path.join(ROOT, "questions", "courses.json")
DATA = os.path.join(ROOT, "data")

# แข่งขัน = โจทย์แนวสอบแข่งขัน (สพฐ./สสวท./TEDET) ยากกว่า "ยาก" และมักต้องใช้หลายหัวข้อร่วมกัน
LEVELS = {"ง่าย", "กลาง", "ยาก", "แข่งขัน"}
TAGS = {"ม.1", "ม.2", "ม.3", "ทบทวน ป.6", "ต่อยอด ม.2", "ต่อยอด ม.3", "ทบทวน ม.2"}
# ค = คณิตศาสตร์ · ว = วิทยาศาสตร์ · ตัวชี้วัดวิทย์บางมาตรฐานมีถึงสองหลัก (เช่น ว 1.2 ม.2/17)
STD_RE = re.compile(r"^([คว] \d\.\d ม\.\d/\d{1,2}|-)$")
CHOICE_LETTERS = {"ก", "ข", "ค", "ง"}
FIELDS = ("subject", "grade", "unit", "uname", "sub",
          "text", "answer", "level", "std", "tag")

errors, notes = [], []


def err(msg):
    errors.append(msg)


def main():
    # index.html เป็นแค่โค้ด ข้อสอบอยู่ใน data/*.json (ออนไลน์) และในสำเนาชื่อไทย (ออฟไลน์)
    # ตรวจจากสำเนาที่รวมไฟล์เดียว เพราะนั่นคือ "ของที่ส่งถึงผู้เรียน" ครบทั้งก้อน
    html = open(HTML, encoding="utf-8").read()
    if not os.path.exists(COPY):
        err("ไม่พบไฟล์สำเนา ข้อสอบคณิตศาสตร์_ม1.html")
        return report()
    bundled = open(COPY, encoding="utf-8").read()

    m = re.search(r"const QUESTIONS = (\[.*?\]);", bundled, re.S)
    if not m:
        err("ไม่พบ const QUESTIONS ในสำเนาชื่อไทย")
        return report()
    try:
        qs = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        err(f"QUESTIONS ไม่ใช่ JSON ที่ถูกต้อง: {e}")
        return report()
    notes.append(f"ข้อสอบทั้งหมด {len(qs)} ข้อ")

    # ---- 0. ไฟล์ที่เสิร์ฟออนไลน์ต้องสอดคล้องกับสำเนา ----
    if not re.search(r"const QUESTIONS = \[\];", html):
        err("index.html ต้องไม่ฝังข้อสอบไว้ (ต้องเป็น const QUESTIONS = [];) — รัน tools/build.py")
    mm = re.search(r"const MANIFEST = (\[.*?\]);", html, re.S)
    if not mm:
        err("ไม่พบ const MANIFEST ใน index.html")
        return report()
    manifest = json.loads(mm.group(1))

    parts = []
    for c in manifest:
        path = os.path.join(DATA, c["slug"] + ".json")
        if not os.path.exists(path):
            err(f"ไม่พบไฟล์ข้อมูล data/{c['slug']}.json")
            continue
        part = json.load(open(path, encoding="utf-8"))
        parts.extend(part)
        if len(part) != c["count"]:
            err(f"data/{c['slug']}.json มี {len(part)} ข้อ แต่ MANIFEST บอก {c['count']}")
        want_units = sum(u["count"] for u in c["units"])
        if want_units != c["count"]:
            err(f"MANIFEST ของ {c['slug']}: จำนวนข้อรายหน่วยรวม {want_units} ไม่เท่ากับ {c['count']}")
    if [q["id"] for q in parts] != [q["id"] for q in qs]:
        err("data/*.json รวมกันแล้วไม่ตรงกับสำเนาชื่อไทย — รัน tools/build.py")
    extra = sorted(set(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(DATA, "*.json")))
                   - {c["slug"] for c in manifest})
    if extra:
        err(f"มีไฟล์ข้อมูลที่ไม่มีวิชารองรับแล้ว: {', '.join(extra)}")
    notes.append(f"ไฟล์ข้อมูลรายวิชา {len(manifest)} ไฟล์ · index.html {len(html.encode('utf-8'))/1024:.0f} KB")

    # ---- 1. ครบทุกฟิลด์และค่าถูกต้อง ----
    for i, q in enumerate(qs, 1):
        for f in FIELDS:
            if not q.get(f) and q.get(f) != 0:
                err(f"ข้อ {i}: ไม่มีฟิลด์ '{f}'")
        if q.get("level") not in LEVELS:
            err(f"ข้อ {i}: level '{q.get('level')}' ไม่ถูกต้อง")
        if q.get("tag") not in TAGS:
            err(f"ข้อ {i}: tag '{q.get('tag')}' ไม่ถูกต้อง")
        if not STD_RE.match(str(q.get("std", ""))):
            err(f"ข้อ {i}: std '{q.get('std')}' ไม่ตรงรูปแบบตัวชี้วัด")

    # ---- 2. วิชาต่อเนื่องกันเป็นบล็อก · เรียงตามหน่วย · ชื่อหน่วยตรงกันทุกข้อ ----
    manifest = [(c["subject"], c["grade"]) for c in json.load(open(COURSES, encoding="utf-8"))]
    blocks = []
    for q in qs:
        key = (q.get("subject"), q.get("grade"))
        if not blocks or blocks[-1] != key:
            blocks.append(key)
    if blocks != manifest:
        err(f"ลำดับวิชาใน index.html ({blocks}) ไม่ตรงกับ questions/courses.json ({manifest}) "
            "— แต่ละวิชาต้องอยู่ติดกันเป็นบล็อกและเรียงตามไฟล์ manifest")

    by_course = {}
    for q in qs:
        by_course.setdefault((q.get("subject"), q.get("grade")), []).append(q)
    for (subj, grade), cqs in by_course.items():
        units = [q["unit"] for q in cqs]
        if units != sorted(units):
            err(f"{subj} {grade}: ข้อสอบไม่ได้เรียงตามหน่วย "
                "(จะทำให้ลำดับข้อในโหมด 'ทุกหน่วย' สลับไปมา)")
        names = {}
        for q in cqs:
            names.setdefault(q["unit"], set()).add(q["uname"])
        for u, ns in sorted(names.items()):
            if len(ns) > 1:
                err(f"{subj} {grade} หน่วย {u}: ชื่อหน่วยไม่ตรงกัน {sorted(ns)}")

    # ตัวชี้วัดต้องขึ้นต้นด้วยอักษรของวิชานั้น (คณิต = ค · วิทยาศาสตร์ = ว)
    PREFIX = {"คณิตศาสตร์": "ค", "วิทยาศาสตร์": "ว"}
    for i, q in enumerate(qs, 1):
        want = PREFIX.get(q.get("subject"))
        std = str(q.get("std", ""))
        if want and std != "-" and not std.startswith(want + " "):
            err(f"ข้อ {i}: วิชา {q.get('subject')} แต่ตัวชี้วัดเป็น '{std}'")
        # ข้อที่ติด tag ทบทวน/ต่อยอด ตั้งใจให้ตัวชี้วัดข้ามชั้น จึงยกเว้นให้
        on_grade = q.get("tag") in ("ม.1", "ม.2", "ม.3")
        if std != "-" and on_grade and f" {q['grade']}/" not in std:
            err(f"ข้อ {i}: ระดับชั้น {q.get('grade')} tag '{q.get('tag')}' "
                f"แต่ตัวชี้วัดเป็น '{std}'")

    # ---- 3. ไม่มีโจทย์ซ้ำ ----
    seen = {}
    for i, q in enumerate(qs, 1):
        if q["text"] in seen:
            err(f"ข้อ {i}: โจทย์ซ้ำกับข้อ {seen[q['text']]}")
        seen[q["text"]] = i

    # ---- 4. ข้อปรนัยต้องเฉลยเป็นตัวอักษรตัวเดียว ----
    mc = 0
    for i, q in enumerate(qs, 1):
        has_choices = 'class="choices' in q["text"]
        is_letter = q["answer"].strip() in CHOICE_LETTERS
        if has_choices:
            mc += 1
            n = q["text"].count('<div class="ch">')
            if n != 4:
                err(f"ข้อ {i}: เป็นข้อปรนัยแต่มี {n} ตัวเลือก (ต้องมี 4)")
            if not is_letter:
                err(f"ข้อ {i}: เป็นข้อปรนัยแต่เฉลยเป็น '{q['answer']}' (ต้องเป็น ก/ข/ค/ง)")
        elif is_letter:
            err(f"ข้อ {i}: เฉลยเป็น '{q['answer']}' แต่โจทย์ไม่มีตัวเลือก")
    notes.append(f"ข้อปรนัย {mc} ข้อ")

    # ---- 5. SVG ทุกรูปต้องเป็น XML ที่ถูกต้อง ----
    svgs = 0
    for i, q in enumerate(qs, 1):
        for svg in re.findall(r"<svg\b.*?</svg>", q["text"], re.S):
            svgs += 1
            try:
                ET.fromstring(svg)
            except ET.ParseError as e:
                err(f"ข้อ {i}: SVG ไม่ถูกต้อง ({e})")
    notes.append(f"รูป SVG {svgs} รูป")

    # ---- 6. โค้ด JS ในไฟล์ต้องไม่มี syntax error ----
    blocks = re.findall(r"<script>([\s\S]*?)</script>", html)
    if len(blocks) != 2:
        err(f"คาดว่าจะมี <script> 2 บล็อก แต่พบ {len(blocks)}")
    for n, code in enumerate(blocks):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(code)
            path = fh.name
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        os.unlink(path)
        if r.returncode:
            err(f"บล็อกสคริปต์ที่ {n+1} มี syntax error: {r.stderr.strip().splitlines()[:3]}")

    # ---- 7. เฉลยทุกข้อต้องถูกตรวจว่า "ถูกต้อง" เมื่อกรอกค่าตรงเฉลย ----
    try:
        start = html.index("  // ---------- answer-key comparison ----------")
        end = html.index("  // ---------- solution lines ----------")
    except ValueError:
        err("ไม่พบส่วนตรวจคำตอบใน index.html")
        return report()
    harness = f"""
const QUESTIONS = {m.group(1)};
{html[start:end]}
const bad = [], manual = [];
for (const [i, q] of QUESTIONS.entries()) {{
  // กรอกค่าตรงเฉลย ต้องได้ "ถูกต้อง" เสมอ
  const s = checkAnswer(q.answer, htmlToText(q.answer)).status;
  if (s !== 'ok') bad.push([i + 1, htmlToText(q.answer), s, q.sub]);
  // เฉลยเชิงบรรยาย: คำตอบที่ผิดจะได้ 'manual' แทน 'no' (ต้องเทียบเฉลยเอง)
  if (checkAnswer(q.answer, 'คำตอบที่ไม่ตรงเฉลยแน่นอน').status === 'manual') manual.push(i + 1);
}}
console.log(JSON.stringify({{ bad, manual }}));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
        fh.write(harness)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True)
    os.unlink(path)
    if r.returncode:
        err(f"รันการตรวจเฉลยไม่สำเร็จ: {r.stderr.strip()[:400]}")
    else:
        res = json.loads(r.stdout)
        for row in res["bad"]:
            err(f"ข้อ {row[0]} ({row[3]}): กรอกค่าตรงเฉลย '{row[1]}' แต่ระบบตอบ '{row[2]}'")
        notes.append(f"เฉลยที่ตรวจอัตโนมัติไม่ได้ {len(res['manual'])} ข้อ "
                     f"(คำตอบเชิงบรรยาย)")

    # ---- 8. สำเนาออฟไลน์ต้องเป็นไฟล์เดียวกับ index.html ต่างแค่ข้อมูลที่ฝังไว้ ----
    strip = lambda t: re.sub(r"const QUESTIONS = \[.*?\];", "const QUESTIONS = [];", t, flags=re.S)
    if strip(bundled) != strip(html):
        err("สำเนา ข้อสอบคณิตศาสตร์_ม1.html มีโค้ดไม่ตรงกับ index.html "
            "(รัน: python3 tools/build.py)")

    # ---- 9. ตัวชี้วัดคณิตศาสตร์ ม.ต้น ต้องมีข้อสอบครบทุกตัว ----
    # รายการตามหลักสูตรแกนกลาง 2551 (ปรับปรุง 2560) สาระการเรียนรู้คณิตศาสตร์
    # ถ้าเพิ่มระดับชั้นใหม่ ต้องมาต่อรายการนี้ด้วย ไม่งั้น "ครอบคลุมทุกหัวข้อ" จะเป็นแค่คำพูด
    MATH_STD = {
        "ม.1": ["ค 1.1 ม.1/1", "ค 1.1 ม.1/2", "ค 1.1 ม.1/3",
                "ค 1.3 ม.1/1", "ค 1.3 ม.1/2", "ค 1.3 ม.1/3",
                "ค 2.2 ม.1/1", "ค 2.2 ม.1/2", "ค 3.1 ม.1/1"],
        "ม.2": ["ค 1.1 ม.2/1", "ค 1.1 ม.2/2", "ค 1.2 ม.2/1", "ค 1.2 ม.2/2",
                "ค 2.1 ม.2/1", "ค 2.1 ม.2/2",
                "ค 2.2 ม.2/1", "ค 2.2 ม.2/2", "ค 2.2 ม.2/3", "ค 2.2 ม.2/4", "ค 2.2 ม.2/5",
                "ค 3.1 ม.2/1"],
        "ม.3": ["ค 1.2 ม.3/1", "ค 1.2 ม.3/2",
                "ค 1.3 ม.3/1", "ค 1.3 ม.3/2", "ค 1.3 ม.3/3",
                "ค 2.1 ม.3/1", "ค 2.1 ม.3/2",
                "ค 2.2 ม.3/1", "ค 2.2 ม.3/2", "ค 2.2 ม.3/3",
                "ค 3.1 ม.3/1", "ค 3.2 ม.3/1"],
    }
    have = {}
    for q in qs:
        if q.get("subject") == "คณิตศาสตร์":
            have[q.get("std")] = have.get(q.get("std"), 0) + 1
    for grade, stds in MATH_STD.items():
        missing = [s for s in stds if s not in have]
        if missing:
            err(f"คณิตศาสตร์ {grade}: ยังไม่มีข้อสอบของตัวชี้วัด {', '.join(missing)}")
        else:
            notes.append(f"ตัวชี้วัดคณิตศาสตร์ {grade} ครบทั้ง {len(stds)} ตัว · "
                         + " · ".join(f"{s.replace(' ' + grade + '/', '/')}:{have[s]}"
                                      for s in stds))

    # ---- 10. ระดับความยากต้องมีครบทุกระดับในทุกวิชาคณิตศาสตร์ ----
    by_grade_level = {}
    for q in qs:
        if q.get("subject") == "คณิตศาสตร์":
            by_grade_level.setdefault(q.get("grade"), {}).setdefault(q.get("level"), 0)
            by_grade_level[q["grade"]][q["level"]] += 1
    for grade in sorted(by_grade_level):
        lv = by_grade_level[grade]
        if "แข่งขัน" not in lv:
            err(f"คณิตศาสตร์ {grade}: ยังไม่มีข้อสอบระดับ 'แข่งขัน'")
        notes.append(f"ระดับความยากคณิตศาสตร์ {grade}: "
                     + " · ".join(f"{k}:{lv[k]}" for k in ("ง่าย", "กลาง", "ยาก", "แข่งขัน")
                                  if k in lv))

    # ---- 11. สรุปจำนวนข้อตามวิชาและหน่วย ----
    for (subj, grade), cqs in by_course.items():
        per_unit = {}
        for q in cqs:
            per_unit[q["unit"]] = per_unit.get(q["unit"], 0) + 1
        notes.append(f"{subj} {grade}: {len(cqs)} ข้อ · " +
                     " · ".join(f"{u}:{c}" for u, c in sorted(per_unit.items())))
    return report()


def report():
    for n in notes:
        print(f"  … {n}")
    if errors:
        print(f"\n❌ พบข้อผิดพลาด {len(errors)} รายการ")
        for e in errors[:40]:
            print(f"   - {e}")
        if len(errors) > 40:
            print(f"   … และอีก {len(errors)-40} รายการ")
        return 1
    print("\n✅ ผ่านการตรวจทั้งหมด")
    return 0


if __name__ == "__main__":
    sys.exit(main())
