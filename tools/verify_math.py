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
import ast
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


# หน่วยที่ผู้เขียนโจทย์อาจติดมากับเฉลย — ตัดออกก่อนเทียบตัวเลข (ชุดเดียวกับ NOISE_WORDS ในหน้าเว็บ)
UNIT_RE = re.compile(
    r"ลูกบาศก์เซนติเมตร|ตารางเซนติเมตร|เซนติเมตร|กิโลเมตร|มิลลิเมตร|กิโลกรัม|ชั่วโมง|"
    r"ลบ\.ซม\.|ตร\.ซม\.|ลบ\.ม\.|ตร\.ม\.|องศา|หน่วย|บาท|เมตร|ลิตร|นาที|วินาที|"
    r"ซม\.|กม\.|มม\.|กก\.|ข้อ|คน|ปี|วัน|เล่ม|ด้าม|ชิ้น|ลูก|ใบ|ตัว|เท่า|จำนวน|ส่วน|%")


def num(s):
    """เฉลยอาจเป็น HTML (เศษส่วนซ้อน) หรือมีหน่วยติดมา — ทำให้เหลือแต่ตัวเลขก่อนเทียบ"""
    s = re.sub(r'<span class="frac"><span class="num">(.*?)</span>'
               r'<span class="den">(.*?)</span></span>', r"\1/\2", str(s))
    s = re.sub(r"<[^>]+>", "", s)
    if "=" in s:
        s = s.split("=")[-1]
    s = UNIT_RE.sub(" ", s).replace(",", "").replace("−", "-").strip()
    if re.fullmatch(r"-?\d+\s*/\s*-?\d+", s):
        return Fraction(s.replace(" ", ""))
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return Fraction(s)
    return None


def want(q, value, why):
    global checks
    checks += 1
    got = num(q["answer"])
    if got is None or Fraction(value) != got:
        bad.append((q["id"], why, q["answer"], str(Fraction(value)), txt(q)[:95]))


# ---------- ตัวประเมินนิพจน์เลขคณิต ----------
# ใช้ ast แทน eval — โจทย์มาจากไฟล์ในโปรเจกต์ก็จริง แต่ตัวตรวจไม่ควรรันอะไรก็ได้ที่อ่านเจอ
_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}


class NotArithmetic(Exception):
    """ไม่ใช่นิพจน์เลขคณิตล้วน — ตรวจซ้ำแบบคิดเลขไม่ได้"""


