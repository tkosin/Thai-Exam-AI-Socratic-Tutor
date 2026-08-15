#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ตรวจว่าเฉลยของข้อสอบคณิตศาสตร์ "ถูกตามคณิตศาสตร์" จริง ไม่ใช่แค่กรอกแล้วระบบว่าถูก

validate.py ตรวจได้แค่ว่ากรอกค่าตรงเฉลยแล้ว checkAnswer() ตอบ 'ok' — ถ้าตัวสร้างข้อสอบ
ใช้สูตรผิด เฉลยก็ผิดตามกันไปทั้งชุดโดยไม่มีใครจับได้

ไฟล์นี้จึง *อ่านจากตัวโจทย์* แล้วคิดใหม่ด้วยวิธีที่ไม่เหมือนตัวสร้าง (ส่วนใหญ่ไล่ค่าดิบ ๆ
แทนการใช้สูตรปิด) ถ้าคิดแล้วไม่ตรงกับเฉลยที่บันทึกไว้ ถือว่าไม่ผ่าน

ครอบคลุมเฉพาะรูปแบบโจทย์ที่แยกวิเคราะห์ได้ ข้อที่ไม่เข้ารูปแบบใดจะถูกนับเป็น "ข้าม"
และรายงานไว้ให้เห็นว่าเหลือกี่ข้อที่ยังต้องเชื่อตัวสร้าง

