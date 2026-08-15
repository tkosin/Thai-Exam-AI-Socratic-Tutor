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


# หน่วยที่ผู้เขียนโจทย์อาจติดมากับเฉลย — ตัดออกก่อนเทียบตัวเลข
# อ่านจาก NOISE_WORDS ใน index.html โดยตรง เพราะต้องเป็นชุดเดียวกันเสมอ
# (เคยเขียนแยกกันไว้แล้วหลุดกัน ตัวตรวจอ่านเฉลยอย่าง "ร้อยละ 15" ไม่ออกทั้งที่หน้าเว็บอ่านออก)
def _noise_words():
    src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    m = re.search(r"const NOISE_WORDS = \[(.*?)\];", src, re.S)
    if not m:
        raise SystemExit("ไม่พบ NOISE_WORDS ใน index.html")
    body = re.sub(r"//[^\n]*", "", m.group(1))          # ตัดคอมเมนต์ในอาร์เรย์ออกก่อน
    words = re.findall(r"'([^']+)'", body)
    if len(words) < 20:
        raise SystemExit(f"NOISE_WORDS อ่านได้แค่ {len(words)} คำ — รูปแบบในหน้าเว็บเปลี่ยนไปแล้ว")
    return words


# เรียงคำยาวก่อน เพื่อให้ "ตารางเซนติเมตร" ถูกตัดทั้งคำ ไม่ใช่โดน "เซนติเมตร" กินไปครึ่ง
UNIT_RE = re.compile("|".join(re.escape(w) for w in
                              sorted(_noise_words(), key=len, reverse=True)) + r"|%")


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
    # ต้องเป็นรายการตัวเลขล้วน ๆ ไม่งั้นตัวเลขที่ดึงมาไม่ใช่ข้อมูลจริง
    # (เช่น แผนภาพต้น-ใบ ที่ตัวเลขมาจากตาราง ไม่ใช่ข้อมูลเรียงกันในโจทย์)
    # รับทั้งจุลภาคและช่องว่าง เพราะ txt() ตัดจุลภาคทิ้งไปแล้วตอนถอดแท็ก
    if not re.fullmatch(r"\s*-?\d+(\s*,?\s+-?\d+)+\s*", s):
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