def _walk(node):
    if isinstance(node, ast.Expression):
        return _walk(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        # ผ่าน str() เพื่อให้ 0.2 เป็น 1/5 พอดี ไม่ใช่ค่าประมาณของ float
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _walk(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        a, b = _walk(node.left), _walk(node.right)
        if isinstance(node.op, ast.Div) and b == 0:
            raise NotArithmetic("หารด้วยศูนย์")
        if isinstance(node.op, ast.Pow) and (b.denominator != 1 or b < 0 or b > 64):
            raise NotArithmetic("เลขชี้กำลังไม่เหมาะ")
        return _OPS[type(node.op)](a, b)
    raise NotArithmetic(ast.dump(node)[:40])


def _split_top(expr, ops):
    """แยกนิพจน์ที่ตัวดำเนินการระดับนอกสุด -> ([ตัวถูกดำเนินการ], [ตัวดำเนินการ])"""
    parts, seps, buf, depth = [], [], "", 0
    for ch in expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch in ops and buf.strip():
            parts.append(buf)
            seps.append(ch)
            buf = ""
            continue
        buf += ch
    parts.append(buf)
    return parts, seps


def _group(expr):
    """ครอบวงเล็บรอบตัวถูกดำเนินการของ × ÷ ที่ระดับนอกสุด

    โจทย์ "3/4 ÷ 6/9" ที่มาจากเศษส่วนซ้อน ถ้าแปลงตรง ๆ จะกลายเป็น 3/4/6/9 ซึ่งผิดความหมาย

    ทำเฉพาะเมื่อ *ทั้งนิพจน์* เป็นการคูณ/หารล้วน และมีตัวถูกดำเนินการที่เป็นเศษส่วนอยู่จริง
    ถ้ามี + หรือ - ระดับนอกสุดด้วย ห้ามครอบเด็ดขาด ไม่งั้นลำดับการดำเนินการเพี้ยน
    (เช่น "9 + (-2) × 2 - (-3)" ต้องได้ 8 ไม่ใช่ (9 + (-2)) × (2 - (-3)) = 35)
    """
    parts, seps = _split_top(expr, "×÷")
    if not seps:
        return expr
    if _split_top(expr, "+")[1] or _split_top(expr.lstrip(" -"), "-")[1]:
        return expr
    if not any("/" in p for p in parts):
        return expr
    out = f"({parts[0]})"
    for sep, part in zip(seps, parts[1:]):
        out += ("*" if sep == "×" else "/") + f"({part})"
    return out


def arith(expr):
    """'(-52) - (-74)' -> Fraction(22) · รับเฉพาะ + - × ÷ ^ วงเล็บ และจำนวนเต็ม"""
    e = _group(expr.replace("✕", "×"))
    e = (e.replace("×", "*").replace("÷", "/")
          .replace("^", "**").replace("−", "-").replace(",", "").strip())
    e = e.rstrip(" .")
    if not re.fullmatch(r"[-+*/() \d.]+", e) or not re.search(r"\d", e):
        raise NotArithmetic(e[:40])
    try:
        return _walk(ast.parse(e, mode="eval"))
    except NotArithmetic:
        raise
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, MemoryError,
            RecursionError, OverflowError):
        raise NotArithmetic(e[:40])


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


# ---------- นิพจน์เลขคณิตล้วน (ครอบคลุมโจทย์คิดเลขของ ม.1/ม.2 จำนวนมาก) ----------
@rule(r"^จงหาผลลัพธ์ของ (.+?)\s*$")
def _(q, m):
    want(q, arith(m[1]), "คิดเลขตามนิพจน์")


@rule(r"^จงหาค่าของ ((?:[-+*/()\d.,×÷^ ])+)\s*$")
def _(q, m):
    want(q, arith(m[1]), "คิดเลขตามนิพจน์")


# ---------- รูปหลายเหลี่ยมด้านเท่ามุมเท่า ----------
@rule(r"สร้างรูป (\d+) เหลี่ยมด้านเท่ามุมเท่า จงหาขนาดของมุมภายในแต่ละมุม")
def _(q, m):
    n = int(m[1])
    want(q, Fraction(180 * (n - 2), n), "มุมภายในรูป n เหลี่ยม")


@rule(r"แบ่งมุมรอบจุดศูนย์กลางออกเป็น (\d+) ส่วนเท่า ๆ กัน จงหาขนาดของมุมที่จุดศูนย์กลาง")
def _(q, m):
    want(q, Fraction(360, int(m[1])), "มุมที่จุดศูนย์กลาง")


@rule(r"^รูป (\d+) เหลี่ยมด้านเท่ามุมเท่า จงหาจำนวนเส้นทแยงมุมทั้งหมด")
def _(q, m):
    n = int(m[1])
    want(q, Fraction(n * (n - 3), 2), "จำนวนเส้นทแยงมุม")


@rule(r"มุมภายในของรูปหลายเหลี่ยมด้านเท่ามุมเท่ารูปหนึ่งมีขนาด (\d+) องศา จงหาจำนวนด้าน")
def _(q, m):
    inner = int(m[1])
    # ไล่หา n ที่ทำให้มุมภายในตรงตามโจทย์ ไม่ใช้สูตรย้อน
    ns = [n for n in range(3, 400) if Fraction(180 * (n - 2), n) == inner]
    if not ns:
        bad.append((q["id"], "หาจำนวนด้านจากมุมภายใน", q["answer"],
                    "ไม่มีรูปหลายเหลี่ยมที่มุมภายในเท่านี้", txt(q)[:95]))
        return
    want(q, ns[0], "หาจำนวนด้านจากมุมภายใน")


# ---------- การสร้างทางเรขาคณิต ----------
@rule(r"สร้างเส้นแบ่งครึ่งมุมของมุมขนาด (\d+) องศา จงหาขนาดของมุมที่ได้แต่ละมุม")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "แบ่งครึ่งมุม")


