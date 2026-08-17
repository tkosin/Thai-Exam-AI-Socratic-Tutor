#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ตรวจความถูกต้องของ index.html และคลังข้อสอบ — ใช้เป็นด่านตรวจใน CI

รัน:  python3 tools/validate.py             ตรวจทั้งหมด (รัน selftest ให้ก่อนเสมอ)
      python3 tools/validate.py --selftest  ตรวจแต่ตัวด่านตรวจความครอบคลุมเอง
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
COPY = os.path.join(ROOT, "คลังข้อสอบ_ออฟไลน์.html")
COURSES = os.path.join(ROOT, "questions", "courses.json")
TOPICS = os.path.join(ROOT, "questions", "topics.json")
DATA = os.path.join(ROOT, "data")

# แข่งขัน = โจทย์แนวสอบแข่งขัน (สพฐ./สสวท./TEDET) ยากกว่า "ยาก" และมักต้องใช้หลายหัวข้อร่วมกัน
# โอลิมปิก = แนว สอวน./TMO ยากกว่าแข่งขันอีกขั้น มักไม่มีสูตรตรง ๆ ให้ใช้
LEVELS = {"ง่าย", "กลาง", "ยาก", "แข่งขัน", "โอลิมปิก"}
LEVEL_ORDER = ("ง่าย", "กลาง", "ยาก", "แข่งขัน", "โอลิมปิก")
TAGS = {"ป.5", "ป.6", "ม.1", "ม.2", "ม.3",
        "ทบทวน ป.6", "ต่อยอด ม.2", "ต่อยอด ม.3", "ทบทวน ม.2"}
# อักษรนำของตัวชี้วัด ครบทั้ง 8 กลุ่มสาระ — ค คณิต · ว วิทย์/เทคโนโลยี · ท ไทย · ส สังคม
# พ สุขศึกษา · ศ ศิลปะ · ง การงานอาชีพ · ต ภาษาต่างประเทศ
# ตัวชี้วัดวิทย์บางมาตรฐานมีถึงสองหลัก (เช่น ว 1.2 ม.2/17) · รับทั้ง ม. และ ป.
STD_RE = re.compile(r"^([ควทสพศงต] \d\.\d [มป]\.\d/\d{1,2}|-)$")
CHOICE_LETTERS = {"ก", "ข", "ค", "ง"}
FIELDS = ("subject", "grade", "unit", "uname", "sub",
          "text", "answer", "level", "std", "tag")
# คำอธิบายวิธีคิดสั้นกว่านี้แทบไม่มีทางอธิบายอะไรได้ — กัน "ตอบ ก" ที่นับเป็นคำอธิบายไม่ได้
EXPLAIN_MIN = 40

errors, notes = [], []


def err(msg):
    errors.append(msg)