@rule(r"จงหามัธยฐานของข้อมูล (-?\d.+)$")
def _(q, m):
    d = sorted(parse_data(m[1]))
    n = len(d)
    want(q, d[n // 2] if n % 2 else Fraction(d[n // 2 - 1] + d[n // 2], 2), "มัธยฐาน")


@rule(r"จงหาพิสัยของข้อมูล (-?\d.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, max(d) - min(d), "พิสัย")


@rule(r"จงหาค่าเฉลี่ยเลขคณิตของข้อมูล (-?\d.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, Fraction(sum(d), len(d)), "ค่าเฉลี่ย")


@rule(r"จงหาฐานนิยมของข้อมูล (-?\d.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, max(set(d), key=d.count), "ฐานนิยม")


@rule(r"จงหาควอร์ไทล์ที่ 1 \(Q_1\) ของข้อมูล (-?\d.+)$")
def _(q, m):
    want(q, quart(parse_data(m[1]), 1), "Q1")


@rule(r"จงหาควอร์ไทล์ที่ 3 \(Q_3\) ของข้อมูล (-?\d.+)$")
def _(q, m):
    want(q, quart(parse_data(m[1]), 3), "Q3")


@rule(r"จงหาพิสัยระหว่างควอร์ไทล์ \(IQR\) ของข้อมูล (-?\d.+)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, quart(d, 3) - quart(d, 1), "IQR")


# ---------- แผนภาพกล่อง · เปอร์เซ็นไทล์ · ค่านอกเกณฑ์ (ค 3.1 ม.3/1) ----------
def box_five(html):
    """อ่านค่าห้าค่ากลับออกมาจาก "รูปที่วาดไว้จริง" ไม่ใช่จากค่าที่ตัวสร้างจดไว้

    วัดพิกัดของกล่อง เส้นมัธยฐาน และปลายหนวดใน SVG แล้วเทียบกลับเป็นค่าด้วยสเกลของแกน
    ที่อ่านจากป้ายขีดบนแกนนั้นเอง — ถ้ารูปที่ผู้เรียนเห็นไม่ตรงกับเฉลย ตรงนี้จะจับได้
    คืน (ค่าห้าค่า, ค่านอกเกณฑ์)
    """
    svg = re.search(r"<svg\b.*?</svg>", html, re.S)
    if not svg:
        raise NotPlainData("ไม่มีรูปในโจทย์")
    svg = svg.group(0)
    ticks = sorted((float(x), int(v)) for x, v in
                   re.findall(r'<text x="([\d.]+)" y="[\d.]+"[^>]*>(-?\d+)</text>', svg))
    if len(ticks) < 2 or ticks[0][0] == ticks[-1][0]:
        raise NotPlainData("อ่านสเกลของแกนไม่ได้")
    (x0, v0), (x1, v1) = ticks[0], ticks[-1]
    scale = Fraction(v1 - v0) / Fraction(str(x1 - x0))

    def val(x):
        v = v0 + (Fraction(str(x)) - Fraction(str(x0))) * scale
        near = round(v)
        if abs(v - near) > Fraction(1, 4):     # ค่าที่อ่านได้ต้องตกบนขีดพอดี ไม่งั้นโจทย์กำกวม
            raise NotPlainData(f"ค่าที่อ่านจากรูปไม่ลงตัว ({float(v):.2f})")
        return near

    for x, v in ticks:                          # สเกลต้องอธิบายทุกขีดได้ ไม่ใช่แค่สองขีดที่ใช้ฟิต
        if val(x) != v:
            raise NotPlainData("แกนไม่เป็นเชิงเส้น")
    box = re.search(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)"[^>]*'
                    r'fill-opacity="0\.16"', svg)
    med = re.search(r'<line x1="([\d.]+)"[^>]*stroke-width="2\.6"', svg)
    caps = [float(a) for a, b, c, d in
            re.findall(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"'
                       r'[^>]*stroke-width="1\.5"', svg) if a == c]
    if not box or not med or len(caps) != 2:
        raise NotPlainData("รูปนี้ไม่ใช่แผนภาพกล่อง")
    lo, hi = sorted(val(x) for x in caps)
    q1 = val(float(box[1]))
    q3 = val(float(box[1]) + float(box[2]))
    outs = sorted(val(float(x)) for x in re.findall(r'<circle cx="([\d.]+)"', svg))
    return (lo, q1, val(float(med[1])), q3, hi), outs


@rule(r"จากแผนภาพกล่อง.*? จงหา(.+)$")
def _(q, m):
    (lo, q1, med, q3, hi), outs = box_five(q["text"])
    both = sorted(outs + [lo, hi])
    ask = m[1]
    # เรียงจากคำถามที่เจาะจงที่สุดลงมา — "พิสัย…เมื่อนับค่านอกเกณฑ์ด้วย" มีคำว่า "พิสัย" อยู่ด้วย
    for key, val in (("พิสัยระหว่างควอร์ไทล์", q3 - q1),
                     ("พิสัยของข้อมูลชุดนี้เมื่อนับค่านอกเกณฑ์ด้วย", both[-1] - both[0]),
                     ("พิสัยของข้อมูลชุดนี้", hi - lo),
                     ("ค่านอกเกณฑ์ที่ปรากฏ", outs[0] if len(outs) == 1 else None),
                     ("ควอร์ไทล์ที่ 1", q1), ("มัธยฐาน", med), ("ควอร์ไทล์ที่ 3", q3),
                     ("ค่าต่ำสุด", lo), ("ค่าสูงสุด", hi)):
        if key in ask:
            if val is None:
                raise NotPlainData(ask[:40])
            return want(q, val, f"แผนภาพกล่อง · {key}")
    raise NotPlainData(ask[:40])


@rule(r"จากแผนภาพกล่อง.*?ของนักเรียน (\d+) คน มีข้อมูลประมาณกี่ค่าที่มีค่ามากกว่ามัธยฐาน")
def _(q, m):
    want(q, int(m[1]) // 2, "ครึ่งบนของข้อมูล")


@rule(r"จากแผนภาพกล่อง.*?ข้อมูลประมาณร้อยละเท่าใดที่มีค่าอยู่ระหว่าง Q_1 กับ Q_3")
def _(q, m):
    want(q, 50, "ในกล่องคือครึ่งกลางของข้อมูล")


@rule(r"จากแผนภาพกล่อง.*?ของนักเรียน (\d+) คน ข้อมูลประมาณกี่ค่าที่มีค่าน้อยกว่าควอร์ไทล์ที่ 1")
def _(q, m):
    want(q, int(m[1]) // 4, "หนึ่งในสี่ล่างของข้อมูล")


@rule(r"ข้อมูลชุดหนึ่งคือ (-?\d.+?) ถ้าจะเขียนแผนภาพกล่องของข้อมูลชุดนี้ "
      r"จงหาควอร์ไทล์ที่ (\d) \(Q_\d\)$")
def _(q, m):
    want(q, quart(parse_data(m[1]), int(m[2])), f"Q{m[2]} จากข้อมูลดิบ")


@rule(r"ห้อง ก มีค่าห้าค่าคือ (-?\d[\d ]+) และของห้อง ข คือ (-?\d[\d ]+) \(เรียงจาก"
      r".*?จงหาผลต่างของมัธยฐานของสองห้องนี้")
def _(q, m):
    a, b = parse_data(m[1]), parse_data(m[2])
    want(q, abs(b[2] - a[2]), "ผลต่างมัธยฐานสองกล่อง")


@rule(r"ห้อง ก มีค่าห้าค่าคือ (-?\d[\d ]+) และของห้อง ข คือ (-?\d[\d ]+) \(เรียงจาก"
      r".*?ให้ตอบเป็นค่า IQR ที่น้อยกว่า")
def _(q, m):
    a, b = parse_data(m[1]), parse_data(m[2])
    want(q, min(a[3] - a[1], b[3] - b[1]), "IQR ที่น้อยกว่า")


def pctile(d, r):
    """เปอร์เซ็นไทล์ที่ r — ตำแหน่ง r(N+1)/100 แล้วเทียบสัดส่วนแบบเดียวกับควอร์ไทล์"""
    d = sorted(d)
    n = len(d)
    pos = Fraction(r * (n + 1), 100)
    lo = math.floor(pos)
    if lo < 1:
        return Fraction(d[0])
    if lo >= n:
        return Fraction(d[-1])
    return d[lo - 1] + (pos - lo) * (d[lo] - d[lo - 1])


@rule(r"ข้อมูล (\d+) จำนวนเรียงจากน้อยไปมากคือ (-?\d.+?) จงหาเปอร์เซ็นไทล์ที่ (\d+) \(P_\d+\)$")
def _(q, m):
    d = parse_data(m[2])
    if len(d) != int(m[1]):
        raise NotPlainData("จำนวนข้อมูลไม่ตรงกับที่โจทย์บอก")
    want(q, pctile(d, int(m[3])), f"P{m[3]}")


@rule(r"ข้อมูล (\d+) จำนวนเรียงจากน้อยไปมากคือ (-?\d.+?) "
      r"จงหาตำแหน่งของเปอร์เซ็นไทล์ที่ (\d+) \(P_\d+\) ว่าเป็นข้อมูลลำดับที่เท่าใด")
def _(q, m):
    d = parse_data(m[2])
    if len(d) != int(m[1]):
        raise NotPlainData("จำนวนข้อมูลไม่ตรงกับที่โจทย์บอก")
    want(q, Fraction(int(m[3]) * (len(d) + 1), 100), f"ตำแหน่งของ P{m[3]}")


@rule(r"ข้อมูลชุดหนึ่งมี (\d+) จำนวน จงหาว่าเปอร์เซ็นไทล์ที่ (\d+) \(P_\d+\) "
      r"อยู่ที่ข้อมูลลำดับที่เท่าใด")
def _(q, m):
    want(q, Fraction(int(m[2]) * (int(m[1]) + 1), 100), f"ตำแหน่งของ P{m[2]}")


@rule(r"เปอร์เซ็นไทล์ที่ 75 ของข้อมูลชุดหนึ่งเท่ากับ (\d+) และเปอร์เซ็นไทล์ที่ 25 เท่ากับ (\d+) "
      r"จงหาพิสัยระหว่างควอร์ไทล์")
def _(q, m):
    want(q, int(m[1]) - int(m[2]), "IQR จาก P75 กับ P25")


@rule(r"อยู่ที่เปอร์เซ็นไทล์ที่ (\d+) ของนักเรียนทั้งหมด (\d+) คน "
      r"จงหาว่ามีนักเรียนประมาณกี่คนที่ได้คะแนนน้อยกว่า")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 100), "จำนวนคนใต้เปอร์เซ็นไทล์")


def fences(q1, q3):
    """ขอบเขตค่านอกเกณฑ์แบบ 1.5 เท่าของ IQR"""
    iqr = Fraction(q3 - q1)
    return q1 - iqr * 3 / 2, q3 + iqr * 3 / 2


@rule(r"มีควอร์ไทล์ที่ 1 เท่ากับ (\d+) และควอร์ไทล์ที่ 3 เท่ากับ (\d+) จงหาขอบเขต(ล่าง|บน)"
      r"ของการเป็นค่านอกเกณฑ์")
def _(q, m):
    low, high = fences(int(m[1]), int(m[2]))
    want(q, low if m[3] == "ล่าง" else high, f"ขอบเขต{m[3]}")


@rule(r"มีควอร์ไทล์ที่ 1 เท่ากับ (\d+) และควอร์ไทล์ที่ 3 เท่ากับ (\d+) "
      r"ถ้าข้อมูลทั้งหมดคือ (-?\d.+?) จงหาจำนวนค่านอกเกณฑ์")
def _(q, m):
    low, high = fences(int(m[1]), int(m[2]))
    want(q, sum(1 for v in parse_data(m[3]) if v < low or v > high), "นับค่านอกเกณฑ์")


@rule(r"มี Q_1 = (\d+) และ Q_3 = (\d+) จงหาว่าค่า (\d+) เป็นค่านอกเกณฑ์หรือไม่")
def _(q, m):
    low, high = fences(int(m[1]), int(m[2]))
    v = int(m[3])
    want(q, high if (v < low or v > high) else 0, "เป็นค่านอกเกณฑ์หรือไม่")


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
        if t and t.isdigit():
            eat()
            return {(): Fraction(int(t))}
        if t and t.isalpha():
            eat()
            return {((t, 1),): Fraction(1)}
        raise NotPoly(str(t))

    def power():
        # เครื่องหมายลบต้องคลุมทั้งเลขยกกำลัง — -x^2 คือ -(x^2) ไม่ใช่ (-x)^2
        # เดิมจัดการลบไว้ใน atom() ทำให้ -x^2 กลายเป็น +x^2 เงียบ ๆ (เลขชี้กำลังคู่เท่านั้น)
        if peek() == "-":
            eat()
            return _padd({}, power(), -1)
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


# ---------- โจทย์ปัญหาพีทาโกรัส (ตัวเลขอยู่ในข้อความ) ----------
@rule(r"สูง (\d+) เมตร มีเชือกยึดจากยอดเสามายังหมุดบนพื้นที่ห่างโคนเสา (\d+) เมตร")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "ความยาวเชือก")


@rule(r"ฐานบันไดห่างจากกำแพง (\d+) เมตร และปลายบันไดอยู่สูงจากพื้น (\d+) เมตร")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "ความยาวบันได")


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


# ---------- ชุดที่เพิ่มมาภายหลัง ----------
# แต่ละกฎอ่านตัวเลขจากโจทย์แล้วคิดใหม่ ไม่ได้ดูว่าตัวสร้างคิดยังไง

# --- ความเท่ากันทุกประการ ---
@rule(r"เท่ากันทุกประการ.*?มุม [ABC] เท่ากับ (\d+) องศา และมุม [ABC] เท่ากับ (\d+) องศา")
def _(q, m):
    want(q, 180 - int(m[1]) - int(m[2]), "มุมที่สามของสามเหลี่ยม")


@rule(r"เท่ากันทุกประการ มีความยาวรอบรูป (\d+) เซนติเมตร ถ้า [A-Z]{2} ยาว (\d+) "
      r"และ [A-Z]{2} ยาว (\d+)")
def _(q, m):
    per, a, b_ = map(int, m.groups())
    want(q, per - a - b_, "ด้านที่เหลือจากความยาวรอบรูป")


# --- ปริมาตรและพื้นที่ผิวของทรงต่าง ๆ ---
@rule(r"ปริซึมสามเหลี่ยมมีฐาน.*?ความยาวฐาน (\d+) ซม\. สูง (\d+) ซม\. และปริซึมสูง (\d+) ซม\.")
def _(q, m):
    b_, h, l = map(int, m.groups())
    want(q, Fraction(b_ * h, 2) * l, "ปริมาตรปริซึมสามเหลี่ยม")


@rule(r"ปริซึมสามเหลี่ยมมีพื้นที่ฐาน (\d+) ตารางเซนติเมตร สูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "ปริมาตรจากพื้นที่ฐาน")


@rule(r"ทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    w, l, h = map(int, m.groups())
    want(q, w * l * h, "ปริมาตรทรงสี่เหลี่ยมมุมฉาก")


@rule(r"^ลูกบาศก์มีด้านยาว (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    want(q, int(m[1]) ** 3, "ปริมาตรลูกบาศก์")


@rule(r"ลูกบาศก์ยาวด้านละ (\d+) เซนติเมตร มีปริมาตร")
def _(q, m):
    want(q, int(m[1]) ** 3, "ปริมาตรลูกบาศก์")


@rule(r"ลูกบาศก์ไม้มีความยาวด้านละ (\d+) เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    want(q, 6 * int(m[1]) ** 2, "พื้นที่ผิวลูกบาศก์")


@rule(r"ทรงกระบอกมีรัศมีฐาน (\d+) ซม\. สูง (\d+) ซม\. จงหาพื้นที่ผิวทั้งหมด "
      r"\(กำหนด π ≈ 3\.14\)")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    pi = Fraction(314, 100)
    want(q, 2 * pi * r * (r + h), "พื้นที่ผิวทรงกระบอก")


@rule(r"ถังน้ำทรงกระบอกรัศมีฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร จุน้ำได้กี่ลิตร")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    want(q, Fraction(22, 7) * r * r * h / 1000, "ความจุเป็นลิตร")


@rule(r"กล่องของขวัญทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร "
      r"ต้องใช้กระดาษห่อ")
def _(q, m):
    w, l, h = map(int, m.groups())
    want(q, 2 * (w * l + l * h + w * h), "พื้นที่ผิวกล่อง")


# --- สมการกำลังสองจากการแยกตัวประกอบ ---
@rule(r"จงหาคำตอบที่เป็นบวกของสมการ x\^2 - (\d+) เท่ากับ 0")
def _(q, m):
    n = int(m[1])
    want(q, next(k for k in range(1, 10001) if k * k == n), "รากบวกของ x²=n")


@rule(r"จงหาผล(บวก|คูณ)ของคำตอบทั้งหมดของสมการ x\^2 ([+-]) (\d+)x ([+-]) (\d+) เท่ากับ 0")
def _(q, m):
    b_ = int(m[3]) * (1 if m[2] == "+" else -1)
    c = int(m[5]) * (1 if m[4] == "+" else -1)
    roots = [x for x in range(-500, 501) if x * x + b_ * x + c == 0]
    rs = roots * 2 if len(roots) == 1 else roots
    want(q, rs[0] + rs[1] if m[1] == "บวก" else rs[0] * rs[1], "ผลบวก/ผลคูณของคำตอบ")


# --- พีทาโกรัสจากข้อความ ---
@rule(r"เดินไปทางทิศ\S+ (\d+) กิโลเมตร แล้วเลี้ยวไปทางทิศ\S+อีก (\d+) กิโลเมตร")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "ระยะทางแนวตรง")


@rule(r"แล่นไปทางทิศ\S+ (\d+) กิโลเมตร แล้วแล่นไปทางทิศ\S+อีก (\d+) กิโลเมตร")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "ระยะทางแนวตรง")


@rule(r"สี่เหลี่ยมผืนผ้ากว้าง (\d+) เมตร ยาว (\d+) เมตร ถ้าเดินตัดตามแนวเส้นทแยงมุม")
def _(q, m):
    a, b_ = int(m[1]), int(m[2])
    want(q, math.isqrt(a * a + b_ * b_), "เส้นทแยงมุมสี่เหลี่ยมผืนผ้า")


# แยกสองแบบให้ชัด — บางข้อถาม "ความยาว" บางข้อถาม "กำลังสอง" ของด้านที่เหลือ
@rule(r"ด้านตรงข้ามมุมฉากยาว (\d+) เซนติเมตร และด้านประกอบมุมฉากด้านหนึ่งยาว (\d+) เซนติเมตร "
      r"จงหาความยาวด้านประกอบมุมฉากอีกด้าน")
def _(q, m):
    c, a = int(m[1]), int(m[2])
    want(q, math.isqrt(c * c - a * a), "ความยาวด้านประกอบมุมฉากอีกด้าน")


@rule(r"ด้านตรงข้ามมุมฉากยาว (\d+) เซนติเมตร และด้านประกอบมุมฉากด้านหนึ่งยาว (\d+) เซนติเมตร "
      r"จงหากำลังสองของด้านประกอบมุมฉากอีกด้าน")
def _(q, m):
    c, a = int(m[1]), int(m[2])
    want(q, c * c - a * a, "กำลังสองของด้านประกอบมุมฉากอีกด้าน")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) และจุด [A-Z]\((-?\d+) (-?\d+)\) อยู่บนระนาบพิกัดฉาก "
      r"จงหาระยะห่าง")
def _(q, m):
    x1, y1, x2, y2 = map(int, m.groups())
    want(q, math.isqrt((x2 - x1) ** 2 + (y2 - y1) ** 2), "ระยะห่างระหว่างจุด")


# --- การแปลงทางเรขาคณิต: ถามพิกัดเดียว และการหมุน 90 องศา ---
@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) สะท้อนข้ามแกน ([XY]) จงหาพิกัด ([xy]) ของภาพ")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    nx, ny = (x, -y) if m[3] == "X" else (-x, y)
    want(q, nx if m[4] == "x" else ny, "พิกัดหลังสะท้อน")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) สะท้อนข้ามเส้นตรง y = x ภาพที่ได้มีพิกัดใด")
def _(q, m):
    want_pair(q, (int(m[2]), int(m[1])), "สะท้อนข้าม y = x")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) หมุนรอบจุดกำเนิด 90 องศา(ทวนเข็ม|ตามเข็ม)นาฬิกา "
      r"ภาพที่ได้มีพิกัดใด")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    want_pair(q, (-y, x) if m[3] == "ทวนเข็ม" else (y, -x), "หมุน 90 องศา")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) หมุนรอบจุดกำเนิด 90 องศา(ทวนเข็ม|ตามเข็ม)นาฬิกา "
      r"จงหาพิกัด ([xy]) ของภาพ")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    nx, ny = (-y, x) if m[3] == "ทวนเข็ม" else (y, -x)
    want(q, nx if m[4] == "x" else ny, "พิกัดหลังหมุน 90 องศา")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) เลื่อนขนานไปทาง(ขวา|ซ้าย) (\d+) หน่วย "
      r"และ(ขึ้น|ลง) (\d+) หน่วย จงหาพิกัด ([xy]) ของภาพ")