@rule(r"สร้างเส้นแบ่งครึ่งมุมของมุมขนาด (\d+) องศา แล้วแบ่งครึ่งมุมที่ได้อีกครั้งหนึ่ง")
def _(q, m):
    want(q, Fraction(int(m[1]), 4), "แบ่งครึ่งมุมสองครั้ง")


@rule(r"แบ่งครึ่งส่วนของเส้นตรง AB ที่ยาว (\d+) เซนติเมตร ที่จุด M จงหาความยาว AM")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "แบ่งครึ่งส่วนของเส้นตรง")


@rule(r"แบ่งส่วนของเส้นตรงยาว (\d+) เซนติเมตร ออกเป็น (\d+) ส่วนเท่า ๆ กัน")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "แบ่งส่วนของเส้นตรง")


@rule(r"สร้างรูปสามเหลี่ยมมุมฉากที่มีด้านประกอบมุมฉากยาว (\d+) และ (\d+) เซนติเมตร")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b * b), "ด้านตรงข้ามมุมฉาก")


# ---------- กราฟฟังก์ชันกำลังสอง: จุดยอด ----------
@rule(r"กราฟของ y = -?\d*\(x ([+-]) (\d+)\)\^2 [+-] \d+ มีจุดยอดที่ \(h k\) จงหาค่าของ h")
def _(q, m):
    want(q, -int(m[2]) * (1 if m[1] == "+" else -1), "จุดยอด h")


@rule(r"กราฟของ y = -?\d*\(x [+-] \d+\)\^2 ([+-]) (\d+) มีจุดยอดที่ \(h k\) จงหาค่าของ k")
def _(q, m):
    want(q, int(m[2]) * (1 if m[1] == "+" else -1), "จุดยอด k")


@rule(r"จงหาค่าสูงสุดของ y = -\d*\(x [+-] \d+\)\^2 \+ (\d+)")
def _(q, m):
    want(q, int(m[1]), "ค่าสูงสุด")


# ---------- ความเท่ากันทุกประการ ----------
@rule(r"เท่ากันทุกประการกับรูปสามเหลี่ยม DEF ถ้า (?:AB|BC|CA) ยาว (\d+) เซนติเมตร")
def _(q, m):
    want(q, int(m[1]), "ด้านสมนัยของรูปที่เท่ากันทุกประการ")


# ---------- รากที่สอง / รากที่สาม ----------
@rule(r"^จงหารากที่สองที่เป็นบวกของ (\d+)\s*$")
def _(q, m):
    n = int(m[1])
    want(q, next(k for k in range(0, 10001) if k * k == n), "รากที่สอง")


@rule(r"^จงหารากที่สามของ (\d+)\s*$")
def _(q, m):
    n = int(m[1])
    want(q, next(k for k in range(0, 1001) if k ** 3 == n), "รากที่สาม")


# ---------- ปริมาตรทรงสี่เหลี่ยมมุมฉาก ----------
@rule(r"ทรงสี่เหลี่ยมมุมฉากมีความกว้าง (\d+) ซม. ยาว (\d+) ซม. สูง (\d+) ซม. จงหาปริมาตร")
def _(q, m):
    w, l, h = map(int, m.groups())
    want(q, w * l * h, "ปริมาตรทรงสี่เหลี่ยมมุมฉาก")


# ---------- สัญกรณ์วิทยาศาสตร์ ----------
@rule(r"^จงเขียน (\d+) ในรูปสัญกรณ์วิทยาศาสตร์ โดยตอบเฉพาะเลขชี้กำลังของ 10")
def _(q, m):
    want(q, len(m[1].lstrip("0")) - 1, "เลขชี้กำลังสัญกรณ์วิทยาศาสตร์")