def coverage(qs, doc=None, courses=None):
    """ด่านตรวจความครอบคลุม — เทียบคลังข้อสอบกับแผนที่หัวข้อใน questions/topics.json

    แทนรายการตัวชี้วัดที่เคยฮาร์ดโค้ดไว้เฉพาะคณิตศาสตร์ ตอนนี้ใช้ได้กับทุกวิชา
    เพิ่มระดับชั้นใหม่ = เพิ่มรายวิชาใน topics.json ไม่ต้องมาแก้โค้ดตรวจ

    หัวข้อ status:
      active    — ต้องมีข้อสอบแล้ว · ไม่มี = ผิด (กันไม่ให้ "ครอบคลุม" เป็นแค่คำพูด)
      planned   — ยังไม่มี ตั้งใจไว้ทำเฟสถัดไป · ถ้าดันมีข้อสอบแล้วก็ผิด (ลืมอัปเดตแผนที่)
      practical — ตัวชี้วัดเชิงปฏิบัติ ประเมินด้วยข้อเขียนไม่ได้โดยหลักการ ("เล่นกีฬา…"
                  "แสดงนาฏศิลป์…") · ไม่บังคับให้มีข้อสอบ และไม่นับเป็นงานค้าง
                  แต่ยังนับรวมในยอดตัวชี้วัดของ check_official() ความครอบคลุมจึงยังพูดความจริง
                  ต้องมี practical_reason กำกับเสมอ กันการใช้เป็นที่ซุกหัวข้อที่แค่ทำยาก

    doc/courses ใส่เองได้เพื่อให้ selftest ป้อนข้อมูลสมมุติเข้ามาตรวจว่าด่านนี้ดักได้จริง
    """
    if doc is None:
        if not os.path.exists(TOPICS):
            err("ไม่พบ questions/topics.json (แผนที่หัวข้อสำหรับตรวจความครอบคลุม)")
            return
        doc = json.load(open(TOPICS, encoding="utf-8"))
    if courses is None:
        courses = json.load(open(COURSES, encoding="utf-8"))
    svg_types = set(doc["svg_types"])

    # ---- 9.1 ตัว topics.json เองต้องสมเหตุสมผลก่อน ----
    seen_id, by_course, unchecked = {}, {}, []
    for c in doc["courses"]:
        key = (c["subject"], c["grade"])
        if key in by_course:
            err(f"topics.json: มีรายวิชา {c['subject']} {c['grade']} ซ้ำ")
        by_course[key] = c
        stds = set()
        for t in c["topics"]:
            where = f"topics.json {t['id']}"
            if t["id"] in seen_id:
                err(f"{where}: รหัสหัวข้อซ้ำกับ {seen_id[t['id']]}")
            seen_id[t["id"]] = f"{c['slug']} {t['std']}"
            if t["std"] in stds:
                err(f"{where}: ตัวชี้วัด {t['std']} ซ้ำในวิชาเดียวกัน")
            stds.add(t["std"])
            if not STD_RE.match(t["std"]) or t["std"] == "-":
                err(f"{where}: ตัวชี้วัด '{t['std']}' ไม่ตรงรูปแบบ")
            elif f" {c['grade']}/" not in t["std"]:
                err(f"{where}: ตัวชี้วัด '{t['std']}' ไม่ใช่ของชั้น {c['grade']}")
            if t["status"] not in ("active", "planned", "practical"):
                err(f"{where}: status '{t['status']}' ต้องเป็น active · planned หรือ practical")
            if t["status"] == "practical" and not (t.get("practical_reason") or "").strip():
                err(f"{where}: status practical ต้องมี practical_reason บอกว่าทำไม"
                    "ข้อเขียนประเมินไม่ได้ (กันการใช้ practical ซุกหัวข้อที่แค่ทำยาก)")
            if t["status"] != "practical" and t.get("practical_reason"):
                err(f"{where}: มี practical_reason แต่ status ไม่ใช่ practical")
            # กติกาจากสเปก: หัวข้อที่ต้องใช้รูป ต้องบอกด้วยว่าเป็นรูปแบบไหน
            if t["needs_svg"] and not t["svg_type"]:
                err(f"{where}: needs_svg เป็น true แต่ไม่ได้ระบุ svg_type")
            if not t["needs_svg"] and t["svg_type"]:
                err(f"{where}: needs_svg เป็น false แต่ระบุ svg_type '{t['svg_type']}'")
            if t["svg_type"] and t["svg_type"] not in svg_types:
                err(f"{where}: svg_type '{t['svg_type']}' ไม่อยู่ในรายการ svg_types")
        if not check_official(c, stds):
            unchecked.append(f"{c['subject']} {c['grade']}")
    if unchecked:
        notes.append("รายวิชาที่ยังไม่ได้ทานจำนวนตัวชี้วัดกับเอกสารหลักสูตร "
                     f"{len(unchecked)} วิชา: " + " · ".join(unchecked))

    # วิชาที่มีข้อสอบแล้ว ต้องมีแผนที่หัวข้อทุกวิชา ไม่งั้นด่านนี้ปล่อยผ่านไปเงียบ ๆ
    for c in courses:
        if (c["subject"], c["grade"]) not in by_course:
            err(f"topics.json: ไม่มีรายวิชา {c['subject']} {c['grade']} ทั้งที่มีข้อสอบแล้ว")

    # ---- 9.2 ตัวชี้วัดในคลัง ต้องมีที่อยู่ในแผนที่ ----
    # ข้อ tag ทบทวน/ต่อยอด ตั้งใจให้ข้ามชั้น จึงเทียบกับทุกชั้นของวิชาเดียวกัน
    known = {}
    for (subj, grade), c in by_course.items():
        for t in c["topics"]:
            known.setdefault(subj, {})[t["std"]] = (grade, t)
    have = {}
    for q in qs:
        if q["std"] == "-":
            continue
        have.setdefault((q["subject"], q["std"]), []).append(q)
    for (subj, std), group in sorted(have.items()):
        if std not in known.get(subj, {}):
            err(f"{subj}: ตัวชี้วัด '{std}' มีข้อสอบ {len(group)} ข้อ "
                "แต่ไม่มีในแผนที่หัวข้อ (เพิ่มใน questions/topics.json)")
    blank = sum(1 for q in qs if q["std"] == "-")
    if blank:
        notes.append(f"ข้อที่ไม่ผูกกับตัวชี้วัด (โจทย์ประยุกต์/รวมหลายหัวข้อ) {blank} ข้อ")

    # ---- 9.3 หัวข้อ active ต้องมีข้อสอบ · planned ต้องยังไม่มี ----
    for (subj, grade), c in sorted(by_course.items()):
        missing, early, nofig, waiting, done = [], [], [], [], 0
        hands_on = []
        for t in c["topics"]:
            n = len(have.get((subj, t["std"]), []))
            if t["status"] == "active":
                if n:
                    done += 1
                else:
                    missing.append(t["std"])
            elif t["status"] == "practical":
                # ไม่บังคับให้มีข้อสอบ และไม่นับเป็นงานค้าง — แต่ถ้ามีข้อสอบแล้วแปลว่า
                # เราประเมินมันด้วยข้อเขียนได้จริง คำว่า practical จึงผิด
                hands_on.append(t["std"])
                if n:
                    err(f"{subj} {grade}: หัวข้อ {t['std']} ตั้งเป็น practical "
                        f"แต่มีข้อสอบแล้ว {n} ข้อ — ถ้าประเมินด้วยข้อเขียนได้ ให้เปลี่ยนเป็น active")
            elif n:
                early.append(t["std"])
            if t["needs_svg"] and not any("<svg" in q["text"]
                                          for q in have.get((subj, t["std"]), [])):
                nofig.append(t["std"])
            waiting += check_subtopics(c, t, have.get((subj, t["std"]), []))
        if waiting:
            notes.append(f"หัวข้อย่อยที่ยังไม่มีข้อสอบใน {subj} {grade}: " + " · ".join(waiting))
        if missing:
            err(f"{subj} {grade}: หัวข้อ active ที่ยังไม่มีข้อสอบ — {', '.join(missing)}")
        if early:
            err(f"{subj} {grade}: หัวข้อ planned ที่มีข้อสอบแล้ว "
                f"ให้เปลี่ยน status เป็น active — {', '.join(early)}")
        plan = [t["std"] for t in c["topics"] if t["status"] == "planned"]
        # ตัวส่วนไม่รวมหัวข้อเชิงปฏิบัติ ไม่งั้นวิชาอย่างศิลปะจะดูเหมือนทำได้ครึ่งเดียวตลอดกาล
        # ทั้งที่ครึ่งที่เหลือไม่ใช่งานที่ค้าง แต่เป็นงานที่ตั้งใจไม่ทำ
        scope = len(c["topics"]) - len(hands_on)
        notes.append(f"หัวข้อ {subj} {grade}: มีข้อสอบ {done}/{scope}"
                     + (f" · รอทำอีก {len(plan)}" if plan else "")
                     + (f" · เชิงปฏิบัติ ประเมินด้วยข้อเขียนไม่ได้ {len(hands_on)} หัวข้อ"
                        if hands_on else "")
                     # ไม่ใช่ข้อผิดพลาด แต่เป็นงานค้าง: หัวข้อที่ควรมีรูปประกอบแต่ยังไม่มีสักข้อ
                     + (f" · ควรมีรูปแต่ยังไม่มี {len(nofig)} หัวข้อ" if nofig else ""))

    check_explain(qs, doc)

    later = doc.get("planned_courses", [])
    if later:
        notes.append(f"วิชาที่ยังไม่เริ่ม {len(later)} วิชา · "
                     + " · ".join(f"{p['subject']} {p['grade']} (เฟส {p['phase']})"
                                  for p in later[:4])
                     + (" …" if len(later) > 4 else ""))