def _(q, m):
    x = int(m[1]) + (int(m[4]) if m[3] == "ขวา" else -int(m[4]))
    y = int(m[2]) + (int(m[6]) if m[5] == "ขึ้น" else -int(m[6]))
    want(q, x if m[7] == "x" else y, "พิกัดหลังเลื่อนขนาน")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) เลื่อนขนานไปทาง(ขวา|ซ้าย) (\d+) หน่วย "
      r"และ(ขึ้น|ลง) (\d+) หน่วย ภาพที่ได้มีพิกัดใด")
def _(q, m):
    x = int(m[1]) + (int(m[4]) if m[3] == "ขวา" else -int(m[4]))
    y = int(m[2]) + (int(m[6]) if m[5] == "ขึ้น" else -int(m[6]))
    want_pair(q, (x, y), "เลื่อนขนาน")


# --- กราฟ: ค่า y ที่ x = 0 คิดจากพหุนามจริง ไม่ใช่อ่านพจน์คงที่ ---
@rule(r"จงหาค่า y เมื่อ x = 0 ของกราฟ y = (.+?)\s*$")
def _(q, m):
    global checks
    checks += 1
    try:
        p = poly_of(m[1])
    except NotPoly:
        checks -= 1
        raise NotPlainData("แยกวิเคราะห์พหุนามไม่ได้")
    got = num(q["answer"])
    at0 = p.get((), Fraction(0))          # แทน x = 0 -> เหลือเฉพาะพจน์ที่ไม่มีตัวแปร
    if got is None or got != at0:
        bad.append((q["id"], "ค่า y ที่ x = 0", q["answer"], str(at0), txt(q)[:95]))


# --- เลขยกกำลัง ---
@rule(r"จงเขียน ([a-z])\^(\d+) ([×÷]) \1\^(\d+) ให้อยู่ในรูปเลขยกกำลังฐานเดียว")
def _(q, m):
    e1, op, e2 = int(m[2]), m[3], int(m[4])
    exp = e1 + e2 if op == "×" else e1 - e2
    global checks
    checks += 1
    got = re.sub(r"<[^>]+>", "^", str(q["answer"])).replace("−", "-")
    mm = re.fullmatch(r"\s*([a-z])\^(-?\d+)\^?\s*", got)
    if not mm or mm[1] != m[1] or int(mm[2]) != exp:
        bad.append((q["id"], "เลขยกกำลังฐานตัวแปร", q["answer"],
                    f"{m[1]}^{exp}", txt(q)[:95]))


@rule(r"แบคทีเรียแบ่งตัวเป็น 2 เท่าทุกชั่วโมง เริ่มต้นมี 1 ตัว เมื่อผ่านไป (\d+) ชั่วโมง")
def _(q, m):
    want(q, 2 ** int(m[1]), "การเพิ่มเป็นสองเท่า")


@rule(r"หน่วยความจำขนาด 2\^(\d+) ไบต์ เท่ากับกี่ไบต์")
def _(q, m):
    want(q, 2 ** int(m[1]), "เลขยกกำลังฐานสอง")


@rule(r"^ถ้า (\d+)\^x = (\d+) ค่าของ x")
def _(q, m):
    base, val = int(m[1]), int(m[2])
    want(q, next(k for k in range(0, 65) if base ** k == val), "หาเลขชี้กำลัง")


# --- สมการเชิงเส้นและโจทย์ปัญหาพื้นฐาน ---
@rule(r"จงแก้สมการ (-?\d+)x ([+-]) (\d+) = (-?\d+) เพื่อหาค่า x")
def _(q, m):
    a = int(m[1])
    b_ = int(m[3]) * (1 if m[2] == "+" else -1)
    c = int(m[4])
    want(q, Fraction(c - b_, a), "แก้สมการเชิงเส้น")


@rule(r"จำนวนหนึ่งบวกด้วย (\d+) ได้ผลลัพธ์ (\d+)")
def _(q, m):
    want(q, int(m[2]) - int(m[1]), "หาจำนวนจากผลบวก")


@rule(r"(สาม|สี่|ห้า|สอง)เท่าของจำนวนหนึ่งลบด้วย (\d+) ได้ผลลัพธ์ (\d+)")
def _(q, m):
    k = {"สอง": 2, "สาม": 3, "สี่": 4, "ห้า": 5}[m[1]]
    want(q, Fraction(int(m[3]) + int(m[2]), k), "หาจำนวนจากสมการ")


@rule(r"ซื้อดินสอ (\d+) แท่งและยางลบ 1 ก้อน รวมราคา (\d+) บาท ถ้ายางลบราคา (\d+) บาท")
def _(q, m):
    n, tot, eraser = map(int, m.groups())
    want(q, Fraction(tot - eraser, n), "ราคาต่อหน่วย")


@rule(r"จำนวนสองจำนวนบวกกันได้ (\d+) และต่างกัน (\d+) จำนวนที่มากกว่า")
def _(q, m):
    want(q, Fraction(int(m[1]) + int(m[2]), 2), "จำนวนที่มากกว่า")


@rule(r"ผลบวกของจำนวนนับตั้งแต่ 1 ถึง (\d+) เท่ากับเท่าใด")
def _(q, m):
    want(q, sum(range(1, int(m[1]) + 1)), "ผลบวกจำนวนนับ")


@rule(r"อัตราส่วน (\d+) : (\d+) ถ้าต้องการน้ำผสม (\d+) ลิตร ต้องใช้น้ำส้ม")
def _(q, m):
    a, b_, tot = map(int, m.groups())
    want(q, Fraction(tot * a, a + b_), "แบ่งตามอัตราส่วน")


# --- รากที่สองจากพื้นที่ ---
@rule(r"สี่เหลี่ยมจัตุรัสมีพื้นที่ (\d+) ตารางเซนติเมตร จงหาความยาวด้าน")
def _(q, m):
    want(q, math.isqrt(int(m[1])), "ด้านของจัตุรัส")


@rule(r"สี่เหลี่ยมจัตุรัสมีพื้นที่ (\d+) ตารางเมตร (?:จงหาความยาวรอบรูป|ต้องการล้อมรั้ว)")
def _(q, m):
    want(q, 4 * math.isqrt(int(m[1])), "ความยาวรอบรูปจัตุรัส")


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
    # สัญกรณ์วิทยาศาสตร์ — ต้องแม่นทั้งฝั่งบวกและฝั่งลบของเลขชี้กำลัง
    for v, expect in [("6700000", 6), ("0.00058", -4), ("1.5", 0), ("9.99", 0), ("10", 1)]:
        if sci_exp(v) != expect:
            fails.append(f"sci_exp({v}) -> {sci_exp(v)} (ต้องได้ {expect})")
    if sci(Fraction("7.5"), -3) != Fraction(3, 400):
        fails.append("sci(7.5, -3) ไม่ตรง")

    # ตารางความสัมพันธ์ต้องยอมรับเฉพาะที่เป็นเชิงเส้นจริง
    if table_xy("1 2 3 4", "5 8 11 14") != (Fraction(3), Fraction(2)):
        fails.append(f"table_xy เชิงเส้นอ่านผิด -> {table_xy('1 2 3 4', '5 8 11 14')}")
    try:
        table_xy("1 2 3", "1 4 9")            # กำลังสอง ไม่ใช่เชิงเส้น
        fails.append("table_xy ควรปฏิเสธข้อมูลที่ไม่เป็นเชิงเส้น")
    except NotPlainData:
        pass

    # อ่านค่าห้าค่ากลับจากรูปแผนภาพกล่องที่วาดจริง
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from svg_helpers import box_plot
        five, outs = box_five(box_plot((10, 20, 25, 35, 45), None, "คะแนน"))
        if five != (10, 20, 25, 35, 45) or outs:
            fails.append(f"box_five อ่านรูปผิด -> {five} {outs}")
        five, outs = box_five(box_plot((20, 40, 50, 70, 90), None, "ราคา", outliers=(110,)))
        if five != (20, 40, 50, 70, 90) or outs != [110]:
            fails.append(f"box_five อ่านค่านอกเกณฑ์ผิด -> {five} {outs}")
    except ImportError:
        pass

    X2, X1 = (("x", 2),), (("x", 1),)
    for src, expect in [("(x + 2)(x + 3)", {X2: Fraction(1), X1: Fraction(5), (): Fraction(6)}),
                        ("x^2 + 5x + 6", {X2: Fraction(1), X1: Fraction(5), (): Fraction(6)}),
                        ("3x", {X1: Fraction(3)}),
                        ("(x - 2)(x + 2)", {X2: Fraction(1), (): Fraction(-4)}),
                        ("(x + 2)(x + 3) หรือ (x + 3)(x + 2)",
                         {X2: Fraction(1), X1: Fraction(5), (): Fraction(6)}),
                        ("3a + 2b", {(("a", 1),): Fraction(3), (("b", 1),): Fraction(2)}),
                        ("7x + 3", {X1: Fraction(7), (): Fraction(3)}),
                        # เครื่องหมายลบหน้าเลขยกกำลัง — เลขชี้กำลังคู่คือจุดที่เคยพลาด
                        ("-x^2", {X2: Fraction(-1)}),
                        ("-x^2 + 2x + 3", {X2: Fraction(-1), X1: Fraction(2),
                                           (): Fraction(3)}),
                        ("-2x^2 + 4x", {X2: Fraction(-2), X1: Fraction(4)}),
                        ("(-x)^2", {X2: Fraction(1)}),
                        ("5 - x^2", {X2: Fraction(-1), (): Fraction(5)})]:
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


# ---------- สัญกรณ์วิทยาศาสตร์ ----------
# โจทย์ชุดเดิมเขียน × ÷ เป็นเอนทิตี HTML ชุดใหม่เขียนเป็นสัญลักษณ์ตรง ๆ รับทั้งสองแบบ
X = r"(?:&times;|×)"
D = r"(?:&divide;|÷)"
DEC = r"(\d+(?:\.\d+)?)"


def sci(a, n):
    """A × 10^n เป็นค่าที่แน่นอน (ไม่ใช้ float — 0.1 ในฐานสองไม่ลงตัว)"""
    return Fraction(str(a)) * Fraction(10) ** int(n)