# ---------- พหุนามตัวแปรเดียว ----------
# เก็บเป็น dict {เลขชี้กำลัง: สัมประสิทธิ์} เพื่อเทียบว่า "เฉลยที่แยกตัวประกอบแล้ว"
# กระจายออกมาแล้วตรงกับโจทย์จริงหรือไม่ — เป็นการตรวจที่ไม่พึ่งตัวสร้างเลย
class NotPoly(Exception):
    pass


_TOK = re.compile(r"\s*(\*\*|[-+*()^]|\d+|[a-zA-Z])")


def _tokens(src):
    out, i = [], 0
    while i < len(src):
        m = _TOK.match(src, i)
        if not m:
            if src[i].isspace():
                i += 1
                continue
            raise NotPoly(src[i:i + 12])
        out.append(m.group(1))
        i = m.end()
    return out


def _mono(k1, k2):
    d = dict(k1)
    for v, e in k2:
        d[v] = d.get(v, 0) + e
    return tuple(sorted((v, e) for v, e in d.items() if e))


def _pmul(a, b):
    out = {}
    for k1, c1 in a.items():
        for k2, c2 in b.items():
            k = _mono(k1, k2)
            out[k] = out.get(k, Fraction(0)) + c1 * c2
    return {k: c for k, c in out.items() if c}


def _padd(a, b, sign=1):
    out = dict(a)
    for k, c in b.items():
        out[k] = out.get(k, Fraction(0)) + sign * c
    return {k: c for k, c in out.items() if c}


def poly(src):
    """'(x + 2)(x + 3)' -> {(('x',2),):1, (('x',1),):5, ():6}

    รับหลายตัวแปร (เช่น 3a + 2b) และเลขชี้กำลังจำนวนเต็มไม่ติดลบเท่านั้น
    """
    toks = _tokens(src)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def eat():
        t = peek()
        pos[0] += 1
        return t

    def atom():
        t = peek()
        if t == "(":
            eat()
            v = expr()
            if eat() != ")":
                raise NotPoly("วงเล็บไม่ครบ")
            return v
        if t == "-":
            eat()
            return _padd({}, atom(), -1)
        if t and t.isdigit():
            eat()
            return {(): Fraction(int(t))}
        if t and t.isalpha():
            eat()
            return {((t, 1),): Fraction(1)}
        raise NotPoly(str(t))

    def power():
        base = atom()
        while peek() in ("^", "**"):
            eat()
            e = peek()
            neg = False
            if e == "-":
                eat()
                neg = True
                e = peek()
            if not (e and e.isdigit()):
                raise NotPoly("เลขชี้กำลังไม่ใช่จำนวนเต็ม")
            eat()
            n = int(e)
            if neg or n > 12:
                raise NotPoly("เลขชี้กำลังไม่เหมาะ")
            out = {(): Fraction(1)}
            for _ in range(n):
                out = _pmul(out, base)
            base = out
        return base

    def term():
        v = power()
        while True:
            t = peek()
            if t == "*":
                eat()
                v = _pmul(v, power())
            elif t == "(" or (t and (t.isdigit() or t.isalpha())):
                v = _pmul(v, power())          # คูณโดยละเครื่องหมาย เช่น 3x หรือ (x+1)(x+2)
            else:
                return v

    def expr():
        v = term()
        while peek() in ("+", "-"):
            op = eat()
            v = _padd(v, term(), 1 if op == "+" else -1)
        return v

    v = expr()
    if pos[0] != len(toks):
        raise NotPoly("อ่านไม่หมด: " + " ".join(toks[pos[0]:])[:20])
    return v