รัน:  python3 tools/verify_math.py
"""
import glob
import json
import math
import os
import re
import sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "questions")

checks, skipped, bad = 0, 0, []
RULES = []


def rule(pattern):
    def deco(fn):
        RULES.append((re.compile(pattern), fn))
        return fn
    return deco


def txt(q):
    """โจทย์เป็นข้อความล้วน — ถอดแท็ก แปลงเศษส่วน/เลขยกกำลังกลับเป็นสัญกรณ์บรรทัดเดียว"""
    s = q["text"]
    s = re.sub(r'<span class="frac"><span class="num">(.*?)</span>'
               r'<span class="den">(.*?)</span></span>', r"(\1)/(\2)", s)
    s = re.sub(r"<sup>(.*?)</sup>", r"^\1", s)
    s = re.sub(r"<sub>(.*?)</sub>", r"_\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s.replace("−", "-").replace(",", "")).strip()


def num(s):
    s = str(s).strip()
    if re.fullmatch(r"-?\d+/-?\d+", s):
        return Fraction(s)
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return Fraction(s)
    return None


def want(q, value, why):
    global checks
    checks += 1
    got = num(q["answer"])
    if got is None or Fraction(value) != got:
        bad.append((q["id"], why, q["answer"], str(Fraction(value)), txt(q)[:95]))


# ---------- อสมการ ----------
@rule(r"จำนวนเต็มที่มากที่สุดที่สอดคล้องกับอสมการ (-?\d+)x ([+-]) (\d+) ≤ (-?\d+)")
def _(q, m):
    a, sg, b, c = int(m[1]), m[2], int(m[3]), int(m[4])
    b = b if sg == "+" else -b
    want(q, max(x for x in range(-500, 501) if a * x + b <= c), "อสมการ ≤")


@rule(r"จำนวนเต็มที่น้อยที่สุดที่สอดคล้องกับอสมการ (-?\d+)x ([+-]) (\d+) ≥ (-?\d+)")
def _(q, m):
    a, sg, b, c = int(m[1]), m[2], int(m[3]), int(m[4])
    b = b if sg == "+" else -b
    want(q, min(x for x in range(-500, 501) if a * x + b >= c), "อสมการ ≥")


@rule(r"จำนวนเต็มบวกที่มากที่สุดที่สอดคล้องกับอสมการ -(\d+)x \+ (\d+) > 0")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, max(x for x in range(1, 501) if -a * x + b > 0), "อสมการกลับเครื่องหมาย")


@rule(r"มีจำนวนเต็มกี่จำนวนที่สอดคล้องกับอสมการ (-?\d+) < x ≤ (-?\d+)")
def _(q, m):
    want(q, len([x for x in range(-500, 501) if int(m[1]) < x <= int(m[2])]), "นับจำนวนเต็ม")


@rule(r"มีจำนวนเต็มกี่จำนวนที่สอดคล้องกับ (-?\d+) < x \+ (\d+) < (-?\d+)")
def _(q, m):
    a, b, c = int(m[1]), int(m[2]), int(m[3])
    want(q, len([x for x in range(-500, 501) if a < x + b < c]), "อสมการสองชั้น")


@rule(r"จำนวนเต็มที่น้อยที่สุดที่สอดคล้องกับอสมการ (\d+)x \+ (\d+) > (\d+)x \+ (\d+)")
def _(q, m):
    a, b, c, d = map(int, m.groups())
    want(q, min(x for x in range(-500, 501) if a * x + b > c * x + d), "ตัวแปรสองข้าง")


@rule(r"สมุดเล่มละ (\d+) บาท มีเงิน (\d+) บาท")
def _(q, m):
    p, b = int(m[1]), int(m[2])
    want(q, max(n for n in range(0, 1000) if n * p <= b), "ซื้อสมุด")


@rule(r"ค่าแรกเข้า (\d+) บาท และคิดเพิ่มชั่วโมงละ (\d+) บาท ถ้ามีเงินไม่เกิน (\d+)")
def _(q, m):
    f, r, l = map(int, m.groups())
    want(q, max(h for h in range(0, 1000) if f + r * h <= l), "เช่าจักรยาน")


@rule(r"สอบมาแล้ว (\d+) ครั้ง ได้คะแนน ([\d, ]+) คะแนน ถ้าต้องการให้คะแนนเฉลี่ยทั้ง (\d+) "
      r"ครั้งไม่ต่ำกว่า (\d+)")
def _(q, m):
    got = [int(x) for x in m[2].split()]
    n, target = int(m[3]), int(m[4])
    want(q, min(s for s in range(-500, 501) if (sum(got) + s) >= target * n), "คะแนนเฉลี่ย")


# ---------- แยกตัวประกอบ / เศษเหลือ ----------
@rule(r"x\^3 \+ (\d+) แล้วตอบว่าตัวประกอบที่เป็นพหุนามดีกรีหนึ่งคือ x \+ k")
def _(q, m):
    c = int(m[1])
    want(q, round(c ** (1 / 3)), "ผลบวกกำลังสาม")


@rule(r"x\^3 - (\d+) แล้วตอบว่าตัวประกอบที่เป็นพหุนามดีกรีหนึ่งคือ x - k")
def _(q, m):
    c = int(m[1])
    want(q, round(c ** (1 / 3)), "ผลต่างกำลังสาม")


@rule(r"จงหาค่าของ x\^2 - (\d+)x \+ (\d+) เมื่อ x = (\d+)")
def _(q, m):
    a, b, x = map(int, m.groups())
    want(q, x * x - a * x + b, "แทนค่าในพหุนาม")


@rule(r"จงหาเศษเหลือจากการหาร x\^3 ([+-]) (\d+)x\^2 ([+-]) (\d+)x ([+-]) (\d+) ด้วย x - (-?\d+)")
def _(q, m):
    g = m.groups()
    b = int(g[1]) * (1 if g[0] == "+" else -1)
    c = int(g[3]) * (1 if g[2] == "+" else -1)
    d = int(g[5]) * (1 if g[4] == "+" else -1)
    r = int(g[6])
    want(q, r ** 3 + b * r * r + c * r + d, "ทฤษฎีบทเศษเหลือ")


@rule(r"ถ้า x - (-?\d+) เป็นตัวประกอบหนึ่งของ x\^3 ([+-]) (\d+)x\^2 ([+-]) (\d+)x \+ c")
def _(q, m):
    g = m.groups()
    r = int(g[0])
    b = int(g[2]) * (1 if g[1] == "+" else -1)
    c = int(g[4]) * (1 if g[3] == "+" else -1)
    # หา c ที่ทำให้ p(r) = 0 ด้วยการไล่ค่า ไม่ใช้สูตร
    want(q, next(k for k in range(-5000, 5001) if r ** 3 + b * r * r + c * r + k == 0),
         "ตัวประกอบเชิงเส้น")


@rule(r"x\^3 \+ (\d+)x\^2 \+ (\d+)x \+ (\d+) ให้อยู่ในรูป \(x \+ k\)\^3")
def _(q, m):
    a3, a2, a1 = map(int, m.groups())
    want(q, next(k for k in range(1, 200)
                 if (3 * k, 3 * k * k, k ** 3) == (a3, a2, a1)), "กำลังสามสมบูรณ์")


@rule(r"ถ้า x \+ \(1\)/\(x\) = (\d+) จงหาค่าของ x\^3")
def _(q, m):
    a = int(m[1])
    want(q, a ** 3 - 3 * a, "เอกลักษณ์กำลังสาม")


# ---------- สมการกำลังสอง ----------
@rule(r"รากที่มากกว่าของสมการ x\^2 - (\d+)x \+ (\d+) = 0")
def _(q, m):
    s, p = int(m[1]), int(m[2])
    roots = [x for x in range(-500, 501) if x * x - s * x + p == 0]
    want(q, max(roots), "รากที่มากกว่า")


@rule(r"ผลบวกของรากทั้งสองของสมการ x\^2 - (\d+)x \+ (\d+) = 0")
def _(q, m):
    s, p = int(m[1]), int(m[2])
    roots = [x for x in range(-500, 501) if x * x - s * x + p == 0]
    want(q, sum(roots) if len(roots) == 2 else 2 * roots[0], "ผลบวกของราก")


@rule(r"ผลคูณของรากทั้งสองของสมการ x\^2 - (\d+)x \+ (\d+) = 0")
def _(q, m):
    s, p = int(m[1]), int(m[2])
    roots = [x for x in range(-500, 501) if x * x - s * x + p == 0]
    want(q, roots[0] * roots[1] if len(roots) == 2 else roots[0] ** 2, "ผลคูณของราก")


@rule(r"จงหารากที่เป็นจำนวนบวกของสมการ x\^2 - (\d+) = 0")
def _(q, m):
    want(q, math.isqrt(int(m[1])), "รากที่สอง")


@rule(r"ด้านยาวมากกว่าด้านกว้าง 3 เซนติเมตร และมีพื้นที่ (\d+) ตาราง")
def _(q, m):
    a = int(m[1])
    want(q, next(w for w in range(1, 1000) if w * (w + 3) == a), "พื้นที่สี่เหลี่ยม")


@rule(r"จำนวนเต็มบวกสองจำนวนเรียงติดกันมีผลคูณเท่ากับ (\d+)")
def _(q, m):
    a = int(m[1])
    want(q, next(n for n in range(1, 1000) if n * (n + 1) == a), "จำนวนเรียงติดกัน")


@rule(r"สมการ (\d+)x\^2 - (\d+)x \+ (\d+) = 0 มีรากซ้ำ")
def _(q, m):
    a, b, c = map(int, m.groups())
    assert b * b - 4 * a * c == 0, "โจทย์บอกว่ารากซ้ำแต่ดิสคริมิแนนต์ไม่เป็นศูนย์"
    want(q, Fraction(b, 2 * a), "รากซ้ำ")


@rule(r"รากทั้งสองของสมการ x\^2 - (\d+)x \+ (\d+) = 0 คือ m และ n จงหาค่าของ m\^2 \+ n\^2")
def _(q, m):
    s, p = int(m[1]), int(m[2])
    roots = [x for x in range(-500, 501) if x * x - s * x + p == 0]
    rs = roots * 2 if len(roots) == 1 else roots
    want(q, rs[0] ** 2 + rs[1] ** 2, "m²+n²")


# ---------- ความคล้าย ----------
@rule(r"AB = (\d+) เซนติเมตร และ DE = (\d+) เซนติเมตร ถ้า BC = (\d+)")
def _(q, m):
    ab, de, bc = map(int, m.groups())
    want(q, Fraction(bc * de, ab), "ด้านสมนัย")


@rule(r"อัตราส่วนของด้านที่สมนัยกันเป็น 1 : (\d+) จงหาอัตราส่วนของพื้นที่")
def _(q, m):
    want(q, int(m[1]) ** 2, "พื้นที่รูปคล้าย")


@rule(r"อัตราส่วนของด้านที่สมนัยกันเป็น 1 : (\d+) จงหาอัตราส่วนของปริมาตร")
def _(q, m):
    want(q, int(m[1]) ** 3, "ปริมาตรรูปคล้าย")


@rule(r"AD = (\d+) เซนติเมตร DB = (\d+) เซนติเมตร และ AE = (\d+)")
def _(q, m):
    ad, db, ae = map(int, m.groups())
    want(q, Fraction(db * ae, ad), "เส้นขนานตัดด้าน")


@rule(r"รูปเล็กมีพื้นที่ (\d+) ตารางเซนติเมตร และรูปใหญ่มีพื้นที่ (\d+) ตาราง")
def _(q, m):
    s, b = int(m[1]), int(m[2])
    k = Fraction(b, s)
    want(q, math.isqrt(k.numerator) // math.isqrt(k.denominator), "อัตราส่วนจากพื้นที่")


@rule(r"รูปแรกมีฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร รูปที่สองมีสูง (\d+)")
def _(q, m):
    b, h1, h2 = map(int, m.groups())
    want(q, Fraction(b * h2, h1), "ฐานของรูปคล้าย")


@rule(r"ชายคนหนึ่งสูง (\d+) เซนติเมตร มีเงายาว (\d+) เมตร .*?เสาต้นหนึ่งมีเงายาว (\d+) เมตร")
def _(q, m):
    h, s, S = map(int, m.groups())
    want(q, Fraction(h * S, s), "เงาและความสูง")


# ---------- กราฟฟังก์ชันกำลังสอง ----------
@rule(r"จงหาสมการแกนสมมาตรของกราฟ y = x\^2 ([+-]) (\d+)x")
def _(q, m):
    b = int(m[2]) * (1 if m[1] == "+" else -1)
    want(q, Fraction(-b, 2), "แกนสมมาตร")


@rule(r"จงหาค่าต่ำสุดของ y = x\^2 ([+-]) (\d+)x ([+-]) (\d+)")
def _(q, m):
    b = int(m[2]) * (1 if m[1] == "+" else -1)
    c = int(m[4]) * (1 if m[3] == "+" else -1)
    # ไล่หาค่าต่ำสุดจริงบนกริดละเอียด แทนการใช้สูตรจุดยอด
    lo = min(Fraction(x, 2) ** 2 + b * Fraction(x, 2) + c for x in range(-200, 201))
    want(q, lo, "ค่าต่ำสุด")


@rule(r"y = \(x ([+-]) (\d+)\)\(x ([+-]) (\d+)\) ตัดแกน X ที่จุดใดบ้าง")
def _(q, m):
    p = -int(m[2]) * (1 if m[1] == "+" else -1)
    r = -int(m[4]) * (1 if m[3] == "+" else -1)
    want(q, p + r, "ผลบวกจุดตัดแกน X")


@rule(r"กราฟของ y = x\^2 ([+-]) (\d+)x ([+-]) (\d+) ตัดแกน X กี่จุด")
def _(q, m):
    b = int(m[2]) * (1 if m[1] == "+" else -1)
    c = int(m[4]) * (1 if m[3] == "+" else -1)
    d = b * b - 4 * c
    want(q, 2 if d > 0 else (1 if d == 0 else 0), "จำนวนจุดตัดแกน X")


@rule(r"เขียน y = \(x ([+-]) (\d+)\)\^2 ([+-]) (\d+) ให้อยู่ในรูป y = x\^2 \+ bx \+ c")
def _(q, m):
    h = -int(m[2]) * (1 if m[1] == "+" else -1)
    want(q, -2 * h, "กระจายจุดยอด")


# ---------- ระบบสมการ ----------
@rule(r"จงหาค่าของ (x|y) จากระบบสมการ (-?\d+)x ([+-]) (\d+)y = (-?\d+) และ (-?\d+)x ([+-]) (\d+)y = (-?\d+)")
def _(q, m):
    which = m[1]
    a = int(m[2]); b = int(m[4]) * (1 if m[3] == "+" else -1); e = int(m[5])
    c = int(m[6]); d = int(m[8]) * (1 if m[7] == "+" else -1); f = int(m[9])
    det = a * d - b * c
    x = Fraction(e * d - b * f, det)
    y = Fraction(a * f - e * c, det)
    want(q, x if which == "x" else y, "แก้ระบบสมการ")


@rule(r"จำนวนสองจำนวนรวมกันได้ (\d+) และมีผลต่างเท่ากับ (\d+)")
def _(q, m):
    s, d = int(m[1]), int(m[2])
    want(q, Fraction(s + d, 2), "ผลบวกผลต่าง")


@rule(r"ปากกาด้ามละ (\d+) บาท และสมุดเล่มละ (\d+) บาท รวม (\d+) ชิ้น จ่ายเงินทั้งหมด (\d+)")
def _(q, m):
    a, b, n, tot = map(int, m.groups())
    want(q, next(na for na in range(0, n + 1) if a * na + b * (n - na) == tot), "ราคาสินค้า")


@rule(r"แล่นตามน้ำได้ (\d+) กิโลเมตรใน (\d+) ชั่วโมง และแล่นทวนน้ำได้ (\d+) กิโลเมตรใน (\d+)")
def _(q, m):
    d1, t1, d2, t2 = map(int, m.groups())
    want(q, Fraction(Fraction(d1, t1) + Fraction(d2, t2), 2), "เรือตามน้ำทวนน้ำ")


# ---------- วงกลม ----------
@rule(r"มุมที่จุดศูนย์กลาง.*?มีขนาด (\d+) องศา จงหาขนาดของมุมในส่วนโค้ง")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "มุมในส่วนโค้ง")


@rule(r"มุมในส่วนโค้งของวงกลมมีขนาด (\d+) องศา จงหาขนาดของมุมที่จุดศูนย์กลาง")
def _(q, m):
    want(q, 2 * int(m[1]), "มุมที่จุดศูนย์กลาง")


@rule(r"รูปสี่เหลี่ยมแนบในวงกลมรูปหนึ่งมีมุมหนึ่งขนาด (\d+) องศา")
def _(q, m):
    want(q, 180 - int(m[1]), "สี่เหลี่ยมแนบในวงกลม")


@rule(r"วงกลมรัศมี (\d+) เซนติเมตร จงหาความยาวรอบวง")
def _(q, m):
    want(q, 2 * Fraction(22, 7) * int(m[1]), "ความยาวรอบวง")


@rule(r"วงกลมรัศมี (\d+) เซนติเมตร จงหาพื้นที่เป็นตาราง")
def _(q, m):
    want(q, Fraction(22, 7) * int(m[1]) ** 2, "พื้นที่วงกลม")


@rule(r"วงกลมรัศมี (\d+) เซนติเมตร มีคอร์ดเส้นหนึ่งอยู่ห่างจากจุดศูนย์กลาง (\d+)")
def _(q, m):
    r, d = int(m[1]), int(m[2])
    want(q, 2 * math.isqrt(r * r - d * d), "ความยาวคอร์ด")


@rule(r"ภายนอกวงกลมรัศมี (\d+) เซนติเมตร.*?ระยะจากจุด P ถึงจุดศูนย์กลางเท่ากับ (\d+)")
def _(q, m):
    r, d = int(m[1]), int(m[2])
    want(q, math.isqrt(d * d - r * r), "เส้นสัมผัส")


# ---------- พีระมิด กรวย ทรงกลม ----------
@rule(r"กรวยกลมตรงมีรัศมีฐาน (\d+) เซนติเมตร และสูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    want(q, Fraction(1, 3) * Fraction(22, 7) * r * r * h, "ปริมาตรกรวย")


@rule(r"ทรงกลมรัศมี (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    want(q, Fraction(4, 3) * Fraction(22, 7) * int(m[1]) ** 3, "ปริมาตรทรงกลม")


@rule(r"ทรงกลมรัศมี (\d+) เซนติเมตร จงหาพื้นที่ผิว")
def _(q, m):
    want(q, 4 * Fraction(22, 7) * int(m[1]) ** 2, "พื้นที่ผิวทรงกลม")


@rule(r"กรวยกลมตรงมีรัศมีฐาน (\d+) เซนติเมตร และสูงเอียง (\d+) เซนติเมตร จงหาพื้นที่ผิวข้าง")
def _(q, m):
    want(q, Fraction(22, 7) * int(m[1]) * int(m[2]), "พื้นที่ผิวข้างกรวย")


@rule(r"พีระมิดฐานสี่เหลี่ยมจัตุรัสมีด้านฐานยาว (\d+) เซนติเมตร และสูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    s, h = int(m[1]), int(m[2])
    want(q, Fraction(s * s * h, 3), "ปริมาตรพีระมิด")


@rule(r"พีระมิดฐานสี่เหลี่ยมจัตุรัสมีด้านฐานยาว (\d+) เซนติเมตร และสูงเอียง (\d+) เซนติเมตร จงหาพื้นที่ผิวข้าง")
def _(q, m):
    s, l = int(m[1]), int(m[2])
    want(q, 4 * Fraction(s * l, 2), "พื้นที่ผิวข้างพีระมิด")


@rule(r"กรวยกลมตรงมีรัศมีฐาน (\d+) เซนติเมตร และสูง (\d+) เซนติเมตร จงหาความยาวของสูงเอียง")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    want(q, math.isqrt(r * r + h * h), "สูงเอียงของกรวย")


# ---------- ความน่าจะเป็น ----------
@rule(r"ลูกแก้วสีแดง (\d+) ลูก และสีน้ำเงิน (\d+) ลูก สุ่มหยิบมา 1 ลูก จงหาความน่าจะเป็นที่จะได้ลูกแก้วสีแดง")
def _(q, m):
    r, b = int(m[1]), int(m[2])
    want(q, Fraction(r, r + b), "ลูกแก้วสีแดง")


@rule(r"ทอดลูกเต๋า 1 ลูก 1 ครั้ง จงหาความน่าจะเป็นที่จะได้แต้มมากกว่า (\d+)")
def _(q, m):
    n = int(m[1])
    want(q, Fraction(len([x for x in range(1, 7) if x > n]), 6), "แต้มมากกว่า")


@rule(r"โยนเหรียญที่เที่ยงตรง (\d+) เหรียญพร้อมกัน จงหาความน่าจะเป็นที่จะออกหัวทั้งหมด")
def _(q, m):
    want(q, Fraction(1, 2 ** int(m[1])), "หัวทั้งหมด")


@rule(r"ทอดลูกเต๋า 2 ลูกพร้อมกัน จงหาความน่าจะเป็นที่ผลรวมของแต้มเท่ากับ (\d+)")
def _(q, m):
    s = int(m[1])
    want(q, Fraction(len([1 for a in range(1, 7) for b in range(1, 7) if a + b == s]), 36),
         "ผลรวมแต้ม")


@rule(r"หมายเลข 1 ถึง (\d+) จงหาความน่าจะเป็นที่จะได้หมายเลขที่เป็นจำนวนคู่\s*$")
def _(q, m):
    n = int(m[1])
    want(q, Fraction(len([x for x in range(1, n + 1) if x % 2 == 0]), n), "จำนวนคู่")


@rule(r"หมายเลข 1 ถึง (\d+) จงหาความน่าจะเป็นที่จะได้หมายเลขที่หารด้วย 3 ลงตัว\s*$")
def _(q, m):
    n = int(m[1])
    want(q, Fraction(len([x for x in range(1, n + 1) if x % 3 == 0]), n), "หารด้วย 3")


@rule(r"หมายเลข 1 ถึง (\d+) จงหาความน่าจะเป็นที่จะได้จำนวนเฉพาะ")
def _(q, m):
    n = int(m[1])
    def isp(x):
        return x > 1 and all(x % p for p in range(2, int(x ** .5) + 1))
    want(q, Fraction(len([x for x in range(1, n + 1) if isp(x)]), n), "จำนวนเฉพาะ")


@rule(r"สีแดง (\d+) ลูก สีน้ำเงิน (\d+) ลูก และสีเขียว (\d+) ลูก สุ่มหยิบมา 1 ลูก จงหาความน่าจะเป็นที่จะไม่ได้")
def _(q, m):
    r, b, g = map(int, m.groups())
    want(q, Fraction(r + b, r + b + g), "ส่วนเติมเต็ม")


@rule(r"หยิบลูกบอล (\d+) ลูกพร้อมกันจากลูกบอลที่ต่างกัน (\d+) ลูก จงหาจำนวนวิธี")
def _(q, m):
    k, n = int(m[1]), int(m[2])
    want(q, math.comb(n, k), "จำนวนวิธี")


# ---------- สถิติ ----------
class NotPlainData(Exception):
    """ข้อมูลไม่ได้อยู่ในรูป "12, 15, 18" ตรง ๆ (เช่น อ่านจากแผนภาพต้น-ใบ) — ตรวจซ้ำไม่ได้"""


def parse_data(s):
    # ต้องเป็นรายการตัวเลขคั่นด้วยจุลภาคล้วน ๆ ไม่งั้นตัวเลขที่ดึงมาไม่ใช่ข้อมูลจริง
    if not re.fullmatch(r"\s*-?\d+(\s*,\s*-?\d+)+\s*", s):
        raise NotPlainData(s[:40])
    return [int(x) for x in re.findall(r"-?\d+", s)]


def quart(d, qn):
    d = sorted(d)
    n = len(d)
    pos = Fraction(qn * (n + 1), 4)
    lo = math.floor(pos)
    if lo < 1:
        return Fraction(d[0])
    if lo >= n:
        return Fraction(d[-1])
    return d[lo - 1] + (pos - lo) * (d[lo] - d[lo - 1])


@rule(r"จงหามัธยฐานของข้อมูล (.+)$")
def _(q, m):
    d = sorted(parse_data(m[1]))
    n = len(d)
    want(q, d[n // 2] if n % 2 else Fraction(d[n // 2 - 1] + d[n // 2], 2), "มัธยฐาน")


@rule(r"จงหาพิสัยของข้อมูล (.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, max(d) - min(d), "พิสัย")


@rule(r"จงหาค่าเฉลี่ยเลขคณิตของข้อมูล (.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, Fraction(sum(d), len(d)), "ค่าเฉลี่ย")


@rule(r"จงหาฐานนิยมของข้อมูล (.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, max(set(d), key=d.count), "ฐานนิยม")


@rule(r"จงหาควอร์ไทล์ที่ 1 \(Q_1\) ของข้อมูล (.+)$")
def _(q, m):
    want(q, quart(parse_data(m[1]), 1), "Q1")


@rule(r"จงหาควอร์ไทล์ที่ 3 \(Q_3\) ของข้อมูล (.+)$")
def _(q, m):
    want(q, quart(parse_data(m[1]), 3), "Q3")


@rule(r"จงหาพิสัยระหว่างควอร์ไทล์ \(IQR\) ของข้อมูล (.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, quart(d, 3) - quart(d, 1), "IQR")


@rule(r"มี (\d+) จำนวน มีค่าเฉลี่ยเลขคณิตเท่ากับ (\d+) ถ้าทราบข้อมูล \d+ จำนวนคือ (.+?) จงหา")
def _(q, m):
    n, mean = int(m[1]), int(m[2])
    known = parse_data(m[3])
    want(q, mean * n - sum(known), "ค่าที่หายไป")


# ---------- ตรีโกณมิติ ----------
@rule(r"ด้านตรงข้ามมุม A ยาว (\d+) หน่วย ด้านประชิดมุม A ยาว (\d+) หน่วย และด้านตรงข้ามมุมฉากยาว (\d+) "
      r"หน่วย จงหาค่าของ (sin|cos) A")
def _(q, m):
    a, b, c, fn = int(m[1]), int(m[2]), int(m[3]), m[4]
    assert a * a + b * b == c * c, "สามเหลี่ยมไม่เป็นมุมฉาก"
    want(q, Fraction(a, c) if fn == "sin" else Fraction(b, c), f"{fn} A")


@rule(r"ด้านตรงข้ามมุม A ยาว (\d+) หน่วย และด้านประชิดมุม A ยาว (\d+) หน่วย จงหาค่าของ tan A")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "tan A")


@rule(r"ด้านประกอบมุมฉากยาว (\d+) และ (\d+) หน่วย จงหาค่าของ sin θ เมื่อ θ .*?ด้านยาว (\d+) หน่วย")
def _(q, m):
    a, b, opp = map(int, m.groups())
    want(q, Fraction(opp, math.isqrt(a * a + b * b)), "sin θ")


@rule(r"ถ้า sin A = \((\d+)\)/\((\d+)\) และ A เป็นมุมแหลม จงหาค่าของ cos A")
def _(q, m):
    a, c = int(m[1]), int(m[2])
    want(q, Fraction(math.isqrt(c * c - a * a), c), "cos จาก sin")


def main():
    global skipped
    for course in json.load(open(os.path.join(QDIR, "courses.json"), encoding="utf-8")):
        for path in sorted(glob.glob(os.path.join(QDIR, course["slug"], "unit-*.json"))):
            data = json.load(open(path, encoding="utf-8"))
            for i, q in enumerate(data["questions"], 1):
                q = dict(q, id=f"{course['slug']}/u{data['unit']:02d}#{i}")
                body = txt(q)
                for pat, fn in RULES:
                    mt = pat.search(body)
                    if mt:
                        try:
                            fn(q, mt)
                        except NotPlainData:
                            skipped += 1
                        break
                else:
                    skipped += 1

    print(f"  ตรวจซ้ำด้วยการคิดใหม่ {checks} ข้อ · ไม่เข้ารูปแบบที่ตรวจได้ {skipped} ข้อ")
    if bad:
        print(f"\n❌ เฉลยไม่ตรงกับที่คิดใหม่ {len(bad)} ข้อ")
        for row in bad[:25]:
            print(f"   - {row[0]} [{row[1]}] เฉลยว่า {row[2]} แต่คิดได้ {row[3]}")
            print(f"     {row[4]}")
        return 1
    print("\n✅ เฉลยที่ตรวจได้ ถูกต้องตามคณิตศาสตร์ทั้งหมด")
    return 0


if __name__ == "__main__":
    sys.exit(main())
