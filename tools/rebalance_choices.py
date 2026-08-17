#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""สลับตำแหน่งตัวเลือกของข้อปรนัย ให้เฉลยกระจายทั่วทั้ง ก ข ค ง

`verify_mcq.py` วัดได้ว่าบางวิชาเฉลยกองอยู่ตัวเลือกเดียวหนักมาก — วิทยาศาสตร์ ม.2
มีเฉลยอยู่ที่ ก ถึง 96% แปลว่าเด็กที่ตอบ ก ทุกข้อโดยไม่อ่านโจทย์ได้ 96%
ข้อสอบชุดนั้นจึงไม่ได้วัดอะไร และที่แย่กว่าคือมันสอนให้เด็กเชื่อว่าการเดาเป็น
ได้ผลดีกว่าการอ่าน

**ไม่แตะเนื้อหาสักตัวอักษร** — สลับเฉพาะลำดับที่ตัวเลือกปรากฏ แล้วแก้ตัวอักษรเฉลยตาม
ความหมายของข้อสอบจึงเหมือนเดิมทุกประการ

## เรื่องรหัสประจำข้อ

`build.py` คิดรหัสจากแฮชของ text + figure + answer การสลับจึงทำให้รหัสเปลี่ยน
และความก้าวหน้าที่ผู้เรียนบันทึกไว้จะหาข้อเดิมไม่เจอ · สคริปต์นี้จึงเขียน
`questions/id-moves.json` (รหัสเก่า -> รหัสใหม่) ไว้ให้หน้าเว็บย้ายให้เอง
เหมือนที่ `legacy-order.json` เคยใช้ย้ายตอนเปลี่ยนจากอ้างลำดับมาเป็นอ้างรหัส

ถ้ามีไฟล์อยู่แล้วจะ **ต่อสายให้** (เก่า -> กลาง -> ใหม่ ยุบเป็น เก่า -> ใหม่)
ไม่ใช่เขียนทับ ไม่งั้นผู้เรียนที่ยังไม่ได้เปิดเว็บตั้งแต่รอบก่อนจะย้ายไม่ได้

## ข้อที่ไม่แตะ

- ตัวเลือกที่เรียงเป็นตัวเลขจากน้อยไปมาก (หรือมากไปน้อย) — ลำดับมีความหมายในตัวเอง
- ตัวเลือกแบบ "ทั้งหมดข้างต้น" / "ไม่มีข้อใดถูก" — ต้องอยู่ตำแหน่งท้ายเสมอ
- วิชาที่ตำแหน่งเฉลยกระจายดีอยู่แล้ว

รัน:  python3 tools/rebalance_choices.py            ดูว่าจะแก้อะไรบ้าง (ไม่เขียนไฟล์)
      python3 tools/rebalance_choices.py --apply    เขียนไฟล์จริง
      python3 tools/rebalance_choices.py --selftest ตรวจว่าตัวสลับทำงานถูก