def poly_of(src):
    """เตรียมข้อความก่อนแยกวิเคราะห์ — ถอด HTML, แปลง × ÷ และ ^ ให้เป็นรูปที่ parser รับ"""
    t = (src.replace("−", "-").replace("×", "*").replace("✕", "*")
            .replace("·", "*").replace(",", ""))
    t = re.sub(r"<sup>(.*?)</sup>", r"^\1", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.split("หรือ")[0]        # เฉลยอาจให้หลายรูปแบบ ใช้แบบแรกพอ
    if "/" in t or "÷" in t or "√" in t:
        raise NotPoly("มีการหาร/ราก")
    return poly(t.strip())


# ---------- พหุนาม: กระจายเฉลยแล้วต้องตรงกับโจทย์ ----------
@rule(r"^จงแยกตัวประกอบของ (.+?)\s*$")
def _(q, m):
    global checks
    checks += 1
    try:
        want_p, got_p = poly_of(m[1]), poly_of(q["answer"])
    except NotPoly:
        checks -= 1
        raise NotPlainData("แยกวิเคราะห์พหุนามไม่ได้")
    if want_p != got_p:
        bad.append((q["id"], "แยกตัวประกอบ", q["answer"],
                    "กระจายแล้วไม่ตรงกับโจทย์", txt(q)[:95]))


@rule(r"^จงหาผล(คูณ|บวก|ลบ)ของ (.+?) กับ (.+?) ในรูปผลสำเร็จ")
def _(q, m):
    global checks
    checks += 1
    try:
        a, b_, got = poly_of(m[2]), poly_of(m[3]), poly_of(q["answer"])
    except NotPoly:
        checks -= 1
        raise NotPlainData("แยกวิเคราะห์พหุนามไม่ได้")
    exp = {"คูณ": _pmul(a, b_), "บวก": _padd(a, b_), "ลบ": _padd(a, b_, -1)}[m[1]]
    if exp != got:
        bad.append((q["id"], "พหุนาม" + m[1], q["answer"],
                    "คิดเองแล้วไม่ตรง", txt(q)[:95]))


@rule(r"ถ้า \(x - (\d+)\)\(x - (\d+)\) เท่ากับ 0 คำตอบของสมการคือ x เท่ากับ \d+ และเท่าใด")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    roots = [x for x in range(-500, 501) if (x - a) * (x - b_) == 0]
    want(q, max(roots), "รากอีกตัวของสมการ")


# ---------- ความเท่ากันทุกประการ: มุมสมนัย ----------
@rule(r"เท่ากันทุกประการกับรูปสามเหลี่ยม DEF ถ้ามุม [ABC] มีขนาด (\d+) องศา")
def _(q, m):
    want(q, int(m[1]), "มุมสมนัยของรูปที่เท่ากันทุกประการ")


# ---------- การแปลงทางเรขาคณิตบนระนาบพิกัด ----------
def want_pair(q, xy, why):
    """เฉลยเป็นพิกัด เช่น "(3, -5)" — เทียบเป็นคู่อันดับ ไม่ใช่ตัวเลขเดี่ยว"""
    global checks
    checks += 1
    raw = re.sub(r"<[^>]+>", "", str(q["answer"])).replace("−", "-").split("หรือ")[0]
    nums = re.findall(r"-?\d+", raw)
    got = tuple(int(n) for n in nums)
    if got != tuple(xy):
        bad.append((q["id"], why, q["answer"], str(tuple(xy)), txt(q)[:95]))


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) สะท้อนข้ามแกน ([XY]) ภาพที่ได้มีพิกัดใด")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    want_pair(q, (x, -y) if m[3] == "X" else (-x, y), "สะท้อนข้ามแกน")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) หมุนรอบจุดกำเนิด 180 องศา")
def _(q, m):
    want_pair(q, (-int(m[1]), -int(m[2])), "หมุน 180 องศา")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) เลื่อนขนานไปทาง(ขวา|ซ้าย) (\d+) หน่วย "
      r"และ(ขึ้นบน|ลงล่าง) (\d+) หน่วย")
def _(q, m):
    x = int(m[1]) + (int(m[4]) if m[3] == "ขวา" else -int(m[4]))
    y = int(m[2]) + (int(m[6]) if m[5] == "ขึ้นบน" else -int(m[6]))
    want_pair(q, (x, y), "เลื่อนขนาน")