def check_explain(qs, doc):
    """ด่านคำอธิบายวิธีคิด — ตอบผิดแล้วต้องได้เรียนรู้อะไรกลับไป

    คลังเดิม 5,175 ข้อไม่มีคำอธิบายเลยสักข้อ ตอบผิดแล้วได้แค่ "ยังไม่ถูก ลองทบทวนอีกครั้ง"
    ซึ่งไม่มีความหมายกับวิชาความรู้ — ไม่รู้ก็คือไม่รู้ ทบทวนกี่รอบก็ไม่รู้อยู่ดี
    บังคับย้อนหลังทั้งคลังไม่ได้ จึงเปิดเป็นรายวิชาด้วย explain_required ใน topics.json
    วิชาใหม่ตั้งค่านี้ตั้งแต่วันแรก · วิชาเดิมทยอยเติมแล้วค่อยเปิด

    ที่ต้องตรวจไม่ใช่แค่ "มีฟิลด์" — คำอธิบายที่ลอกตัวเลือกที่ถูกมาวางเฉย ๆ
    ผ่านด่าน "มีฟิลด์" ได้สบายโดยไม่ได้อธิบายอะไรเลย
    """
    required = {(c["subject"], c["grade"]) for c in doc["courses"]
                if c.get("explain_required")}
    filled = {}
    for i, q in enumerate(qs, 1):
        key = (q.get("subject"), q.get("grade"))
        ex = (q.get("explain") or "").strip()
        seen, has = filled.get(key, (0, 0))
        filled[key] = (seen + 1, has + bool(ex))
        if not ex:
            if key in required:
                err(f"ข้อ {i}: วิชา {key[0]} {key[1]} บังคับคำอธิบาย แต่ไม่มีฟิลด์ 'explain'")
            continue
        where = f"ข้อ {i} ({key[0]} {key[1]})"
        if len(ex) < EXPLAIN_MIN:
            err(f"{where}: คำอธิบายสั้นเกินไป {len(ex)} ตัวอักษร (อย่างน้อย {EXPLAIN_MIN})")
        # ลอกตัวเลือกที่ถูกมาวางเฉย ๆ ไม่ใช่คำอธิบาย — เทียบกับข้อความในตัวเลือกของโจทย์
        for choice in re.findall(r"<div class=\"ch\">.*?</div>", q.get("text", "")):
            body = re.sub(r"<[^>]+>", "", choice).strip()
            body = re.sub(r"^[ก-ง]\.\s*", "", body)
            if len(body) >= EXPLAIN_MIN and body in ex and len(ex) < len(body) * 1.5:
                err(f"{where}: คำอธิบายเป็นการทวนตัวเลือกเฉย ๆ ไม่ได้บอกว่าทำไม")
                break

    for key in sorted(filled, key=lambda k: (k[0], k[1])):
        seen, has = filled[key]
        if has and has < seen:
            notes.append(f"คำอธิบาย {key[0]} {key[1]}: {has}/{seen} ข้อ"
                         + ("" if key in required else " · ยังไม่บังคับ (explain_required)"))