"""
import collections
import glob
import hashlib
import io
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "questions")
COURSES = os.path.join(QDIR, "courses.json")
MOVES = os.path.join(QDIR, "id-moves.json")

LETTERS = "กขคง"
CHOICE_RE = re.compile(r'(<div class="ch"><b>)([ก-ง])(\.</b>)(.*?)(</div>)', re.S)
TAG_RE = re.compile(r"<[^>]+>")
# ตัวเลือกที่ต้องอยู่ท้ายเสมอ ถ้าสลับจะอ่านไม่รู้เรื่อง
ANCHOR = ("ทั้งหมดข้างต้น", "ไม่มีข้อใด", "ถูกทุกข้อ", "ผิดทุกข้อ", "ข้างต้นถูก")
# เกินสัดส่วนนี้ถือว่ากองจนเดาได้ — ตรงกับ POS_MAX ของ verify_mcq.py
SKEW = 0.40
SEED = 20250816          # คงที่ เพื่อให้รันกี่ครั้งก็ได้ผลเดิม


def parts(text):
    """คืนรายการชิ้นส่วนของตัวเลือกตามลำดับที่ปรากฏ · ข้อที่ไม่ใช่ปรนัยคืนลิสต์ว่าง"""
    return [(m.start(), m.end(), m.group(2), m.group(4)) for m in CHOICE_RE.finditer(text)]


def numeric_order(bodies):
    """ตัวเลือกเป็นตัวเลขล้วนและเรียงอยู่แล้วหรือไม่ — ถ้าใช่ ลำดับมีความหมาย ห้ามสลับ"""
    vals = []
    for b in bodies:
        plain = TAG_RE.sub("", b).strip().replace(",", "")
        if not re.fullmatch(r"-?\d+(\.\d+)?", plain):
            return False
        vals.append(float(plain))
    return vals == sorted(vals) or vals == sorted(vals, reverse=True)


def swap(text, ans, target):
    """สลับเนื้อตัวเลือกที่ตำแหน่ง ans กับ target แล้วคืน (ข้อความใหม่, ตัวอักษรเฉลยใหม่)

    สลับแค่ "เนื้อ" ไม่แตะตัวอักษรกำกับ — ก ข ค ง จึงยังเรียงตามเดิมในหน้าเว็บ
    """
    p = parts(text)
    if not p or ans == target:
        return text, ans
    idx = {let: i for i, (_, _, let, _) in enumerate(p)}
    if ans not in idx or target not in idx:
        return text, ans
    i, j = idx[ans], idx[target]
    out, prev = [], 0
    for k, (s, e, let, body) in enumerate(p):
        other = p[j][3] if k == i else (p[i][3] if k == j else body)
        out.append(text[prev:s])
        out.append(f'<div class="ch"><b>{let}.</b>{other}</div>')
        prev = e
    out.append(text[prev:])
    return "".join(out), target


def targets(n):
    """ตัวอักษรเป้าหมาย n ตัว กระจายเท่ากันแล้วสับด้วยเมล็ดคงที่

    ไม่ใช้การไล่ ก ข ค ง วนไปเรื่อย ๆ เพราะนั่นคือแบบรูปที่เด็กจับได้ง่ายกว่าเดิมอีก
    (ข้อ 1 ตอบ ก ข้อ 2 ตอบ ข …) · สับด้วยเมล็ดคงที่จึงได้ทั้งกระจายเท่ากันและไม่มีแบบรูป
    """
    seq = [LETTERS[i % 4] for i in range(n)]
    random.Random(SEED).shuffle(seq)
    return seq


def load_courses():
    out = []
    for c in json.load(open(COURSES, encoding="utf-8")):
        files = sorted(glob.glob(os.path.join(QDIR, c["slug"], "unit-*.json")))
        out.append((c, files))
    return out


def patch(raw, edits):
    """แก้เฉพาะค่า text/answer ในข้อความไฟล์ตรง ๆ ไม่ประกอบ JSON ใหม่

    ไฟล์ในคลังเขียนกันคนละรูปแบบ — ย่อหน้า 1 บ้าง 2 บ้าง · บางไฟล์ข้อละบรรทัดเดียว ·
    บางไฟล์มีบรรทัดว่างคั่นเป็นกลุ่ม · บางไฟล์ไม่จบด้วยบรรทัดใหม่
    การอ่านเข้ามาแล้วเขียนกลับทั้งไฟล์จะจัดรูปแบบใหม่หมด ได้ diff บวมทั้งไฟล์
    ทั้งที่แก้จริงไม่กี่ข้อ ซึ่งกลบสิ่งที่เปลี่ยนจริงจนรีวิวไม่ได้

    edits เรียงตามลำดับข้อในไฟล์ · ค้นต่อจากตำแหน่งเดิมเสมอ จึงไม่ไปโดนข้อที่โจทย์ซ้ำกัน
    """
    out, at = [], 0
    for old_text, old_ans, new_text, new_ans in edits:
        needle = json.dumps(old_text, ensure_ascii=False)
        i = raw.find(needle, at)
        if i < 0:
            raise SystemExit(f"หาโจทย์เดิมในไฟล์ไม่เจอ: {old_text[:60]}")
        out.append(raw[at:i])
        out.append(json.dumps(new_text, ensure_ascii=False))
        at = i + len(needle)
        # เฉลยอยู่หลังโจทย์เสมอในทุกไฟล์ของคลัง (text เป็นคีย์แรกของทุกข้อ)
        want = json.dumps(old_ans, ensure_ascii=False)
        j = raw.find('"answer":', at)
        k = raw.find(want, j)
        if j < 0 or k < 0 or k > j + 40:
            raise SystemExit(f"หาเฉลยเดิมของข้อนี้ไม่เจอ: {old_text[:60]}")
        out.append(raw[at:k])
        out.append(json.dumps(new_ans, ensure_ascii=False))
        at = k + len(want)
    out.append(raw[at:])
    return "".join(out)


def qid(slug, unit, q):
    """ต้องตรงกับ build.py ทุกประการ ไม่งั้นแผนที่ย้ายรหัสจะชี้ผิดข้อ"""
    raw = "␟".join([q["text"], q.get("figure", ""), str(q["answer"])])
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{unit:02d}-{h}"


def plan_course(course, files):
    """คืน (รายการที่จะแก้, สรุปก่อน-หลัง) ของวิชาเดียว · ไม่เขียนไฟล์"""
    items = []
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        for i, q in enumerate(data["questions"]):
            p = parts(q["text"])
            if len(p) != 4:
                continue
            bodies = [b for _, _, _, b in p]
            if numeric_order(bodies):
                continue
            if any(a in TAG_RE.sub("", b) for b in bodies for a in ANCHOR):
                continue
            items.append((f, data, i, q))
    if not items:
        return [], None

    before = collections.Counter(str(q["answer"]).strip() for _, _, _, q in items)
    n = len(items)
    if max(before[k] for k in LETTERS) / n <= SKEW:
        return [], None

    want = targets(n)
    changes = []
    for (f, data, i, q), target in zip(items, want):
        ans = str(q["answer"]).strip()
        if ans == target:
            continue
        text, new_ans = swap(q["text"], ans, target)
        changes.append({"file": f, "data": data, "index": i,
                        "old_id": qid(course["slug"], data["unit"], q),
                        "text": text, "answer": new_ans})
    after = collections.Counter(want)
    return changes, (before, after, n)


def compose(old_map, new_pairs):
    """ต่อสายการย้ายรหัส — ถ้า a->b อยู่แล้วและรอบนี้ b->c ต้องได้ a->c ไม่ใช่ทับทิ้ง"""
    merged = dict(new_pairs)
    for src, dst in old_map.items():
        merged[src] = merged.get(dst, dst)
    return merged


def selftest():
    T = ('ถาม<div class="choices">'
         '<div class="ch"><b>ก.</b> หนึ่ง</div><div class="ch"><b>ข.</b> สอง</div>'
         '<div class="ch"><b>ค.</b> สาม</div><div class="ch"><b>ง.</b> สี่</div></div>')
    bad = []

    text, ans = swap(T, "ก", "ค")
    got = [b.strip() for _, _, _, b in parts(text)]
    if got != ["สาม", "สอง", "หนึ่ง", "สี่"]:
        bad.append(f"สลับเนื้อตัวเลือกผิด: {got}")
    if ans != "ค":
        bad.append(f"ตัวอักษรเฉลยใหม่ผิด: {ans}")
    if [l for _, _, l, _ in parts(text)] != list(LETTERS):
        bad.append("ตัวอักษรกำกับต้องเรียง ก ข ค ง เหมือนเดิม")
    if TAG_RE.sub("", text).count("ถาม") != 1:
        bad.append("ตัวโจทย์ถูกแตะ ทั้งที่ต้องไม่เปลี่ยน")

    same, a2 = swap(T, "ข", "ข")
    if same != T or a2 != "ข":
        bad.append("สลับกับตำแหน่งเดิมต้องไม่เปลี่ยนอะไรเลย")

    back, a3 = swap(*swap(T, "ก", "ง")[:1] + ("ง",), "ก")
    if back != T or a3 != "ก":
        bad.append("สลับกลับต้องได้ของเดิมเป๊ะ")

    if not numeric_order([" 10 ", " 20 ", " 30 ", " 40 "]):
        bad.append("ตัวเลือกตัวเลขเรียงแล้ว ต้องถูกจับได้")
    if numeric_order(["10", "40", "20", "30"]):
        bad.append("ตัวเลขที่ไม่ได้เรียง ไม่ควรถูกกันออก")
    if numeric_order(["หนึ่ง", "สอง", "สาม", "สี่"]):
        bad.append("ตัวเลือกที่เป็นข้อความ ไม่ควรถูกมองว่าเป็นตัวเลข")

    t = collections.Counter(targets(120))
    if set(t.values()) != {30}:
        bad.append(f"เป้าหมายต้องกระจายเท่ากัน: {dict(t)}")
    if targets(40)[:8] == list(LETTERS) * 2:
        bad.append("เป้าหมายเรียง ก ข ค ง วนไปเรื่อย ๆ ซึ่งเดาได้")
    if targets(40) != targets(40):
        bad.append("เป้าหมายต้องเหมือนเดิมทุกครั้งที่รัน")

    if compose({"a": "b"}, {"b": "c"}) != {"a": "c", "b": "c"}:
        bad.append("ต่อสายการย้ายรหัสผิด")

    if bad:
        print("❌ selftest ของตัวสลับตำแหน่งไม่ผ่าน")
        for b in bad:
            print(f"   - {b}")
        return False
    return True


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        print("✅ ตัวสลับตำแหน่งตัวเลือกทำงานถูก")
        return 0

    apply = "--apply" in sys.argv
    all_changes, moves = [], {}
    for course, files in load_courses():
        changes, stat = plan_course(course, files)
        if not stat:
            continue
        before, after, n = stat
        name = f"{course['subject']} {course['grade']}"
        show = lambda c: " · ".join(f"{k}:{c[k] * 100 // n}%" for k in LETTERS)
        print(f"  {name}: ปรนัย {n} ข้อ · แก้ {len(changes)} ข้อ")
        print(f"      ก่อน {show(before)}")
        print(f"      หลัง {show(after)}")
        all_changes += changes

    if not all_changes:
        print("\n✅ ทุกวิชาตำแหน่งเฉลยกระจายดีอยู่แล้ว ไม่ต้องแก้")
        return 0

    if not apply:
        print(f"\nรวมที่จะแก้ {len(all_changes)} ข้อ — ยังไม่ได้เขียนไฟล์")
        print("เขียนจริงด้วย: python3 tools/rebalance_choices.py --apply")
        return 0

    touched, by_file = {}, collections.defaultdict(list)
    for ch in all_changes:
        q = ch["data"]["questions"][ch["index"]]
        by_file[ch["file"]].append((q["text"], q["answer"], ch["text"], ch["answer"]))
        q["text"], q["answer"] = ch["text"], ch["answer"]
        slug = os.path.basename(os.path.dirname(ch["file"]))
        moves[ch["old_id"]] = qid(slug, ch["data"]["unit"], q)
        touched[ch["file"]] = ch["data"]
    for f, data in touched.items():
        raw = io.open(f, encoding="utf-8").read()
        edits = by_file[f]
        out = patch(raw, edits)
        # ยืนยันว่าการแก้ข้อความตรง ๆ ให้ข้อมูลตรงกับที่ตั้งใจ ก่อนเขียนทับของจริง
        if json.loads(out) != data:
            raise SystemExit(f"แก้ข้อความแล้วข้อมูลไม่ตรงกับที่ตั้งใจ: {f}")
        io.open(f, "w", encoding="utf-8").write(out)

    old = json.load(open(MOVES, encoding="utf-8")) if os.path.exists(MOVES) else {}
    merged = compose(old, moves)
    with io.open(MOVES, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    print(f"\n✅ แก้แล้ว {len(all_changes)} ข้อ ใน {len(touched)} ไฟล์")
    print(f"   questions/id-moves.json มี {len(merged)} รายการ "
          f"(รอบนี้เพิ่ม {len(moves)})")
    print("   ต่อไป: python3 tools/build.py แล้ว bash tools/check.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