def sci_exp(v):
    """เลขชี้กำลังของ 10 เมื่อเขียน v ในรูป A × 10^n โดย 1 ≤ A < 10"""
    v = abs(Fraction(str(v)))
    if v == 0:
        raise NotPlainData("0 ไม่มีสัญกรณ์วิทยาศาสตร์")
    n = 0
    while v >= 10:
        v /= 10
        n += 1
    while v < 1:
        v *= 10
        n -= 1
    return n


@rule(rf"{DEC} {X} 10\^(-?\d+) เขียนเป็น(?:จำนวนธรรมดา|ทศนิยม)ได้เท่าใด")
@rule(rf"จงเขียน {DEC} {X} 10\^(-?\d+) ในรูป(?:จำนวนเต็มธรรมดา|ทศนิยม)")
@rule(rf"ประมาณ {DEC} {X} 10\^(-?\d+) กิโลเมตร เขียนเป็นจำนวนธรรมดาได้กี่กิโลเมตร")
def _(q, m):
    want(q, sci(m[1], m[2]), "กระจายสัญกรณ์วิทยาศาสตร์")


@rule(rf"เขียน {DEC} ในรูป A {X} 10\^n เมื่อ 1 &le; A &lt; 10 ค่าของ n เท่ากับเท่าใด")
@rule(rf"จงเขียน {DEC} ในรูปสัญกรณ์วิทยาศาสตร์ โดยตอบเฉพาะเลขชี้กำลังของ 10")
@rule(rf"ประมาณ {DEC} (?:กิโลเมตร|เมตร) เขียนในรูปสัญกรณ์วิทยาศาสตร์ได้ "
      rf"{DEC} {X} 10 ยกกำลังเท่าใด")
def _(q, m):
    want(q, sci_exp(m[1]), "เลขชี้กำลังของสัญกรณ์วิทยาศาสตร์")


LHS = rf"\({DEC} {X} 10\^(-?\d+)\) ({X}|{D}|\+) \({DEC} {X} 10\^(-?\d+)\)"


def combine(m):
    """คิดค่าจริงของ (a × 10^m) ⟨+ × ÷⟩ (b × 10^n) — กลุ่มที่ 1-5 ของ LHS"""
    a, b = sci(m[1], m[2]), sci(m[4], m[5])
    if m[3] in ("&times;", "×"):
        return a * b
    if m[3] in ("&divide;", "÷"):
        return a / b
    return a + b


@rule(rf"{LHS} = A {X} 10\^(-?\d+) ค่าของ A เท่ากับเท่าใด")
def _(q, m):
    want(q, combine(m) / Fraction(10) ** int(m[6]), "ค่า A เมื่อโจทย์ตรึงเลขชี้กำลังไว้")


@rule(rf"{LHS} = A {X} 10\^n เมื่อ 1 &le; A &lt; 10 ค่าของ A เท่ากับเท่าใด")
def _(q, m):
    v = combine(m)
    want(q, v / Fraction(10) ** sci_exp(v), "ค่า A ของผลลัพธ์")


@rule(rf"{LHS} = A {X} 10\^n (?:เมื่อ 1 &le; A &lt; 10|โดย A = {DEC}) "
      rf"ค่าของ n เท่ากับเท่าใด")
@rule(rf"{LHS} มีค่าเท่ากับ {DEC} {X} 10 ยกกำลังเท่าใด")
def _(q, m):
    want(q, sci_exp(combine(m)), "เลขชี้กำลังของผลลัพธ์")


@rule(rf"แสงเดินทางได้ประมาณ {DEC} {X} 10\^(-?\d+) เมตรต่อวินาที ใน (\d+) วินาที "
      rf"แสงเดินทางได้ {DEC} {X} 10 ยกกำลังเท่าใด เมตร")
def _(q, m):
    want(q, sci_exp(sci(m[1], m[2]) * int(m[3])), "ระยะทางของแสง")


@rule(rf"จำนวนใดมีค่ามากกว่าระหว่าง {DEC} {X} 10\^(-?\d+) กับ {DEC} {X} 10\^(-?\d+) "
      rf"จงตอบเลขชี้กำลังของ 10 ของจำนวนที่มากกว่า")
def _(q, m):
    want(q, sci_exp(max(sci(m[1], m[2]), sci(m[3], m[4]))), "จำนวนที่มากกว่า")


# ---------- รากที่สอง ----------
def isqrt_exact(n):
    r = math.isqrt(int(n))
    if r * r != int(n):
        raise NotPlainData(f"{n} ไม่ใช่กำลังสองสมบูรณ์")
    return r


@rule(r"จงหารากที่สองที่เป็น(บวก|ลบ)ของ (\d+)$")
def _(q, m):
    want(q, isqrt_exact(m[2]) * (1 if m[1] == "บวก" else -1), f"รากที่สองที่เป็น{m[1]}")


@rule(r"จำนวนเต็มบวกใดมีรากที่สองเป็น (\d+)$")
def _(q, m):
    want(q, int(m[1]) ** 2, "ยกกำลังสองกลับ")


@rule(r"จงหาค่าของรากที่สองที่เป็นบวกของ (\d+) (บวกกับ|คูณกับ|ลบด้วย)"
      r"รากที่สองที่เป็นบวกของ (\d+)$")
def _(q, m):
    a, b = isqrt_exact(m[1]), isqrt_exact(m[3])
    want(q, {"บวกกับ": a + b, "คูณกับ": a * b, "ลบด้วย": a - b}[m[2]], "คิดรากแล้วดำเนินการ")


# ---------- ปริซึมและทรงสี่เหลี่ยมมุมฉาก ----------
@rule(r"ทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    a, b, c = map(int, (m[1], m[2], m[3]))
    want(q, 2 * (a * b + b * c + a * c), "พื้นที่ผิวทรงสี่เหลี่ยมมุมฉาก")


@rule(r"ลูกบาศก์มีด้านยาว (\d+) เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    want(q, 6 * int(m[1]) ** 2, "พื้นที่ผิวลูกบาศก์")


@rule(r"ลูกบาศก์มีปริมาตร (\d+) ลูกบาศก์เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    v = int(m[1])
    a = round(v ** (1 / 3))
    if a ** 3 != v:
        raise NotPlainData("ไม่ใช่กำลังสามสมบูรณ์")
    want(q, 6 * a * a, "ถอดด้านจากปริมาตรแล้วหาพื้นที่ผิว")


@rule(r"ปริซึมสามเหลี่ยมมีฐานเป็นสามเหลี่ยมมุมฉากด้านประกอบมุมฉากยาว (\d+) และ (\d+) "
      r"เซนติเมตร ด้านตรงข้ามมุมฉากยาว (\d+) เซนติเมตร ปริซึมสูง (\d+) เซนติเมตร "
      r"จงหาพื้นที่ผิว(ข้าง|ทั้งหมด)")
def _(q, m):
    a, b, c, h = map(int, (m[1], m[2], m[3], m[4]))
    if a * a + b * b != c * c:
        raise NotPlainData("ไม่ใช่สามเหลี่ยมมุมฉาก")
    side = (a + b + c) * h
    want(q, side if m[5] == "ข้าง" else side + a * b, f"พื้นที่ผิว{m[5]}ของปริซึมสามเหลี่ยม")


@rule(r"ปริซึมสี่เหลี่ยมจัตุรัสมีด้านฐานยาว (\d+) เซนติเมตร สูง (\d+) เซนติเมตร "
      r"จงหาพื้นที่ผิว(ข้าง|ทั้งหมด)")
def _(q, m):
    a, h = int(m[1]), int(m[2])
    want(q, 4 * a * h + (0 if m[3] == "ข้าง" else 2 * a * a),
         f"พื้นที่ผิว{m[3]}ของปริซึมสี่เหลี่ยมจัตุรัส")


@rule(r"ปริซึมมีความยาวรอบฐาน (\d+) เซนติเมตร พื้นที่ฐาน (\d+) ตารางเซนติเมตร "
      r"และสูง (\d+) เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    p, a, h = map(int, (m[1], m[2], m[3]))
    want(q, p * h + 2 * a, "พื้นที่ผิวข้าง + ฐานสองหน้า")


@rule(r"กล่องกระดาษทรงสี่เหลี่ยมมุมฉากไม่มีฝาบน กว้าง (\d+) ยาว (\d+) สูง (\d+) "
      r"เซนติเมตร ต้องใช้กระดาษกี่ตารางเซนติเมตร")
def _(q, m):
    a, b, h = map(int, (m[1], m[2], m[3]))
    want(q, a * b + 2 * (a + b) * h, "ฐานหนึ่งหน้า + ด้านข้างสี่หน้า")


@rule(r"ปริซึมสามเหลี่ยมมีฐานเป็นสามเหลี่ยมฐานยาว (\d+) เซนติเมตร สูง (\d+) เซนติเมตร "
      r"และปริซึมสูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    b, h, H = map(int, (m[1], m[2], m[3]))
    want(q, Fraction(b * h, 2) * H, "ปริมาตรปริซึมสามเหลี่ยม")


@rule(r"ปริซึม\S* ?มีพื้นที่ฐาน (\d+) ตารางเซนติเมตร สูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "พื้นที่ฐาน × สูง")


@rule(r"(?:ปริซึม|ทรงกระบอก)มีปริมาตร (\d+) ลูกบาศก์เซนติเมตร "
      r"และพื้นที่ฐาน (\d+) ตารางเซนติเมตร จงหาความสูง")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "ปริมาตร ÷ พื้นที่ฐาน")


@rule(r"ปริซึมมีปริมาตร (\d+) ลูกบาศก์เซนติเมตร และสูง (\d+) เซนติเมตร จงหาพื้นที่ฐาน")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "ปริมาตร ÷ ความสูง")


@rule(r"สระว่ายน้ำทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) เมตร ยาว (\d+) เมตร ลึก ([\d.]+) เมตร "
      r"จงหาปริมาตร")
def _(q, m):
    want(q, int(m[1]) * int(m[2]) * Fraction(m[3]), "กว้าง × ยาว × ลึก")


@rule(r"กล่องทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร จุน้ำได้กี่ลิตร")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]) * int(m[3]), 1000), "ปริมาตรเป็นลิตร")


@rule(r"ตู้ปลาทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร "
      r"เติมน้ำสูง (\d+) เซนติเมตร จงหาปริมาตรน้ำ")
def _(q, m):
    want(q, int(m[1]) * int(m[2]) * int(m[4]), "ใช้ความสูงของน้ำ ไม่ใช่ของตู้")


# ---------- ทรงกระบอก ----------
PI = Fraction(22, 7)