def check_official(course, stds):
    """เทียบตัวชี้วัดที่บันทึกไว้ กับยอดที่เอกสารหลักสูตรสรุปไว้จริง

    ไม่มีด่านนี้ ตัวชี้วัดที่ตกหล่นจะเงียบสนิท — แผนที่หัวข้อบอกว่า "ครบ 30 ตัว" ได้สบาย
    ทั้งที่หลักสูตรมี 32 ตัว เพราะไม่มีอะไรรู้จักเลข 32 นอกจากตัวเอกสาร
    ฟิลด์ official จึงเก็บสามอย่างที่ตรวจกันเองได้: ยอดรวม · รหัสสาระที่มี · รหัสสาระที่ยืนยันว่าไม่มี
    รายวิชาที่ยังไม่ได้ทานกับเอกสาร จะไม่มีฟิลด์นี้ และถูกรายงานเป็นงานค้าง ไม่ใช่ผ่านฟรี
    """
    o = course.get("official")
    if not o:
        return False
    where = f"topics.json {course['subject']} {course['grade']}"
    if len(stds) != o["total"]:
        err(f"{where}: บันทึกตัวชี้วัดไว้ {len(stds)} ตัว "
            f"แต่หลักสูตรมี {o['total']} ตัว")
    codes = {s.rsplit(" ", 1)[0] for s in stds}
    missing = sorted(set(o["std_present"]) - codes)
    extra = sorted(codes - set(o["std_present"]))
    if missing:
        err(f"{where}: ไม่มีตัวชี้วัดของสาระ {', '.join(missing)} ทั้งที่หลักสูตรระบุว่ามี")
    if extra:
        err(f"{where}: มีสาระ {', '.join(extra)} ที่ไม่อยู่ในรายการสาระของชั้นนี้")
    banned = sorted(codes & set(o["std_absent"]))
    if banned:
        err(f"{where}: มีสาระ {', '.join(banned)} ทั้งที่ยืนยันแล้วว่าชั้นนี้ไม่มี")
    return True