# ---------- โจทย์ปัญหาพีทาโกรัส (ตัวเลขอยู่ในข้อความ) ----------
@rule(r"สูง (\d+) เมตร มีเชือกยึดจากยอดเสามายังหมุดบนพื้นที่ห่างโคนเสา (\d+) เมตร")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "ความยาวเชือก")


@rule(r"ฐานบันไดห่างจากกำแพง (\d+) เมตร และปลายบันไดอยู่สูงจากพื้น (\d+) เมตร")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "ความยาวบันได")


# ---------- ปริซึมสามเหลี่ยม ----------
@rule(r"ปริซึมสามเหลี่ยมมีฐานเป็นรูปสามเหลี่ยมที่มีความยาวฐาน (\d+) ซม. สูง (\d+) ซม."
      r".*?ยาว (\d+) ซม. จงหาปริมาตร")
def _(q, m):
    b_, h, l = map(int, m.groups())
    want(q, Fraction(b_ * h, 2) * l, "ปริมาตรปริซึมสามเหลี่ยม")


# ---------- สมการกำลังสองจากการแยกตัวประกอบ ----------
@rule(r"จงหาคำตอบที่เป็นบวกของสมการ x\^2 ([+-]) (\d+)x ([+-]) (\d+) เท่ากับ 0 ที่มีค่ามากกว่า")
def _(q, m):
    b_ = int(m[2]) * (1 if m[1] == "+" else -1)
    c = int(m[4]) * (1 if m[3] == "+" else -1)
    roots = [x for x in range(-500, 501) if x * x + b_ * x + c == 0]
    want(q, max(roots), "รากที่มากกว่า")


# ---------- เลขยกกำลังฐานเดียว ----------
@rule(r"จงเขียน (\d+)\^(\d+) ([×÷]) \1\^(\d+) ให้อยู่ในรูปเลขยกกำลังฐานเดียว")
def _(q, m):
    e1, op, e2 = int(m[2]), m[3], int(m[4])
    exp = e1 + e2 if op == "×" else e1 - e2
    got = re.findall(r"-?\d+", re.sub(r"<[^>]+>", "^", str(q["answer"])))
    global checks
    checks += 1
    if len(got) < 2 or int(got[0]) != int(m[1]) or int(got[1]) != exp:
        bad.append((q["id"], "เลขยกกำลังฐานเดียว", q["answer"],
                    f"{m[1]}^{exp}", txt(q)[:95]))


# ---------- คูณพหุนามที่เขียนติดกัน ----------
@rule(r"^จงหาผลคูณของ (\(.+?\)\(.+?\)) ในรูปผลสำเร็จ")
def _(q, m):
    global checks
    checks += 1
    try:
        exp, got = poly_of(m[1]), poly_of(q["answer"])
    except NotPoly:
        checks -= 1
        raise NotPlainData("แยกวิเคราะห์พหุนามไม่ได้")
    if exp != got:
        bad.append((q["id"], "คูณพหุนาม", q["answer"], "กระจายแล้วไม่ตรง", txt(q)[:95]))