@rule(r"ทรงกระบอกมีรัศมีฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    want(q, PI * int(m[1]) ** 2 * int(m[2]), "πr²h")


@rule(r"ทรงกระบอกมีเส้นผ่านศูนย์กลางฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร จงหาปริมาตร")
def _(q, m):
    want(q, PI * Fraction(int(m[1]), 2) ** 2 * int(m[2]), "แปลงเส้นผ่านศูนย์กลางเป็นรัศมีก่อน")


@rule(r"ทรงกระบอกมีรัศมีฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร จงหาพื้นที่ผิวข้าง")
def _(q, m):
    want(q, 2 * PI * int(m[1]) * int(m[2]), "2πrh")


@rule(r"ทรงกระบอกมีรัศมีฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    want(q, 2 * PI * r * (r + h), "2πr(r + h)")


@rule(r"ทรงกระบอกมีรัศมีฐาน (\d+) เซนติเมตร จงหาพื้นที่ฐานหนึ่งฐาน")
def _(q, m):
    want(q, PI * int(m[1]) ** 2, "πr²")


@rule(r"ถ้าเพิ่ม(รัศมี|ความสูง)ของทรงกระบอกเป็น (\d+) เท่าโดย(?:ความสูง|รัศมี)คงเดิม "
      r"ปริมาตรจะเป็นกี่เท่าของเดิม")
def _(q, m):
    k = int(m[2])
    want(q, k * k if m[1] == "รัศมี" else k, "ปริมาตรแปรตามรัศมียกกำลังสอง")


# ---------- มุมภายในรูปหลายเหลี่ยม / เส้นขนาน ----------
SIDES = {"สาม": 3, "สี่": 4, "ห้า": 5, "หก": 6, "เจ็ด": 7, "แปด": 8,
         "เก้า": 9, "สิบ": 10, "สิบสอง": 12}


@rule(r"ผลบวกของมุมภายในของรูป(สิบสอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ)เหลี่ยมเท่ากับกี่องศา")
def _(q, m):
    want(q, (SIDES[m[1]] - 2) * 180, "(n − 2) × 180")


@rule(r"ผลบวกของมุมภายในของรูป n เหลี่ยมหาได้จากสูตร \(n - 2\) คูณด้วยกี่องศา")
def _(q, m):
    want(q, 180, "สูตรมุมภายใน")


@rule(r"มุม(?:ภายในบนข้างเดียวกัน|ตรงข้ามที่เกิดจากเส้นตัดกับเส้นขนานเส้นหนึ่งมี)"
      r"ขนาด (\d+) องศา จงหาขนาดของ(?:อีกมุมหนึ่ง|มุมประชิด)")
def _(q, m):
    want(q, 180 - int(m[1]), "มุมภายในบนข้างเดียวกันรวมกันได้ 180°")


@rule(r"มุมแย้งขนาด (\d+) องศา จงหาขนาดของมุมแย้งอีกมุมหนึ่ง")
@rule(r"มุมภายนอกกับมุมภายในที่อยู่ตรงข้ามบนข้างเดียวกันมีขนาด (\d+) องศา "
      r"จงหาขนาดของมุมภายนอกนั้น")
def _(q, m):
    want(q, int(m[1]), "มุมคู่นี้เท่ากัน")


@rule(r"มุมภายในบนข้างเดียวกันสองมุม โดยมุมหนึ่งมีขนาดเป็นสองเท่าของอีกมุมหนึ่ง "
      r"จงหาขนาดของมุมที่เล็กกว่า")
def _(q, m):
    want(q, Fraction(180, 3), "x + 2x = 180")


@rule(r"มุมภายในบนข้างเดียวกันสองมุม มุมหนึ่งมีขนาด \((\d*)x\) องศา "
      r"อีกมุมมีขนาด \(x \+ (\d+)\) องศา จงหาค่าของ x")
def _(q, m):
    a = int(m[1] or 1)
    want(q, Fraction(180 - int(m[2]), a + 1), "ax + (x + b) = 180")


@rule(r"มุมแย้งสองมุม มุมหนึ่งมีขนาด \((\d*)x - (\d+)\) องศา "
      r"อีกมุมมีขนาด \(x \+ (\d+)\) องศา จงหาค่าของ x")
def _(q, m):
    a = int(m[1] or 1)
    want(q, Fraction(int(m[3]) + int(m[2]), a - 1), "มุมแย้งเท่ากัน: ax − b = x + c")


@rule(r"เส้นตัดตั้งฉากกับเส้นขนานเส้นหนึ่ง มุมที่เส้นตัดทำกับเส้นขนานอีกเส้นมีขนาดกี่องศา")
@rule(r"ถ้ามุมหนึ่งมีขนาด 90 องศา มุมทั้งแปดที่เกิดขึ้นมีขนาดกี่องศาเท่ากันหมด")
def _(q, m):
    want(q, 90, "ตั้งฉากกับเส้นหนึ่งย่อมตั้งฉากกับเส้นขนานอีกเส้น")


# ---------- ดิสคริมิแนนต์ ----------
@rule(r"จงหาค่าของ b\^2 - 4ac ของสมการ (.+?) = 0$")
def _(q, m):
    p = poly_of(m[1])
    deg = {k: v for k, v in p.items() if v}
    for k in deg:
        if k and (len(k) != 1 or k[0][0] != "x" or k[0][1] > 2):
            raise NotPoly("ไม่ใช่พหุนามกำลังสองตัวแปรเดียว")
    a = p.get((("x", 2),), 0)
    b = p.get((("x", 1),), 0)
    c = p.get((), 0)
    if not a:
        raise NotPoly("ไม่มีพจน์กำลังสอง")
    want(q, b * b - 4 * a * c, "ดิสคริมิแนนต์")


# ---------- ตรีโกณมิติของมุมพิเศษ ----------
TRIG = {("sin", 0): 0, ("sin", 30): Fraction(1, 2), ("sin", 90): 1,
        ("cos", 0): 1, ("cos", 60): Fraction(1, 2), ("cos", 90): 0,
        ("tan", 0): 0, ("tan", 45): 1}


@rule(r"จงหาค่าของ (sin|cos|tan) (\d+)°$")
def _(q, m):
    key = (m[1], int(m[2]))
    if key not in TRIG:                 # 45°/60° ของ sin/cos เป็นจำนวนอตรรกยะ เทียบเป็นตัวเลขไม่ได้
        raise NotPlainData(f"{m[1]} {m[2]}° ไม่ใช่ค่าตรรกยะ")
    want(q, TRIG[key], f"{m[1]} {m[2]}°")


@rule(r"จงหาค่าของ sin\^2 (\d+)° \+ cos\^2 \1° \+ tan 45°")
def _(q, m):
    want(q, 2, "sin²θ + cos²θ = 1 แล้วบวก tan 45° = 1")


@rule(r"จากยอดเสาสูง (\d+) เมตร มองเห็นจุดหนึ่งบนพื้นราบเป็นมุมก้ม 45 องศา "
      r"จงหาระยะจากโคนเสาถึงจุดนั้น")
def _(q, m):
    want(q, int(m[1]), "tan 45° = 1 ระยะจึงเท่ากับความสูง")


@rule(r"เสาสูง (\d+) เมตร ทำมุมเงย 30 องศากับจุดสังเกตบนพื้นราบ .*?"
      r"ตอบในรูป k√3 จงหาค่าของ k")
def _(q, m):
    want(q, int(m[1]), "h / tan 30° = h√3")


# ---------- เลขยกกำลัง ----------
@rule(r"จงหาค่าของ \((\d+)\)/\((\d+)\)\^(\d+) ในรูปเศษส่วน")
@rule(r"จงหาค่าของ \((\d+)/(\d+)\)\^(\d+) ในรูปเศษส่วน")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])) ** int(m[3]), "ยกกำลังทั้งเศษและส่วน")


@rule(rf"จงหาค่าของ (\d+)\^(-?\d+) {X} (\d+)\^(-?\d+) ในรูปเศษส่วน")
def _(q, m):
    if m[1] != m[3]:
        raise NotPlainData("ฐานไม่เท่ากัน")
    want(q, Fraction(int(m[1])) ** (int(m[2]) + int(m[4])), "ฐานเดียวกันบวกเลขชี้กำลัง")


@rule(r"ถ้า (\d+)\^n เท่ากับ (\d+) จงหาค่าของ n$")
def _(q, m):
    base, v, n = int(m[1]), int(m[2]), 0
    cur = 1
    while cur < v:
        cur *= base
        n += 1
    if cur != v:
        raise NotPlainData("ไม่ใช่กำลังของฐานนี้")
    want(q, n, "ไล่คูณฐานจนได้ค่าที่โจทย์บอก")


@rule(rf"ถ้า (\d+)\^x {X} (\d+)\^(\d+) เท่ากับ (\d+)\^(\d+) จงหาค่าของ x")
def _(q, m):
    if not (m[1] == m[2] == m[4]):
        raise NotPlainData("ฐานไม่เท่ากัน")
    want(q, int(m[5]) - int(m[3]), "เทียบเลขชี้กำลังของฐานเดียวกัน")


@rule(r"ถ้า (\d+)\^(\d+)x เท่ากับ (\d+)\^(\d+) จงหาค่าของ x")
def _(q, m):
    if m[1] != m[3]:
        raise NotPlainData("ฐานไม่เท่ากัน")
    want(q, Fraction(int(m[4]), int(m[2])), "เทียบเลขชี้กำลังของฐานเดียวกัน")


# ---------- โจทย์ปัญหาเลขโดด ----------
@rule(r"จำนวนเต็มสองหลักจำนวนหนึ่งมีผลบวกของเลขโดดเท่ากับ (\d+) และเมื่อสลับตำแหน่งเลขโดด"
      r"จะได้จำนวนใหม่ที่ต่างจากจำนวนเดิมอยู่ (\d+) โดยจำนวนเดิม(มากกว่า|น้อยกว่า)จำนวนใหม่ "
      r"จงหาจำนวนเดิม")
def _(q, m):
    """ไล่ทุกจำนวนสองหลัก — คนละวิธีกับตัวสร้างที่แก้สมการสองตัวแปร"""
    s, d = int(m[1]), int(m[2])
    hit = [n for n in range(10, 100)
           if n // 10 + n % 10 == s
           and (n - (n % 10 * 10 + n // 10) == (d if m[3] == "มากกว่า" else -d))
           and n % 10 != 0]
    if len(hit) != 1:
        raise NotPlainData(f"คำตอบไม่ได้มีค่าเดียว ({hit})")
    want(q, hit[0], "ไล่ทุกจำนวนสองหลัก")


# ---------- เฉลยที่เป็นคำ ไม่ใช่ตัวเลข ----------
def want_yesno(q, ok, neg, why):
    """เฉลยเป็นคำคู่ตรงข้าม (เป็น/ไม่เป็น · ได้/ไม่ได้ · ตรรกยะ/อตรรกยะ)

    neg คือคำฝั่งปฏิเสธ ซึ่งมีคำฝั่งบวกซ้อนอยู่ข้างในเสมอ ("ไม่ได้" มี "ได้")
    จึงดูว่าเฉลยมี neg อยู่หรือเปล่า แทนที่จะเทียบตรง ๆ
    โจทย์เดียวกันมีทั้งแบบเติมคำและแบบปรนัย ปรนัยให้ไล่ดูตัวเลือกว่าตัวไหนคือฝั่งไหน
    """
    global checks
    got = re.sub(r"<[^>]+>", " ", str(q["answer"])).split("หรือ")[0].strip()
    if 'class="choices' in q["text"]:
        opts = re.findall(r'<div class="ch"><b>(.)\.</b>\s*(.*?)</div>', q["text"])
        pick = [L for L, t in opts if (neg in t) != ok]
        # นับว่า "ตรวจแล้ว" ต่อเมื่อตรวจได้จริง — ไม่งั้นข้อเดียวถูกนับสองที่
        # (ทั้งในยอดที่ตรวจแล้วและในกองที่ข้าม) ทำให้ยอดรวมในรายงานเกินจริง
        if len(pick) != 1:
            raise NotPlainData(f"ตัวเลือกไม่ได้แยกเป็นสองฝั่งชัดเจน ({opts})")
        checks += 1
        if got != pick[0]:
            bad.append((q["id"], why, q["answer"], pick[0], txt(q)[:95]))
        return
    checks += 1
    if (neg in got) == ok:
        bad.append((q["id"], why, q["answer"], f"ควรเป็นฝั่ง{'บวก' if ok else neg}",
                    txt(q)[:95]))


def want_ratio(q, a, b, why):
    """เฉลยอยู่ในรูป 'a : b' — เทียบเป็นอัตราส่วนอย่างต่ำ"""
    global checks
    checks += 1
    got = re.sub(r"<[^>]+>", "", str(q["answer"])).replace(" ", "")
    m = re.fullmatch(r"(\d+):(\d+)", got)
    if not m or Fraction(int(m[1]), int(m[2])) != Fraction(a, b):
        bad.append((q["id"], why, q["answer"], f"{Fraction(a, b)}", txt(q)[:95]))


# ---------- อัตราส่วน สัดส่วน ร้อยละ ----------
@rule(r"จงหาค่า x จากสัดส่วน (\d+) : (\d+) = (\d+) : x$")
def _(q, m):
    want(q, Fraction(int(m[2]) * int(m[3]), int(m[1])), "คูณไขว้")


@rule(r"จงหาค่า x จากสัดส่วน (\d+) : (\d+) = x : (\d+)$")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[3]), int(m[2])), "คูณไขว้")