def check_subtopics(course, topic, group):
    """หัวข้อย่อย — ตรวจละเอียดกว่าระดับตัวชี้วัด

    ตัวชี้วัดหนึ่งตัวมีหลายเรื่องย่อยได้ การมีข้อสอบของตัวชี้วัดนั้นแล้วจึงไม่ได้แปลว่าครบ
    (เช่น ค 3.1 ม.3/1 มีควอร์ไทล์ครบ แต่ไม่มีแผนภาพกล่อง เปอร์เซ็นไทล์ ค่านอกเกณฑ์เลย)
    นับด้วยคำสำคัญใน match ที่ต้องปรากฏในโจทย์หรือชื่อเรื่องย่อยของข้อ
    คืนรายชื่อหัวข้อย่อยที่ยังรอทำ เพื่อเอาไปสรุปเป็นงานค้างให้เห็น
    """
    waiting = []
    for sub in topic.get("subtopics", []):
        n = sum(1 for q in group
                if any(w in q["text"] or w in q["sub"] for w in sub["match"]))
        where = f"{course['subject']} {course['grade']} {topic['std']} · {sub['name']}"
        if sub["status"] not in ("active", "planned"):
            err(f"{where}: status '{sub['status']}' ต้องเป็น active หรือ planned")
        elif sub["status"] == "active" and not n:
            err(f"{where}: หัวข้อย่อย active แต่ไม่มีข้อสอบสักข้อ")
        elif sub["status"] == "planned":
            if n:
                err(f"{where}: หัวข้อย่อย planned แต่มีข้อสอบแล้ว {n} ข้อ "
                    "ให้เปลี่ยน status เป็น active")
            else:
                waiting.append(f"{topic['std']} {sub['name']}")
    return waiting