def selftest():
    """ตัวตรวจเองก็เคยพลาดมาแล้ว (ครอบวงเล็บจนลำดับการดำเนินการเพี้ยน) จึงต้องมีเทสต์ของตัวเอง"""
    cases = [
        ("9 + (-2) × 2 - (-3)", Fraction(8)),      # ต้องคูณก่อนบวก
        ("(-2) + 3 × 6 - (-8)", Fraction(24)),
        ("(-52) - (-74)", Fraction(22)),
        ("(5)/(8) ÷ (6)/(9)", Fraction(15, 16)),   # เศษส่วนหารเศษส่วน ต้องครอบวงเล็บให้
        ("(1)/(3) × (1)/(5)", Fraction(1, 15)),
        ("-(3)/(12) + (2)/(5)", Fraction(3, 20)),
        ("3^4 ÷ 3^3", Fraction(3)),
        ("((-2)^2)^2", Fraction(16)),
        ("2 × 3 × 4", Fraction(24)),
    ]
    fails = []
    for expr, expect in cases:
        try:
            got = arith(expr)
        except NotArithmetic as e:
            got = f"NotArithmetic({e})"
        if got != expect:
            fails.append(f"{expr!r} -> {got} (ต้องได้ {expect})")
    # ค่าที่ไม่ใช่เลขคณิตต้องถูกปฏิเสธ ไม่ใช่เดาเอา
    for expr in ["x + 1", "__import__('os')", "2 ** 999999", "5/0"]:
        try:
            arith(expr)
            fails.append(f"{expr!r} ควรถูกปฏิเสธแต่ผ่าน")
        except NotArithmetic:
            pass
    # เฉลยที่มี HTML / หน่วย / เครื่องหมายเท่ากับ ต้องอ่านเป็นตัวเลขได้
    for raw, expect in [('<span class="frac"><span class="num">3</span>'
                         '<span class="den">4</span></span>', Fraction(3, 4)),
                        ("588 ลบ.ซม.", Fraction(588)),
                        ("3<sup>1</sup> = 3", Fraction(3)),
                        ("-19/40", Fraction(-19, 40)),
                        ("4.8", Fraction(24, 5))]:
        if num(raw) != expect:
            fails.append(f"num({raw[:30]!r}) -> {num(raw)} (ต้องได้ {expect})")
    X2, X1 = (("x", 2),), (("x", 1),)
    for src, expect in [("(x + 2)(x + 3)", {X2: Fraction(1), X1: Fraction(5), (): Fraction(6)}),
                        ("x^2 + 5x + 6", {X2: Fraction(1), X1: Fraction(5), (): Fraction(6)}),
                        ("3x", {X1: Fraction(3)}),
                        ("(x - 2)(x + 2)", {X2: Fraction(1), (): Fraction(-4)}),
                        ("(x + 2)(x + 3) หรือ (x + 3)(x + 2)",
                         {X2: Fraction(1), X1: Fraction(5), (): Fraction(6)}),
                        ("3a + 2b", {(("a", 1),): Fraction(3), (("b", 1),): Fraction(2)}),
                        ("7x + 3", {X1: Fraction(7), (): Fraction(3)})]:
        try:
            got = poly_of(src)
        except NotPoly as e:
            got = f"NotPoly({e})"
        if got != expect:
            fails.append(f"poly_of({src!r}) -> {got} (ต้องได้ {expect})")
    for src in ["3/x", "x^-2", "x^99"]:
        try:
            poly_of(src)
            fails.append(f"poly_of({src!r}) ควรถูกปฏิเสธแต่ผ่าน")
        except NotPoly:
            pass
    if fails:
        print("❌ ตัวตรวจเองทำงานผิด")
        for f in fails:
            print("   -", f)
        return 1
    return 0


def bucket(course, q):
    """จัดกลุ่มข้อที่ตรวจซ้ำไม่ได้ เพื่อให้เห็นชัดว่าเหลืออะไรที่ยังต้องเชื่อตัวสร้าง"""
    if course["subject"] != "คณิตศาสตร์":
        return "วิชาอื่น (ตัวตรวจนี้ดูเฉพาะคณิตศาสตร์)"
    if "figure" in q or "[[fig]]" in q["text"]:
        return "ตัวเลขอยู่ในรูป อ่านจากข้อความไม่ได้"
    if 'class="choices' in q["text"]:
        return "ปรนัยเชิงนิยาม/แนวคิด ไม่มีเลขให้คิด"
    return "คณิตศาสตร์ที่ยังไม่มีกฎรองรับ"


def main():
    global skipped
    if selftest():
        return 1
    buckets = {}
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
                        except (NotPlainData, NotArithmetic, NotPoly):
                            k = bucket(course, q)
                            buckets[k] = buckets.get(k, 0) + 1
                        break
                else:
                    k = bucket(course, q)
                    buckets[k] = buckets.get(k, 0) + 1

    tot = sum(buckets.values()) + checks
    print(f"  ตรวจซ้ำด้วยการคิดใหม่ {checks} ข้อ จาก {tot} ข้อ")
    for k, n in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"    ยังไม่ได้ตรวจ {n:>4} ข้อ — {k}")
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