@rule(r"จงทำอัตราส่วน (\d+) : (\d+) ให้เป็นอัตราส่วนอย่างต่ำ")
def _(q, m):
    want_ratio(q, int(m[1]), int(m[2]), "อัตราส่วนอย่างต่ำ")


@rule(r"^(\d+) คิดเป็นร้อยละเท่าใดของ (\d+)$")
def _(q, m):
    want(q, Fraction(int(m[1]) * 100, int(m[2])), "ส่วน ÷ ทั้งหมด × 100")


@rule(r"ถ้า (\d+) คิดเป็นร้อยละ (\d+) ของจำนวนหนึ่ง จงหาจำนวนนั้น")
def _(q, m):
    want(q, Fraction(int(m[1]) * 100, int(m[2])), "ย้อนจากร้อยละกลับเป็นจำนวนเต็ม")


@rule(r"จงหาว่า (\d+)% ของ (\d+) มีค่าเท่าใด")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 100), "ร้อยละของจำนวน")


@rule(r"ซื้อสินค้ามาราคาทุน (\d+) บาท ต้องการกำไร (\d+)% ของราคาทุน จงหาว่าต้องขายราคาเท่าใด")
def _(q, m):
    c, p = int(m[1]), int(m[2])
    want(q, c + Fraction(c * p, 100), "ราคาทุน + กำไร")


@rule(r"ราคาป้าย (\d+) บาท ลดราคา (\d+)% จงหาว่าต้องจ่ายเงินกี่บาท")
def _(q, m):
    c, p = int(m[1]), int(m[2])
    want(q, c - Fraction(c * p, 100), "ราคาป้าย − ส่วนลด")


# ---------- พีทาโกรัส ----------
@rule(r"สามเหลี่ยมมุมฉากมีด้านประกอบมุมฉากยาว (\d+) และ (\d+) เซนติเมตร "
      r"จงหาความยาวด้านตรงข้ามมุมฉาก")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, isqrt_exact(a * a + b * b), "√(a² + b²)")


@rule(r"สามเหลี่ยมมีด้านยาว (\d+) (\d+) และ (\d+) หน่วย เป็นรูปสามเหลี่ยมมุมฉากหรือไม่")
def _(q, m):
    a, b, c = sorted(map(int, (m[1], m[2], m[3])))
    want_yesno(q, a * a + b * b == c * c, "ไม่เป็น", "บทกลับพีทาโกรัส")


# ---------- เลขยกกำลังและราก (ต่อ) ----------
@rule(r"^(\d+) เขียนในรูป (\d+)\^n ค่าของ n เท่ากับเท่าใด")
def _(q, m):
    v, base, n, cur = int(m[1]), int(m[2]), 0, 1
    while cur < v:
        cur *= base
        n += 1
    if cur != v:
        raise NotPlainData("ไม่ใช่กำลังของฐานนี้")
    want(q, n, "ไล่คูณฐานจนได้ค่าที่โจทย์บอก")


@rule(rf"จงหาค่าของ (\d+)\^(\d+) {X} (\d+)\^(\d+) \(เขียนในรูปเลขยกกำลังฐานเดียวก่อน")
def _(q, m):
    if m[1] != m[3]:
        raise NotPlainData("ฐานไม่เท่ากัน")
    want(q, int(m[1]) ** (int(m[2]) + int(m[4])), "ฐานเดียวกันบวกเลขชี้กำลัง")


@rule(r"รากที่สองที่เป็นบวกของ (\d+) อยู่ระหว่างจำนวนเต็มใดกับจำนวนเต็มถัดไป "
      r"จงตอบจำนวนเต็มที่น้อยกว่า")
def _(q, m):
    n = int(m[1])
    r = math.isqrt(n)
    if r * r == n:
        raise NotPlainData("เป็นกำลังสองสมบูรณ์ ไม่ได้อยู่ระหว่างจำนวนเต็ม")
    want(q, r, "จำนวนเต็มที่มากที่สุดซึ่งกำลังสองยังไม่เกิน n")


@rule(r"จงหารากที่สามของ (-?\d+)$")
def _(q, m):
    v = int(m[1])
    r = round(abs(v) ** (1 / 3)) * (1 if v >= 0 else -1)
    if r ** 3 != v:
        raise NotPlainData("ไม่ใช่กำลังสามสมบูรณ์")
    want(q, r, "รากที่สาม")


@rule(r"รากที่สองที่เป็นบวกของ (\d+) เป็นจำนวนตรรกยะหรืออตรรกยะ")
def _(q, m):
    n = int(m[1])
    want_yesno(q, math.isqrt(n) ** 2 == n, "อตรรกยะ", "รากลงตัวหรือไม่")


# ---------- จำนวนเต็มและเศษส่วน ----------
@rule(r"จงหาค่าของ \|(-?\d+)\|$")
def _(q, m):
    want(q, abs(int(m[1])), "ค่าสัมบูรณ์")


@rule(r"จงหาค่าของ \|(-?\d+)\| ([+-]) \|(-?\d+)\|$")
def _(q, m):
    a, b = abs(int(m[1])), abs(int(m[3]))
    want(q, a + b if m[2] == "+" else a - b, "ค่าสัมบูรณ์แล้วบวกลบ")


@rule(r"อินเวอร์สการบวกของ (-?\d+) คือจำนวนใด")
def _(q, m):
    want(q, -int(m[1]), "อินเวอร์สการบวก")


@rule(r"จงเขียน(?:เศษส่วน)? \((\d+)\)/\((\d+)\) ในรูปทศนิยม$")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "เศษส่วนเป็นทศนิยม")


@rule(r"จงเขียนเศษส่วน \((\d+)\)/\((\d+)\) ในรูปทศนิยม แล้วเขียนเป็นร้อยละ")
def _(q, m):
    """เฉลยข้อนี้เขียนไว้สองรูปคั่นด้วย "หรือ" ต้องถูกทั้งคู่"""
    global checks
    checks += 1
    v = Fraction(int(m[1]), int(m[2]))
    parts = [num(x) for x in re.sub(r"<[^>]+>", "", q["answer"]).split("หรือ")]
    if len(parts) != 2 or parts[0] != v or parts[1] != v * 100:
        bad.append((q["id"], "ทศนิยมและร้อยละ", q["answer"],
                    f"{float(v)} หรือร้อยละ {float(v * 100)}", txt(q)[:95]))


# ---------- เรขาคณิตพื้นฐาน ----------
@rule(r"จงหาพื้นที่รูปสี่เหลี่ยมผืนผ้าที่มีความกว้าง (\d+) เซนติเมตร และความยาว (\d+)")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "กว้าง × ยาว")


@rule(r"จงหาพื้นที่รูปสามเหลี่ยมที่มีความยาวฐาน (\d+) เซนติเมตร และสูง (\d+)")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 2), "½ × ฐาน × สูง")


@rule(r"จงหาพื้นที่วงกลมที่มีรัศมียาว (\d+) เซนติเมตร \(กำหนด π ≈ 3\.14\)")
def _(q, m):
    want(q, Fraction("3.14") * int(m[1]) ** 2, "πr² ด้วย π ≈ 3.14")


@rule(r"วงกลมวงหนึ่งมีรัศมียาว (\d+) เซนติเมตร จงหาความยาวเส้นรอบวง \(กำหนด π ≈ 3\.14\)")
def _(q, m):
    want(q, 2 * Fraction("3.14") * int(m[1]), "2πr ด้วย π ≈ 3.14")


@rule(r"รูปสี่เหลี่ยมผืนผ้ารูปหนึ่งมีความกว้าง (\d+) เซนติเมตร และความยาว (\d+) เซนติเมตร "
      r"จงหาความยาวเส้นรอบรูป")
def _(q, m):
    want(q, 2 * (int(m[1]) + int(m[2])), "2(กว้าง + ยาว)")


@rule(r"ทรงกระบอกมีรัศมีฐาน (\d+) ซม\. สูง (\d+) ซม\. จงหาปริมาตร \(กำหนด π ≈ 3\.14\)")
def _(q, m):
    want(q, Fraction("3.14") * int(m[1]) ** 2 * int(m[2]), "πr²h ด้วย π ≈ 3.14")


@rule(r"ถ้ามุมสองมุมรวมกันได้ (\d+) องศา และมุมหนึ่งมีขนาด (\d+) องศา อีกมุมมีขนาดกี่องศา")
def _(q, m):
    want(q, int(m[1]) - int(m[2]), "มุมที่เหลือ")


@rule(r"สร้างรูปสามเหลี่ยมที่มีด้านยาว (\d+) (\d+) และ (\d+) เซนติเมตร จะสร้างได้หรือไม่")
def _(q, m):
    a, b, c = sorted(map(int, (m[1], m[2], m[3])))
    want_yesno(q, a + b > c, "ไม่ได้", "อสมการสามเหลี่ยม")


@rule(r"ถ้าสร้างมุมโดยสร้างมุม (\d+) องศาแล้วต่อด้วยมุม (\d+) องศา จะได้มุมขนาดกี่องศา")
def _(q, m):
    want(q, int(m[1]) + int(m[2]), "มุมต่อกัน")


@rule(r"ถ้าสร้างมุมโดยแบ่งครึ่งมุม (\d+) องศา จะได้มุมขนาดกี่องศา")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "แบ่งครึ่งมุม")


@rule(r"จุด \((-?\d+) (-?\d+)\) อยู่ในจตุภาคใดของระนาบพิกัดฉาก")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    if x == 0 or y == 0:
        raise NotPlainData("อยู่บนแกน ไม่อยู่ในจตุภาคใด")
    want(q, 1 if (x > 0 and y > 0) else 2 if (x < 0 < y) else 3 if (x < 0 and y < 0) else 4,
         "จตุภาคจากเครื่องหมายของพิกัด")


# ---------- ความสัมพันธ์เชิงเส้น ----------
@rule(r"เมื่อ x = (-?\d+) y = (-?\d+) และเมื่อ x = (-?\d+) y = (-?\d+) "
      r"จงหาอัตราการเปลี่ยนแปลง")