def main():
    # index.html เป็นแค่โค้ด ข้อสอบอยู่ใน data/*.json (ออนไลน์) และในสำเนาชื่อไทย (ออฟไลน์)
    # ตรวจจากสำเนาที่รวมไฟล์เดียว เพราะนั่นคือ "ของที่ส่งถึงผู้เรียน" ครบทั้งก้อน
    html = open(HTML, encoding="utf-8").read()
    if not os.path.exists(COPY):
        err("ไม่พบไฟล์สำเนา คลังข้อสอบ_ออฟไลน์.html")
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
    # เทคโนโลยีใช้อักษร ว เหมือนกัน เพราะเป็นสาระที่ 4 ของกลุ่มสาระวิทยาศาสตร์ฯ
    # ชื่อวิชาที่ยังไม่มีในคลังใส่ไว้ล่วงหน้า เพราะด่านนี้เงียบสนิทถ้าไม่รู้จักชื่อวิชา —
    # วิชาใหม่ที่ลืมลงทะเบียนจะผ่านฉลุยโดยไม่มีใครตรวจตัวชี้วัดให้เลย
    # "สุขศึกษา" ไม่ใช่ "สุขศึกษาและพลศึกษา" — คลังไม่ครอบคลุมพลศึกษา ชื่อวิชาต้องตรงกับของจริง
    PREFIX = {"คณิตศาสตร์": "ค", "วิทยาศาสตร์": "ว", "เทคโนโลยี": "ว",
              "ภาษาไทย": "ท", "สังคมศึกษา ศาสนา และวัฒนธรรม": "ส",
              "สุขศึกษา": "พ", "ศิลปะ": "ศ", "การงานอาชีพ": "ง",
              "ภาษาอังกฤษ": "ต"}
    unknown = sorted({q.get("subject") for q in qs} - set(PREFIX))
    if unknown:
        err(f"วิชา {', '.join(unknown)} ไม่มีอักษรตัวชี้วัดกำกับ — เพิ่มใน PREFIX "
            "ของ validate.py ไม่งั้นด่านตัวชี้วัดจะไม่ตรวจวิชานี้เลย")
    for i, q in enumerate(qs, 1):
        want = PREFIX.get(q.get("subject"))
        std = str(q.get("std", ""))
        if want and std != "-" and not std.startswith(want + " "):
            err(f"ข้อ {i}: วิชา {q.get('subject')} แต่ตัวชี้วัดเป็น '{std}'")
        # ข้อที่ติด tag ทบทวน/ต่อยอด ตั้งใจให้ตัวชี้วัดข้ามชั้น จึงยกเว้นให้
        on_grade = q.get("tag") in ("ป.5", "ป.6", "ม.1", "ม.2", "ม.3")
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

    # ---- 8. สำเนาออฟไลน์ต้องเป็นไฟล์เดียวกับ index.html ต่างแค่ข้อมูลกับฟอนต์ที่ฝังไว้ ----
    def strip(t):
        t = re.sub(r"const QUESTIONS = \[.*?\];", "const QUESTIONS = [];", t, flags=re.S)
        # สำเนาออฟไลน์ฝังฟอนต์ไว้แทนลิงก์ CDN — ตัดทั้งสองฝั่งออกก่อนเทียบโค้ด
        t = re.sub(r"/\* สร้างจาก tools/build_font\.py.*?\*/\n", "", t, flags=re.S)
        t = re.sub(r"@font-face\{font-family:'IBM Plex Sans Thai Looped'.*?\}\n?", "",
                   t, flags=re.S)
        t = re.sub(r'<link rel="preconnect" href="https://fonts\.[^\n]*\n', "", t)
        t = re.sub(r'<link href="https://fonts\.googleapis\.com[^\n]*\n', "", t)
        return t
    if strip(bundled) != strip(html):
        err("สำเนา คลังข้อสอบ_ออฟไลน์.html มีโค้ดไม่ตรงกับ index.html "
            "(รัน: python3 tools/build.py)")

    # ---- 8ก. สำเนาออฟไลน์ต้องพึ่งตัวเองได้จริง ----
    # เคยโฆษณาใน README ว่าเปิดออฟไลน์ได้ แต่ฟอนต์ยังโหลดจาก CDN — เปิดจริงแล้วฟอนต์ไม่มา
    if "fonts.googleapis.com" in bundled or "fonts.gstatic.com" in bundled:
        err("สำเนาออฟไลน์ยังอ้างถึง Google Fonts — เปิดออฟไลน์แล้วฟอนต์จะไม่มา")
    faces = bundled.count("@font-face")
    if faces < 4:
        err(f"สำเนาออฟไลน์มี @font-face แค่ {faces} ชุด "
            "(รัน: python3 tools/build_font.py && python3 tools/build.py)")
    else:
        notes.append(f"สำเนาออฟไลน์ฝังฟอนต์ไว้ {faces} น้ำหนัก ไม่ต้องพึ่ง CDN")

    # ---- 9. ความครอบคลุมหัวข้อ เทียบกับ questions/topics.json ----
    coverage(qs)

    # ---- 10. ระดับความยากต้องมีครบทุกระดับในทุกวิชา ----
    # เดิมบังคับเฉพาะคณิตศาสตร์ วิทยาศาสตร์จึงไม่มีระดับแข่งขันเลยสักข้อโดยไม่มีใครดัก
    # ระดับที่ทุกวิชาต้องมี ส่วนโอลิมปิกบังคับเฉพาะคณิตศาสตร์ (วิทย์ยังไม่มีแนวข้อสอบรองรับ)
    REQUIRED = {"คณิตศาสตร์": ("ง่าย", "กลาง", "ยาก", "แข่งขัน", "โอลิมปิก"),
                "วิทยาศาสตร์": ("ง่าย", "กลาง", "ยาก", "แข่งขัน"),
                # เทคโนโลยีมีโอลิมปิกได้ เพราะโจทย์แนว สอวน. คอมพิวเตอร์ ตอบเป็นค่าเดียวได้
                "เทคโนโลยี": ("ง่าย", "กลาง", "ยาก", "แข่งขัน", "โอลิมปิก")}
    by_course_level = {}
    for q in qs:
        key = (q.get("subject"), q.get("grade"))
        by_course_level.setdefault(key, {}).setdefault(q.get("level"), 0)
        by_course_level[key][q["level"]] += 1
    for (subj, grade), lv in sorted(by_course_level.items(), key=lambda kv: str(kv[0])):
        for need in REQUIRED.get(subj, ()):
            if need not in lv:
                err(f"{subj} {grade}: ยังไม่มีข้อสอบระดับ '{need}'")
        notes.append(f"ระดับความยาก{subj} {grade}: "
                     + " · ".join(f"{k}:{lv[k]}" for k in LEVEL_ORDER if k in lv))

    # ---- 11. สรุปจำนวนข้อตามวิชาและหน่วย ----
    for (subj, grade), cqs in by_course.items():
        per_unit = {}
        for q in cqs:
            per_unit[q["unit"]] = per_unit.get(q["unit"], 0) + 1
        notes.append(f"{subj} {grade}: {len(cqs)} ข้อ · " +
                     " · ".join(f"{u}:{c}" for u, c in sorted(per_unit.items())))
    return report()


