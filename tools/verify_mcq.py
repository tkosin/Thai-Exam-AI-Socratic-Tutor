#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ตรวจว่าข้อปรนัย "ตอบถูกเพราะรู้" ไม่ใช่ "ตอบถูกเพราะเดาเป็น"

`verify_math.py` คิดเลขใหม่จากตัวโจทย์ได้ เพราะคณิตศาสตร์มีคำตอบให้คิดใหม่
แต่ภาษาไทย สังคม อังกฤษ สุขศึกษา ศิลปะ การงานอาชีพ **ไม่มีอะไรให้คิดใหม่**
ด่านของวิชาเหล่านี้จึงต้องเป็นการตรวจที่ *ไม่ต้องรู้ว่าคำตอบไหนถูก* — ตรวจว่าข้อสอบ
รั่วคำตอบออกมาทางรูปแบบหรือเปล่า ซึ่งเป็นสิ่งที่วัดได้ล้วน ๆ จากตัวข้อสอบเอง

ด่านที่ตรวจ
  1. เฉลยต้องเป็นตัวเลือกที่มีจริง            (ข้อพัง)
  2. ตัวเลือกห้ามซ้ำกันเอง                     (ข้อพัง)
  3. โจทย์+ตัวเลือกชุดเดียวกันห้ามเฉลยขัดกัน    (ข้อพัง — อันหนึ่งต้องผิดแน่นอน)
  4. ตำแหน่งเฉลยต้องไม่กองอยู่ตัวเลือกใดตัวเลือกหนึ่ง
  5. เฉลยต้องไม่ใช่ "ตัวเลือกที่ยาวที่สุด" บ่อยเกินไป

ข้อ 4 กับ 5 คือช่องที่เด็กเดาได้โดยไม่ต้องรู้เนื้อหาเลย — ถ้าเฉลย 96% อยู่ที่ ก
เด็กที่ตอบ ก ทุกข้อได้ 96% โดยไม่ต้องอ่านโจทย์ ข้อสอบชุดนั้นจึงไม่ได้วัดอะไร
และที่แย่กว่าคือมันสอนให้เด็กเชื่อว่าการเดาเป็นได้ผลดีกว่าการอ่าน

**บังคับเป็นรายวิชา** ด้วย `mcq_gate: true` ใน questions/topics.json เหมือน
`explain_required` — วิชาใหม่เปิดตั้งแต่วันแรก ส่วนวิชาเดิมรายงานตัวเลขไว้ให้เห็น
เพราะการแก้ข้อเดิมทำให้รหัสประจำข้อเปลี่ยนและความก้าวหน้าของผู้เรียนหลุด
(เหตุผลเดียวกับที่ recommendations.md 2.3 เลือกเพิ่มข้อคู่ขนานแทนการแก้ของเดิม)

รัน:  python3 tools/verify_mcq.py
      python3 tools/verify_mcq.py --selftest    ตรวจว่าด่านยังดักของผิดได้จริง