def _(q, m):
    x1, y1, x2, y2 = map(int, (m[1], m[2], m[3], m[4]))
    if x1 == x2:
        raise NotPlainData("x ซ้ำ หาความชันไม่ได้")
    want(q, Fraction(y2 - y1, x2 - x1), "Δy / Δx")


@rule(r"กราฟเส้นตรงผ่านจุด \((-?\d+) (-?\d+)\) และ \((-?\d+) (-?\d+)\) "
      r"อัตราการเปลี่ยนแปลงเท่ากับเท่าใด")
def _(q, m):
    x1, y1, x2, y2 = map(int, (m[1], m[2], m[3], m[4]))
    if x1 == x2:
        raise NotPlainData("x ซ้ำ หาความชันไม่ได้")
    want(q, Fraction(y2 - y1, x2 - x1), "Δy / Δx")


@rule(r"จงแก้สมการ (-?\d+)x ([+-]) (\d+) = (-?\d+)x ([+-]) (\d+) เพื่อหาค่า x")
def _(q, m):
    a = int(m[1]) - int(m[4])
    b = (int(m[6]) if m[5] == "+" else -int(m[6])) - (int(m[3]) if m[2] == "+" else -int(m[3]))
    if a == 0:
        raise NotPlainData("สัมประสิทธิ์ x หักกันหมด")
    want(q, Fraction(b, a), "ย้ายข้างแล้วหาร")


@rule(r"กำหนดความสัมพันธ์เชิงเส้น y = (-?\d+)x ([+-]) (\d+) จงหาค่า x เมื่อ y = (-?\d+)")
def _(q, m):
    a = int(m[1])
    b = int(m[3]) if m[2] == "+" else -int(m[3])
    want(q, Fraction(int(m[4]) - b, a), "แทน y แล้วแก้หา x")


# ---------- กระจายแล้วเทียบสัมประสิทธิ์ ----------
@rule(r"ถ้า (\(.+?\)) = x\^3 \+ bx\^2 \+ cx \+ d จงหาค่าของ b \+ c \+ d")
def _(q, m):
    """b + c + d คือค่าของพหุนามที่ x = 1 ลบพจน์ x³ ออก — กระจายจริงแล้วแทนค่า"""
    p = poly_of(m[1])
    if p.get((("x", 3),)) != 1:
        raise NotPoly("สัมประสิทธิ์ x³ ไม่ใช่ 1")
    at1 = sum(v for k, v in p.items() if all(name == "x" for name, _ in k))
    want(q, at1 - 1, "P(1) − 1")


# ---------- จำนวนเต็ม สมบัติการดำเนินการ ----------
@rule(r"จำนวนตรงข้ามของ (-?\d+) คือจำนวนใด")
def _(q, m):
    want(q, -int(m[1]), "จำนวนตรงข้าม")


@rule(r"เอกลักษณ์การบวกของจำนวนเต็มคือจำนวนใด")
def _(q, m):
    want(q, 0, "เอกลักษณ์การบวก")


@rule(r"เปรียบเทียบ (-?\d+) กับ (-?\d+) จำนวนใดมีค่ามากกว่า")
def _(q, m):
    want(q, max(int(m[1]), int(m[2])), "เทียบค่าจำนวนเต็ม")


@rule(r"เมื่อเรียงจำนวน (-?\d[\d -]*) จากน้อยไปมาก จำนวนที่อยู่ในลำดับที่ (\d+) คือจำนวนใด")
def _(q, m):
    d = sorted(parse_data(m[1]))
    k = int(m[2])
    if not 1 <= k <= len(d):
        raise NotPlainData("ลำดับเกินจำนวนข้อมูล")
    want(q, d[k - 1], "เรียงใหม่แล้วหยิบตามลำดับ")


@rule(r"จำนวนเต็มที่มากที่สุดซึ่งน้อยกว่า (-?\d+) คือจำนวนใด")
def _(q, m):
    want(q, int(m[1]) - 1, "จำนวนเต็มถัดลงไปหนึ่ง")


@rule(r"มีจำนวนเต็ม x กี่จำนวนที่ทำให้ \|x\| &lt; (\d+) เป็นจริง")
def _(q, m):
    n = int(m[1])
    want(q, sum(1 for x in range(-n, n + 1) if abs(x) < n), "ไล่นับทุกจำนวนเต็มในช่วง")


@rule(rf"จากสมบัติการแจกแจง (\d+) {X} \((\d+) \+ (\d+)\) = \(\d+ {X} \d+\) \+ "
      rf"\(\d+ {X} ⬜\) จำนวนในช่องว่างคือจำนวนใด")
def _(q, m):
    want(q, int(m[3]), "พจน์ที่สองในวงเล็บ")


@rule(rf"จากสมบัติการแจกแจง (\d+) {X} (\d+) \+ \d+ {X} (\d+) = \d+ {X} ⬜ "
      rf"จำนวนในช่องว่างคือจำนวนใด")
def _(q, m):
    want(q, int(m[2]) + int(m[3]), "ดึงตัวร่วมออกแล้วบวกกัน")


@rule(rf"ใช้สมบัติการแจกแจงหาค่าของ (\d+) {X} (\d+) โดยเขียน \d+ = \d+ - \d+")
@rule(rf"จงใช้สมบัติการแจกแจงหาค่าของ (\d+) {X} (\d+)$")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "คูณตรง ๆ")


@rule(rf"จงใช้ผลต่างกำลังสองหาค่าของ (\d+)\^2 - (\d+)\^2")
def _(q, m):
    want(q, int(m[1]) ** 2 - int(m[2]) ** 2, "ยกกำลังแล้วลบตรง ๆ")


@rule(r"แบคทีเรียแบ่งตัวจาก 1 เซลล์เป็น 2 เท่าทุกชั่วโมง เมื่อผ่านไป (\d+) ชั่วโมงจะมีกี่เซลล์")
def _(q, m):
    n = 1
    for _ in range(int(m[1])):
        n *= 2
    want(q, n, "คูณสองทีละชั่วโมง")


@rule(r"จงหาค่าของ (\d+)\^(-\d+) ในรูปเศษส่วน")
def _(q, m):
    want(q, Fraction(int(m[1])) ** int(m[2]), "เลขชี้กำลังลบ")


@rule(r"จงหาค่าเฉลี่ยเลขคณิตของ (-?\d[\d -]*)$")
def _(q, m):
    d = parse_data(m[1])
    want(q, Fraction(sum(d), len(d)), "ค่าเฉลี่ย")


# ---------- เรขาคณิต (ต่อ) ----------
@rule(r"ลูกบาศก์มีปริมาตร (\d+) ลูกบาศก์เซนติเมตร จงหาความยาวด้าน")
def _(q, m):
    v = int(m[1])
    a = round(v ** (1 / 3))
    if a ** 3 != v:
        raise NotPlainData("ไม่ใช่กำลังสามสมบูรณ์")
    want(q, a, "รากที่สามของปริมาตร")


@rule(r"รูปสามเหลี่ยมมีมุมภายในขนาด (\d+) และ (\d+) องศา จงหาขนาดของมุมที่เหลือ")
def _(q, m):
    want(q, 180 - int(m[1]) - int(m[2]), "มุมภายในรวมกันได้ 180°")


@rule(r"รูปหลายเหลี่ยมด้านเท่ามุมเท่าที่มี (\d+) ด้าน มีมุมภายในแต่ละมุมขนาดกี่องศา")
def _(q, m):
    n = int(m[1])
    want(q, Fraction((n - 2) * 180, n), "(n − 2)180 ÷ n")


@rule(r"กรวยกลมตรงรัศมีฐาน (\d+) เซนติเมตร สูง (\d+) เซนติเมตร และทรงกลมรัศมี (\d+) "
      r"เซนติเมตร จงหาอัตราส่วนของปริมาตรกรวยต่อปริมาตรทรงกลม ในรูป 1 : k จงหาค่าของ k")
def _(q, m):
    r, h, R = map(int, (m[1], m[2], m[3]))
    cone = Fraction(1, 3) * r * r * h          # ตัด π ออกทั้งคู่ อัตราส่วนไม่เปลี่ยน
    ball = Fraction(4, 3) * R ** 3
    want(q, ball / cone, "ปริมาตรทรงกลม ÷ ปริมาตรกรวย")


# ---------- ตารางความสัมพันธ์เชิงเส้น ----------
def table_xy(xs, ys):
    """อ่านตาราง x/y แล้วยืนยันว่าเป็นเชิงเส้นจริงก่อนใช้ — คืน (ความชัน, จุดตัดแกน y)"""
    x, y = parse_data(xs), parse_data(ys)
    if len(x) != len(y) or len(x) < 2:
        raise NotPlainData("ตารางไม่ครบคู่")
    a = Fraction(y[1] - y[0], x[1] - x[0])
    b = y[0] - a * x[0]
    for xi, yi in zip(x, y):
        if a * xi + b != yi:
            raise NotPlainData("ตารางไม่เป็นความสัมพันธ์เชิงเส้น")
    return a, b


@rule(r"จากตารางความสัมพันธ์ ค่าของ y เมื่อ x = (-?\d+) เท่ากับเท่าใด x (-?\d[\d -]*) y (-?\d[\d -]*)$")
def _(q, m):
    a, b = table_xy(m[2], m[3])
    want(q, a * int(m[1]) + b, "หาสมการจากตารางแล้วแทนค่า")


@rule(r"จากตารางความสัมพันธ์ ความสัมพันธ์นี้เขียนได้เป็น y = (-?\d+)x \+ ⬜ "
      r"จำนวนในช่องว่างคือจำนวนใด x (-?\d[\d -]*) y (-?\d[\d -]*)$")
def _(q, m):
    a, b = table_xy(m[2], m[3])
    if a != int(m[1]):
        raise NotPlainData("ความชันไม่ตรงกับที่โจทย์เขียนไว้")
    want(q, b, "จุดตัดแกน y")


# ---------- ตัวช่วยสุดท้าย: โจทย์ที่เป็นนิพจน์เลขคณิตล้วน ----------
# วางไว้ท้ายสุดเพราะกฎเฉพาะทางด้านบนต้องได้จับก่อน
@rule(r"จงหาค่าของ ([-\d(][^ก-๛]*)$")
def _(q, m):
    want(q, arith(m[1]), "คิดนิพจน์ใหม่ทั้งหมด")


@rule(r"ใช้สมบัติการสลับที่และการเปลี่ยนกลุ่มหาค่าของ ([-\d(][^ก-๛]*)$")
def _(q, m):
    want(q, arith(m[1]), "บวกตามลำดับเดิม")


# ---------- ม.3 · ข้อที่มีรูปประกอบ ----------
# ตัวเลขอยู่ในตัวโจทย์ด้วย (รูปเป็นตัวอธิบายว่าเส้นไหนคืออะไร) จึงคิดใหม่จากข้อความได้
OPS = {"&ge;": "≥", "&le;": "≤", "&lt;": "<", "&gt;": ">"}


@rule(r"เส้นจำนวนข้างต้นแสดงคำตอบของอสมการ (-?\d*)x ([+-]) (\d+) "
      r"(&ge;|&le;|&lt;|&gt;) (-?\d+) (.+)$")