def selftest():
    """ตรวจตัวด่านตรวจเอง — ป้อนแผนที่หัวข้อสมมุติแล้วดูว่าดักผิดได้ครบไหม

    ด่านที่ไม่เคยเห็นของผิดจริง ๆ ก็ไม่รู้ว่าตัวเองยังทำงานอยู่หรือเปล่า
    """
    def run(doc, qs, courses=()):
        global errors, notes
        keep_e, keep_n = errors, notes
        errors, notes = [], []
        try:
            coverage(qs, doc, list(courses))
            return list(errors)
        finally:
            errors, notes = keep_e, keep_n

    Q = lambda **kw: dict({"subject": "คณิตศาสตร์", "std": "ค 1.1 ม.1/1",
                           "text": "โจทย์", "sub": "เรื่องย่อย"}, **kw)

    def topic(**kw):
        return dict({"id": "T-1", "std": "ค 1.1 ม.1/1", "strand": "จำนวนและพีชคณิต",
                     "topic": "จำนวนเต็ม", "needs_svg": False, "svg_type": None,
                     "status": "active"}, **kw)

    def off(**kw):
        return dict({"total": 1, "std_present": ["ค 1.1"], "std_absent": ["ค 1.3"]}, **kw)

    def doc(*topics, **kw):
        return {"svg_types": ["number_line", "bar_chart"],
                "courses": [dict({"slug": "math-m1", "subject": "คณิตศาสตร์",
                                  "grade": "ม.1", "topics": list(topics)}, **kw)]}

    ok = [Q()]
    cases = [
        ("หัวข้อครบ ไม่มีอะไรผิด", doc(topic()), ok, ()),
        ("หัวข้อ active แต่ไม่มีข้อสอบ", doc(topic()), [], ("ยังไม่มีข้อสอบ",)),
        ("หัวข้อ planned แต่มีข้อสอบแล้ว", doc(topic(status="planned")), ok,
         ("เปลี่ยน status เป็น active",)),
        ("ตัวชี้วัดในคลังไม่มีในแผนที่", doc(topic()),
         ok + [Q(std="ค 9.9 ม.1/9")], ("ไม่มีในแผนที่หัวข้อ",)),
        ("needs_svg true แต่ไม่มี svg_type", doc(topic(needs_svg=True)), ok,
         ("ไม่ได้ระบุ svg_type",)),
        ("needs_svg false แต่ใส่ svg_type", doc(topic(svg_type="number_line")), ok,
         ("needs_svg เป็น false แต่ระบุ svg_type",)),
        ("svg_type ไม่อยู่ในรายการ", doc(topic(needs_svg=True, svg_type="ไม่มีจริง")), ok,
         ("ไม่อยู่ในรายการ svg_types",)),
        ("รหัสหัวข้อซ้ำ", doc(topic(), topic(std="ค 1.1 ม.1/2")), ok + [Q(std="ค 1.1 ม.1/2")],
         ("รหัสหัวข้อซ้ำ",)),
        ("ตัวชี้วัดซ้ำในวิชาเดียวกัน", doc(topic(), topic(id="T-2")), ok, ("ซ้ำในวิชาเดียวกัน",)),
        ("ตัวชี้วัดผิดชั้น", doc(topic(std="ค 1.1 ม.2/1")), [], ("ไม่ใช่ของชั้น ม.1",)),
        ("status สะกดผิด", doc(topic(status="ทำแล้ว")), ok,
         ("ต้องเป็น active · planned หรือ practical",)),
        ("วิชาที่มีข้อสอบแล้วแต่ไม่มีในแผนที่", doc(topic()), ok, ("ทั้งที่มีข้อสอบแล้ว",),
         [{"subject": "วิทยาศาสตร์", "grade": "ม.3"}]),
        ("หัวข้อย่อย active แต่ไม่มีข้อสอบ",
         doc(topic(subtopics=[{"name": "ก", "match": ["ไม่มีคำนี้"], "status": "active"}])),
         ok, ("หัวข้อย่อย active แต่ไม่มีข้อสอบ",)),
        ("หัวข้อย่อย planned แต่มีข้อสอบแล้ว",
         doc(topic(subtopics=[{"name": "ก", "match": ["โจทย์"], "status": "planned"}])),
         ok, ("หัวข้อย่อย planned แต่มีข้อสอบแล้ว",)),
        ("หัวข้อย่อยจับคำจากฟิลด์ sub ได้ด้วย",
         doc(topic(subtopics=[{"name": "ก", "match": ["เรื่องย่อย"], "status": "active"}])),
         ok, ()),
        # ---- ด่านทานยอดตัวชี้วัดกับเอกสารหลักสูตร ----
        ("ตัวชี้วัดครบตามยอดหลักสูตร", doc(topic(), official=off()), ok, ()),
        ("บันทึกตัวชี้วัดไม่ครบยอด", doc(topic(), official=off(total=2)), ok,
         ("บันทึกตัวชี้วัดไว้ 1 ตัว แต่หลักสูตรมี 2 ตัว",)),
        ("ขาดตัวชี้วัดทั้งสาระ", doc(topic(), official=off(std_present=["ค 1.1", "ค 2.1"], total=1)),
         ok, ("ไม่มีตัวชี้วัดของสาระ ค 2.1",)),
        ("มีสาระที่ไม่ใช่ของชั้นนี้", doc(topic(), official=off(std_present=["ค 2.1"])),
         ok, ("มีสาระ ค 1.1 ที่ไม่อยู่ในรายการสาระของชั้นนี้",)),
        ("มีสาระที่ยืนยันแล้วว่าไม่มี",
         doc(topic(), official=off(std_present=["ค 1.1"], std_absent=["ค 1.1"])), ok,
         ("ทั้งที่ยืนยันแล้วว่าชั้นนี้ไม่มี",)),
        ("รายวิชาที่ยังไม่ได้ทานยอด ไม่นับเป็นข้อผิดพลาด", doc(topic()), ok, ()),
        # ---- ด่านคำอธิบายวิธีคิด ----
        ("คลังเดิมที่ไม่ได้บังคับคำอธิบาย ต้องไม่พัง", doc(topic()), [Q(grade="ม.1")], ()),
        ("บังคับคำอธิบายแล้วแต่ไม่มีฟิลด์", doc(topic(), explain_required=True),
         [Q(grade="ม.1")], ("บังคับคำอธิบาย แต่ไม่มีฟิลด์ 'explain'",)),
        ("บังคับคำอธิบายแล้วและมีครบ", doc(topic(), explain_required=True),
         [Q(grade="ม.1", explain="จำนวนเต็มลบคูณจำนวนเต็มลบได้ผลเป็นบวก "
                                 "เพราะเป็นการกลับทิศสองครั้งบนเส้นจำนวน")], ()),
        ("คำอธิบายสั้นเกินไป", doc(topic(), explain_required=True),
         [Q(grade="ม.1", explain="ตอบ ก")], ("คำอธิบายสั้นเกินไป",)),
        # ---- หัวข้อเชิงปฏิบัติ (ประเมินด้วยข้อเขียนไม่ได้) ----
        ("practical ไม่ต้องมีข้อสอบ และไม่นับเป็นข้อผิดพลาด",
         doc(topic(status="practical", practical_reason="ตัวชี้วัดคือการเล่นกีฬาจริง")), [], ()),
        ("practical ต้องมี practical_reason",
         doc(topic(status="practical")), [], ("ต้องมี practical_reason",)),
        ("practical แต่ดันมีข้อสอบแล้ว",
         doc(topic(status="practical", practical_reason="ตัวชี้วัดคือการปฏิบัติ")), ok,
         ("ให้เปลี่ยนเป็น active",)),
        ("ใส่ practical_reason ทั้งที่ status ไม่ใช่ practical",
         doc(topic(practical_reason="อ้างว่าปฏิบัติ")), ok,
         ("แต่ status ไม่ใช่ practical",)),
        ("practical ยังนับรวมในยอดตัวชี้วัดของหลักสูตร",
         doc(topic(status="practical", practical_reason="ปฏิบัติ"), official=off(total=2)),
         [], ("บันทึกตัวชี้วัดไว้ 1 ตัว แต่หลักสูตรมี 2 ตัว",)),
        ("คำอธิบายเป็นการทวนตัวเลือกที่ถูกเฉย ๆ", doc(topic()),
         [Q(grade="ม.1",
            text='ข้อใดถูก<div class="choices">'
                 '<div class="ch"><b>ก.</b> ผลคูณของจำนวนเต็มลบสองจำนวนเป็นจำนวนเต็มบวกเสมอ</div>'
                 '</div>',
            explain="ผลคูณของจำนวนเต็มลบสองจำนวนเป็นจำนวนเต็มบวกเสมอ")],
         ("ทวนตัวเลือกเฉย ๆ",)),
    ]
    bad = []
    for name, d, qs, want, *rest in cases:
        got = run(d, qs, rest[0] if rest else [{"subject": "คณิตศาสตร์", "grade": "ม.1"}])
        for w in want:
            if not any(w in e for e in got):
                bad.append(f"{name}: ควรดักได้ '{w}' แต่ได้ {got or 'ไม่มีข้อผิดพลาด'}")
        if not want and got:
            bad.append(f"{name}: ไม่ควรมีข้อผิดพลาด แต่ได้ {got}")
    if bad:
        print("❌ selftest ของด่านตรวจความครอบคลุมไม่ผ่าน")
        for b in bad:
            print(f"   - {b}")
        return False
    return True


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
    if not selftest():
        sys.exit(1)
    if "--selftest" in sys.argv:
        print("✅ ด่านตรวจความครอบคลุมยังดักของผิดได้ครบ")
        sys.exit(0)
    sys.exit(main())