"""
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "questions")
COURSES = os.path.join(QDIR, "courses.json")
TOPICS = os.path.join(QDIR, "topics.json")

CHOICE_RE = re.compile(r'<div class="ch"><b>([ก-ง])\.</b>(.*?)</div>', re.S)
TAG_RE = re.compile(r"<[^>]+>")

# ต่ำกว่านี้ตัวเลขไม่มีความหมายทางสถิติ — ชุด 8 ข้อที่เฉลยอยู่ที่ ก สี่ครั้งไม่ใช่ความผิดปกติ
MIN_N = 20
# สุ่มล้วนแต่ละตัวเลือกได้ 25% · ให้ช่วงกว้างพอสำหรับความไม่ลงตัวของจำนวนข้อจริง
POS_MAX, POS_MIN = 0.40, 0.12
# เฉลยเป็นตัวเลือกที่ยาวที่สุด สุ่มล้วนได้ 25% · เกิน 40% แปลว่าความยาวเริ่มบอกคำตอบ
LONGEST_MAX = 0.40


def choices(text):
    """คืน [(ตัวอักษร, ข้อความตัวเลือกที่ถอด tag แล้ว)] · ข้อที่ไม่ใช่ปรนัยคืนลิสต์ว่าง"""
    return [(m.group(1), TAG_RE.sub("", m.group(2)).strip())
            for m in CHOICE_RE.finditer(text)]


def stem(text):
    """ตัวโจทย์ล้วน ๆ ไม่รวมตัวเลือก — ใช้จับข้อที่โจทย์เดียวกันแต่เฉลยขัดกัน"""
    return TAG_RE.sub("", text.split('<div class="choices">')[0]).strip()


def load():
    courses = json.load(open(COURSES, encoding="utf-8"))
    gated = set()
    if os.path.exists(TOPICS):
        doc = json.load(open(TOPICS, encoding="utf-8"))
        gated = {(c["subject"], c["grade"]) for c in doc["courses"] if c.get("mcq_gate")}
    out = []
    for c in courses:
        qs = []
        for f in sorted(glob.glob(os.path.join(QDIR, c["slug"], "unit-*.json"))):
            data = json.load(open(f, encoding="utf-8"))
            for q in data["questions"]:
                qs.append(dict(q, unit=data["unit"]))
        out.append((c, qs, (c["subject"], c["grade"]) in gated))
    return out


def check_course(course, qs, gated):
    """คืน (รายการข้อผิดพลาด, รายการตัวเลข) ของวิชาเดียว

    gated=False ยังตรวจครบทุกด่าน แต่ข้อ 4/5 รายงานเป็นตัวเลขแทนที่จะเป็นข้อผิดพลาด
    ข้อ 1–3 เป็นข้อพังจริง ไม่ใช่เรื่องสถิติ จึงเป็นข้อผิดพลาดเสมอ
    """
    errs, stats = [], []
    where = f"{course['subject']} {course['grade']}"
    mcq = [(q, choices(q["text"])) for q in qs]
    mcq = [(q, ch) for q, ch in mcq if ch]
    if not mcq:
        return errs, stats

    seen = {}
    pos = collections.Counter()
    longest = 0
    for q, ch in mcq:
        ans = str(q["answer"]).strip()
        body = {k: v for k, v in ch}
        tag = f"{where} หน่วย {q['unit']} · {stem(q['text'])[:44]}"

        # 1. เฉลยต้องชี้ไปที่ตัวเลือกที่มีจริง
        if ans not in body:
            errs.append(f"{tag} — เฉลย '{ans}' ไม่ใช่ตัวเลือกที่มีในข้อนี้ ({'/'.join(body)})")
            continue
        # 2. ตัวเลือกซ้ำกันเอง = มีคำตอบถูกสองตัวหรือตัวลวงที่ไม่ได้ลวงอะไร
        if len(set(body.values())) < len(body):
            errs.append(f"{tag} — มีตัวเลือกที่ข้อความซ้ำกัน")
        # 3. โจทย์เดียวกัน ตัวเลือกชุดเดียวกัน แต่เฉลยคนละตัว = อย่างน้อยหนึ่งข้อผิดแน่
        key = (stem(q["text"]), tuple(sorted(body.values())))
        if key in seen and seen[key] != ans:
            errs.append(f"{tag} — โจทย์และตัวเลือกชุดเดียวกับอีกข้อ "
                        f"แต่เฉลยขัดกัน ('{seen[key]}' กับ '{ans}')")
        seen.setdefault(key, ans)

        pos[ans] += 1
        # ต้อง "ยาวกว่าทุกตัวที่เหลือ" ไม่ใช่ "ยาวเท่าตัวที่ยาวที่สุด" — ชุดที่เขียนตัวเลือก
        # ยาวเท่ากันหมดคือชุดที่ไม่รั่วเลย ถ้านับแบบเสมอด้วยจะกลายเป็นรั่ว 100%
        other = max(len(v) for k, v in body.items() if k != ans)
        if len(body[ans]) > other:
            longest += 1

    n = len(mcq)
    rate = longest / n
    spread = " · ".join(f"{k}:{pos[k] * 100 // n}%" for k in "กขคง")
    stats.append(f"{where}: ปรนัย {n} ข้อ · เฉลยยาวที่สุด {rate * 100:.0f}% · {spread}"
                 + ("" if gated else " · ยังไม่บังคับ (mcq_gate)"))
    if n < MIN_N:
        return errs, stats

    if gated:
        for k in "กขคง":
            share = pos[k] / n
            if share > POS_MAX:
                errs.append(f"{where}: เฉลยอยู่ที่ '{k}' ถึง {share * 100:.0f}% "
                            f"({pos[k]}/{n}) — เดาตัวเดียวรวดก็ได้คะแนนเท่านี้")
            elif share < POS_MIN:
                errs.append(f"{where}: เฉลยอยู่ที่ '{k}' แค่ {share * 100:.0f}% "
                            f"({pos[k]}/{n}) — ผู้เรียนตัดตัวเลือกนี้ทิ้งได้โดยไม่ต้องอ่าน")
        if rate > LONGEST_MAX:
            errs.append(f"{where}: เฉลยเป็นตัวเลือกที่ยาวที่สุด {rate * 100:.0f}% "
                        f"({longest}/{n}) — เลือกตัวที่ยาวที่สุดทุกข้อก็ได้คะแนนเท่านี้ "
                        "แก้ด้วยการเขียนตัวลวงให้ยาวพอกัน ไม่ใช่ตัดคำอธิบายในเฉลยให้สั้นลง")
    return errs, stats


def selftest():
    """ป้อนของผิดที่รู้คำตอบอยู่แล้ว แล้วยืนยันว่าด่านจับได้จริง

    ด่านที่ไม่เคยเห็นของผิดก็ไม่รู้ว่าตัวเองยังทำงานอยู่หรือเปล่า
    """
    def Q(ans, opts, s="โจทย์", unit=1):
        ch = "".join(f'<div class="ch"><b>{k}.</b> {v}</div>'
                     for k, v in zip("กขคง", opts))
        return {"answer": ans, "unit": unit,
                "text": f'{s}<div class="choices">{ch}</div>'}

    course = {"subject": "ทดสอบ", "grade": "ม.1"}
    # ตัวเลือกยาวเท่ากันทุกตัว และเฉลยกระจายครบสี่ตัว = ชุดที่ควรผ่านสะอาด
    even = ["ตัวเลือกที่หนึ่ง", "ตัวเลือกที่สองน", "ตัวเลือกที่สามม", "ตัวเลือกที่สี่ๆๆ"]
    clean = [Q("กขคง"[i % 4], even, s=f"โจทย์ที่ {i}") for i in range(24)]

    cases = [
        ("ชุดสะอาดต้องไม่มีข้อผิดพลาด", clean, True, ()),
        ("เฉลยชี้ตัวเลือกที่ไม่มี",
         [Q("ง", ["ก1", "ข1", "ค1"], s="โจทย์เดี่ยว")], False,
         ("ไม่ใช่ตัวเลือกที่มีในข้อนี้",)),
        ("ตัวเลือกซ้ำกันเอง",
         [Q("ก", ["ซ้ำ", "ซ้ำ", "ค1", "ง1"], s="โจทย์เดี่ยว")], False,
         ("ข้อความซ้ำกัน",)),
        ("โจทย์เดียวกันแต่เฉลยขัดกัน",
         [Q("ก", even, s="โจทย์เดียวกัน"), Q("ข", even, s="โจทย์เดียวกัน")], False,
         ("เฉลยขัดกัน",)),
        ("เฉลยกองอยู่ตัวเลือกเดียว",
         [Q("ก", even, s=f"โจทย์ที่ {i}") for i in range(24)], True,
         ("เฉลยอยู่ที่ 'ก' ถึง 100%",)),
        ("ตัวเลือกหนึ่งแทบไม่เคยเป็นเฉลย",
         [Q("กขค"[i % 3], even, s=f"โจทย์ที่ {i}") for i in range(24)], True,
         ("เฉลยอยู่ที่ 'ง' แค่ 0%",)),
        ("เฉลยเป็นตัวที่ยาวที่สุดเกือบทุกข้อ",
         [Q("กขคง"[i % 4], [("ยาวมากกกกกกกกกกกกกก" if j == i % 4 else "สั้น")
                            for j in range(4)], s=f"โจทย์ที่ {i}") for i in range(24)],
         True, ("เฉลยเป็นตัวเลือกที่ยาวที่สุด 100%",)),
        ("วิชาที่ยังไม่บังคับ ไม่ฟ้องเรื่องสถิติ",
         [Q("ก", even, s=f"โจทย์ที่ {i}") for i in range(24)], False, ()),
        ("จำนวนข้อน้อยเกินไป ไม่ตัดสินเรื่องสถิติ",
         [Q("ก", even, s=f"โจทย์ที่ {i}") for i in range(8)], True, ()),
    ]
    bad = []
    for name, qs, gated, want in cases:
        got, _ = check_course(course, qs, gated)
        for w in want:
            if not any(w in e for e in got):
                bad.append(f"{name}: ควรดักได้ '{w}' แต่ได้ {got or 'ไม่มีข้อผิดพลาด'}")
        if not want and got:
            bad.append(f"{name}: ไม่ควรมีข้อผิดพลาด แต่ได้ {got}")
    if bad:
        print("❌ selftest ของด่านตรวจข้อปรนัยไม่ผ่าน")
        for b in bad:
            print(f"   - {b}")
        return False
    return True


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        print("✅ ด่านตรวจข้อปรนัยยังดักของผิดได้ครบ")
        return 0

    errors, stats, gated_n = [], [], 0
    for course, qs, gated in load():
        e, s = check_course(course, qs, gated)
        errors += e
        stats += s
        gated_n += gated
    for s in stats:
        print("  " + s)
    print()
    if errors:
        print(f"❌ ข้อปรนัยไม่ผ่าน {len(errors)} รายการ")
        for e in errors:
            print(f"   - {e}")
        return 1
    print(f"✅ ข้อปรนัยผ่านทุกด่าน · บังคับเต็มรูปแบบแล้ว {gated_n} วิชา "
          "(วิชาที่เหลือรายงานตัวเลขไว้ ยังไม่บังคับ — ดู docs/implementation-plan.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
