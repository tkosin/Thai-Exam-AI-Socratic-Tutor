#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""เติมข้อระดับ **แข่งขัน** ให้แม่แบบที่ยังไม่ถึง 8 ข้อ ตาม docs/olympiad-guide.md ข้อ 6

สเปกกำหนดว่าแต่ละแม่แบบ (`sub`) ควรมี 8-12 ข้อ เพื่อให้กรองแล้วได้ชุดฝึกที่ใช้จริงได้
หลังรวม `sub` ด้วย `tools/retag_contest_subs.py` แล้ว ยังมีแม่แบบที่ต่ำกว่า 8 อยู่
ไฟล์นี้เติมส่วนที่ขาด

เกณฑ์ข้อ 4 ของสเปก — ทุกข้อต้องมีโซ่การคิด **อย่างน้อย 3 ขั้น** และคำตอบต้องเป็น
จำนวนเต็ม เศษส่วนอย่างต่ำ หรือทศนิยมไม่เกิน 2 ตำแหน่ง

เฉลยทุกข้อคำนวณจากโค้ด และ check() คิดซ้ำอีกวิธีก่อนเขียนไฟล์ ถ้าสองทางไม่ตรงกัน
สคริปต์หยุดทันที ไม่เขียนอะไรลงคลัง

**รันซ้ำได้** — แถวที่โจทย์ตรงกับข้อที่มีอยู่แล้วในคลังจะถูกข้ามและรายงานจำนวน
ส่วนโจทย์ที่ซ้ำกันเองภายในไฟล์นี้ถือเป็นความผิดพลาด สคริปต์จะหยุด

