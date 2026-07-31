#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ตรวจความถูกต้องของ index.html และคลังข้อสอบ — ใช้เป็นด่านตรวจใน CI

รัน:  python3 tools/validate.py
ออกด้วยรหัส 1 ถ้าพบข้อผิดพลาด
"""
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

LEVELS = {"ง่าย", "กลาง", "ยาก"}
TAGS = {"ม.1", "ทบทวน ป.6", "ต่อยอด ม.2"}
STD_RE = re.compile(r"^(ค \d\.\d ม\.\d/\d|-)$")
CHOICE_LETTERS = {"ก", "ข", "ค", "ง"}
FIELDS = ("unit", "uname", "sub", "text", "answer", "level", "std", "tag")

errors, notes = [], []


def err(msg):
    errors.append(msg)


def main():
    html = open(HTML, encoding="utf-8").read()

    m = re.search(r"const QUESTIONS = (\[.*?\]);", html, re.S)
    if not m:
        err("ไม่พบ const QUESTIONS ใน index.html")
        return report()
    try:
        qs = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        err(f"QUESTIONS ไม่ใช่ JSON ที่ถูกต้อง: {e}")
        return report()
    notes.append(f"ข้อสอบทั้งหมด {len(qs)} ข้อ")

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

    # ---- 2. เรียงตามหน่วย และชื่อหน่วยตรงกันทุกข้อ ----
    units = [q["unit"] for q in qs]
    if units != sorted(units):
        err("ข้อสอบไม่ได้เรียงตามหน่วย (จะทำให้ลำดับข้อในโหมด 'ทุกหน่วย' สลับไปมา)")
    names = {}
    for q in qs:
        names.setdefault(q["unit"], set()).add(q["uname"])
    for u, ns in sorted(names.items()):
        if len(ns) > 1:
            err(f"หน่วย {u}: ชื่อหน่วยไม่ตรงกัน {sorted(ns)}")

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

    # ---- 8. สำเนาชื่อภาษาไทยต้องตรงกับ index.html ----
    if not os.path.exists(COPY):
        err("ไม่พบไฟล์สำเนา ข้อสอบคณิตศาสตร์_ม1.html")
    elif open(COPY, encoding="utf-8").read() != html:
        err("สำเนา ข้อสอบคณิตศาสตร์_ม1.html ไม่ตรงกับ index.html "
            "(รัน: cp index.html ข้อสอบคณิตศาสตร์_ม1.html)")

    # ---- 9. สรุปจำนวนข้อตามหน่วย ----
    per_unit = {}
    for q in qs:
        per_unit[q["unit"]] = per_unit.get(q["unit"], 0) + 1
    notes.append("ต่อหน่วย: " + " · ".join(f"{u}:{c}" for u, c in sorted(per_unit.items())))
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