def _(q, m):
    a = int(m[1] or 1)
    b = int(m[3]) if m[2] == "+" else -int(m[3])
    pt = Fraction(int(m[5]) - b, a)
    op = OPS[m[4]]
    if a < 0:                                  # หารด้วยจำนวนลบ เครื่องหมายกลับข้าง
        op = {"≥": "≤", "≤": "≥", ">": "<", "<": ">"}[op]
    ask = m[6]
    if "จุดปลายของช่วงคำตอบ" in ask:
        return want(q, pt, "แก้อสมการหาจุดปลาย")
    if "จงหาจำนวนเต็มที่" in ask:
        big = "มากที่สุด" in ask
        if pt.denominator != 1:
            return want(q, math.floor(pt) if big else math.ceil(pt), "จำนวนเต็มที่ติดขอบ")
        pt = int(pt)
        return want(q, pt if op in ("≥", "≤") else (pt - 1 if big else pt + 1),
                    "จำนวนเต็มที่ติดขอบ")
    if "มีจำนวนเต็มกี่จำนวน" in ask:
        # ช่วงของเส้นจำนวนอ่านจากป้ายขีดที่วาดไว้จริงในรูป ไม่ได้เดาเอง
        head = re.match(r"^((?:-?\d+ )+)เส้นจำนวนข้างต้น", txt(q))
        if not head:
            raise NotPlainData("อ่านช่วงของเส้นจำนวนจากรูปไม่ได้")
        ticks = [int(x) for x in head[1].split()]
        keep = (lambda x: x >= pt) if op == "≥" else (lambda x: x > pt) \
            if op == ">" else (lambda x: x <= pt) if op == "≤" else (lambda x: x < pt)
        return want(q, sum(1 for x in range(min(ticks), max(ticks) + 1) if keep(x)),
                    "นับจำนวนเต็มในช่วงที่รูปครอบไว้")
    raise NotPlainData(ask[:40])


def _quad(src):
    """แยก y = ax² + bx + c ออกเป็นสัมประสิทธิ์ (ปฏิเสธถ้าไม่ใช่กำลังสองตัวแปรเดียว)"""
    p = poly_of(src)
    for k in p:
        if k and (len(k) != 1 or k[0][0] != "x" or k[0][1] > 2):
            raise NotPoly("ไม่ใช่พหุนามกำลังสองตัวแปรเดียว")
    a = p.get((("x", 2),), Fraction(0))
    if not a:
        raise NotPoly("ไม่มีพจน์กำลังสอง")
    return a, p.get((("x", 1),), Fraction(0)), p.get((), Fraction(0))


@rule(r"กราฟข้างต้นคือกราฟของ y = (.+?) (จงหา.+|กราฟตัดแกน.+)$")
def _(q, m):
    a, b, c = _quad(m[1])
    vx = -b / (2 * a)
    ask = m[2]
    if "พิกัด x ของจุดยอด" in ask:
        return want(q, vx, "x ของจุดยอด = −b/2a")
    if "ค่าต่ำสุดของ y" in ask or "ค่าสูงสุดของ y" in ask:
        if ("ต่ำ" in ask) != (a > 0):
            raise NotPlainData("ถามค่าต่ำสุด/สูงสุดไม่ตรงกับทิศทางของกราฟ")
        return want(q, a * vx * vx + b * vx + c, "ค่าที่จุดยอด")
    if "ตัดแกน y" in ask:
        return want(q, c, "ค่าคงตัวคือจุดตัดแกน y")
    if "ตัดแกน x" in ask:
        d = b * b - 4 * a * c
        if d < 0:
            raise NotPlainData("ไม่ตัดแกน x")
        r = math.isqrt(int(d)) if d.denominator == 1 else -1
        if r < 0 or r * r != d:
            raise NotPlainData("รากไม่เป็นจำนวนตรรกยะ")
        return want(q, max((-b + r) / (2 * a), (-b - r) / (2 * a)), "รากที่มากกว่า")
    raise NotPlainData(ask[:40])


@rule(r"กราฟข้างต้นคือกราฟของ y = (.+?) \(เส้น &#8467;_1\) กับ y = (.+?) "
      r"\(เส้น &#8467;_2\) จงหา(ค่า x|ค่า y|ผลบวกของ x และ y)")
def _(q, m):
    (a1, b1), (a2, b2) = (poly_of(m[1]), poly_of(m[2]))
    lin = lambda p: (p.get((("x", 1),), Fraction(0)), p.get((), Fraction(0)))
    (m1, c1), (m2, c2) = lin(poly_of(m[1])), lin(poly_of(m[2]))
    if m1 == m2:
        raise NotPlainData("เส้นขนานกัน ไม่มีจุดตัด")
    x = (c2 - c1) / (m1 - m2)
    y = m1 * x + c1
    want(q, x if m[3] == "ค่า x" else y if m[3] == "ค่า y" else x + y, "จุดตัดของสองเส้น")


@rule(r"โดย AB ยาว (\d+) เซนติเมตร AC ยาว (\d+) เซนติเมตร และ DE ยาว (\d+) เซนติเมตร "
      r"(จงหาความยาว DF|อัตราส่วน(?:ความยาวด้าน|พื้นที่)ของ DEF)")
def _(q, m):
    ab, ac, de = map(int, (m[1], m[2], m[3]))
    k = Fraction(de, ab)
    if m[4] == "จงหาความยาว DF":
        return want(q, ac * k, "ด้านที่สมนัยกันมีอัตราส่วนเท่ากัน")
    want(q, k * k if "พื้นที่" in m[4] else k,
         "อัตราส่วนพื้นที่เป็นกำลังสองของอัตราส่วนด้าน")


@rule(r"จากรูป มุม AOB ซึ่งเป็นมุมที่จุดศูนย์กลางมีขนาด (\d+) องศา จงหาขนาดของมุม ACB")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "มุมในส่วนโค้งเป็นครึ่งหนึ่งของมุมที่จุดศูนย์กลาง")


@rule(r"จากรูป มุม AOB มีขนาด (\d+) องศา จงหาขนาดของมุมที่จุดศูนย์กลาง "
      r"ซึ่งรองรับส่วนโค้ง AB อีกด้านหนึ่ง")
def _(q, m):
    want(q, 360 - int(m[1]), "มุมรอบจุดศูนย์กลางรวมกันได้ 360°")


@rule(r"OM ตั้งฉากกับคอร์ด AB ที่จุด M โดย AB ยาว (\d+) เซนติเมตร จงหาความยาว AM")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "เส้นตั้งฉากจากจุดศูนย์กลางแบ่งครึ่งคอร์ด")


@rule(r"โดย AB ยาว (\d+) เซนติเมตร และ OM ยาว (\d+) เซนติเมตร จงหารัศมีของวงกลม")
def _(q, m):
    want(q, isqrt_exact((int(m[1]) // 2) ** 2 + int(m[2]) ** 2), "พีทาโกรัสใน OMA")


@rule(r"จงหาขนาดของมุมระหว่างรัศมี OP กับเส้นสัมผัส")
def _(q, m):
    want(q, 90, "เส้นสัมผัสตั้งฉากกับรัศมีที่จุดสัมผัส")


@rule(r"รัศมี OP ยาว (\d+) เซนติเมตร ถ้าจุด Q อยู่บนเส้นสัมผัสและ PQ ยาว (\d+) เซนติเมตร "
      r"จงหาความยาว OQ")
def _(q, m):
    want(q, isqrt_exact(int(m[1]) ** 2 + int(m[2]) ** 2), "พีทาโกรัสใน OPQ")


@rule(r"รูปสี่เหลี่ยม ABCD แนบในวงกลม โดยมุม A มีขนาด (\d+) องศา จงหาขนาดของมุม C")
def _(q, m):
    want(q, 180 - int(m[1]), "มุมตรงข้ามของสี่เหลี่ยมแนบในวงกลมรวมกันได้ 180°")


@rule(r"พีระมิดฐานสี่เหลี่ยมจัตุรัส ฐานยาวด้านละ (\d+) เซนติเมตร และสูงเอียง (\d+) "
      r"เซนติเมตร จงหาพื้นที่ผิว(ข้าง|ทั้งหมด)")
def _(q, m):
    b, l = int(m[1]), int(m[2])
    side = 4 * Fraction(b * l, 2)                       # สามเหลี่ยมสี่หน้า
    want(q, side + (0 if m[3] == "ข้าง" else b * b), f"พื้นที่ผิว{m[3]}ของพีระมิด")


@rule(r"พีระมิดฐานสี่เหลี่ยมจัตุรัส ฐานยาวด้านละ (\d+) เซนติเมตร และสูง (\d+) เซนติเมตร "
      r"จงหาปริมาตร")
def _(q, m):
    want(q, Fraction(int(m[1]) ** 2 * int(m[2]), 3), "⅓ × พื้นที่ฐาน × สูง")


@rule(r"กรวยกลมตรง รัศมีฐาน (\d+) เซนติเมตร และสูงเอียง (\d+) เซนติเมตร .*?"
      r"จงหาพื้นที่ผิว(ข้าง|ทั้งหมด)")
def _(q, m):
    r, l = int(m[1]), int(m[2])
    want(q, PI * r * l + (0 if m[3] == "ข้าง" else PI * r * r), f"พื้นที่ผิว{m[3]}ของกรวย")


@rule(r"กรวยกลมตรง รัศมีฐาน (\d+) เซนติเมตร และสูง (\d+) เซนติเมตร .*?จงหาปริมาตร")
def _(q, m):
    want(q, PI * int(m[1]) ** 2 * int(m[2]) / 3, "⅓πr²h")


@rule(r"ทรงกลมรัศมี (\d+) เซนติเมตร กำหนดให้ &pi; เท่ากับ 22/7 จงหา(พื้นที่ผิว|ปริมาตร)")
def _(q, m):
    r = int(m[1])
    want(q, 4 * PI * r * r if m[2] == "พื้นที่ผิว" else Fraction(4, 3) * PI * r ** 3,
         f"{m[2]}ทรงกลม")


@rule(r"โดย BC ยาว (\d+) เซนติเมตร AB ยาว (\d+) เซนติเมตร และ AC ยาว (\d+) เซนติเมตร "
      r"จงหาค่าของ (sin|cos|tan) &theta;")
def _(q, m):
    adj, opp, hyp = map(int, (m[1], m[2], m[3]))
    if adj * adj + opp * opp != hyp * hyp:
        raise NotPlainData("ด้านทั้งสามไม่เป็นสามเหลี่ยมมุมฉาก")
    want(q, {"sin": Fraction(opp, hyp), "cos": Fraction(adj, hyp),
             "tan": Fraction(opp, adj)}[m[4]], f"{m[4]} θ จากด้านของสามเหลี่ยม")


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
    buckets, seen = {}, 0
    for course in json.load(open(os.path.join(QDIR, "courses.json"), encoding="utf-8")):
        for path in sorted(glob.glob(os.path.join(QDIR, course["slug"], "unit-*.json"))):
            data = json.load(open(path, encoding="utf-8"))
            for i, q in enumerate(data["questions"], 1):
                q = dict(q, id=f"{course['slug']}/u{data['unit']:02d}#{i}")
                seen += 1
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
    if tot != seen:
        print(f"❌ ยอดในรายงานไม่ตรงกับคลัง ({tot} เทียบกับ {seen}) — "
              "มีข้อที่ถูกนับสองที่ หรือนับตกไป")
        return 1
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