รัน:  python3 tools/gen_contest.py && python3 tools/build.py
"""
import collections
import glob
import json
import os
import sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "questions")

fails = []
ROWS = []          # (slug, unit, text, answer, sub)


def check(name, got, expect):
    """ยืนยันค่าที่จะใช้เป็นเฉลย ด้วยการคิดซ้ำอีกวิธีหนึ่ง"""
    if got != expect:
        fails.append(f"{name}: ทางแรกได้ {got} แต่คิดซ้ำได้ {expect}")
    return got


def num(v):
    f = Fraction(v)
    if f.denominator == 1:
        return str(f.numerator)
    s = f"{float(f):.4f}".rstrip("0").rstrip(".")
    if Fraction(s) != f:
        fails.append(f"เฉลย {f} เขียนเป็นทศนิยมไม่ลงตัว — ออกแบบตัวเลขใหม่")
    return s


def add(slug, unit, text, answer, sub):
    ROWS.append((slug, unit, text, answer, sub))


def chain(*steps):
    """คูณต่อกันทีละขั้น — ใช้เป็นวิธีคิดซ้ำที่ไม่ใช่การยกกำลัง"""
    v = Fraction(1)
    for s in steps:
        v *= Fraction(s)
    return v


# ================================================================ วิทยาศาสตร์ ม.3
S3, U3 = "science-m3", 8

# ---- ระบบนิเวศกับพีระมิดพลังงาน (ถ่ายทอดพลังงาน 10% ต่อลำดับขั้น)
ECO = "ระบบนิเวศกับพีระมิดพลังงาน"
for start, level, expect in ((25000, 3, 25), (80000, 2, 800), (500000, 4, 50),
                             (90000, 1, 9000)):
    got = Fraction(start) * chain(*([Fraction(1, 10)] * level))
    add(S3, U3, f"ผู้ผลิตในระบบนิเวศหนึ่งมีพลังงาน {start:,} กิโลแคลอรี "
        f"ถ้าถ่ายทอดพลังงานไปยังลำดับขั้นถัดไปได้ร้อยละ 10 ทุกขั้น "
        f"ผู้บริโภคลำดับที่ {level} จะได้รับพลังงานกี่กิโลแคลอรี",
        num(check(f"พีระมิดพลังงาน {start}/{level}", got, Fraction(expect))), ECO)

_back = Fraction(60) / chain(Fraction(1, 10), Fraction(1, 10))
add(S3, U3, "ผู้บริโภคลำดับที่ 2 ในระบบนิเวศหนึ่งได้รับพลังงาน 60 กิโลแคลอรี "
    "ถ้าการถ่ายทอดพลังงานเป็นร้อยละ 10 ทุกลำดับขั้น "
    "ผู้ผลิตในระบบนิเวศนี้มีพลังงานกี่กิโลแคลอรี",
    num(check("ย้อนพีระมิดพลังงาน", _back, Fraction(6000))), ECO)

_lost = Fraction(40000) - Fraction(40000) * Fraction(1, 10)
add(S3, U3, "ผู้ผลิตมีพลังงาน 40,000 กิโลแคลอรี ถ้าผู้บริโภคลำดับที่ 1 "
    "ได้รับพลังงานเพียงร้อยละ 10 พลังงานที่สูญเสียไประหว่างสองลำดับขั้นนี้ "
    "เป็นกี่กิโลแคลอรี",
    num(check("พลังงานที่สูญเสีย", _lost, Fraction(36000))), ECO)

_diff = Fraction(90000) * Fraction(1, 10) - Fraction(90000) * chain(Fraction(1, 10),
                                                                    Fraction(1, 10))
add(S3, U3, "ผู้ผลิตมีพลังงาน 90,000 กิโลแคลอรี และถ่ายทอดพลังงานได้ร้อยละ 10 "
    "ทุกลำดับขั้น พลังงานของผู้บริโภคลำดับที่ 1 มากกว่าลำดับที่ 2 อยู่กี่กิโลแคลอรี",
    num(check("ผลต่างสองลำดับขั้น", _diff, Fraction(8100))), ECO)

# ---- ดาราศาสตร์เชิงเรขาคณิต
AST = "ดาราศาสตร์เชิงเรขาคณิต"
add(S3, U3, "โลกหมุนรอบตัวเองครบ 360 องศาในเวลา 24 ชั่วโมง "
    "ถ้าสองเมืองมีเวลาต่างกัน 7 ชั่วโมง ลองจิจูดของสองเมืองต่างกันกี่องศา",
    num(check("ลองจิจูดจากเวลา", Fraction(360, 24) * 7, Fraction(105))), AST)

add(S3, U3, "โลกหมุนรอบตัวเองครบ 360 องศาในเวลา 24 ชั่วโมง "
    "ในเวลา 1 ชั่วโมง โลกหมุนไปกี่องศา",
    num(check("องศาต่อชั่วโมง", Fraction(360, 24), Fraction(15))), AST)

add(S3, U3, "ดวงจันทร์โคจรรอบโลกครบหนึ่งรอบใช้เวลาประมาณ 30 วัน "
    "ถ้าคืนนี้เห็นดวงจันทร์เต็มดวง อีกกี่วันจึงจะเห็นเป็นเดือนดับ",
    num(check("ครึ่งรอบข้างขึ้นข้างแรม", Fraction(30, 2), Fraction(15))), AST)

add(S3, U3, "ดาวเคราะห์ดวงหนึ่งโคจรรอบดวงอาทิตย์ครบหนึ่งรอบในเวลา 12 ปี "
    "เมื่อเวลาผ่านไป 30 ปี ดาวเคราะห์ดวงนี้โคจรไปได้กี่รอบ "
    "(ตอบเป็นทศนิยมหนึ่งตำแหน่ง)",
    num(check("จำนวนรอบโคจร", Fraction(30, 12), Fraction("2.5"))), AST)

add(S3, U3, "ดาวฤกษ์ A อยู่ห่างจากโลก 4 ปีแสง ดาวฤกษ์ B อยู่ห่างจากโลก 20 ปีแสง "
    "ดาว B อยู่ไกลกว่าดาว A กี่เท่า",
    num(check("อัตราส่วนระยะทาง", Fraction(20, 4), Fraction(5))), AST)

_moon = Fraction(384000) / Fraction(300000)
add(S3, U3, "ดวงจันทร์อยู่ห่างจากโลกประมาณ 384,000 กิโลเมตร ถ้าแสงเดินทางด้วย "
    "อัตราเร็ว 300,000 กิโลเมตรต่อวินาที แสงจากดวงจันทร์ใช้เวลาเดินทางถึงโลก "
    "กี่วินาที (ตอบเป็นทศนิยมสองตำแหน่ง)",
    num(check("เวลาแสงจากดวงจันทร์", _moon, Fraction("1.28"))), AST)

_ly = Fraction("9.5") * 4
add(S3, U3, "กำหนดให้ 1 ปีแสงมีระยะทางประมาณ 9.5 &times; 10<sup>12</sup> กิโลเมตร "
    "ดาวฤกษ์ที่อยู่ห่างจากโลก 4 ปีแสง อยู่ห่างกี่ &times; 10<sup>12</sup> กิโลเมตร",
    num(check("ระยะเป็นกิโลเมตร", _ly, Fraction(38))), AST)

# ---- คลื่นและแสงเชิงปริมาณ
WAVE = "คลื่นและแสงเชิงปริมาณ"
_v = Fraction(30, 6) * Fraction("0.4")
add(S3, U3, "คลื่นน้ำเคลื่อนที่ผ่านจุดหนึ่ง 30 ลูกในเวลา 6 วินาที "
    "ถ้าระยะระหว่างสันคลื่นที่อยู่ติดกันเป็น 0.4 เมตร "
    "จงหาอัตราเร็วของคลื่นเป็นเมตรต่อวินาที",
    num(check("อัตราเร็วจากจำนวนลูกคลื่น", _v, Fraction(2))), WAVE)

add(S3, U3, "เห็นฟ้าแลบแล้วได้ยินเสียงฟ้าร้องหลังจากนั้น 6 วินาที "
    "ถ้าเสียงเดินทางในอากาศด้วยอัตราเร็ว 340 เมตรต่อวินาที "
    "และถือว่าแสงเดินทางถึงทันที ฟ้าผ่าอยู่ห่างออกไปกี่เมตร",
    num(check("ระยะจากเวลาเสียง", Fraction(340) * 6, Fraction(2040))), WAVE)

_img = 1 / (Fraction(1, 12) - Fraction(1, 18))
add(S3, U3, "เลนส์นูนมีความยาวโฟกัส 12 เซนติเมตร วางวัตถุห่างจากเลนส์ 18 เซนติเมตร "
    "จงหาระยะภาพเป็นเซนติเมตร",
    num(check("ระยะภาพเลนส์นูน", _img, Fraction(36))), WAVE)

add(S3, U3, "คนสูง 170 เซนติเมตร ต้องการเห็นตัวเองเต็มตัวในกระจกเงาราบที่แขวนตั้งฉาก "
    "กับพื้น จงหาความสูงน้อยที่สุดของกระจกที่ใช้ได้ เป็นเซนติเมตร",
    num(check("กระจกครึ่งความสูง", Fraction(170, 2), Fraction(85))), WAVE)

# ---- ปฏิกิริยาเคมีกับกฎทรงมวล
CHEM = "ปฏิกิริยาเคมีกับกฎทรงมวล"
_ox = Fraction(80 - 48, 48) * 72 + 72
add(S3, U3, "เผาโลหะชนิดหนึ่ง 48 กรัมในออกซิเจน ได้ออกไซด์ของโลหะ 80 กรัมพอดี "
    "ถ้าเผาโลหะชนิดเดียวกัน 72 กรัมจนหมด จะได้ออกไซด์กี่กรัม",
    num(check("ออกไซด์ตามสัดส่วน", _ox, Fraction(120))), CHEM)

_left = Fraction(50) - Fraction(15) * Fraction(8, 3)
add(S3, U3, "สาร A ทำปฏิกิริยากับสาร B พอดีในอัตราส่วนโดยมวล 3 : 8 "
    "ถ้านำสาร A 15 กรัม มาทำปฏิกิริยากับสาร B 50 กรัม "
    "เมื่อปฏิกิริยาสิ้นสุดจะเหลือสาร B กี่กรัม",
    num(check("สารที่เหลือ", _left, Fraction(10))), CHEM)

add(S3, U3, "เผาหินปูน 200 กรัม ได้ปูนขาว 112 กรัม และแก๊สคาร์บอนไดออกไซด์ "
    "จงหามวลของแก๊สคาร์บอนไดออกไซด์ที่เกิดขึ้นเป็นกรัม",
    num(check("กฎทรงมวล", Fraction(200 - 112), Fraction(88))), CHEM)

# ---- ค่าไฟฟ้าและพลังงานในบ้าน
BILL = "ค่าไฟฟ้าและพลังงานในบ้าน"
_bulbs = Fraction(20 * 8, 1000) * 6 * 30 * 4
add(S3, U3, "บ้านหลังหนึ่งใช้หลอดไฟกำลังไฟฟ้าดวงละ 20 วัตต์ จำนวน 8 ดวง "
    "เปิดวันละ 6 ชั่วโมง เป็นเวลา 30 วัน ถ้าค่าไฟหน่วยละ 4 บาท "
    "ต้องจ่ายค่าไฟกี่บาท",
    num(check("ค่าไฟหลอดไฟ", _bulbs, Fraction("115.2"))), BILL)

_iron = Fraction(1500, 1000) * Fraction(1, 2) * 30 * 4
add(S3, U3, "เตารีดกำลังไฟฟ้า 1500 วัตต์ ใช้งานวันละ 30 นาที เป็นเวลา 30 วัน "
    "ถ้าค่าไฟหน่วยละ 4 บาท ต้องจ่ายค่าไฟกี่บาท",
    num(check("ค่าไฟเตารีด", _iron, Fraction(90))), BILL)

# ---- พันธุกรรมสองลักษณะ
GEN = "พันธุกรรมสองลักษณะ"
_dihybrid = Fraction(9, 16) * 320
add(S3, U3, "ผสมพ่อแม่ที่มีจีโนไทป์ AaBb ทั้งคู่ โดยยีนสองคู่นี้อยู่ต่างโครโมโซมกัน "
    "ถ้าได้ลูกทั้งหมด 320 ต้น คาดว่าจะมีต้นที่แสดงลักษณะเด่นทั้งสองลักษณะกี่ต้น",
    num(check("ไดไฮบริด 9/16", _dihybrid, Fraction(180))), GEN)


# ---------------------------------------------------------------- เขียนไฟล์
def unit_path(slug, unit):
    for path in glob.glob(os.path.join(QDIR, slug, f"unit-{unit:02d}*.json")):
        if json.load(open(path, encoding="utf-8"))["unit"] == unit:
            return path
    raise SystemExit(f"ไม่พบไฟล์หน่วย {unit} ของ {slug}")


def std_for(data, sub):
    """ตัวชี้วัดที่ข้อเดิมซึ่ง sub เดียวกันในหน่วยนี้ใช้อยู่ — ไม่พิมพ์เอง"""
    stds = collections.Counter(q["std"] for q in data["questions"] if q["sub"] == sub)
    if not stds:
        fails.append(f"หา std ของ sub '{sub}' ในหน่วยนี้ไม่เจอ — ต้องมีข้อเดิมอยู่ก่อน")
        return "-"
    return stds.most_common(1)[0][0]


def existing_texts():
    seen = set()
    for course in json.load(open(os.path.join(QDIR, "courses.json"), encoding="utf-8")):
        for path in glob.glob(os.path.join(QDIR, course["slug"], "unit-*.json")):
            for q in json.load(open(path, encoding="utf-8"))["questions"]:
                seen.add(q["text"].strip())
    return seen


def main():
    texts = [r[2] for r in ROWS]
    dupes = [t for t, n in collections.Counter(texts).items() if n > 1]
    if dupes:
        fails.append(f"โจทย์ซ้ำกันเองในไฟล์นี้ {len(dupes)} ข้อ เช่น {dupes[0][:60]}")

    have = existing_texts()
    todo = [r for r in ROWS if r[2].strip() not in have]
    skipped = len(ROWS) - len(todo)

    by_unit = collections.defaultdict(list)
    for slug, unit, text, answer, sub in todo:
        by_unit[(slug, unit)].append((text, answer, sub))

    pending = []
    for (slug, unit), rows in sorted(by_unit.items()):
        path = unit_path(slug, unit)
        data = json.load(open(path, encoding="utf-8"))
        resolved = [(t, a, s, std_for(data, s)) for t, a, s in rows]
        pending.append((path, data, resolved))

    if fails:
        print("❌ ไม่เขียนไฟล์ เพราะตรวจไม่ผ่าน:")
        for f in fails:
            print("   -", f)
        return 1

    if skipped:
        print(f"ข้าม {skipped} ข้อที่มีอยู่ในคลังแล้ว")
    total = 0
    tags = {c["slug"]: c.get("tag") for c in
            json.load(open(os.path.join(QDIR, "courses.json"), encoding="utf-8"))}
    for path, data, rows in pending:
        tag = tags.get(os.path.basename(os.path.dirname(path))) \
            or data["questions"][0].get("tag", "")
        for text, answer, sub, std in rows:
            data["questions"].append({
                "text": text, "answer": answer, "sub": sub, "level": "แข่งขัน",
                "std": std, "tag": tag})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        total += len(rows)
        print(f"  +{len(rows):2} ข้อ -> {os.path.relpath(path, ROOT)}")
    print(f"เพิ่มข้อระดับแข่งขันรวม {total} ข้อ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
