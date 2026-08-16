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
    # ตัดเฉพาะสิ่งที่เป็นแท็กจริง — "<" ที่ตามด้วยช่องว่างคือเครื่องหมายน้อยกว่าในโจทย์อสมการ
    # เบราว์เซอร์ก็มองแบบเดียวกัน (ตรวจกับ jsdom แล้ว) เดิมตัดด้วย <[^>]+> ทำให้โจทย์อย่าง
    # "3x - 7 < 20 และ 5x + 4 > 9" เหลือ "3x - 7 9" แล้วตกหางยาวทั้งหน่วย
    s = re.sub(r"</?[a-zA-Z][^>]*>", " ", s)
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
    # โจทย์บางชุดเขียนเครื่องหมายเป็นเอนทิตี HTML — แปลงกลับก่อน ไม่งั้น _group() มองไม่เห็น
    e = expr.replace("&times;", "×").replace("&divide;", "÷").replace("&minus;", "-")
    e = _group(e.replace("✕", "×"))
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
# txt() ตัดจุลภาคทิ้งตอนถอดแท็ก "(a, b)" ในโจทย์จึงมาถึงกฎเป็น "(a b)"
@rule(r"ถ้า a และ b เป็นจำนวนเต็มบวกที่ a\^2 - b\^2 = (\d+) "
      r"จะมีคู่อันดับ \(a,? b\) ทั้งหมดกี่คู่")
def _(q, m):
    """ไล่ทุกคู่ (a, b) ตรง ๆ แทนการนับจากคู่ตัวประกอบที่ตัวสร้างใช้"""
    k = int(m[1])
    want(q, sum(1 for a in range(1, k + 2) for b in range(1, a) if a * a - b * b == k),
         f"นับคู่จำนวนเต็มบวกที่ผลต่างกำลังสองเป็น {k}")


@rule(r"^จงหาเศษที่ได้จากการหาร (\d+)\^(\d+) ด้วย (\d+)$")
def _(q, m):
    """ยกกำลังมอดุลาร์ตรง ๆ แทนการอ่านจากวัฏจักรของเศษที่ตัวสร้างใช้"""
    base, exp, mod = (int(m[i]) for i in (1, 2, 3))
    if mod < 2:
        raise NotPlainData("ตัวหารต้องมากกว่า 1")
    want(q, pow(base, exp, mod), f"{base}^{exp} mod {mod}")


# ---------- สมการเชิงเส้นตัวแปรเดียว (แก้ให้ทั่วไป ไม่ผูกกับรูปประโยค) ----------
_FRAC_TERM = re.compile(r"^\((.+)\)/\((\d+)\)$")


def _terms(expr):
    """แยกพจน์ระดับบนสุดพร้อมเครื่องหมาย โดยไม่ตัดกลางวงเล็บ"""
    out, buf, depth, sign = [], "", 0, 1
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch in "+-" and buf.strip():
            out.append((sign, buf.strip()))
            sign, buf = (1 if ch == "+" else -1), ""
        elif depth == 0 and ch in "+-" and not buf.strip():
            sign *= (1 if ch == "+" else -1)      # เครื่องหมายนำหน้าพจน์แรก
        else:
            buf += ch
        i += 1
    if buf.strip():
        out.append((sign, buf.strip()))
    return out


def lin_poly(expr):
    """พหุนามจากนิพจน์ที่อาจมีพจน์เศษส่วนตัวส่วนเป็นค่าคงที่ เช่น (x)/(3) + 5

    poly_of() ปฏิเสธเครื่องหมายหารทุกชนิด ตัวห่อนี้จึงถอดพจน์เศษส่วนออกมาหารเอง
    แล้วค่อยส่งตัวเศษให้ poly_of เป็นคนแจงพหุนาม
    """
    total = {}
    for sign, term in _terms(expr):
        m = _FRAC_TERM.match(term)
        if m:
            part, den = poly_of(m.group(1)), int(m.group(2))
            if den == 0:
                raise NotPoly("ตัวส่วนเป็นศูนย์")
            part = {k: v / den for k, v in part.items()}
        else:
            part = poly_of(term)
        for k, v in part.items():
            total[k] = total.get(k, Fraction(0)) + v * sign
    return {k: v for k, v in total.items() if v}


def solve_linear(lhs, rhs):
    """แก้ ax + b = cx + d — คืนค่า x ที่เป็นคำตอบเดียว"""
    p = lin_poly(lhs)
    for k, v in lin_poly(rhs).items():
        p[k] = p.get(k, Fraction(0)) - v
    for term in p:
        if term and term != (("x", 1),):
            raise NotPoly(f"ไม่ใช่สมการเชิงเส้นใน x — พบพจน์ {term}")
    a, b = p.get((("x", 1),), Fraction(0)), p.get((), Fraction(0))
    if a == 0:
        raise NotPlainData("สัมประสิทธิ์ของ x หักล้างกันหมด ไม่มีคำตอบเดียว")
    return -b / a


@rule(r"จงแก้สมการ (.+?) = (.+?)(?: เพื่อหาค่า x| ค่าของ x เท่ากับเท่าใด)$")
def _(q, m):
    want(q, solve_linear(m[1], m[2]), "ย้ายข้างแล้วหารด้วยสัมประสิทธิ์ของ x")


@rule(r"จากสมการ (.+?) = (.+?) ต้อง(บวก|ลบ|คูณ|หาร)ด้วยจำนวนใดทั้งสองข้าง")
def _(q, m):
    """สมบัติการเท่ากัน — ตัวที่ต้องทำคือตัวที่หักล้างสิ่งที่ติดอยู่กับ x"""
    lhs, op = m[1], m[3]
    p = lin_poly(lhs)
    coef, const = p.get((("x", 1),), Fraction(0)), p.get((), Fraction(0))
    if op in ("บวก", "ลบ"):
        if const == 0:
            raise NotPlainData("ข้างซ้ายไม่มีพจน์คงที่ให้ย้าย")
        want(q, abs(const), f"หักล้างพจน์คงที่ {const}")
    else:
        if coef == 0:
            raise NotPlainData("ข้างซ้ายไม่มีสัมประสิทธิ์ของ x")
        # 4x = 28 ต้องหารด้วย 4 · (x)/(3) = 9 ต้องคูณด้วย 3
        want(q, coef if op == "หาร" else 1 / coef, f"หักล้างสัมประสิทธิ์ {coef}")


# ---------- ห.ร.ม. · ค.ร.น. · ผลบวกของชุดจำนวน ----------
@rule(r"(?:จงหา ?)?(ห\.ร\.ม\.|ค\.ร\.น\.) ของ ((?:\d+ )*\d+(?: และ \d+)?) ?(?:เท่ากับเท่าใด)?$")
def _(q, m):
    nums = [int(x) for x in re.findall(r"\d+", m[2])]
    if len(nums) < 2:
        raise NotPlainData("ต้องมีอย่างน้อยสองจำนวน")
    want(q, math.gcd(*nums) if m[1] == "ห.ร.ม." else math.lcm(*nums),
         f"{m[1]} ของ {nums}")


@rule(r"ผลคูณของจำนวนเต็มบวกสองจำนวนเท่ากับ (\d+) และห\.ร\.ม\. เท่ากับ (\d+) "
      r"จงหาค\.ร\.น\.")
def _(q, m):
    prod, g = int(m[1]), int(m[2])
    if prod % g:
        raise NotPlainData("ผลคูณต้องหารด้วย ห.ร.ม. ลงตัว")
    # ยืนยันว่ามีคู่จำนวนจริงที่ให้ผลคูณและ ห.ร.ม. ตามที่โจทย์บอก
    if not any(a * b == prod and math.gcd(a, b) == g
               for a in range(1, prod + 1) if prod % a == 0 for b in [prod // a]):
        raise NotPlainData("ไม่มีคู่จำนวนที่สอดคล้องกับโจทย์")
    want(q, prod // g, "ห.ร.ม. × ค.ร.น. = ผลคูณของสองจำนวน")


@rule(r"^จงหาผลบวกของจำนวนเต็ม(คี่|คู่)?(?:ทั้งหมด)?ตั้งแต่ (-?\d+) ถึง (-?\d+)$")
def _(q, m):
    lo, hi = int(m[2]), int(m[3])
    if lo > hi:
        raise NotPlainData("ช่วงกลับด้าน")
    keep = {None: lambda n: True, "คี่": lambda n: n % 2,
            "คู่": lambda n: n % 2 == 0}[m[1]]
    want(q, sum(n for n in range(lo, hi + 1) if keep(n)), f"ไล่บวกตั้งแต่ {lo} ถึง {hi}")


@rule(r"^จงหาผลบวกของตัวประกอบทั้งหมดของ (\d+)$")
def _(q, m):
    n = int(m[1])
    want(q, sum(d for d in range(1, n + 1) if n % d == 0), f"ไล่หาตัวประกอบของ {n}")


@rule(r"^จงหาผลบวกของจำนวนเฉพาะทั้งหมดที่น้อยกว่า (\d+)$")
def _(q, m):
    n = int(m[1])
    prime = lambda k: k > 1 and all(k % d for d in range(2, math.isqrt(k) + 1))
    want(q, sum(k for k in range(2, n) if prime(k)), f"ไล่หาจำนวนเฉพาะที่น้อยกว่า {n}")


@rule(r"จำนวนเต็มบวกที่น้อยกว่า (\d+) และหารด้วย (\d+) เหลือเศษ (\d+) มีทั้งหมดกี่จำนวน")
def _(q, m):
    n, k, r = (int(m[i]) for i in (1, 2, 3))
    if r >= k:
        raise NotPlainData("เศษต้องน้อยกว่าตัวหาร")
    want(q, sum(1 for v in range(1, n) if v % k == r), f"ไล่นับจำนวนที่ {k}n + {r}")


# หมายเหตุลำดับ: RULES จับคู่ตามลำดับที่ประกาศ และหยุดที่กฎแรกที่ตรง
# กฎของตระกูลด้านล่างจึงต้องอยู่ก่อนกฎทั่วไปอย่าง "จงหาค่าของ …"
# ไม่งั้นกฎทั่วไปจะคว้าไปก่อนแล้วโยน NotArithmetic ทิ้งลงถังหางยาว
# ---------- ตระกูลโจทย์ระดับแข่งขัน/โอลิมปิก ----------
# เขียนเป็นกฎต่อ "ตระกูล" ไม่ใช่ต่อข้อ — ข้อพวกนี้สร้างจากแม่แบบพารามิเตอร์ใน
# tools/gen_advanced.py กฎเดียวจึงคลุมได้ทั้งชุด และไม่ทิ้งหางยาวเพิ่ม

def _int_roots(p, q):
    """รากจำนวนเต็มของ x^2 - px + q = 0 — ต้องได้สองรากพอดี ไม่งั้นตรวจย้อนไม่ได้"""
    roots = [r for r in range(-400, 401) if r * r - p * r + q == 0]
    if len(roots) != 2:
        raise NotPlainData(f"x^2 - {p}x + {q} ไม่มีรากจำนวนเต็มสองราก")
    return roots


@rule(r"ถ้า &alpha; และ &beta; เป็นรากของสมการ x\^2 - (\d+)x \+ (\d+) = 0 "
      r"จงหาค่าของ (&alpha;\^2 \+ &beta;\^2|&alpha;\^3 \+ &beta;\^3|"
      r"\(&alpha; - &beta;\)\^2|\(1\)/\(&alpha;\) \+ \(1\)/\(&beta;\)|"
      r"&alpha;\^2&beta; \+ &alpha;&beta;\^2)$")
def _(q, m):
    # หาค่าจากรากจริง ไม่ใช้เอกลักษณ์ของผลบวก/ผลคูณราก — คนละทางกับตัวสร้าง
    a, b = _int_roots(int(m[1]), int(m[2]))
    expr = m[3]
    if a == 0 or b == 0:
        if "(1)/(&alpha;)" in expr:
            raise NotPlainData("รากเป็นศูนย์ ส่วนกลับไม่นิยาม")
    want(q, {"&alpha;^2 + &beta;^2": Fraction(a * a + b * b),
             "&alpha;^3 + &beta;^3": Fraction(a ** 3 + b ** 3),
             "(&alpha; - &beta;)^2": Fraction((a - b) ** 2),
             "(1)/(&alpha;) + (1)/(&beta;)": Fraction(1, a) + Fraction(1, b),
             "&alpha;^2&beta; + &alpha;&beta;^2": Fraction(a * a * b + a * b * b)}[expr],
         f"แทนรากจริง {a} กับ {b} ลงในนิพจน์")


DICE = [(a, b) for a in range(1, 7) for b in range(1, 7)]


@rule(r"ทอยลูกเต๋าลูกบาศก์สองลูกพร้อมกัน จงหาความน่าจะเป็นที่"
      r"(ผลรวมของแต้มเท่ากับ (\d+)|ผลรวมของแต้มไม่น้อยกว่า (\d+)|"
      r"ผลต่างของแต้มเท่ากับ (\d+)|ผลคูณของแต้มเป็นจำนวนคู่|"
      r"แต้มทั้งสองลูกเป็นจำนวนคู่)")
def _(q, m):
    """ไล่นับผลลัพธ์ทั้ง 36 แบบตรง ๆ — ไม่ใช้สูตรนับกรณี"""
    if m[2]:
        k, ok = int(m[2]), (lambda a, b: a + b == k)
    elif m[3]:
        k, ok = int(m[3]), (lambda a, b: a + b >= k)
    elif m[4]:
        k, ok = int(m[4]), (lambda a, b: abs(a - b) == k)
    elif "ผลคูณ" in m[1]:
        ok = lambda a, b: (a * b) % 2 == 0
    else:
        ok = lambda a, b: a % 2 == 0 and b % 2 == 0
    want(q, Fraction(sum(1 for a, b in DICE if ok(a, b)), 36), f"นับกรณีที่{m[1]}")


@rule(r"สมการ x\^2 - kx \+ (\d+) = 0 มีรากเป็นจำนวนเต็มบวกทั้งสองราก "
      r"จงหา(ผลบวกของค่า k ที่เป็นไปได้ทั้งหมด|จำนวนค่า k ที่เป็นไปได้|"
      r"ค่า k ที่มากที่สุดที่เป็นไปได้)")
def _(q, m):
    """ไล่ทุกคู่รากจำนวนเต็มบวกที่คูณกันได้ c แทนการไล่ตัวประกอบ"""
    c = int(m[1])
    ks = sorted({r + c // r for r in range(1, c + 1) if c % r == 0})
    if not ks:
        raise NotPlainData(f"ไม่มีคู่รากจำนวนเต็มบวกที่คูณกันได้ {c}")
    want(q, {"ผลบวกของค่า k ที่เป็นไปได้ทั้งหมด": sum(ks),
             "จำนวนค่า k ที่เป็นไปได้": len(ks),
             "ค่า k ที่มากที่สุดที่เป็นไปได้": max(ks)}[m[2]],
         f"ค่า k ที่เป็นไปได้คือ {ks}")


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


# ---------- ตระกูลที่ต้องประกาศก่อนกฎทั่วไปท้ายหมวดนี้ ----------
# กฎ "จงหาผลลัพธ์ของ …" กับ "จงหาค่าของ …" ด้านล่างกินโจทย์ทุกข้อที่ขึ้นต้นแบบนั้น
# ตระกูลที่โจทย์ขึ้นต้นเหมือนกันแต่คิดด้วยเลขคณิตตรง ๆ ไม่ได้ จึงต้องมาก่อน

def mul_pow(base, n):
    """คูณซ้ำ n ครั้ง — ไม่ใช้ ** เพื่อให้เป็นคนละวิธีกับตัวสร้างโจทย์"""
    v = Fraction(1)
    for _ in range(n):
        v *= base
    return v


def digit_sum(n):
    return sum(int(c) for c in str(abs(n)))


def divisors(n):
    return [d for d in range(1, abs(n) + 1) if n % d == 0]


def dec_digit(p, q, pos):
    """เลขโดดตำแหน่งทศนิยมที่ pos ของ p/q — หารยาวทีละหลัก ไม่ใช้สูตรคาบ"""
    r, d = p % q, 0
    for _ in range(pos):
        r *= 10
        d, r = divmod(r, q)
    return d


def round_half_up(f, k):
    s = 10 ** k
    n = f * s
    whole = math.floor(n + Fraction(1, 2)) if n >= 0 else -math.floor(-n + Fraction(1, 2))
    return Fraction(whole, s)


_NUM_TOKEN = re.compile(r"-?\((\d+)\)/\((\d+)\)|-?\d+(?:\.\d+)?")


def read_numbers(s):
    """อ่านชุดจำนวนที่คั่นด้วยช่องว่าง รับทั้ง -2.05 และ -(2)/(3)"""
    out = []
    for m in _NUM_TOKEN.finditer(s):
        tok = m.group(0)
        if "/" in tok:
            v = Fraction(int(m[1]), int(m[2]))
            out.append(-v if tok.startswith("-") else v)
        else:
            out.append(Fraction(tok))
    if len(out) < 2:
        raise NotPlainData(f"อ่านจำนวนจากรายการไม่ได้: {s[:40]}")
    return out


# อนุกรมกล้องส่องทางไกล 1/(1·2) + 1/(2·3) + … — บวกจริงทีละพจน์ ไม่ใช้สูตรย่อ 1 - 1/(n+1)
@rule(r"จงหา(?:ค่า|ผลลัพธ์)ของ \(1\)/\(1 ?(?:&times;|×) ?2\).*\(1\)/\((\d+) ?(?:&times;|×) ?(\d+)\)")
def _(q, m):
    n, nxt = int(m[1]), int(m[2])
    if nxt != n + 1:
        raise NotPlainData("พจน์สุดท้ายไม่ได้อยู่ในรูป 1/(n(n+1))")
    want(q, sum((Fraction(1, k * (k + 1)) for k in range(1, n + 1)), Fraction(0)),
         "บวกทีละพจน์จนครบ")


@rule(r"จงหาจำนวนเลขศูนย์ที่อยู่ท้ายสุดติดกันของ ([\d ×&times;]+)")
def _(q, m):
    prod = 1
    for part in re.split(r"&times;|×", m[1]):
        prod *= int(part.strip())
    zeros = 0
    while prod % 10 == 0:
        prod //= 10
        zeros += 1
    want(q, zeros, "หารด้วย 10 ไปเรื่อย ๆ จนไม่ลงตัว")


# ---------- ผลบวกเลขโดด · เลขโดดหลักหน่วย ----------
@rule(r"จงหาผลบวกของเลขโดด(?:ทุกตัว|ทั้งหมด)ของ ?(?:จำนวน )?(\d+)\^(\d+)(?: - (\d+))?")
def _(q, m):
    v = int(m[1]) ** int(m[2]) - (int(m[3]) if m[3] else 0)
    want(q, digit_sum(v), "กระจายเลขทุกหลักแล้วบวก")


@rule(r"(?:จงหา)?เลขโดดในหลักหน่วยของ (\d+)\^(\d+) ([+×]|&times;) (\d+)\^(\d+)")
def _(q, m):
    a = pow(int(m[1]), int(m[2]), 10)
    b = pow(int(m[4]), int(m[5]), 10)
    want(q, (a + b if m[3] == "+" else a * b) % 10, "ยกกำลังแบบมอดุลัส 10")


# ต้องปิดท้ายด้วย $ ไม่งั้นกฎนี้จะกินโจทย์ที่มีพจน์ที่สองต่อท้าย แล้วตอบจากพจน์แรกตัวเดียว
@rule(r"(?:จงหา)?เลขโดดในหลักหน่วยของ (\d+)\^(\d+)(?: คือจำนวนใด)?$")
def _(q, m):
    want(q, pow(int(m[1]), int(m[2]), 10), "ยกกำลังแบบมอดุลัส 10")


# ---------- ทศนิยมซ้ำ ----------
@rule(r"(?:เขียน|เศษส่วน) \((\d+)\)/\((\d+)\) เป็นทศนิยม.*?ตำแหน่งทศนิยมที่ (\d+)")
@rule(r"(?:เขียน|เศษส่วน) \((\d+)\)/\((\d+)\) เขียนเป็นทศนิยม.*?ตำแหน่งทศนิยมที่ (\d+)")
def _(q, m):
    want(q, dec_digit(int(m[1]), int(m[2]), int(m[3])), "หารยาวทีละหลัก")


@rule(r"\((\d+)\)/\((\d+)\) เขียนเป็นทศนิยม ตัวเลขที่ซ้ำคือเลขใด")
def _(q, m):
    p, r = int(m[1]), int(m[2])
    seen = {dec_digit(p, r, i) for i in range(1, 12)}
    if len(seen) != 1:
        raise NotPlainData("ทศนิยมไม่ได้ซ้ำด้วยเลขโดดตัวเดียว")
    want(q, seen.pop(), "หารยาวแล้วดูว่าหลักไหนวนซ้ำ")


@rule(r"^0\.(\d)\1*\.\.\. เขียนเป็นเศษส่วนอย่างต่ำ ตัวส่วนคือจำนวนใด")
def _(q, m):
    # 0.ddd… = d/9 — ยืนยันด้วยการหารยาวกลับ ไม่ใช่ท่องสูตร
    f = Fraction(int(m[1]), 9)
    if any(dec_digit(f.numerator, f.denominator, i) != int(m[1]) for i in range(1, 8)):
        raise NotPlainData("เศษส่วนที่ได้กางเป็นทศนิยมแล้วไม่ซ้ำตามโจทย์")
    want(q, f.denominator, "หารยาวกลับเพื่อยืนยันเศษส่วน")


# ---------- เศษส่วน ↔ ทศนิยม ↔ จำนวนคละ ----------
@rule(r"^\((\d+)\)/\((\d+)\) เขียนเป็นเศษส่วนอย่างต่ำได้เท่าใด")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "ตัดตัวหารร่วมมาก")


@rule(r"^\((\d+)\)/\((\d+)\) เขียนเป็นทศนิยมได้เท่าใด")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "เศษหารส่วน")


@rule(r"อินเวอร์สการคูณ \(ส่วนกลับ\) ของ \((\d+)\)/\((\d+)\) คือจำนวนใด")
def _(q, m):
    want(q, Fraction(int(m[2]), int(m[1])), "จำนวนที่คูณแล้วได้ 1")


@rule(r"^\((\d+)\)/\((\d+)\) เขียนเป็นจำนวนคละ ส่วนที่เป็นจำนวนเต็มคือจำนวนใด")
def _(q, m):
    want(q, int(m[1]) // int(m[2]), "หารเอาผลหารจำนวนเต็ม")


@rule(r"^(\d+)\((\d+)\)/\((\d+)\) เขียนเป็นเศษเกิน(?: ตัวเศษคือจำนวนใด|ได้เท่าใด)")
def _(q, m):
    w, a, b = int(m[1]), int(m[2]), int(m[3])
    f = w + Fraction(a, b)
    want(q, f.numerator if "ตัวเศษ" in txt(q) else f, "รวมส่วนจำนวนเต็มเข้ากับเศษส่วน")


@rule(r"^เขียน (-?\d+\.\d+) ในรูปเศษส่วนอย่างต่ำ(?: ตัวส่วนเท่ากับเท่าใด|ได้เท่าใด)")
def _(q, m):
    f = Fraction(m[1])
    want(q, f.denominator if "ตัวส่วน" in txt(q) else f, "แปลงทศนิยมเป็นเศษส่วนแล้วตัดทอน")


@rule(r"^ค่าของเลข (\d) ในจำนวน (\d+\.\d+) เท่ากับเท่าใด")
def _(q, m):
    d, whole_dot = m[1], m[2]
    frac_part = whole_dot.split(".")[1]
    if frac_part.count(d) != 1:
        raise NotPlainData("เลขโดดที่ถามปรากฏหลายตำแหน่ง")
    place = frac_part.index(d) + 1
    want(q, Fraction(int(d), 10 ** place), "ค่าประจำหลักของทศนิยม")


@rule(r"เมื่อเรียง (.+?) จากน้อยไปมาก จำนวนแรกคือจำนวนใด")
def _(q, m):
    want(q, min(read_numbers(m[1])), "เทียบค่าทุกจำนวนแล้วเอาตัวน้อยสุด")


@rule(r"^ระหว่าง (.+?) จำนวนใดมีค่ามากกว่า")
def _(q, m):
    want(q, max(read_numbers(m[1].replace("กับ", " "))), "เทียบค่าแล้วเอาตัวมากกว่า")


@rule(r"^มีจำนวนเต็มกี่จำนวนที่อยู่ระหว่าง (-?\d+(?:\.\d+)?) และ (-?\d+(?:\.\d+)?)")
def _(q, m):
    lo, hi = sorted((Fraction(m[1]), Fraction(m[2])))
    want(q, sum(1 for n in range(math.floor(lo), math.ceil(hi) + 1) if lo < n < hi),
         "ไล่นับจำนวนเต็มทีละตัว")


@rule(r"^ปัด (-?\d+\.\d+) ให้เป็นทศนิยม(หนึ่ง|สอง|สาม)ตำแหน่ง ได้เท่าใด")
def _(q, m):
    want(q, round_half_up(Fraction(m[1]), {"หนึ่ง": 1, "สอง": 2, "สาม": 3}[m[2]]),
         "ปัดครึ่งขึ้นด้วยเศษส่วน ไม่ผ่าน float")


# ---------- แบบจำลองการเติบโตแบบทวีคูณ ----------
@rule(r"กระดาษแผ่นหนึ่งพับครึ่ง(?:ซ้อนกัน|ซ้ำกัน) (\d+) ครั้ง")
def _(q, m):
    want(q, mul_pow(2, int(m[1])), "คูณสองซ้ำทีละครั้ง")


@rule(r"เซลล์ชนิดหนึ่งเพิ่มจำนวนเป็น (\d+) เท่าทุกวัน เริ่มต้นมี (\d+) เซลล์ "
      r"เมื่อผ่านไป (\d+) วัน")
@rule(r"แบคทีเรียแบ่งตัวจาก (\d+) เซลล์เป็น (\d+) เท่าทุกชั่วโมง "
      r"เมื่อผ่านไป (\d+) ชั่วโมง")
def _(q, m):
    a, b, n = int(m[1]), int(m[2]), int(m[3])
    if "แบคทีเรีย" in txt(q):
        a, b = b, a                       # ประโยคนี้บอกจำนวนเริ่มต้นมาก่อนตัวคูณ
    want(q, b * mul_pow(a, n), "คูณซ้ำทีละรอบจากจำนวนเริ่มต้น")


@rule(r"สารกัมมันตรังสีสลายตัวเหลือครึ่งหนึ่งทุก (\d+) ปี ถ้าเริ่มต้นมี (\d+) กรัม "
      r"เมื่อผ่านไป (\d+) ปี")
def _(q, m):
    half, start, span = int(m[1]), int(m[2]), int(m[3])
    if span % half:
        raise NotPlainData("ช่วงเวลาไม่ลงตัวกับครึ่งชีวิต")
    want(q, start * mul_pow(Fraction(1, 2), span // half), "หารครึ่งซ้ำทีละครึ่งชีวิต")


@rule(r"ต้นไม้ต้นหนึ่งแตกกิ่ง (\d+) กิ่งในแต่ละชั้น เมื่อนับถึงชั้นที่ (\d+)")
def _(q, m):
    want(q, mul_pow(int(m[1]), int(m[2])), "คูณกิ่งทีละชั้น")


@rule(r"จำนวนประชากรเพิ่มขึ้นเป็น (\d+) เท่าทุก (\d+) ปี ถ้าปัจจุบันมี (\d+) คน "
      r"อีก (\d+) ปีข้างหน้า")
def _(q, m):
    k, per, now, span = (int(m[i]) for i in range(1, 5))
    if span % per:
        raise NotPlainData("ช่วงเวลาไม่ลงตัวกับรอบการเพิ่ม")
    want(q, now * mul_pow(k, span // per), "คูณทีละรอบ")


# ---------- แยกตัวประกอบ ----------
@rule(r"จงแยกตัวประกอบของ x\^4 - (\d+) ให้เป็นผลคูณของพหุนามดีกรีหนึ่งสองตัวกับ "
      r"พหุนามดีกรีสองหนึ่งตัว แล้วตอบว่าพจน์คงที่ของพหุนามดีกรีสองนั้น")
def _(q, m):
    n = int(m[1])
    # x⁴ - k⁴ = (x - k)(x + k)(x² + k²) — ไล่หา k ที่ยกกำลังสี่แล้วได้ n จริง ไม่ใช้รากที่สี่
    ks = [k for k in range(1, 200) if k * k * k * k == n]
    if not ks:
        raise NotPlainData(f"{n} ไม่ใช่กำลังสี่ของจำนวนเต็ม")
    want(q, ks[0] ** 2, "พจน์คงที่ของ x² + k²")


@rule(r"จงแยกตัวประกอบของ x\^2 - (\d+)x \+ (\d+) แล้วตอบว่าผลบวกของตัวประกอบทั้งสอง "
      r"เมื่อ x = (\d+)")
def _(q, m):
    b, c, at = int(m[1]), int(m[2]), int(m[3])
    roots = [(r, c // r) for r in divisors(c) if r + c // r == b]
    if not roots:
        raise NotPlainData("แยกตัวประกอบเป็นจำนวนเต็มไม่ได้")
    r, s = roots[0]
    want(q, (at - r) + (at - s), "แทนค่าลงในตัวประกอบทั้งสองแล้วบวก")


# ---------- ทฤษฎีจำนวนแบบไล่ค่า ----------
@rule(r"ที่น้อยที่สุดที่หารด้วย ((?:\d+ )+)และ (\d+) แล้วเหลือเศษ (\d+) ทุกครั้ง")
def _(q, m):
    mods = [int(x) for x in m[1].split()] + [int(m[2])]
    r = int(m[3])
    # n ต้องมากกว่าตัวหารทุกตัว ไม่งั้น n = r เองก็ "เหลือเศษ r" ทุกครั้งแบบไร้ความหมาย
    for n in range(max(mods) + 1, 100000):
        if all(n % d == r for d in mods):
            want(q, n, "ไล่ค่าจากน้อยไปมากจนเจอตัวแรก")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"(?:จำนวนนับ|จงหาจำนวนเต็มบวก)ที่น้อยที่สุดที่หารด้วย (\d+) (\d+) และ (\d+) "
      r"(?:ได้ลงตัว|ลงตัว)")
def _(q, m):
    ds = [int(m[i]) for i in (1, 2, 3)]
    for n in range(1, 100000):
        if all(n % d == 0 for d in ds):
            want(q, n, "ไล่ค่าจากน้อยไปมากจนหารลงตัวทุกตัว")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"นาฬิกาปลุกสองเรือนดังทุก (\d+) นาที และทุก (\d+) นาที .*?"
      r"จะดังพร้อมกันอีกครั้งเมื่อผ่านไปกี่นาที")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    for n in range(1, 100000):
        if n % a == 0 and n % b == 0:
            want(q, n, "ไล่นาทีจนดังพร้อมกันครั้งถัดไป")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"จำนวนนับที่น้อยที่สุดที่มีตัวประกอบทั้งหมด (\d+) ตัว")
def _(q, m):
    k = int(m[1])
    for n in range(1, 100000):
        if len(divisors(n)) == k:
            want(q, n, "นับตัวประกอบของทุกจำนวนไล่ขึ้นไป")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"จำนวนเต็มบวกที่หาร (\d+) ลงตัวมีทั้งหมดกี่จำนวน")
def _(q, m):
    want(q, len(divisors(int(m[1]))), "ไล่หารทีละจำนวน")


@rule(r"มีจำนวนเต็มบวกสามหลักกี่จำนวนที่หารด้วย (\d+) ลงตัว")
def _(q, m):
    d = int(m[1])
    want(q, sum(1 for n in range(100, 1000) if n % d == 0), "ไล่นับทีละจำนวน")


@rule(r"จำนวนนับตั้งแต่ 1 ถึง (\d+) ที่หารด้วย (\d+) หรือ (\d+) ลงตัว มีทั้งหมดกี่จำนวน")
def _(q, m):
    n, a, b = (int(m[i]) for i in (1, 2, 3))
    want(q, sum(1 for k in range(1, n + 1) if k % a == 0 or k % b == 0),
         "ไล่นับทีละจำนวน ไม่ใช้หลักการรวม-ตัด")


@rule(r"จงหาจำนวนเต็มบวก x ที่น้อยที่สุด ที่ทำให้ (\d+)x เป็นกำลังสองสมบูรณ์")
def _(q, m):
    a = int(m[1])
    for x in range(1, 10000):
        r = math.isqrt(a * x)
        if r * r == a * x:
            want(q, x, "ไล่ค่า x จนผลคูณเป็นกำลังสองพอดี")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"มีคู่อันดับ \(x y\) ที่ x และ y เป็นจำนวนเต็มบวก และ x \+ y = (\d+) "
      r"อยู่ทั้งหมดกี่คู่")
def _(q, m):
    s = int(m[1])
    want(q, sum(1 for x in range(1, s) if s - x >= 1), "ไล่นับ x ทีละค่า")


@rule(r"จำนวนเต็มบวกสองจำนวนที่เรียงติดกันมีผลคูณเป็น (\d+) จำนวนที่น้อยกว่า")
def _(q, m):
    p = int(m[1])
    hits = [n for n in range(1, 10000) if n * (n + 1) == p]
    if not hits:
        raise NotPlainData("ไม่มีจำนวนเรียงติดกันคู่ใดคูณกันได้เท่านี้")
    want(q, hits[0], "ไล่ค่าจนผลคูณตรง")


@rule(r"จงหาจำนวนเฉพาะที่มากที่สุดในการแยกตัวประกอบเฉพาะของ (\d+)")
def _(q, m):
    n, big, d = int(m[1]), 1, 2
    while d * d <= n:
        while n % d == 0:
            n //= d
            big = d
        d += 1
    want(q, max(big, n), "ไล่หารด้วยจำนวนเฉพาะจากน้อยไปมาก")


@rule(r"จงหาจำนวนสามเหลี่ยมทั้งหมดที่เกิดจากการเลือกจุดยอด 3 จุดจากจุด (\d+) จุด")
def _(q, m):
    n = int(m[1])
    want(q, sum(1 for a in range(n) for b in range(a + 1, n) for c in range(b + 1, n)),
         "ไล่นับทุกชุดสามจุด")


# ---------- พีทาโกรัสในโจทย์เล่าเรื่อง ----------
@rule(r"ต้นไม้ต้นหนึ่งหักลง.*?ห่างจากโคนต้น (\d+) เมตร ถ้าตอที่เหลือสูง (\d+) เมตร "
      r"(ส่วนที่หักยาว|เดิมต้นไม้ต้นนี้สูง)")
def _(q, m):
    d, h = int(m[1]), int(m[2])
    slant = math.isqrt(d * d + h * h)
    if slant * slant != d * d + h * h:
        raise NotPlainData("ด้านตรงข้ามมุมฉากไม่เป็นจำนวนเต็ม")
    want(q, slant if m[3] == "ส่วนที่หักยาว" else h + slant,
         "ส่วนที่หักคือด้านตรงข้ามมุมฉาก ความสูงเดิมคือตอบวกส่วนที่หัก")


@rule(r"รูปสามเหลี่ยมหน้าจั่วมีฐานยาว (\d+) เซนติเมตร และด้านประกอบยาวด้านละ (\d+) "
      r"เซนติเมตร จงหา(ความสูง|พื้นที่)")
def _(q, m):
    b, s = int(m[1]), int(m[2])
    if b % 2:
        raise NotPlainData("ฐานเป็นเลขคี่ ครึ่งฐานไม่เป็นจำนวนเต็ม")
    h2 = s * s - (b // 2) ** 2
    h = math.isqrt(h2)
    if h * h != h2:
        raise NotPlainData("ความสูงไม่เป็นจำนวนเต็ม")
    want(q, h if m[3] == "ความสูง" else Fraction(b * h, 2), "แบ่งครึ่งหน้าจั่วเป็นมุมฉาก")


# ---------- การแปลงทางเรขาคณิตของจุด ----------
@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) เลื่อนขนานแล้วได้ภาพ [A-Z]'\((-?\d+) (-?\d+)\) "
      r"จงหาระยะที่เลื่อนไปในแนวแกน (X|Y)")
def _(q, m):
    x, y, x2, y2 = (int(m[i]) for i in range(1, 5))
    want(q, x2 - x if m[5] == "X" else y2 - y, "พิกัดปลายลบพิกัดต้น")


@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) สะท้อนข้ามเส้นตรง (x|y) = (-?\d+) "
      r"จงหาพิกัด (?:x|y) ของภาพที่ได้")
def _(q, m):
    x, y, axis, k = int(m[1]), int(m[2]), m[3], int(m[4])
    want(q, 2 * k - (x if axis == "x" else y), "ภาพอยู่ห่างเส้นสะท้อนเท่ากันคนละฝั่ง")


# ---------- อันตรภาคชั้น ----------
@rule(r"อันตรภาคชั้น (\d+)-(\d+) มีขอบล่างและขอบบนที่แท้จริงเท่าใด "
      r"จงตอบขอบล่างที่แท้จริง")
def _(q, m):
    lo = int(m[1])
    # ข้อมูลเป็นจำนวนเต็ม ชั้นก่อนหน้าจึงจบที่ lo - 1 ขอบที่แท้จริงคือจุดกึ่งกลางของช่องว่างนั้น
    want(q, Fraction(lo + (lo - 1), 2), "จุดกึ่งกลางระหว่างชั้นที่ติดกัน")


@rule(r"อันตรภาคชั้น (\d+)-(\d+) มีจุดกึ่งกลางชั้นเท่าใด")
def _(q, m):
    want(q, Fraction(int(m[1]) + int(m[2]), 2), "เฉลี่ยขอบล่างกับขอบบน")


# ---------- อัตราส่วน สัดส่วน มาตราส่วน ----------
@rule(r"ถ้า ([a-z]) : ([a-z]) = (\d+) : (\d+) และ \2 : ([a-z]) = (\d+) : (\d+) "
      r"เมื่อ \5 = (\d+) แล้ว \1 มีค่าเท่าใด")
def _(q, m):
    p, r2, r3, s = (int(m[i]) for i in (3, 4, 6, 7))
    c = int(m[8])
    b = Fraction(c * r3, s)               # จาก b : c = r3 : s
    want(q, b * Fraction(p, r2), "ไล่ค่าจากตัวท้ายย้อนกลับมาทีละคู่")


@rule(r"ถ้า ([a-z]) : ([a-z]) = (\d+) : (\d+) และ \1 = (\d+) แล้ว \2 มีค่าเท่าใด")
def _(q, m):
    want(q, Fraction(int(m[5]) * int(m[4]), int(m[3])), "คูณไขว้ในสัดส่วน")


@rule(r"ถ้า \(([a-z])\)/\((\d+)\) = \((\d+)\)/\((\d+)\) แล้ว \1 มีค่าเท่าใด")
def _(q, m):
    want(q, Fraction(int(m[2]) * int(m[3]), int(m[4])), "คูณไขว้ในสัดส่วน")


# สัดส่วนตรง — เขียนแยกกฎตามสำนวนโจทย์ เพราะลำดับตัวเลขในประโยคไม่เหมือนกัน
@rule(r"ดินสอ (\d+) แท่ง ราคา (\d+) บาท ดินสอ (\d+) แท่ง ราคากี่บาท")
@rule(r"รถยนต์แล่นได้ (\d+) กิโลเมตร ใช้น้ำมัน (\d+) ลิตร ถ้าแล่น (\d+) กิโลเมตร")
@rule(r"คนงาน (\d+) คน ผลิตสินค้าได้ (\d+) ชิ้นต่อวัน ถ้าเพิ่มเป็นคนงาน (\d+) คน")
@rule(r"เครื่องพิมพ์พิมพ์ได้ (\d+) หน้าใน (\d+) นาที ถ้าพิมพ์ (\d+) หน้า")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(b * c, a), "เทียบบัญญัติไตรยางศ์")


@rule(r"น้ำมัน (\d+) ลิตร ราคา (\d+) บาท ถ้ามีเงิน (\d+) บาท จะซื้อน้ำมันได้กี่ลิตร")
def _(q, m):
    lit, price, money = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(money * lit, price), "เทียบจากราคาต่อลิตร")


@rule(r"ข้าวสาร (\d+) กิโลกรัม ราคา (\d+) บาท ราคากิโลกรัมละกี่บาท")
@rule(r"รถแล่นได้ (\d+) กิโลเมตรใน (\d+) ชั่วโมง ความเร็วเฉลี่ยกี่กิโลเมตรต่อชั่วโมง")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    # ประโยคแรกให้ปริมาณมาก่อนราคา ประโยคหลังให้ระยะทางมาก่อนเวลา — ตัวหารคนละตัว
    want(q, Fraction(b, a) if "ข้าวสาร" in txt(q) else Fraction(a, b), "หาค่าต่อหนึ่งหน่วย")


@rule(r"คนงานทาสีได้ (\d+) ตารางเมตรต่อชั่วโมง ถ้าต้องทาสี (\d+) ตารางเมตร "
      r"ใช้เวลากี่ชั่วโมง")
@rule(r"เงิน 1 ดอลลาร์แลกได้ (\d+) บาท ถ้ามีเงิน (\d+) บาท จะแลกได้กี่ดอลลาร์")
def _(q, m):
    want(q, Fraction(int(m[2]), int(m[1])), "หารด้วยอัตราต่อหนึ่งหน่วย")


# สัดส่วนผกผัน — ผลคูณของสองปริมาณคงที่
@rule(r"รถยนต์แล่นด้วยความเร็ว (\d+) กิโลเมตรต่อชั่วโมง ใช้เวลา (\d+) ชั่วโมง "
      r"ถ้าแล่นด้วยความเร็ว (\d+) กิโลเมตรต่อชั่วโมง")
@rule(r"คนงาน (\d+) คน ทำงานหนึ่งเสร็จใน (\d+) วัน ถ้าใช้คนงาน (\d+) คน")
@rule(r"อาหารสำรองเลี้ยงคน (\d+) คน ได้ (\d+) วัน ถ้ามีคน (\d+) คน")
@rule(r"ท่อน้ำ (\d+) ท่อ เติมน้ำเต็มสระใน (\d+) ชั่วโมง ถ้าใช้ท่อน้ำ (\d+) ท่อ")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(a * b, c), "งานรวมคงที่ จึงเป็นสัดส่วนผกผัน")


@rule(r"เครื่องจักร (\d+) เครื่อง ผลิตสินค้าเสร็จใน (\d+) วัน "
      r"ถ้าต้องการให้เสร็จใน (\d+) วัน ต้องใช้เครื่องจักรเพิ่มขึ้นกี่เครื่อง")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(a * b, c) - a, "จำนวนที่ต้องใช้ ลบด้วยจำนวนเดิม")


# มาตราส่วน — คิดเป็นเซนติเมตรทั้งหมดก่อน แล้วค่อยแปลงกลับ ลดโอกาสสลับหน่วย
@rule(r"แผน(?:ที่มี|ที่|ผังบ้าน)?มาตราส่วน 1 : (\d+) ระยะในแผนที่ (\d+) เซนติเมตร "
      r"เท่ากับระยะทางจริงกี่กิโลเมตร")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 100000), "คูณตามมาตราส่วนแล้วแปลง ซม. เป็น กม.")


@rule(r"แผนผังบ้านมาตราส่วน 1 : (\d+) ห้องหนึ่งกว้างจริง (\d+) เมตร "
      r"ในแผนผังกว้างกี่เซนติเมตร")
def _(q, m):
    want(q, Fraction(int(m[2]) * 100, int(m[1])), "แปลงเมตรเป็น ซม. แล้วหารด้วยมาตราส่วน")


@rule(r"แผนที่มาตราส่วน 1 : (\d+) ระยะทางจริง (\d+) กิโลเมตร วัดในแผนที่ได้กี่เซนติเมตร")
def _(q, m):
    want(q, Fraction(int(m[2]) * 100000, int(m[1])), "แปลง กม. เป็น ซม. แล้วหารด้วยมาตราส่วน")


@rule(r"หุ่นจำลองรถยนต์มาตราส่วน 1 : (\d+) รถจริงยาว ([\d.]+) เมตร หุ่นจำลองยาวกี่เซนติเมตร")
def _(q, m):
    want(q, Fraction(m[2]) * 100 / int(m[1]), "แปลงเมตรเป็น ซม. แล้วหารด้วยมาตราส่วน")


@rule(r"แผนที่มาตราส่วน 1 : (\d+) วัดเส้นทางเดินได้ (\d+) เซนติเมตร "
      r"ถ้าเดินด้วยความเร็ว (\d+) กิโลเมตรต่อชั่วโมง จะใช้เวลากี่ชั่วโมง")
def _(q, m):
    km = Fraction(int(m[1]) * int(m[2]), 100000)
    want(q, km / int(m[3]), "ได้ระยะจริงก่อน แล้วหารด้วยความเร็ว")


# ---------- ความสัมพันธ์เชิงเส้น y = mx + c ----------
@rule(r"กำหนดความสัมพันธ์เชิงเส้น y = (-?\d+)x ([+-]) (\d+) จงหาค่า y เมื่อ x = (-?\d+)")
@rule(r"จากสมการ y = (-?\d+)x ([+-]) (\d+) เมื่อ x = (-?\d+) ค่าของ y เท่ากับเท่าใด")
def _(q, m):
    a, c, x = int(m[1]), int(m[3]) * (1 if m[2] == "+" else -1), int(m[4])
    want(q, a * x + c, "แทนค่า x ลงในสมการ")


@rule(r"จากสมการ y = (-?\d+)x ([+-]) (\d+) เมื่อ y = (-?\d+) ค่าของ x เท่ากับเท่าใด")
def _(q, m):
    a, c, y = int(m[1]), int(m[3]) * (1 if m[2] == "+" else -1), int(m[4])
    want(q, Fraction(y - c, a), "ย้ายข้างแล้วหารด้วยสัมประสิทธิ์")


@rule(r"กราฟของ y = (\d+)x ผ่านจุด \((\d+) ⬜\)")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "แทนค่า x ลงในสมการ")


@rule(r"กราฟของ y = x ([+-]) (\d+) ตัดแกน Y ที่ค่า y เท่ากับเท่าใด")
def _(q, m):
    want(q, int(m[2]) * (1 if m[1] == "+" else -1), "แทน x = 0")


@rule(r"กราฟของ y = (-?\d+)x ([+-]) (\d+) ตัดแกน X ที่ค่า x เท่ากับเท่าใด")
def _(q, m):
    a, c = int(m[1]), int(m[3]) * (1 if m[2] == "+" else -1)
    want(q, Fraction(-c, a), "แทน y = 0 แล้วแก้สมการ")


@rule(r"กราฟเส้นตรงผ่านจุด \((-?\d+) (-?\d+)\) และ \((-?\d+) (-?\d+)\) จงหาความชันของกราฟ")
def _(q, m):
    x1, y1, x2, y2 = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(y2 - y1, x2 - x1), "ผลต่างของ y หารด้วยผลต่างของ x")


@rule(r"กราฟเส้นตรง y = (-?\d+)x \+ k ผ่านจุด \((-?\d+) (-?\d+)\) จงหาค่าของ k")
def _(q, m):
    a, x, y = (int(m[i]) for i in (1, 2, 3))
    want(q, y - a * x, "แทนพิกัดของจุดลงในสมการ")


@rule(r"จุด \(a (-?\d+)\) อยู่บนกราฟของ y = (-?\d+)x ([+-]) (\d+) จงหาค่าของ a")
def _(q, m):
    y, a = int(m[1]), int(m[2])
    c = int(m[4]) * (1 if m[3] == "+" else -1)
    want(q, Fraction(y - c, a), "แทน y แล้วแก้หา x")


@rule(r"เส้นตรงผ่านจุด \((-?\d+) (-?\d+)\) และมีอัตราการเปลี่ยนแปลงเท่ากับ (-?\d+) "
      r"เขียนสมการได้เป็น y = -?\d+x \+ ⬜")
def _(q, m):
    x, y, a = (int(m[i]) for i in (1, 2, 3))
    want(q, y - a * x, "จุดตัดแกน Y คือ y - mx")


@rule(r"จากตารางความสัมพันธ์ อัตราการเปลี่ยนแปลงของ y ต่อ x เท่ากับเท่าใด "
      r"x ([\d ]+) y ([\d ]+)$")
def _(q, m):
    slope, _c = table_xy(m[1], m[2])
    want(q, slope, "ตรวจว่าตารางเป็นเชิงเส้นจริงแล้วอ่านความชัน")


# ---------- แบบจำลองค่าใช้จ่ายเชิงเส้น (ค่าเริ่มต้น + อัตราต่อหน่วย) ----------
@rule(r"ค่าโดยสารแท็กซี่เริ่มต้น (\d+) บาท (?:แล้ว)?คิดเพิ่มกิโลเมตรละ (\d+) บาท "
      r"ถ้าเดินทาง (\d+) กิโลเมตร")
@rule(r"ค่าน้ำประปาคิดค่าบริการเดือนละ (\d+) บาท บวกหน่วยละ (\d+) บาท ถ้าใช้ (\d+) หน่วย")
@rule(r"ร้านเช่าจักรยานคิดค่าเช่าเริ่มต้น (\d+) บาท และคิดเพิ่มชั่วโมงละ (\d+) บาท "
      r"ถ้าเช่าทั้งหมด (\d+) ชั่วโมง")
@rule(r"เริ่มออมเงิน (\d+) บาท แล้วออมเพิ่มสัปดาห์ละ (\d+) บาท เมื่อผ่านไป (\d+) สัปดาห์")
def _(q, m):
    base, rate, n = (int(m[i]) for i in (1, 2, 3))
    want(q, base + rate * n, "ค่าเริ่มต้นบวกอัตราคูณจำนวนหน่วย")


@rule(r"ค่าโดยสารแท็กซี่เริ่มต้น (\d+) บาท คิดเพิ่มกิโลเมตรละ (\d+) บาท "
      r"ถ้าจ่ายค่าโดยสาร (\d+) บาท เดินทางได้กี่กิโลเมตร")
@rule(r"ค่าน้ำประปาคิดค่าบริการพื้นฐาน (\d+) บาท บวกกับหน่วยละ (\d+) บาท "
      r"ถ้าเดือนหนึ่งจ่ายค่าน้ำทั้งหมด (\d+) บาท")
@rule(r"เริ่มออมเงิน (\d+) บาท ออมเพิ่มสัปดาห์ละ (\d+) บาท จะมีเงินครบ (\d+) บาท")
def _(q, m):
    base, rate, total = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(total - base, rate), "หักค่าเริ่มต้นออกก่อน แล้วหารด้วยอัตรา")


@rule(r"ค่าโดยสารแท็กซี่เริ่มต้น (\d+) บาท คิดเพิ่มกิโลเมตรละ (\d+) บาท "
      r"เขียนความสัมพันธ์ได้เป็น y = \d+x \+ ⬜")
def _(q, m):
    want(q, int(m[1]), "ค่าเริ่มต้นคือจุดตัดแกน Y")


@rule(r"เช่าจักรยานชั่วโมงแรก (\d+) บาท ชั่วโมงต่อไปชั่วโมงละ (\d+) บาท "
      r"ถ้าเช่า (\d+) ชั่วโมง")
def _(q, m):
    first, rate, n = (int(m[i]) for i in (1, 2, 3))
    want(q, first + rate * (n - 1), "ชั่วโมงแรกคิดต่างหาก ที่เหลือคิดตามอัตรา")


@rule(r"ถังน้ำมีน้ำ (\d+) ลิตร เปิดให้น้ำไหลออกนาทีละ (\d+) ลิตร น้ำจะหมดถังเมื่อผ่านไปกี่นาที")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "ปริมาตรหารด้วยอัตราการไหล")


# ---------- ความน่าจะเป็น: ไล่แจงผลลัพธ์ทุกแบบ ไม่ใช้สูตรนับ ----------
def prob(hits, total):
    return Fraction(hits, total)


@rule(r"ทอ[ดย]ลูกเต๋า(?:ลูกบาศก์)? ?(?:2 ลูก|สองลูก)พร้อมกัน จงหาความน่าจะเป็นที่"
      r"(ผลคูณของแต้มเป็นจำนวนคู่|ผลรวมของแต้มเป็นจำนวนเฉพาะ|ได้แต้มไม่เท่ากัน)")
def _(q, m):
    primes = {2, 3, 5, 7, 11}
    tests = {
        "ผลคูณของแต้มเป็นจำนวนคู่": lambda a, b: (a * b) % 2 == 0,
        "ผลรวมของแต้มเป็นจำนวนเฉพาะ": lambda a, b: a + b in primes,
        "ได้แต้มไม่เท่ากัน": lambda a, b: a != b,
    }[m[1]]
    pairs = [(a, b) for a in range(1, 7) for b in range(1, 7)]
    want(q, prob(sum(1 for a, b in pairs if tests(a, b)), len(pairs)),
         "ไล่แจงหน้าลูกเต๋าทั้ง 36 แบบ")


@rule(r"ทอ[ดย]ลูกเต๋า(?:ลูกบาศก์)? ?(?:3 ลูก|สามลูก)พร้อมกัน "
      r"จงหาความน่าจะเป็นที่ได้แต้มเหมือนกันทั้งสามลูก")
def _(q, m):
    out = [(a, b, c) for a in range(1, 7) for b in range(1, 7) for c in range(1, 7)]
    want(q, prob(sum(1 for a, b, c in out if a == b == c), len(out)),
         "ไล่แจงหน้าลูกเต๋าทั้ง 216 แบบ")


@rule(r"โยนเหรียญที่เที่ยงตรง (\d+) เหรียญพร้อมกัน "
      r"จงหาความน่าจะเป็นที่จะออกหัวอย่างน้อย (\d+) เหรียญ")
def _(q, m):
    n, k = int(m[1]), int(m[2])
    total = 2 ** n
    hits = sum(1 for s in range(total) if bin(s).count("1") >= k)
    want(q, prob(hits, total), "ไล่แจงผลการโยนทุกแบบ")


@rule(r"ในกล่องมีลูกแก้วสีแดง (\d+) ลูก และสีขาว (\d+) ลูก สุ่มหยิบพร้อมกัน 2 ลูก "
      r"จงหาความน่าจะเป็นที่จะได้สีเดียวกันทั้งสองลูก")
def _(q, m):
    r, w = int(m[1]), int(m[2])
    balls = ["แดง"] * r + ["ขาว"] * w
    pairs = [(i, j) for i in range(len(balls)) for j in range(i + 1, len(balls))]
    want(q, prob(sum(1 for i, j in pairs if balls[i] == balls[j]), len(pairs)),
         "ไล่แจงคู่ลูกแก้วทุกคู่")


@rule(r"สุ่มหยิบสลาก 1 ใบจากสลากหมายเลข 1 ถึง (\d+) "
      r"จงหาความน่าจะเป็นที่จะได้หมายเลขที่หารด้วย (\d+) ลงตัว หรือหารด้วย (\d+) ลงตัว")
def _(q, m):
    n, a, b = (int(m[i]) for i in (1, 2, 3))
    want(q, prob(sum(1 for k in range(1, n + 1) if k % a == 0 or k % b == 0), n),
         "ไล่นับสลากทีละใบ")


# ---------- ผลรวม/ผลคูณของสองจำนวน แล้วถามนิพจน์สมมาตร ----------
def int_pair(s, p):
    """หาจำนวนเต็มคู่ที่บวกกันได้ s และคูณกันได้ p — ไล่ค่า ไม่ใช้สูตรราก"""
    for u in range(-500, 501):
        if u * (s - u) == p:
            return u, s - u
    raise NotPlainData(f"ไม่มีจำนวนเต็มคู่ใดที่ผลบวก {s} ผลคูณ {p}")


@rule(r"ถ้า ([a-z]) \+ ([a-z]) = (-?\d+) และ \1\2 = (-?\d+) จงหาค่าของ (.+?)\s*$")
def _(q, m):
    v1, v2, tail = m[1], m[2], m[5]
    u, v = int_pair(int(m[3]), int(m[4]))
    forms = {
        f"{v1}^2 + {v2}^2": u * u + v * v,
        f"({v1} - {v2})^2": (u - v) ** 2,
    }
    if tail not in forms:
        raise NotPlainData(f"ยังไม่รองรับนิพจน์ {tail}")
    want(q, forms[tail], "หาจำนวนคู่นั้นจริง ๆ แล้วแทนค่า")


@rule(r"ถ้า ([a-z]) \+ ([a-z]) = (-?\d+) และ \1 - \2 = (-?\d+) จงหาค่าของ "
      r"\1\^2 - \2\^2")
def _(q, m):
    s, d = int(m[3]), int(m[4])
    if (s + d) % 2:
        raise NotPlainData("ระบบสมการไม่ให้คำตอบเป็นจำนวนเต็ม")
    x, y = (s + d) // 2, (s - d) // 2
    want(q, x * x - y * y, "แก้ระบบสมการหาค่าจริงของ x และ y ก่อน")


# ---------- พาราโบลา: ค่าต่ำสุด แกนสมมาตร จุดตัดแกน X ----------
def quad(expr):
    p = poly_of(expr)
    for term in p:
        if term and term != (("x", 1),) and term != (("x", 2),):
            raise NotPoly(f"ไม่ใช่พหุนามกำลังสองใน x — พบพจน์ {term}")
    return (p.get((("x", 2),), Fraction(0)), p.get((("x", 1),), Fraction(0)),
            p.get((), Fraction(0)), p)


def quad_min(a, b, c, p):
    """ค่าต่ำสุดของพาราโบลาหงาย — ไล่ค่าบนกริดเศษส่วน ไม่ใช้สูตรจุดยอด

    ตัวสร้างโจทย์ใช้สูตรจุดยอด ตัวตรวจจึงไล่ค่าเอาแทน แล้วยืนยันด้วยเงื่อนไขที่เป็นจริง
    ก็ต่อเมื่อ low คือค่าต่ำสุดจริง: p(x) - low ต้องมีรากซ้ำ นั่นคือดิสคริมิแนนต์เป็นศูนย์
    """
    if a <= 0:
        raise NotPlainData("สัมประสิทธิ์ของ x² ไม่เป็นบวก ไม่มีค่าต่ำสุด")
    low = min(poly_eval(p, Fraction(k, 4)) for k in range(-400, 401))
    if b * b - 4 * a * (c - low) != 0:
        raise NotPlainData("ค่าที่ไล่ได้บนกริดยังไม่ใช่ค่าต่ำสุดจริง")
    return low


# ต้องยึด ^ ไว้ ไม่งั้นกฎนี้จะแย่งโจทย์ที่ขึ้นต้นด้วย "กราฟข้างต้นคือกราฟของ y = …"
# ซึ่งมีกฎอ่านค่าจากรูปดูแลอยู่แล้ว ผลคือตรวจได้น้อยลงกว่าเดิม
@rule(r"^จงหาค่า(?:ต่ำสุด|ที่น้อยที่สุด)ของ (?:y = )?(.+?)(?: เมื่อ x เป็นจำนวนจริง)?\s*$")
def _(q, m):
    want(q, quad_min(*quad(m[1])), "ไล่ค่าบนกริดหาค่าต่ำสุด แล้วเทียบกับสูตรจุดยอด")


@rule(r"^จงหาสมการแกนสมมาตรของกราฟ y = (.+?) ในรูป x = k จงหาค่าของ k")
def _(q, m):
    a, b, _c, p = quad(m[1])
    if a == 0:
        raise NotPlainData("ไม่ใช่พาราโบลา")
    xv = -b / (2 * a)
    # แกนสมมาตรต้องทำให้ค่าที่ระยะเท่ากันสองข้างเท่ากันจริง
    if poly_eval(p, xv - 3) != poly_eval(p, xv + 3):
        raise NotPlainData("เส้นที่คิดได้ไม่สมมาตร")
    want(q, xv, "ตรวจความสมมาตรสองข้างของเส้นที่คิดได้")


@rule(r"^กราฟของ y = (.+?) ตัดแกน X กี่จุด")
def _(q, m):
    a, b, c, _p = quad(m[1])
    if a == 0:
        raise NotPlainData("ไม่ใช่พาราโบลา")
    disc = b * b - 4 * a * c
    want(q, 2 if disc > 0 else (1 if disc == 0 else 0), "ดูเครื่องหมายของดิสคริมิแนนต์")


@rule(r"^กราฟของ y = (.+?) ตัดแกน X ที่จุด A และ B จงหาความยาว AB")
def _(q, m):
    _a, _b, _c, p = quad(m[1])
    roots = [x for x in range(-200, 201) if poly_eval(p, x) == 0]
    if len(roots) != 2:
        raise NotPlainData("ไม่ได้ตัดแกน X ที่จำนวนเต็มสองจุด")
    want(q, roots[1] - roots[0], "ไล่หาจุดตัดที่เป็นจำนวนเต็มแล้วลบกัน")


@rule(r"(?:กราฟของ y = x\^2 ([+-]) (\d+)x \+ k สัมผัสแกน X พอดี|"
      r"สมการ x\^2 ([+-]) (\d+)x \+ k = 0 มีรากซ้ำกัน) จงหาค่าของ k")
def _(q, m):
    b = int(m[2] or m[4]) * (1 if (m[1] or m[3]) == "+" else -1)
    # รากซ้ำ = มีจุดตัดจุดเดียว — ไล่หา k ที่ทำให้เป็นจริง แทนการใช้สูตร b²/4
    ks = [Fraction(k, 4) for k in range(-4000, 4001)
          if b * b - 4 * Fraction(k, 4) == 0]
    if not ks:
        raise NotPlainData("ไม่พบ k ที่ทำให้รากซ้ำ")
    want(q, ks[0], "ไล่ค่า k จนดิสคริมิแนนต์เป็นศูนย์")


@rule(r"จงหาค่า k ที่มากที่สุดซึ่งทำให้สมการ x\^2 \+ kx \+ (\d+) = 0 "
      r"ไม่มีคำตอบที่เป็นจำนวนจริง")
def _(q, m):
    c = int(m[1])
    ks = [k for k in range(-1000, 1001) if k * k - 4 * c < 0]
    if not ks:
        raise NotPlainData("ไม่มี k จำนวนเต็มที่ทำให้ไม่มีรากจริง")
    want(q, max(ks), "ไล่ค่า k ทุกจำนวนเต็มแล้วเอาตัวมากสุดที่ยังไม่มีรากจริง")


# ---------- รากของสมการพหุนาม ----------
@rule(r"จงหาผล(บวก|คูณ)ของรากทั้งหมดของสมการ (.+?) = 0")
def _(q, m):
    p = poly_of(m[2])
    top = max(deg(t) for t in p)
    roots = [x for x in range(-200, 201) if poly_eval(p, x) == 0]
    if len(roots) != top:
        raise NotPlainData("รากที่เป็นจำนวนเต็มไม่ครบตามดีกรี")
    total = sum(roots) if m[1] == "บวก" else math.prod(roots)
    want(q, total, "ไล่หารากที่เป็นจำนวนเต็มให้ครบดีกรีก่อน")


@rule(r"จงหาผลบวกของรากที่ต่างกันทั้งหมดของสมการ (.+?) = 0")
def _(q, m):
    p = poly_of(m[1])
    roots = {x for x in range(-200, 201) if poly_eval(p, x) == 0}
    if not roots:
        raise NotPlainData("ไม่พบรากที่เป็นจำนวนเต็ม")
    want(q, sum(roots), "ไล่หารากที่เป็นจำนวนเต็มแล้วนับเฉพาะค่าที่ต่างกัน")


# ---------- ระบบสมการในโจทย์เล่าเรื่อง: ไล่แจงคำตอบ ----------
@rule(r"ในฟาร์มมีไก่และวัวรวมกัน (\d+) ตัว นับขาได้ทั้งหมด (\d+) ขา จงหาจำนวนวัว")
def _(q, m):
    n, legs = int(m[1]), int(m[2])
    hits = [c for c in range(n + 1) if 4 * c + 2 * (n - c) == legs]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่จำนวนวัวทีละตัวจนขาครบ")


@rule(r"ตั๋วผู้ใหญ่ราคาใบละ (\d+) บาท ตั๋วเด็กราคาใบละ (\d+) บาท ขายตั๋วได้ (\d+) ใบ "
      r"เป็นเงิน (\d+) บาท จงหาจำนวนตั๋วเด็ก")
def _(q, m):
    pa, pc, n, total = (int(m[i]) for i in range(1, 5))
    hits = [k for k in range(n + 1) if pc * k + pa * (n - k) == total]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่จำนวนตั๋วเด็กทีละใบจนยอดเงินตรง")


@rule(r"มีเหรียญ (\d+) บาท และ (\d+) บาท รวมกัน (\d+) เหรียญ คิดเป็นเงิน (\d+) บาท "
      r"จงหาจำนวนเหรียญ (\d+) บาท")
def _(q, m):
    v1, v2, n, total, askv = (int(m[i]) for i in range(1, 6))
    hits = [k for k in range(n + 1) if v1 * k + v2 * (n - k) == total]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0] if askv == v1 else n - hits[0], "ไล่จำนวนเหรียญทีละเหรียญ")


@rule(r"ตอบถูกได้ข้อละ (\d+) คะแนน ตอบผิดถูกหัก (\d+) คะแนน ถ้าทำครบ (\d+) ข้อ "
      r"แล้วได้ (\d+) คะแนน จงหาจำนวนข้อที่ตอบถูก")
def _(q, m):
    plus, minus, n, score = (int(m[i]) for i in range(1, 5))
    hits = [k for k in range(n + 1) if plus * k - minus * (n - k) == score]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่จำนวนข้อที่ถูกทีละข้อจนคะแนนตรง")


# ---------- ค่าเฉลี่ยเลขคณิตที่เปลี่ยนไปเมื่อกลุ่มข้อมูลเปลี่ยน ----------
@rule(r"นักเรียน (\d+) คนมีความสูงเฉลี่ย (\d+) เซนติเมตร นักเรียนอีก (\d+) คน"
      r"มีความสูงเฉลี่ย (\d+) เซนติเมตร จงหาความสูงเฉลี่ยของนักเรียนทั้ง \d+ คน")
def _(q, m):
    n1, a1, n2, a2 = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(n1 * a1 + n2 * a2, n1 + n2), "รวมผลรวมทั้งสองกลุ่มแล้วหารจำนวนคนรวม")


@rule(r"ข้อมูล (\d+) จำนวนมีค่าเฉลี่ยเลขคณิต (\d+) ถ้าเปลี่ยนข้อมูลตัวหนึ่งจาก (\d+) "
      r"เป็น (\d+) ค่าเฉลี่ยใหม่")
def _(q, m):
    n, mean, old, new = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(n * mean - old + new, n), "แก้ผลรวมแล้วหารใหม่")


@rule(r"นักเรียน (\d+) คน สอบได้คะแนนเฉลี่ย (\d+) คะแนน ถ้าตัดนักเรียนที่ได้ (\d+) "
      r"คะแนน ออกไป 1 คน")
def _(q, m):
    n, mean, drop = (int(m[i]) for i in range(1, 4))
    want(q, Fraction(n * mean - drop, n - 1), "หักคะแนนที่ตัดออกจากผลรวมแล้วหารใหม่")


@rule(r"นักเรียน(?:กลุ่มหนึ่ง)? (\d+) คน สอบได้คะแนนเฉลี่ย (\d+) คะแนน "
      r"ถ้าแยกเป็นชาย (\d+) คน คะแนนเฉลี่ย (\d+) คะแนน จงหาคะแนนเฉลี่ยของนักเรียนหญิง")
def _(q, m):
    n, mean, nb, mb = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(n * mean - nb * mb, n - nb), "หักผลรวมของกลุ่มชายออกแล้วหารจำนวนหญิง")


@rule(r"นักเรียนต้องการคะแนนเฉลี่ย (\d+) คะแนน จาก (\d+) วิชา สอบไปแล้ว \d+ วิชา "
      r"ได้ (.+?) คะแนน วิชาที่ \d+ ต้องได้กี่คะแนน")
def _(q, m):
    goal, n = int(m[1]), int(m[2])
    done = read_numbers(m[3])
    want(q, goal * n - sum(done), "ผลรวมที่ต้องการ ลบผลรวมที่สอบไปแล้ว")


# ---------- รูปเรขาคณิตสามมิติ: ประกอบรูปขึ้นมาจริงแล้วนับ ----------
# ไม่ใช้สูตร n+2 / 3n / 2n เพราะสูตรคือสิ่งที่ตัวสร้างโจทย์ใช้ ถ้าจำสูตรผิดก็ผิดตรงกันทั้งคู่
def prism_parts(n):
    """(จำนวนหน้า ขอบ จุดยอด) ของปริซึม n เหลี่ยม — สร้างเซตของขอบขึ้นมาจริงแล้วนับ"""
    bottom = [("ล่าง", i) for i in range(n)]
    top = [("บน", i) for i in range(n)]
    edges = set()
    for i in range(n):
        edges.add(frozenset((bottom[i], bottom[(i + 1) % n])))
        edges.add(frozenset((top[i], top[(i + 1) % n])))
        edges.add(frozenset((bottom[i], top[i])))
    return 2 + n, len(edges), len(bottom) + len(top)


def pyramid_parts(n):
    """(จำนวนหน้า ขอบ จุดยอด) ของพีระมิดฐาน n เหลี่ยม"""
    base = [("ฐาน", i) for i in range(n)]
    apex = ("ยอด", 0)
    edges = set()
    for i in range(n):
        edges.add(frozenset((base[i], base[(i + 1) % n])))
        edges.add(frozenset((base[i], apex)))
    return 1 + n, len(edges), n + 1


NGON = {"สามเหลี่ยม": 3, "สี่เหลี่ยม": 4, "สี่เหลี่ยมจัตุรัส": 4, "สี่เหลี่ยมผืนผ้า": 4,
        "ห้าเหลี่ยม": 5, "หกเหลี่ยม": 6, "แปดเหลี่ยม": 8}
PART = {"หน้า": 0, "ขอบ": 1, "จุดยอด": 2}


@rule(r"ปริซึม(\S+?)มี(หน้า|ขอบ|จุดยอด)ทั้งหมดกี่(?:หน้า|ขอบ|จุด)")
def _(q, m):
    if m[1] not in NGON:
        raise NotPlainData(f"ยังไม่รู้จักฐานรูป {m[1]}")
    want(q, prism_parts(NGON[m[1]])[PART[m[2]]], f"ประกอบปริซึมแล้วนับ{m[2]}")


@rule(r"พีระมิดฐาน(\S+?)มี(หน้า|ขอบ|จุดยอด)ทั้งหมดกี่(?:หน้า|ขอบ|จุด)")
def _(q, m):
    if m[1] not in NGON:
        raise NotPlainData(f"ยังไม่รู้จักฐานรูป {m[1]}")
    want(q, pyramid_parts(NGON[m[1]])[PART[m[2]]], f"ประกอบพีระมิดแล้วนับ{m[2]}")


@rule(r"ลูกบาศก์มี(หน้า|ขอบ|จุดยอด)ทั้งหมดกี่(?:หน้า|ขอบ|จุด)")
def _(q, m):
    want(q, prism_parts(4)[PART[m[1]]], f"ลูกบาศก์คือปริซึมสี่เหลี่ยม นับ{m[1]}")


@rule(r"รูปคลี่ของลูกบาศก์ประกอบด้วยรูปสี่เหลี่ยมจัตุรัสกี่รูป")
def _(q, m):
    want(q, prism_parts(4)[0], "รูปคลี่มีหน้าครบเท่าจำนวนหน้าของทรง")


@rule(r"รูปคลี่ของปริซึมสามเหลี่ยมประกอบด้วยรูปสี่เหลี่ยมกี่รูป")
def _(q, m):
    # หน้าทั้งหมดของปริซึมสามเหลี่ยม ลบสองหน้าที่เป็นรูปสามเหลี่ยม (ฐานบน-ล่าง)
    want(q, prism_parts(3)[0] - 2, "หักหน้าที่เป็นรูปสามเหลี่ยมออกจากจำนวนหน้าทั้งหมด")


# ---------- แทนค่าตัวแปรลงในนิพจน์ ----------
def poly_eval_vars(p, vals):
    total = Fraction(0)
    for term, coef in p.items():
        v = coef
        for name, e in term:
            if name not in vals:
                raise NotPoly(f"ไม่รู้ค่าของตัวแปร {name}")
            v *= Fraction(vals[name]) ** e
        total += v
    return total


@rule(r"^ถ้า ([a-z]) = (-?\d+) ค่าของนิพจน์ (.+?) เท่ากับเท่าใด")
def _(q, m):
    want(q, poly_eval_vars(poly_of(m[3]), {m[1]: int(m[2])}), "แทนค่าตัวแปรลงในนิพจน์")


@rule(r"^ถ้า ([a-z]) = (-?\d+) และ ([a-z]) = (-?\d+) ค่าของนิพจน์ (.+?) เท่ากับเท่าใด")
def _(q, m):
    want(q, poly_eval_vars(poly_of(m[5]), {m[1]: int(m[2]), m[3]: int(m[4])}),
         "แทนค่าตัวแปรลงในนิพจน์")


@rule(r"^ถ้า ([a-z]) = (-?\d+) ([a-z]) = (-?\d+) และ ([a-z]) = (-?\d+) "
      r"จงหาค่าของ (.+?)\s*$")
def _(q, m):
    vals = {m[1]: int(m[2]), m[3]: int(m[4]), m[5]: int(m[6])}
    want(q, poly_eval_vars(poly_of(m[7]), vals), "แทนค่าตัวแปรลงในนิพจน์")


@rule(r"^สมการ x \+ (\d+) = x \+ (\d+) มีคำตอบกี่คำตอบ")
def _(q, m):
    # ไล่แทนค่าดูจริง ๆ ว่ามี x ไหนที่ทำให้สองข้างเท่ากันบ้าง
    want(q, sum(1 for x in range(-500, 501) if x + int(m[1]) == x + int(m[2])),
         "ไล่แทนค่า x แล้วนับที่สองข้างเท่ากัน")


@rule(r"^สูตรพื้นที่รูปสามเหลี่ยม A = \(1\)/\(2\)bh ถ้า b = (\d+) และ h = (\d+)")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 2), "แทนค่าลงในสูตร")


@rule(r"^สูตรความยาวรอบรูปสี่เหลี่ยมผืนผ้า P = 2\(w \+ l\) ถ้า w = (\d+) และ l = (\d+)")
def _(q, m):
    want(q, 2 * (int(m[1]) + int(m[2])), "แทนค่าลงในสูตร")


@rule(r"^สูตรเปลี่ยนหน่วยอุณหภูมิ C = \(5\)/\(9\)\(F - 32\) ถ้า F = (\d+)")
def _(q, m):
    want(q, Fraction(5, 9) * (int(m[1]) - 32), "แทนค่าลงในสูตร")


# ---------- แบบรูปของลำดับ ----------
def seq_next(terms, n):
    """พจน์ที่ n ของลำดับ — ต้องเป็นเลขคณิตหรือเรขาคณิตล้วน ไม่งั้นปฏิเสธ"""
    if len(terms) < 3:
        raise NotPlainData("พจน์ที่ให้มาน้อยเกินกว่าจะยืนยันแบบรูป")
    diffs = {terms[i + 1] - terms[i] for i in range(len(terms) - 1)}
    if len(diffs) == 1:
        d = diffs.pop()
        return terms[0] + d * (n - 1)
    if all(t != 0 for t in terms):
        ratios = {terms[i + 1] / terms[i] for i in range(len(terms) - 1)}
        if len(ratios) == 1:
            r = ratios.pop()
            return terms[0] * mul_pow(r, n - 1)
    raise NotPlainData("ไม่ใช่ลำดับเลขคณิตหรือเรขาคณิต")


@rule(r"^จากแบบรูป (.+?) \.\.\. พจน์ถัดไปคือจำนวนใด")
def _(q, m):
    terms = read_numbers(m[1])
    want(q, seq_next(terms, len(terms) + 1), "ยืนยันแบบรูปจากทุกพจน์ที่ให้มาก่อน")


@rule(r"^จากแบบรูป (.+?) \.\.\. พจน์ที่ (\d+) มีค่าเท่าใด")
def _(q, m):
    want(q, seq_next(read_numbers(m[1]), int(m[2])),
         "ยืนยันแบบรูปจากทุกพจน์ที่ให้มาก่อน")


# ---------- จำนวนเต็มในสถานการณ์จริง ----------
@rule(r"ตอนเช้าอุณหภูมิ (-?\d+) องศาเซลเซียส ตอนบ่ายเพิ่มขึ้น (\d+) องศาเซลเซียส")
@rule(r"ลิฟต์อยู่ที่ชั้นใต้ดินที่ \d+ \(แทนด้วย (-?\d+)\) ขึ้นไป (\d+) ชั้น")
def _(q, m):
    want(q, int(m[1]) + int(m[2]), "บวกจำนวนเต็มตามทิศทางที่โจทย์บอก")


@rule(r"นักดำน้ำอยู่ที่ระดับ (-?\d+) เมตร ขึ้นมา (\d+) เมตร แล้วดำลงไปอีก (\d+) เมตร")
def _(q, m):
    want(q, int(m[1]) + int(m[2]) - int(m[3]), "ขึ้นเป็นบวก ลงเป็นลบ")


@rule(r"ร้านค้าวันแรกได้กำไร (\d+) บาท วันที่สองขาดทุน (\d+) บาท")
def _(q, m):
    want(q, int(m[1]) - int(m[2]), "กำไรเป็นบวก ขาดทุนเป็นลบ")


@rule(r"อุณหภูมิที่ยอดเขา (-?\d+) องศาเซลเซียส ที่เชิงเขา (-?\d+) องศาเซลเซียส ต่างกัน")
def _(q, m):
    want(q, abs(int(m[2]) - int(m[1])), "ผลต่างคือระยะห่างบนเส้นจำนวน")


@rule(r"บัญชีมีเงิน (\d+) บาท ถอนเงิน (\d+) บาท .*?แล้วฝากเพิ่ม (\d+) บาท")
def _(q, m):
    want(q, int(m[1]) - int(m[2]) + int(m[3]), "ถอนเป็นลบ ฝากเป็นบวก")


@rule(r"อุณหภูมิลดลงเฉลี่ยวันละ ([\d.]+) องศาเซลเซียส เริ่มจาก (-?\d+) องศาเซลเซียส "
      r"เมื่อผ่านไป (\d+) วัน")
def _(q, m):
    want(q, Fraction(m[2]) - Fraction(m[1]) * int(m[3]), "ลดลงวันละเท่ากันคือคูณแล้วลบ")


# ---------- เลขยกกำลังที่เครื่องหมายลบอยู่นอก/ในวงเล็บ ----------
@rule(r"^\((-?\d+)\)\^(\d+) มีค่ามากกว่า (-?\d+)\^(\d+) เท่าใด")
def _(q, m):
    # (-3)^4 ยกกำลังทั้งจำนวนติดลบ ส่วน -3^4 ยกกำลังเฉพาะ 3 แล้วค่อยใส่ลบ
    inside = mul_pow(int(m[1]), int(m[2]))
    outside = -mul_pow(abs(int(m[3])), int(m[4])) if m[3].startswith("-") \
        else mul_pow(int(m[3]), int(m[4]))
    want(q, inside - outside, "แยกให้ชัดว่าเครื่องหมายลบอยู่ในหรือนอกวงเล็บ")


@rule(r"^จงหาค่าของ (-)?(\d+)\^(\d+) \(สังเกตว่าไม่มีวงเล็บ\)")
def _(q, m):
    v = mul_pow(int(m[2]), int(m[3]))
    want(q, -v if m[1] else v, "ไม่มีวงเล็บ เลขชี้กำลังจึงคลุมเฉพาะฐาน")


@rule(r"^จงหาค่าของ \((-?\d+)\)\^(\d+) (?:&times;|×) \(\1\)\^(\d+) "
      r"\(เขียนในรูปเลขยกกำลังฐานเดียวก่อน")
def _(q, m):
    want(q, mul_pow(int(m[1]), int(m[2]) + int(m[3])), "ฐานเดียวกัน เลขชี้กำลังบวกกัน")


# ---------- ทศนิยมและเศษส่วนในสถานการณ์จริง ----------
@rule(r"^จงหาค่าของ (.+?) \(ตอบเป็นทศนิยม\)")
def _(q, m):
    want(q, arith(m[1]), "คิดเลขตามนิพจน์")


@rule(r"^ใช้สมบัติการเปลี่ยนกลุ่มหาค่าของ (.+?)\s*$")
def _(q, m):
    want(q, arith(m[1]), "คิดเลขตามนิพจน์ ผลลัพธ์ไม่ขึ้นกับการจัดกลุ่ม")


@rule(r"^ประมาณค่าของ ([\d.]+) (?:&times;|×) ([\d.]+) "
      r"โดยปัดตัวเลขทั้งสองเป็นจำนวนเต็มก่อนคูณ")
def _(q, m):
    want(q, round_half_up(Fraction(m[1]), 0) * round_half_up(Fraction(m[2]), 0),
         "ปัดทั้งสองตัวก่อนแล้วค่อยคูณ")


@rule(r"^ผ้ายาว ([\d.]+) เมตร ตัดออกไป ([\d.]+) เมตร เหลือผ้ายาวกี่เมตร")
def _(q, m):
    want(q, Fraction(m[1]) - Fraction(m[2]), "ความยาวเดิมลบส่วนที่ตัด")


@rule(r"^แบ่งเชือกยาว ([\d.]+) เมตร ออกเป็น (\d+) ส่วนเท่ากัน")
@rule(r"^แบ่งส่วนของเส้นตรงยาว ([\d.]+) เซนติเมตร ออกเป็น (\d+) ส่วนเท่ากัน")
def _(q, m):
    want(q, Fraction(m[1]) / int(m[2]), "ความยาวทั้งหมดหารจำนวนส่วน")


@rule(r"^ซื้อของราคา ([\d.]+) บาท และ ([\d.]+) บาท จ่ายเงิน ([\d.]+) บาท ได้เงินทอนกี่บาท")
def _(q, m):
    want(q, Fraction(m[3]) - Fraction(m[1]) - Fraction(m[2]), "เงินที่จ่ายลบราคารวม")


@rule(r"^น้ำมัน 1 ลิตร ราคา ([\d.]+) บาท ซื้อ (\d+) ลิตร")
@rule(r"^ค่าไฟฟ้าหน่วยละ ([\d.]+) บาท เดือนนี้ใช้ไป (\d+) หน่วย")
def _(q, m):
    want(q, Fraction(m[1]) * int(m[2]), "ราคาต่อหน่วยคูณจำนวนหน่วย")


@rule(r"^นักเรียนสามคนหนัก (.+?) กิโลกรัม รวมกันหนักกี่กิโลกรัม")
def _(q, m):
    want(q, sum(read_numbers(m[1]), Fraction(0)), "บวกน้ำหนักทุกคน")


@rule(r"^มีเงิน (\d+) บาท ใช้ไป \((\d+)\)/\((\d+)\) ของเงินทั้งหมด เหลือเงินกี่บาท")
def _(q, m):
    want(q, int(m[1]) * (1 - Fraction(int(m[2]), int(m[3]))), "ส่วนที่เหลือคือ 1 ลบส่วนที่ใช้")


@rule(r"^งานหนึ่งทำเสร็จไปแล้ว \((\d+)\)/\((\d+)\) ของงานทั้งหมด เหลืองานอีกเป็นเศษส่วนเท่าใด")
def _(q, m):
    want(q, 1 - Fraction(int(m[1]), int(m[2])), "งานทั้งหมดคือ 1")


@rule(r"^ถังน้ำมีน้ำอยู่ \((\d+)\)/\((\d+)\) ของถัง ใช้ไป \((\d+)\)/\((\d+)\) ของถัง")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])) - Fraction(int(m[3]), int(m[4])),
         "ลบเศษส่วนตรง ๆ")


@rule(r"^ผ้ายาว \((\d+)\)/\((\d+)\) เมตร ตัดเป็นชิ้นละ \((\d+)\)/\((\d+)\) เมตร ได้กี่ชิ้น")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])) / Fraction(int(m[3]), int(m[4])),
         "ความยาวทั้งหมดหารความยาวต่อชิ้น")


@rule(r"^ห้องหนึ่งมีนักเรียน (\d+) คน เป็นนักเรียนหญิง \((\d+)\)/\((\d+)\) ของทั้งห้อง "
      r"มีนักเรียนชายกี่คน")
def _(q, m):
    want(q, int(m[1]) * (1 - Fraction(int(m[2]), int(m[3]))), "ส่วนที่เหลือคือนักเรียนชาย")


@rule(r"^สูตรขนมใช้แป้ง (\d+)\((\d+)\)/\((\d+)\) ถ้วย ถ้าทำ (\d+) เท่าของสูตร")
def _(q, m):
    want(q, (int(m[1]) + Fraction(int(m[2]), int(m[3]))) * int(m[4]),
         "แปลงจำนวนคละเป็นเศษเกินก่อนคูณ")


@rule(r"^มีเศษส่วนที่มีตัวส่วนเป็น (\d+) และตัวเศษเป็นจำนวนเต็ม กี่จำนวน "
      r"ที่มากกว่า \((\d+)\)/\((\d+)\) และน้อยกว่า \((\d+)\)/\((\d+)\)")
def _(q, m):
    den = int(m[1])
    lo, hi = Fraction(int(m[2]), int(m[3])), Fraction(int(m[4]), int(m[5]))
    want(q, sum(1 for k in range(-10 * den, 10 * den + 1) if lo < Fraction(k, den) < hi),
         "ไล่ตัวเศษทีละจำนวนแล้วนับที่อยู่ในช่วง")


# ---------- เรขาคณิตพื้นฐาน ----------
@rule(r"^รูปสามเหลี่ยมมีด้านยาว (\d+) เซนติเมตร และ (\d+) เซนติเมตร "
      r"ถ้าด้านที่สามยาวเป็นจำนวนเต็มเซนติเมตร จะยาวได้มากที่สุดกี่เซนติเมตร")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    # อสมการสามเหลี่ยม: ด้านที่สามต้องน้อยกว่าผลบวก และมากกว่าผลต่าง — ไล่ค่าดู
    ok = [c for c in range(1, 10 * (a + b)) if a + b > c and a + c > b and b + c > a]
    want(q, max(ok), "ไล่ความยาวด้านที่สามจนสร้างสามเหลี่ยมไม่ได้")


@rule(r"^รูปสามเหลี่ยมด้านเท่ามีมุมภายในแต่ละมุมขนาดกี่องศา")
def _(q, m):
    want(q, Fraction(180 * (3 - 2), 3), "มุมภายในรูป n เหลี่ยมด้านเท่า")


@rule(r"^ผลบวกของขนาดของมุมภายในทั้งสี่มุมของรูปสี่เหลี่ยมเท่ากับกี่องศา")
def _(q, m):
    want(q, 180 * (4 - 2), "แบ่งรูปสี่เหลี่ยมเป็นสามเหลี่ยมสองรูป")


@rule(r"^รูปหลายเหลี่ยมนูนที่มี (\d+) ด้าน มีผลบวกของมุมภายในทั้งหมดกี่องศา")
def _(q, m):
    want(q, 180 * (int(m[1]) - 2), "แบ่งเป็นสามเหลี่ยมจากจุดยอดเดียว")


@rule(r"^รูปสี่เหลี่ยมจัตุรัสมีความยาวด้านละ (\d+) เซนติเมตร จงหาความยาวเส้นรอบรูป")
def _(q, m):
    want(q, 4 * int(m[1]), "ด้านเท่ากันสี่ด้าน")


@rule(r"^รูปสี่เหลี่ยมจัตุรัสมีพื้นที่ (\d+) ตารางเซนติเมตร มีความยาวรอบรูปกี่เซนติเมตร")
def _(q, m):
    a = int(m[1])
    s = math.isqrt(a)
    if s * s != a:
        raise NotPlainData("พื้นที่ไม่เป็นกำลังสองสมบูรณ์")
    want(q, 4 * s, "หาด้านจากพื้นที่ก่อนแล้วคูณสี่")


@rule(r"^สร้างรูปหกเหลี่ยมด้านเท่าโดยใช้วงเวียนรัศมี (\d+) เซนติเมตร")
def _(q, m):
    # หกเหลี่ยมด้านเท่าแนบในวงกลมแบ่งได้เป็นสามเหลี่ยมด้านเท่าหกรูป ด้านจึงยาวเท่ารัศมี
    want(q, int(m[1]), "หกเหลี่ยมด้านเท่าแนบในวงกลมมีด้านยาวเท่ารัศมี")


# ---------- สมการเชิงเส้นในโจทย์เล่าเรื่อง (ม.1 หน่วย 6) ----------
@rule(r"^จำนวนจำนวนหนึ่ง เมื่อคูณด้วย (\d+) แล้วบวกด้วย (\d+) จะได้ผลลัพธ์เท่ากับ (\d+)")
def _(q, m):
    a, b, r = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(r - b, a), "ย้อนขั้นตอน: ลบก่อนแล้วหาร")


@rule(r"^สมชายอายุมากกว่าน้องชาย (\d+) ปี.*?สมชายอายุ (\d+) ปี")
def _(q, m):
    want(q, int(m[2]) - int(m[1]), "อายุพี่ลบผลต่าง")


@rule(r"^ปากการาคาด้ามละ (\d+) บาท ซื้อมา x ด้าม จ่ายเงินทั้งหมด (\d+) บาท")
@rule(r"^คนงานคนหนึ่งได้รับค่าจ้างชั่วโมงละ (\d+) บาท ทำงาน x ชั่วโมง "
      r"ได้รับเงินทั้งหมด (\d+) บาท")
def _(q, m):
    want(q, Fraction(int(m[2]), int(m[1])), "ยอดรวมหารราคาต่อหน่วย")


@rule(r"^เชือกเส้นหนึ่งยาว x เมตร ถ้าตัดออก (\d+) เมตร จะเหลือเชือกยาว (\d+) เมตร")
@rule(r"^หนังสือเล่มหนึ่งราคา x บาท ได้รับส่วนลด (\d+) บาท จ่ายเงินจริง (\d+) บาท")
def _(q, m):
    want(q, int(m[1]) + int(m[2]), "บวกส่วนที่หายไปกลับเข้าไป")


@rule(r"^จำนวนเต็มสองจำนวน(?:ที่)?เรียงติดกัน รวมกันได้ (\d+) "
      r"(?:จงหาจำนวนที่น้อยกว่า|จำนวนที่น้อยกว่าคือจำนวนใด)")
def _(q, m):
    s = int(m[1])
    hits = [n for n in range(-500, 501) if n + (n + 1) == s]
    if not hits:
        raise NotPlainData("ไม่มีจำนวนเต็มเรียงติดกันคู่ใดรวมกันได้เท่านี้")
    want(q, hits[0], "ไล่ค่าจนผลรวมตรง")


@rule(r"^ผลบวกของจำนวนเต็มสามจำนวนเรียงติดกันเท่ากับ (\d+) จงหาจำนวนที่มากที่สุด")
def _(q, m):
    s = int(m[1])
    hits = [n for n in range(-500, 501) if n + (n + 1) + (n + 2) == s]
    if not hits:
        raise NotPlainData("ไม่มีจำนวนเต็มเรียงติดกันสามตัวที่รวมกันได้เท่านี้")
    want(q, hits[0] + 2, "ไล่ค่าจนผลรวมตรง แล้วเอาตัวมากสุด")


@rule(r"^พ่ออายุเป็น (\d+) เท่าของลูก อายุรวมกันได้ (\d+) ปี ลูกอายุกี่ปี")
def _(q, m):
    k, total = int(m[1]), int(m[2])
    hits = [c for c in range(1, total + 1) if c + k * c == total]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่อายุลูกทีละปีจนผลรวมตรง")


@rule(r"^แม่อายุมากกว่าลูก (\d+) ปี อีก (\d+) ปีข้างหน้าแม่จะมีอายุเป็น (\d+) เท่าของลูก")
@rule(r"^ปัจจุบันพ่ออายุเป็น (\d+) เท่าของลูก อีก (\d+) ปีข้างหน้าพ่อจะอายุเป็น (\d+) "
      r"เท่าของลูก")
def _(q, m):
    a, years, k = (int(m[i]) for i in (1, 2, 3))
    older = "แม่อายุมากกว่า" in txt(q)
    hits = []
    for c in range(1, 200):
        parent = c + a if older else c * a       # ประโยคแรกให้ผลต่าง ประโยคหลังให้อัตราส่วน
        if parent + years == k * (c + years):
            hits.append(c)
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่อายุลูกทีละปีจนเงื่อนไขในอนาคตเป็นจริง")


@rule(r"^รูปสี่เหลี่ยมผืนผ้ามีความยาวมากกว่าความกว้าง (\d+) เซนติเมตร "
      r"และมีความยาวรอบรูป (\d+) เซนติเมตร ความกว้าง")
def _(q, m):
    d, p = int(m[1]), int(m[2])
    hits = [w for w in range(1, p) if 2 * (w + w + d) == p]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ความกว้างทีละหน่วยจนเส้นรอบรูปตรง")


@rule(r"^รูปสี่เหลี่ยมผืนผ้ามีเส้นรอบรูป (\d+) เซนติเมตร และด้านยาวเป็น (\d+) "
      r"เท่าของด้านกว้าง จงหาพื้นที่")
def _(q, m):
    p, k = int(m[1]), int(m[2])
    hits = [w for w in range(1, p) if 2 * (w + k * w) == p]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0] * k * hits[0], "ไล่ความกว้างจนเส้นรอบรูปตรง แล้วคูณเป็นพื้นที่")


@rule(r"^รถแล่นด้วยความเร็ว (\d+) กิโลเมตรต่อชั่วโมง ต้องใช้เวลากี่ชั่วโมง "
      r"จึงจะแล่นได้ระยะทาง (\d+) กิโลเมตร")
def _(q, m):
    want(q, Fraction(int(m[2]), int(m[1])), "ระยะทางหารความเร็ว")


@rule(r"^มีเงินจำนวนหนึ่ง ใช้ไปครึ่งหนึ่ง แล้วใช้อีก (\d+) บาท เหลือเงิน (\d+) บาท")
def _(q, m):
    spent, left = int(m[1]), int(m[2])
    hits = [n for n in range(1, 100000) if n - Fraction(n, 2) - spent == left]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่เงินตั้งต้นจนเหลือตรงตามโจทย์")


@rule(r"^ครึ่งหนึ่งของจำนวนหนึ่ง บวกกับ \((\d+)\)/\((\d+)\) ของจำนวนเดียวกัน ได้ (\d+)")
def _(q, m):
    f, total = Fraction(int(m[1]), int(m[2])), int(m[3])
    hits = [n for n in range(1, 10000) if Fraction(n, 2) + f * n == total]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ค่าจำนวนนั้นจนผลรวมตรง")


@rule(r"^ซื้อสินค้ามาราคา (\d+) บาท ขายไป (\d+) บาท ขาดทุนร้อยละเท่าใด")
def _(q, m):
    cost, sold = int(m[1]), int(m[2])
    want(q, Fraction((cost - sold) * 100, cost), "ส่วนที่ขาดเทียบกับต้นทุน")


# ---------- ราก: ไล่หาจำนวนเต็มที่ยกกำลังแล้วตรง ไม่ใช้ ** ที่เป็นทศนิยม ----------
def iroot(n, k):
    sign = -1 if n < 0 else 1
    n, c = abs(n), 0
    while c ** k < n:
        c += 1
    if c ** k != n:
        raise NotPlainData(f"{n} ไม่ใช่กำลัง {k} ของจำนวนเต็ม")
    return sign * c


def floor_root(n, k):
    c = 0
    while (c + 1) ** k <= n:
        c += 1
    return c


@rule(r"^จงหาค่าของรากที่สามของ (\d+) บวกกับรากที่สามของ (\d+)")
def _(q, m):
    want(q, iroot(int(m[1]), 3) + iroot(int(m[2]), 3), "ไล่หารากที่สามของแต่ละตัว")


@rule(r"^จำนวนใดมีรากที่สามเท่ากับ (-?\d+)")
def _(q, m):
    want(q, mul_pow(int(m[1]), 3), "ยกกำลังสามกลับ")


@rule(r"^รากที่สามของ (\d+) อยู่ระหว่างจำนวนเต็มใดกับจำนวนเต็มถัดไป "
      r"จงตอบจำนวนเต็มที่น้อยกว่า")
def _(q, m):
    want(q, floor_root(int(m[1]), 3), "ไล่ยกกำลังสามจนเกินค่าที่โจทย์ให้")


@rule(r"^จำนวนเต็มที่ใกล้เคียงกับรากที่สองที่เป็นบวกของ (\d+) มากที่สุดคือจำนวนใด")
def _(q, m):
    n = int(m[1])
    lo = floor_root(n, 2)
    # เทียบระยะห่างด้วยกำลังสอง ไม่ต้องแตะทศนิยม
    want(q, lo if n - lo * lo < (lo + 1) ** 2 - n else lo + 1,
         "เทียบว่า n ใกล้กำลังสองตัวไหนมากกว่า")


@rule(r"^รากที่สองที่เป็นบวกของ (\d+) มีค่าประมาณ ([\d.]+) "
      r"จงหาค่าประมาณของรากที่สองที่เป็นบวกของ (\d+)")
def _(q, m):
    base, approx, target = int(m[1]), Fraction(m[2]), int(m[3])
    ks = [k for k in range(1, 100) if k * k * base == target]
    if not ks:
        raise NotPlainData("ตัวที่ถามไม่ได้เป็นกำลังสองคูณกับตัวที่ให้ค่าประมาณมา")
    want(q, ks[0] * approx, "ดึงกำลังสองสมบูรณ์ออกมาแล้วคูณกับค่าประมาณที่ให้")


@rule(r"^จำนวนใดมีค่ามากกว่าระหว่างรากที่สองที่เป็นบวกของ (\d+) กับ (\d+)")
def _(q, m):
    n, b = int(m[1]), int(m[2])
    # ถ้า b² < n แปลว่ารากเป็นตัวที่มากกว่า ซึ่งตอบเป็นจำนวนเต็มไม่ได้ — โจทย์ผิด ต้องฟ้อง ไม่ใช่ข้าม
    if b * b <= n:
        bad.append((q["id"], "เทียบรากกับจำนวนเต็ม", q["answer"],
                    f"√{n} มากกว่า {b} ตอบเป็นจำนวนเต็มไม่ได้", txt(q)[:95]))
        global checks
        checks += 1
        return
    want(q, b, "เทียบด้วยกำลังสองของทั้งสองฝั่ง")


@rule(r"^นักเรียน (\d+) คน ยืนเข้าแถวเป็นรูปสี่เหลี่ยมจัตุรัสพอดี")
@rule(r"^กระเบื้องรูปสี่เหลี่ยมจัตุรัสปูเต็มพื้นห้องรูปสี่เหลี่ยมจัตุรัสได้พอดี (\d+) แผ่น")
@rule(r"^ถ้า x เป็นจำนวนเต็มบวกและ x² = (\d+) จงหาค่าของ x")
def _(q, m):
    want(q, iroot(int(m[1]), 2), "ไล่หาจำนวนเต็มที่ยกกำลังสองแล้วตรง")


@rule(r"^ถ้า x เป็นจำนวนเต็มและ x³ = (-?\d+) จงหาค่าของ x")
def _(q, m):
    want(q, iroot(int(m[1]), 3), "ไล่หาจำนวนเต็มที่ยกกำลังสามแล้วตรง")


@rule(r"^ถ้า x² = (\d+) จงหาผลบวกของค่าที่เป็นไปได้ทั้งหมดของ x")
def _(q, m):
    n = int(m[1])
    want(q, sum(x for x in range(-1000, 1001) if x * x == n), "ไล่ค่า x ทุกตัวที่สอดคล้อง")


# ---------- ปริมาตร พื้นที่ผิว ในสถานการณ์จริง ----------
@rule(r"^อ่างน้ำทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร "
      r"เปิดน้ำอัตรา (\d+) ลิตรต่อนาที")
def _(q, m):
    w, l, h, rate = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(w * l * h, 1000 * rate), "ปริมาตรเป็น ลบ.ซม. แปลงเป็นลิตรแล้วหารอัตรา")


@rule(r"^ห้องรูปสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เมตร "
      r"ต้องทาสีผนังทั้งสี่ด้าน")
def _(q, m):
    w, l, h = (int(m[i]) for i in (1, 2, 3))
    want(q, 2 * (w + l) * h, "ผนังสี่ด้านคือความยาวรอบฐานคูณความสูง")


@rule(r"^ห้องรูปสี่เหลี่ยมผืนผ้ากว้าง (\d+) เมตร ยาว (\d+) เมตร "
      r"ปูกระเบื้องขนาด (\d+) (?:&times;|×) (\d+) เซนติเมตร")
def _(q, m):
    w, l, a, b = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(w * 100 * l * 100, a * b), "แปลงเป็น ซม. ทั้งหมดแล้วหารพื้นที่กระเบื้อง")


# ---------- เลขยกกำลังและสัญกรณ์วิทยาศาสตร์ ----------
@rule(r"^จงหาค่าของ 10\^(-?\d+) ในรูปทศนิยม")
def _(q, m):
    want(q, mul_pow(Fraction(1, 10), -int(m[1])) if int(m[1]) < 0
         else mul_pow(10, int(m[1])), "คูณสิบหรือหารสิบซ้ำตามเลขชี้กำลัง")


@rule(r"^ในหนึ่งวันมี (\d+) วินาที เขียนในรูปสัญกรณ์วิทยาศาสตร์ได้ [\d.]+ "
      r"(?:&times;|×) 10 ยกกำลังเท่าใด")
def _(q, m):
    want(q, sci_exp(m[1]), "เลื่อนจุดทศนิยมจนเหลือหลักเดียวหน้าจุด")


@rule(r"^ถ้ามวลของอิเล็กตรอนประมาณ (\d+) (?:&times;|×) 10\^(-?\d+) กิโลกรัม "
      r"อิเล็กตรอน (\d+) ตัวมีมวลรวมเท่ากับ \d+ (?:&times;|×) 10 ยกกำลังเท่าใด")
def _(q, m):
    n = int(m[3])
    if 10 ** sci_exp(str(n)) != n:
        raise NotPlainData("จำนวนตัวไม่ใช่กำลังของสิบพอดี")
    want(q, int(m[2]) + sci_exp(str(n)), "เลขชี้กำลังบวกกันเมื่อคูณฐานเดียวกัน")


@rule(r"^ถ้า (\d+)\^x · (\d+)\^(\d+) = (\d+)\^(\d+) จงหาค่าของ x")
def _(q, m):
    a, b, be, c, ce = (int(m[i]) for i in range(1, 6))
    hits = [x for x in range(0, 200)
            if mul_pow(a, x) * mul_pow(b, be) == mul_pow(c, ce)]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ค่า x จนสองข้างเท่ากันจริง")


@rule(r"^จงหาผลลบของ (.+?) ลบด้วย (.+?) ในรูปผลสำเร็จ")
def _(q, m):
    global checks
    checks += 1
    try:
        a, b_, got = poly_of(m[1]), poly_of(m[2]), poly_of(q["answer"])
    except NotPoly:
        checks -= 1
        raise NotPlainData("แยกวิเคราะห์พหุนามไม่ได้")
    # ตัดพจน์ที่สัมประสิทธิ์เป็นศูนย์ทิ้งก่อนเทียบ ไม่งั้นผลลบที่หักล้างกันหมด
    # จะเป็น {y²:0 y:0 c:0} ส่วนเฉลย "0" เป็น {c:0} แล้วฟ้องว่าไม่ตรงทั้งที่เท่ากัน
    def trim(p):
        return {k: v for k, v in p.items() if v != 0}

    if trim(_padd(a, b_, -1)) != trim(got):
        bad.append((q["id"], "ผลลบพหุนาม", q["answer"], "กระจายแล้วไม่ตรง", txt(q)[:95]))


@rule(r"^สวนรูปสี่เหลี่ยมผืนผ้ากว้าง x เมตร ยาวมากกว่าความกว้าง (\d+) เมตร "
      r"ถ้า x เท่ากับ (\d+)")
def _(q, m):
    w = int(m[2])
    want(q, w * (w + int(m[1])), "แทนค่าความกว้างแล้วคูณกับความยาว")


# ---------- มุมและสมมาตร: สร้างรูปแล้วนับ ----------
def rect_axes(w, h):
    """นับแกนสมมาตรของรูปสี่เหลี่ยมมุมฉาก โดยลองสะท้อนจริงแล้วดูว่าจุดยอดกลับมาชุดเดิมไหม"""
    pts = {(w, h), (-w, h), (-w, -h), (w, -h)}
    flips = (lambda p: (-p[0], p[1]), lambda p: (p[0], -p[1]),
             lambda p: (p[1], p[0]), lambda p: (-p[1], -p[0]))
    return sum(1 for f in flips if {f(p) for p in pts} == pts)


@rule(r"^รูปสี่เหลี่ยมจัตุรัสมีแกนสมมาตรกี่แกน")
def _(q, m):
    want(q, rect_axes(1, 1), "สะท้อนจุดยอดจริงแล้วนับแกนที่ได้รูปเดิม")


@rule(r"^รูปสี่เหลี่ยมผืนผ้าที่ไม่ใช่รูปสี่เหลี่ยมจัตุรัสมีแกนสมมาตรกี่แกน")
def _(q, m):
    want(q, rect_axes(2, 1), "สะท้อนจุดยอดจริงแล้วนับแกนที่ได้รูปเดิม")


@rule(r"^รูปสามเหลี่ยมด้านเท่ามีแกนสมมาตรกี่แกน")
def _(q, m):
    # การสะท้อนของรูป n เหลี่ยมด้านเท่าคือ i -> (c - i) mod n · ไล่ c ทุกค่าแล้วนับ
    n = 3
    want(q, sum(1 for c in range(n)
                if sorted((c - i) % n for i in range(n)) == list(range(n))),
         "ไล่การสะท้อนทุกแบบที่สลับจุดยอดแล้วได้รูปเดิม")


@rule(r"^รูป(สี่เหลี่ยมจัตุรัส|สามเหลี่ยมด้านเท่า)หมุนรอบจุดศูนย์กลางแล้วทับรูปเดิมได้พอดี "
      r"ต้องหมุนอย่างน้อยกี่องศา")
def _(q, m):
    n = 4 if m[1] == "สี่เหลี่ยมจัตุรัส" else 3
    want(q, Fraction(360, n), "หมุนทีละหนึ่งจุดยอดจากทั้งหมด n จุด")


@rule(r"^การหมุนรอบจุดกำเนิด (\d+) องศาตามเข็มนาฬิกา "
      r"ให้ผลเหมือนกับการหมุนทวนเข็มนาฬิกากี่องศา")
def _(q, m):
    want(q, (360 - int(m[1])) % 360, "หมุนครบรอบแล้วย้อนทิศ")


@rule(r"^ในเข็มนาฬิกา เมื่อเวลาผ่านไป (\d+) นาที เข็มนาทีหมุนไปกี่องศา")
def _(q, m):
    want(q, Fraction(int(m[1]) * 360, 60), "เข็มนาทีหมุนครบรอบใน 60 นาที")


@rule(r"^รูปสามเหลี่ยมที่มีพื้นที่ (\d+) ตารางหน่วย เมื่อหมุนรอบจุดใดจุดหนึ่ง \d+ องศา "
      r"ภาพที่ได้มีพื้นที่")
def _(q, m):
    # การหมุนเป็นการแปลงที่รักษาระยะ พื้นที่จึงไม่เปลี่ยน
    want(q, int(m[1]), "การหมุนรักษาระยะ พื้นที่จึงเท่าเดิม")


@rule(r"^รูปสามเหลี่ยมด้านเท่าที่ถูกแบ่งครึ่งด้วยเส้นแบ่งครึ่งมุมยอด "
      r"จะได้มุมยอดของรูปย่อยขนาดกี่องศา")
def _(q, m):
    want(q, Fraction(180 * (3 - 2), 3) / 2, "มุมของสามเหลี่ยมด้านเท่าหารสอง")


@rule(r"^รูปสี่เหลี่ยมคางหมูมีมุมหนึ่งบนด้านที่ไม่ขนานขนาด (\d+) องศา "
      r"จงหาขนาดของมุมอีกมุมบนด้านเดียวกัน")
@rule(r"^บันไดเลื่อนทำมุม (\d+) องศากับพื้นชั้นล่าง ถ้าพื้นชั้นบนขนานกับพื้นชั้นล่าง")
def _(q, m):
    a = int(m[1])
    # มุมภายในบนข้างเดียวกันของเส้นตัดรวมได้ 180 · มุมแย้งเท่ากัน
    want(q, 180 - a if "คางหมู" in txt(q) else a,
         "สมบัติของเส้นขนานกับเส้นตัด")


@rule(r"^จงหาคำตอบ(ที่เป็นบวก)?ของสมการ (.+?) เท่ากับ 0\s*$")
def _(q, m):
    p = poly_of(m[2])
    roots = sorted({x for x in range(-500, 501) if poly_eval(p, x) == 0})
    if m[1]:
        roots = [r for r in roots if r > 0]
    if len(roots) != 1:
        raise NotPlainData("ไล่ค่าแล้วไม่ได้รากเดียว")
    want(q, roots[0], "ไล่แทนค่าจำนวนเต็มจนสมการเป็นจริง")


# ---------- โจทย์นับ: ไล่แจงจริง ไม่ใช้สูตรคอมบิเนทอริก ----------
@rule(r"^ตารางสี่เหลี่ยมจัตุรัสขนาด (\d+) (?:&times;|×) (\d+) ช่อง "
      r"มีรูปสี่เหลี่ยม(มุมฉาก|จัตุรัส)ทั้งหมดกี่รูป")
def _(q, m):
    n, k, kind = int(m[1]), int(m[2]), m[3]
    boxes = [(r1, c1, r2, c2)
             for r1 in range(n) for r2 in range(r1, n)
             for c1 in range(k) for c2 in range(c1, k)]
    if kind == "จัตุรัส":
        boxes = [b for b in boxes if b[2] - b[0] == b[3] - b[1]]
    want(q, len(boxes), "ไล่แจงมุมบนซ้าย-ล่างขวาทุกคู่")


@rule(r"^เดินจากมุมซ้ายล่างไปมุมขวาบนของตาราง (\d+) (?:&times;|×) (\d+) ช่อง")
def _(q, m):
    n, k = int(m[1]), int(m[2])
    ways = [[0] * (k + 1) for _ in range(n + 1)]
    ways[0][0] = 1
    for r in range(n + 1):
        for c in range(k + 1):
            if r:
                ways[r][c] += ways[r - 1][c]
            if c:
                ways[r][c] += ways[r][c - 1]
    want(q, ways[n][k], "นับเส้นทางสะสมทีละช่อง")


@rule(r"^ลากเส้นตรง (\d+) เส้นบนระนาบ .*?จะเกิดจุดตัดทั้งหมดกี่จุด")
def _(q, m):
    n = int(m[1])
    want(q, sum(1 for a in range(n) for b in range(a + 1, n)), "ไล่นับทุกคู่ของเส้น")


@rule(r"^ในกล่องมีลูกบอลสีแดง สีเขียว และสีน้ำเงิน อย่างละหลายลูก "
      r"ต้องหยิบอย่างน้อยกี่ลูกจึงจะมั่นใจว่าได้ลูกบอลสีเดียวกันอย่างน้อย (\d+) ลูก")
def _(q, m):
    k, colors = int(m[1]), 3
    # กรณีแย่ที่สุดคือได้ทุกสีสีละ k-1 ลูก อีกลูกเดียวจึงบังคับให้มีสีใดสีหนึ่งครบ k
    want(q, colors * (k - 1) + 1, "คิดจากกรณีแย่ที่สุดแล้วบวกอีกหนึ่ง")


@rule(r"^จำนวนสามหลักจำนวนหนึ่ง มีผลบวกของเลขโดดทั้งสามเท่ากับ (\d+) "
      r"เลขโดดหลักร้อยเป็น (\d+) เท่าของเลขโดดหลักหน่วย และเลขโดดหลักสิบเป็น (\d+)")
def _(q, m):
    s, k, tens = (int(m[i]) for i in (1, 2, 3))
    hits = [n for n in range(100, 1000)
            if digit_sum(n) == s and n // 100 == k * (n % 10) and (n // 10) % 10 == tens]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่จำนวนสามหลักทุกจำนวนแล้วคัดตามเงื่อนไข")


@rule(r"^จำนวนเต็มสองหลักจำนวนหนึ่ง เมื่อสลับตำแหน่งเลขโดดจะได้จำนวนใหม่ที่มากกว่าเดิม "
      r"(\d+) และผลบวกของเลขโดดเท่ากับ (\d+)")
def _(q, m):
    d, s = int(m[1]), int(m[2])
    hits = [n for n in range(10, 100)
            if (n % 10) * 10 + n // 10 - n == d and digit_sum(n) == s]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่จำนวนสองหลักทุกจำนวนแล้วคัดตามเงื่อนไข")


@rule(r"^ในกล่องมีลูกบอลสีแดงกับสีน้ำเงินเป็นอัตราส่วน (\d+) : (\d+) "
      r"ถ้าเพิ่มลูกบอลสีแดง (\d+) ลูก อัตราส่วนจะเป็น (\d+) : (\d+) เดิมมีลูกบอลสีน้ำเงินกี่ลูก")
def _(q, m):
    r1, b1, add, r2, b2 = (int(m[i]) for i in range(1, 6))
    hits = [k for k in range(1, 500) if (r1 * k + add) * b2 == r2 * (b1 * k)]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, b1 * hits[0], "ไล่ตัวคูณของอัตราส่วนจนเงื่อนไขใหม่เป็นจริง")


# ---------- โจทย์ประยุกต์ ----------
@rule(r"^รถออกจากเมือง ก เวลา (\d+):(\d+) นาฬิกา ด้วยความเร็ว (\d+) กิโลเมตรต่อชั่วโมง "
      r"ถึงเมือง ข เวลา (\d+):(\d+)")
def _(q, m):
    h1, m1, v, h2, m2 = (int(m[i]) for i in range(1, 6))
    hours = Fraction((h2 * 60 + m2) - (h1 * 60 + m1), 60)
    want(q, v * hours, "แปลงเวลาเป็นนาทีก่อนแล้วค่อยเป็นชั่วโมง")


@rule(r"^ค่าไฟฟ้าคิด (\d+) หน่วยแรกหน่วยละ (\d+) บาท ส่วนที่เกิน \d+ หน่วย "
      r"หน่วยละ (\d+) บาท ถ้าเดือนนี้ใช้ไฟ (\d+) หน่วย")
def _(q, m):
    cut, r1, r2, used = (int(m[i]) for i in range(1, 5))
    want(q, min(used, cut) * r1 + max(0, used - cut) * r2, "คิดทีละช่วงอัตรา")


@rule(r"^ค่าส่งพัสดุคิดตามน้ำหนัก: (.+?) ถ้าส่งพัสดุ 2 ชิ้น หนัก ([\d.]+) และ ([\d.]+) กิโลกรัม")
def _(q, m):
    tiers = [(Fraction(a), int(b)) for a, b in
             re.findall(r"ไม่เกิน ([\d.]+) กิโลกรัม (\d+) บาท", m[1])]
    if not tiers:
        raise NotPlainData("อ่านตารางอัตราไม่ได้")

    def fee(w):
        for limit, price in tiers:
            if w <= limit:
                return price
        raise NotPlainData("น้ำหนักเกินช่วงที่ตารางครอบคลุม")

    want(q, fee(Fraction(m[2])) + fee(Fraction(m[3])), "เปิดตารางทีละชิ้นแล้วบวกกัน")


@rule(r"^แพ็กเกจ A จ่าย (\d+) บาทต่อเดือน โทรได้ไม่จำกัด แพ็กเกจ B จ่าย (\d+) บาท "
      r"บวกค่าโทรนาทีละ ([\d.]+) บาท ต้องโทรกี่นาที")
def _(q, m):
    a, b, rate = int(m[1]), int(m[2]), Fraction(m[3])
    want(q, (a - b) / rate, "ผลต่างค่าคงที่หารด้วยอัตราต่อนาที")


@rule(r"^โรงเรียนจะซื้อลูกบอล (\d+) ลูก ร้านแรกขายลูกละ (\d+) บาท ลดร้อยละ (\d+) "
      r"ร้านที่สองขายลูกละ (\d+) บาท ไม่ลดราคา")
def _(q, m):
    n, p1, off, p2 = (int(m[i]) for i in range(1, 5))
    a = n * p1 * (1 - Fraction(off, 100))
    b = n * p2
    want(q, abs(a - b), "คิดยอดรวมทั้งสองร้านแล้วหาผลต่าง")


@rule(r"^จากผลสำรวจนักเรียน (\d+) คน \((.+?)\) "
      r"ถ้าจัดแข่งเฉพาะกีฬา 2 ชนิดที่มีคนชอบมากที่สุด")
def _(q, m):
    n = int(m[1])
    pct = sorted((int(x) for x in re.findall(r"ร้อยละ (\d+)", m[2])), reverse=True)
    if len(pct) < 2 or sum(pct) != 100:
        raise NotPlainData("สัดส่วนในวงเล็บรวมกันไม่ครบร้อย")
    want(q, Fraction(n * (pct[0] + pct[1]), 100), "เอาสองอันดับแรกมารวมแล้วคิดเป็นจำนวนคน")


@rule(r"^สินค้าราคา (\d+) บาท ลดราคา (\d+)% แล้วลดอีก (\d+)% จากราคาที่ลดแล้ว")
def _(q, m):
    p, a, b = (int(m[i]) for i in (1, 2, 3))
    want(q, p * (1 - Fraction(a, 100)) * (1 - Fraction(b, 100)), "ลดทีละรอบจากราคาปัจจุบัน")


@rule(r"^ราคาสินค้าขึ้น (\d+)% แล้วลดลง (\d+)% จากราคาใหม่ "
      r"ราคาสุดท้ายคิดเป็นร้อยละเท่าใดของราคาเดิม")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, 100 * (1 + Fraction(a, 100)) * (1 - Fraction(b, 100)), "สมมติราคาเดิมเป็น 100")


@rule(r"^ก ทำงานเสร็จใน (\d+) วัน ข ทำงานเดียวกันเสร็จใน (\d+) วัน ถ้าช่วยกันทำ")
def _(q, m):
    want(q, 1 / (Fraction(1, int(m[1])) + Fraction(1, int(m[2]))),
         "รวมอัตราการทำงานต่อวันแล้วกลับเศษส่วน")


@rule(r"^รถยนต์คันหนึ่งวิ่งไป (\d+) กิโลเมตรด้วยอัตราเร็ว (\d+) กิโลเมตรต่อชั่วโมง "
      r"แล้ววิ่งกลับด้วยอัตราเร็ว (\d+) กิโลเมตรต่อชั่วโมง จงหาอัตราเร็วเฉลี่ย")
def _(q, m):
    d, v1, v2 = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(2 * d) / (Fraction(d, v1) + Fraction(d, v2)),
         "ระยะทางรวมหารเวลารวม ไม่ใช่เฉลี่ยความเร็ว")


@rule(r"^น้ำเชื่อมเข้มข้น (\d+)% ปริมาตร (\d+) มิลลิลิตร ต้องเติมน้ำอีกกี่มิลลิลิตร "
      r"จึงจะได้น้ำเชื่อมเข้มข้น (\d+)%")
def _(q, m):
    c1, v, c2 = (int(m[i]) for i in (1, 2, 3))
    sugar = Fraction(c1 * v, 100)                  # น้ำตาลคงเดิม เปลี่ยนแต่ปริมาตรรวม
    want(q, sugar * 100 / c2 - v, "ปริมาณตัวถูกละลายคงที่")


@rule(r"^ถังใบหนึ่งมีน้ำอยู่ \((\d+)\)/\((\d+)\) ของถัง เมื่อเติมน้ำอีก (\d+) ลิตร "
      r"น้ำจะเต็ม \((\d+)\)/\((\d+)\) ของถัง")
def _(q, m):
    a = Fraction(int(m[1]), int(m[2]))
    add = int(m[3])
    b = Fraction(int(m[4]), int(m[5]))
    want(q, add / (b - a), "น้ำที่เติมคือส่วนต่างของเศษส่วนคูณความจุ")


@rule(r"^จงหาจำนวนเต็มบวก n ที่น้อยที่สุดซึ่งทำให้ \(n\)/\((\d+)\) มากกว่า "
      r"\((\d+)\)/\((\d+)\)")
def _(q, m):
    den, a, b = (int(m[i]) for i in (1, 2, 3))
    for n in range(1, 10000):
        if Fraction(n, den) > Fraction(a, b):
            want(q, n, "ไล่ค่า n จากน้อยไปมากจนเกินเกณฑ์")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"^นาฬิกาบอกเวลา 12 นาฬิกาตรง เข็มสั้นกับเข็มยาวจะทับกันอีกครั้งเมื่อผ่านไปกี่นาที")
def _(q, m):
    # เข็มนาทีเดิน 6 องศา/นาที เข็มชั่วโมงเดิน 0.5 องศา/นาที ต่างกัน 5.5 องศา/นาที
    want(q, Fraction(360) / (Fraction(6) - Fraction(1, 2)), "ผลต่างอัตราเชิงมุมต้องได้ครบรอบ")


# ---------- สถิติจากตารางรายการ ----------
def name_counts(s):
    """อ่านคู่ (ชื่อรายการ จำนวน) จากตารางที่ถูกถอดแท็กมาเป็นข้อความเรียง"""
    pairs = re.findall(r"([^\s\d]+) (\d+)", s)
    if len(pairs) < 2:
        raise NotPlainData("อ่านตารางรายการไม่ได้")
    return [(k, int(v)) for k, v in pairs]


@rule(r"^จากข้อมูล \"[^\"]+\" ต่อไปนี้ รายการ จำนวน (.+?) "
      r"รายการ \"([^\"]+)\" คิดเป็นร้อยละเท่าใดของทั้งหมด")
def _(q, m):
    pairs = name_counts(m[1])
    total = sum(v for _k, v in pairs)
    hit = [v for k, v in pairs if k == m[2]]
    if len(hit) != 1:
        raise NotPlainData(f"หารายการ {m[2]} ในตารางไม่เจอ")
    want(q, Fraction(hit[0] * 100, total), "ค่าของรายการหารผลรวมทั้งหมด")


@rule(r"^จากข้อมูล \"[^\"]+\" ต่อไปนี้ รายการ จำนวน (.+?) มีจำนวนทั้งหมดกี่หน่วย")
def _(q, m):
    want(q, sum(v for _k, v in name_counts(m[1])), "บวกทุกรายการ")


@rule(r"^จากข้อมูล \"[^\"]+\" ต่อไปนี้ รายการ จำนวน (.+?) "
      r"รายการที่มากที่สุดกับน้อยที่สุดต่างกันเท่าใด")
def _(q, m):
    vals = [v for _k, v in name_counts(m[1])]
    want(q, max(vals) - min(vals), "มากสุดลบน้อยสุด")


@rule(r"^จากตารางแจกแจงความถี่ มีนักเรียนทั้งหมดกี่คน คะแนน ([\d ]+) จำนวน \(คน\) ([\d ]+)$")
def _(q, m):
    if len(m[1].split()) != len(m[2].split()):
        raise NotPlainData("จำนวนคะแนนกับจำนวนความถี่ไม่เท่ากัน")
    want(q, sum(int(x) for x in m[2].split()), "บวกความถี่ทุกชั้น")


@rule(r"^แผนภูมิแท่งแสดงยอดขายของสองร้าน ร้าน ก ขายได้ (\d+) ล้านบาท "
      r"ร้าน ข ขายได้ (\d+) ล้านบาท ถ้าเขียนแผนภูมิโดยให้แกนตั้งเริ่มที่ (\d+) ล้านบาท")
def _(q, m):
    a, b, base = (int(m[i]) for i in (1, 2, 3))
    want(q, round_half_up(Fraction(a - base, b - base), 1),
         "ความสูงของแท่งวัดจากฐานที่ถูกตัด ไม่ใช่จากศูนย์")


@rule(r"มีข้อมูลดังนี้ ([\d ]+) จงหาค่าเฉลี่ยเลขคณิต มัธยฐาน และฐานนิยม")
def _(q, m):
    global checks
    data = sorted(int(x) for x in m[1].split())
    n = len(data)
    mean = Fraction(sum(data), n)
    med = (Fraction(data[n // 2]) if n % 2
           else Fraction(data[n // 2 - 1] + data[n // 2], 2))
    top = max(data.count(v) for v in data)
    modes = sorted({v for v in data if data.count(v) == top})
    if len(modes) != 1:
        raise NotPlainData("ฐานนิยมไม่ใช่ค่าเดียว")
    checks += 1
    # เฉลยข้อนี้มีสามค่าในสตริงเดียว num() อ่านได้ค่าเดียว จึงต้องแกะเองทั้งสามค่า
    got = re.findall(r"=\s*(-?[\d.]+)", str(q["answer"]))
    if len(got) != 3 or [Fraction(g) for g in got] != [mean, med, Fraction(modes[0])]:
        bad.append((q["id"], "ค่ากลางสามค่า", q["answer"],
                    f"{mean} · {med} · {modes[0]}", txt(q)[:95]))


# ---------- เครื่องหมายกรณฑ์ในนิพจน์ ----------
def exact_root(v, k):
    """รากที่ k ของเศษส่วน v ที่ยังเป็นเศษส่วนพอดี — ไม่งั้นปฏิเสธ ไม่ปัดเป็นทศนิยม"""
    v = Fraction(v)
    if v < 0:
        raise NotPlainData("รากของจำนวนลบ")
    return Fraction(iroot(v.numerator, k), iroot(v.denominator, k))


@rule(r"^จงหาค่าของ (?:√|&radic;)\((.+?)\)\s*$")
def _(q, m):
    want(q, exact_root(arith(m[1]), 2), "คิดค่าในกรณฑ์ก่อน แล้วไล่หารากที่เป็นจำนวนเต็ม")


@rule(r"^จงหาค่าของ ∛\((.+?)\)\s*$")
def _(q, m):
    want(q, exact_root(arith(m[1]), 3), "คิดค่าในกรณฑ์ก่อน แล้วไล่หารากที่เป็นจำนวนเต็ม")


@rule(r"^จงหาจำนวนเต็มบวก n ที่มากที่สุดซึ่งทำให้ √n น้อยกว่า (\d+)")
def _(q, m):
    b = int(m[1])
    want(q, max(n for n in range(1, b * b + 1) if n < b * b), "ไล่ค่า n จนกำลังสองถึงขีด")


@rule(r"^จงหาจำนวนเต็มที่อยู่ระหว่าง √(\d+) และ √(\d+) ทั้งหมดกี่จำนวน")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, sum(1 for n in range(0, b + 1) if a < n * n < b), "เทียบด้วยกำลังสอง ไม่แตะทศนิยม")


@rule(r"^จงหาค่าของ 1\^3 \+ 2\^3 \+ 3\^3 \+ (?:&hellip;|…) \+ (\d+)\^3")
def _(q, m):
    want(q, sum(k ** 3 for k in range(1, int(m[1]) + 1)), "บวกทีละพจน์จนครบ")


# ---------- เลขยกกำลังที่ฐานเป็นกำลังของกันและกัน ----------
@rule(r"^ถ้า (\d+)\^x = (\d+) และ (\d+)\^y = (\d+) จงหาค่าของ x \+ y")
def _(q, m):
    xs = [x for x in range(0, 100) if mul_pow(int(m[1]), x) == int(m[2])]
    ys = [y for y in range(0, 100) if mul_pow(int(m[3]), y) == int(m[4])]
    if len(xs) != 1 or len(ys) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, xs[0] + ys[0], "ไล่เลขชี้กำลังทีละค่า")


@rule(r"^ถ้า (\d+)\^x = (\d+) จงหาค่าของ (\d+)\^x")
def _(q, m):
    a, v, b = (int(m[i]) for i in (1, 2, 3))
    ks = [k for k in range(1, 20) if mul_pow(a, k) == b]
    if not ks:
        raise NotPlainData(f"{b} ไม่ใช่กำลังของ {a}")
    want(q, mul_pow(v, ks[0]), "เขียนฐานใหม่เป็นกำลังของฐานเดิม")


@rule(r"^จงหาจำนวนเต็มบวก n ที่น้อยที่สุดที่ทำให้ (\d+)\^n (?:&gt;|>|มากกว่า) (\d+)")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    for n in range(1, 200):
        if mul_pow(a, n) > b:
            want(q, n, "ไล่คูณทีละรอบจนเกินเกณฑ์")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"^จงหาจำนวนเต็มบวก n ที่น้อยที่สุดซึ่งทำให้ (\d+)n เป็นกำลังสองสมบูรณ์")
def _(q, m):
    a = int(m[1])
    for n in range(1, 10000):
        r = math.isqrt(a * n)
        if r * r == a * n:
            want(q, n, "ไล่ค่า n จนผลคูณเป็นกำลังสองพอดี")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"^จงหาจำนวนเต็มบวก n ที่น้อยที่สุดซึ่งทำให้ (.+?) มากกว่า (\d+)")
def _(q, m):
    f, b = uni_eval(poly_of(m[1])), int(m[2])
    for n in range(1, 5000):
        if f(n) > b:
            want(q, n, "ไล่แทนค่า n จนเกินเกณฑ์")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


def uni_eval(p):
    """คืนฟังก์ชันแทนค่าของพหุนามตัวแปรเดียว ไม่ว่าตัวแปรจะชื่อ x หรือ n"""
    names = {v for term in p for v, _e in term}
    if len(names) > 1:
        raise NotPoly("มีตัวแปรมากกว่าหนึ่งตัว")
    name = names.pop() if names else "x"
    return lambda v: poly_eval_vars(p, {name: v})


def is_prime(n):
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


@rule(r"^จงหาผลบวกของจำนวนเต็มบวก n ทั้งหมดที่ทำให้ (.+?) เป็นจำนวนเฉพาะ")
def _(q, m):
    f = uni_eval(poly_of(m[1]))
    want(q, sum(n for n in range(1, 3000) if is_prime(f(n))),
         "ไล่ n แล้วตรวจความเป็นจำนวนเฉพาะทีละตัว")


@rule(r"^จงหาจำนวนเต็มบวก n ที่น้อยที่สุดที่ทำให้ (.+?) ไม่ เป็นจำนวนเฉพาะ")
def _(q, m):
    f = uni_eval(poly_of(m[1]))
    for n in range(1, 5000):
        if not is_prime(f(n)):
            want(q, n, "ไล่ n แล้วตรวจความเป็นจำนวนเฉพาะทีละตัว")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"^จงหา ห\.ร\.ม\. ของ (\d+)\^(\d+) - 1 กับ (\d+)\^(\d+) - 1")
def _(q, m):
    a = mul_pow(int(m[1]), int(m[2])).numerator - 1
    b = mul_pow(int(m[3]), int(m[4])).numerator - 1
    want(q, math.gcd(a, b), "หา ห.ร.ม. ด้วยขั้นตอนวิธียุคลิด")


@rule(r"^มีเศษส่วนอย่างต่ำกี่จำนวนที่มีตัวส่วนเป็น (\d+) และมีค่าอยู่ระหว่าง 0 กับ 1")
def _(q, m):
    d = int(m[1])
    want(q, sum(1 for k in range(1, d) if math.gcd(k, d) == 1),
         "ไล่ตัวเศษแล้วนับเฉพาะที่หารร่วมกับตัวส่วนได้ 1")


@rule(r"^กระจาย \((.+?)\)\^(\d+) แล้วจงหาผลบวกของสัมประสิทธิ์ทุกพจน์")
def _(q, m):
    p = poly_of(m[1])
    out = {(): Fraction(1)}
    for _ in range(int(m[2])):
        out = _pmul(out, p)
    want(q, poly_eval(out, 1), "ผลบวกสัมประสิทธิ์คือค่าของพหุนามที่ x = 1")


# ---------- นิพจน์สมมาตรของ x กับ 1/x และของรากสมการกำลังสอง ----------
@rule(r"^ถ้า x \+ \(1\)/\(x\) = (-?\d+) จงหาค่าของ x\^2 \+ \(1\)/\(x\^2\)")
def _(q, m):
    s = int(m[1])
    want(q, s * s - 2, "ยกกำลังสองผลบวกแล้วหักพจน์กลาง")


@rule(r"^ถ้า x\^2 \+ \(1\)/\(x\^2\) = (\d+) และ x (?:&gt;|>) 0 จงหาค่าของ x \+ \(1\)/\(x\)")
def _(q, m):
    want(q, iroot(int(m[1]) + 2, 2), "ผลบวกยกกำลังสองได้ค่านี้บวกสอง")


@rule(r"^ถ้า x\^2 - (\d+)x \+ 1 = 0 โดยที่ x ≠ 0 จงหาค่าของ x\^3 \+ \(1\)/\(x\^3\)")
def _(q, m):
    s = int(m[1])                      # หารทั้งสมการด้วย x จะได้ x + 1/x = s
    want(q, s ** 3 - 3 * s, "จากผลบวกกำลังหนึ่งไปกำลังสามด้วยเอกลักษณ์")


@rule(r"^ถ้า a เป็นรากของสมการ x\^2 - (\d+)x \+ 1 = 0 จงหาค่าของ a\^2 \+ \(1\)/\(a\^2\)")
def _(q, m):
    s = int(m[1])
    want(q, s * s - 2, "จาก a + 1/a = s")


@rule(r"^ถ้า m และ n เป็นรากของสมการ x\^2 - (\d+)x \+ (\d+) = 0 "
      r"จงหาค่าของ \(1\)/\(m\) \+ \(1\)/\(n\)")
def _(q, m):
    want(q, Fraction(int(m[1]), int(m[2])), "ผลบวกรากหารผลคูณราก")


@rule(r"^ถ้า a\^2 \+ b\^2 = (\d+) และ ab = (\d+) จงหาค่าของ \(a \+ b\)\^2")
def _(q, m):
    want(q, int(m[1]) + 2 * int(m[2]), "กระจายกำลังสองของผลบวก")


@rule(r"^ถ้า x \+ y = (-?\d+) และ x - y = (-?\d+) จงหาค่าของ xy")
def _(q, m):
    s, d = int(m[1]), int(m[2])
    if (s + d) % 2:
        raise NotPlainData("ระบบสมการไม่ให้คำตอบเป็นจำนวนเต็ม")
    want(q, ((s + d) // 2) * ((s - d) // 2), "แก้ระบบสมการหาค่าจริงก่อนแล้วคูณ")


@rule(r"^ถ้า x\^2 - (\d+)x \+ (\d+) = 0 จงหาผลบวกของค่า x ที่เป็นไปได้ทั้งหมด")
def _(q, m):
    b, c = int(m[1]), int(m[2])
    roots = sorted({x for x in range(-500, 501) if x * x - b * x + c == 0})
    if not roots:
        raise NotPlainData("ไม่มีรากที่เป็นจำนวนเต็ม")
    want(q, sum(roots), "ไล่หารากที่เป็นจำนวนเต็มแล้วบวกกัน")


@rule(r"^ถ้า a \+ b \+ c = 0 และ abc = (-?\d+) จงหาค่าของ a\^3 \+ b\^3 \+ c\^3")
def _(q, m):
    p = int(m[1])
    # ตรวจเอกลักษณ์กับตัวเลขจริงก่อน: เลือก a b ที่รวมกับ c แล้วได้ศูนย์
    for a in range(-30, 31):
        for b in range(-30, 31):
            c = -a - b
            if a * b * c == p:
                want(q, a ** 3 + b ** 3 + c ** 3, "หาสามจำนวนที่เข้าเงื่อนไขจริงแล้วแทนค่า")
                return
    raise NotPlainData("หาสามจำนวนเต็มที่เข้าเงื่อนไขไม่ได้")


@rule(r"^ผลบวกของกำลังสองของจำนวนเต็มบวกสองจำนวนเรียงติดกันเท่ากับ (\d+) "
      r"จงหาผลบวกของสองจำนวนนั้น")
def _(q, m):
    s = int(m[1])
    hits = [n for n in range(1, 1000) if n * n + (n + 1) ** 2 == s]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0] * 2 + 1, "ไล่ค่าจนผลบวกกำลังสองตรง")


@rule(r"^จำนวนเต็มบวกสองจำนวนต่างกัน (\d+) และคูณกันได้ (\d+) จงหาจำนวนที่น้อยกว่า")
def _(q, m):
    d, p = int(m[1]), int(m[2])
    hits = [n for n in range(1, p + 1) if n * (n + d) == p]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ค่าจนผลคูณตรง")


@rule(r"^จำนวนเต็มบวกจำนวนหนึ่งยกกำลังสองแล้วบวกด้วยตัวมันเองได้ (\d+)")
def _(q, m):
    s = int(m[1])
    hits = [n for n in range(1, s + 1) if n * n + n == s]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ค่าจนผลลัพธ์ตรง")


@rule(r"^สวนรูปสี่เหลี่ยมผืนผ้ามีพื้นที่ (\d+) ตารางเมตร ยาวมากกว่ากว้าง (\d+) เมตร "
      r"จงหาความกว้าง")
def _(q, m):
    a, d = int(m[1]), int(m[2])
    hits = [w for w in range(1, a + 1) if w * (w + d) == a]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ความกว้างจนพื้นที่ตรง")


@rule(r"^จงตรวจสอบคำตอบโดยแทน x เท่ากับ (-?\d+) ใน (.+?) จะได้ค่าเท่าใด")
def _(q, m):
    want(q, poly_eval(poly_of(m[2]), int(m[1])), "แทนค่าลงในพหุนาม")


@rule(r"^จงหาคำตอบที่เป็นบวกของสมการ (.+?) เท่ากับ 0 ที่มีค่ามากกว่า")
def _(q, m):
    p = poly_of(m[1])
    roots = sorted({x for x in range(1, 501) if poly_eval(p, x) == 0})
    if len(roots) < 2:
        raise NotPlainData("รากบวกมีไม่ถึงสองค่า")
    want(q, roots[-1], "ไล่หารากบวกทั้งหมดแล้วเอาตัวมากกว่า")


# ---------- อสมการ: ไล่แทนค่าจำนวนเต็ม ----------
def ineq_ok(expr, op, rhs, x):
    v = poly_eval(poly_of(expr), x)
    return {"<": v < rhs, ">": v > rhs, "≤": v <= rhs, "≥": v >= rhs}[op]


LT = r"(?:&lt;|<)"
GT = r"(?:&gt;|>)"


@rule(rf"^ถ้า x เป็นจำนวนเต็มที่สอดคล้องกับ (.+?) {LT} (-?\d+) และ (.+?) {GT} (-?\d+) "
      r"พร้อมกัน จงหาผลบวกของค่า x ที่เป็นไปได้ทั้งหมด")
@rule(rf"^มีจำนวนเต็ม x กี่จำนวนที่สอดคล้องกับอสมการ (.+?) {LT} (-?\d+) และ (.+?) {GT} "
      r"(-?\d+) พร้อมกัน")
def _(q, m):
    xs = [x for x in range(-2000, 2001)
          if ineq_ok(m[1], "<", int(m[2]), x) and ineq_ok(m[3], ">", int(m[4]), x)]
    if not xs:
        raise NotPlainData("ไม่มีจำนวนเต็มที่สอดคล้อง")
    want(q, sum(xs) if "ผลบวก" in txt(q) else len(xs), "ไล่แทนค่าจำนวนเต็มทีละตัว")


@rule(rf"^จงหาจำนวนเต็ม x ที่มากที่สุดซึ่งทำให้ (.+?) {LT} 0")
def _(q, m):
    xs = [x for x in range(-2000, 2001) if ineq_ok(m[1], "<", 0, x)]
    if not xs:
        raise NotPlainData("ไม่มีจำนวนเต็มที่สอดคล้อง")
    want(q, max(xs), "ไล่แทนค่าจำนวนเต็มทีละตัว")


@rule(rf"^จงหาจำนวนเต็มบวก x ที่น้อยที่สุดซึ่งทำให้ \((.+?)\)/\((.+?)\) {LT} (-?\d+)")
def _(q, m):
    num_p, den_p, rhs = poly_of(m[1]), poly_of(m[2]), int(m[3])
    for x in range(1, 5000):
        d = poly_eval(den_p, x)
        if d != 0 and poly_eval(num_p, x) / d < rhs:
            want(q, x, "ไล่แทนค่า x จากน้อยไปมากจนอสมการเป็นจริง")
            return
    raise NotPlainData("ไล่ค่าจนสุดช่วงแล้วไม่เจอ")


@rule(r"^จำนวนเต็มบวก n ที่ทำให้ \(n \+ (\d+)\)/\(n \+ (\d+)\) เป็นจำนวนเต็ม "
      r"มีทั้งหมดกี่จำนวน")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, sum(1 for n in range(1, 5000) if (n + a) % (n + b) == 0),
         "ไล่ค่า n แล้วตรวจการหารลงตัว")


@rule(r"^ครูมีดินสอจำนวนหนึ่ง ถ้าแจกนักเรียนคนละ (\d+) แท่ง จะเหลือดินสอมากกว่า (\d+) แท่ง "
      r"แต่ถ้าแจกคนละ (\d+) แท่ง จะขาดดินสอมากกว่า (\d+) แท่ง ถ้ามีนักเรียน (\d+) คน")
def _(q, m):
    a, left, b, short, n = (int(m[i]) for i in range(1, 6))
    hits = [p for p in range(1, 10000) if p - a * n > left and b * n - p > short]
    if not hits:
        raise NotPlainData("ไม่มีจำนวนดินสอที่เข้าเงื่อนไข")
    want(q, max(hits), "ไล่จำนวนดินสอทีละแท่งแล้วเอาค่ามากสุดที่ยังเข้าเงื่อนไข")


@rule(r"^มีจำนวนเต็ม x กี่จำนวนที่สอดคล้องกับ \|x - (\d+)\| \+ \|x \+ (\d+)\| = (\d+)")
def _(q, m):
    a, b, s = (int(m[i]) for i in (1, 2, 3))
    want(q, sum(1 for x in range(-2000, 2001) if abs(x - a) + abs(x + b) == s),
         "ไล่แทนค่าจำนวนเต็มทีละตัว")


@rule(r"^นำจำนวนเต็มตั้งแต่ 1 ถึง (\d+) มายกกำลังสองทุกจำนวน จงหามัธยฐาน")
def _(q, m):
    data = sorted(k * k for k in range(1, int(m[1]) + 1))
    n = len(data)
    want(q, Fraction(data[n // 2]) if n % 2
         else Fraction(data[n // 2 - 1] + data[n // 2], 2), "เรียงแล้วหาค่ากลาง")


# ---------- เรขาคณิต ม.2/ม.3 ----------
@rule(r"^รูปสามเหลี่ยมมีด้านยาว (\d+) (\d+) และ (\d+) หน่วย จงหาพื้นที่")
def _(q, m):
    a, b, c = sorted(int(m[i]) for i in (1, 2, 3))
    if a + b <= c:
        raise NotPlainData("สามด้านนี้สร้างสามเหลี่ยมไม่ได้")
    # สูตรเฮรอนในรูปจำนวนเต็ม: 16A² = (a+b+c)(-a+b+c)(a-b+c)(a+b-c)
    sq16 = (a + b + c) * (-a + b + c) * (a - b + c) * (a + b - c)
    area16 = math.isqrt(sq16)
    if area16 * area16 != sq16:
        raise NotPlainData("พื้นที่ไม่เป็นจำนวนตรรกยะ")
    want(q, Fraction(area16, 4), "สูตรเฮรอนแบบยกกำลังสอง ไม่แตะทศนิยม")


@rule(r"^รูปสามเหลี่ยมมีด้านยาว (\d+) และ (\d+) เซนติเมตร ถ้าด้านที่สามยาวเป็นจำนวนเต็ม"
      r"เซนติเมตร จงหาจำนวนค่าที่เป็นไปได้ของด้านที่สาม")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, sum(1 for c in range(1, 10 * (a + b))
                if a + b > c and a + c > b and b + c > a), "ไล่ความยาวด้านที่สามทีละหน่วย")


@rule(r"^ลูกบาศก์มีด้านยาว (\d+) หน่วย จงหากำลังสองของความยาวเส้นทแยงมุมภายในลูกบาศก์")
def _(q, m):
    s = int(m[1])
    want(q, 3 * s * s, "พีทาโกรัสสองชั้นในสามมิติ")


@rule(r"^ทรงกระบอกรัศมี (\d+) เซนติเมตร สูง (\d+) เซนติเมตร บรรจุน้ำครึ่งหนึ่งของความจุ"
      r".*?&pi; = \((\d+)\)/\((\d+)\)")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    pi = Fraction(int(m[3]), int(m[4]))
    want(q, pi * r * r * h / 2, "ปริมาตรทรงกระบอกหารสอง")


@rule(r"^วงกลมรัศมี (\d+) เซนติเมตร จงหาพื้นที่ของส่วนของวงกลมที่รองรับด้วยมุมที่จุด"
      r"ศูนย์กลาง (\d+) องศา.*?π = \((\d+)\)/\((\d+)\)")
def _(q, m):
    r, ang = int(m[1]), int(m[2])
    pi = Fraction(int(m[3]), int(m[4]))
    want(q, pi * r * r * Fraction(ang, 360), "พื้นที่วงกลมคูณสัดส่วนของมุม")


@rule(r"^ทรงกลมบรรจุพอดีในลูกบาศก์ที่มีด้านยาว (\d+) เซนติเมตร .*?"
      r"&pi; = \((\d+)\)/\((\d+)\)")
def _(q, m):
    s = int(m[1])
    pi = Fraction(int(m[2]), int(m[3]))
    ball = Fraction(4, 3) * pi * mul_pow(Fraction(s, 2), 3)
    want(q, ball / mul_pow(s, 3), "ทรงกลมมีรัศมีครึ่งหนึ่งของด้านลูกบาศก์")


@rule(r"^วงกลมรัศมี (\d+) เซนติเมตร มีคอร์ดยาว (\d+) เซนติเมตร จงหาระยะจากจุดศูนย์กลาง")
def _(q, m):
    r, c = int(m[1]), int(m[2])
    if c % 2:
        raise NotPlainData("คอร์ดยาวเป็นเลขคี่ ครึ่งคอร์ดไม่เป็นจำนวนเต็ม")
    want(q, exact_root(r * r - (c // 2) ** 2, 2), "เส้นตั้งฉากจากจุดศูนย์กลางแบ่งครึ่งคอร์ด")


@rule(r"^วงกลมสองวงมีรัศมี (\d+) เซนติเมตร และ (\d+) เซนติเมตร สัมผัสกันภายนอก")
def _(q, m):
    want(q, int(m[1]) + int(m[2]), "จุดสัมผัสอยู่บนเส้นเชื่อมจุดศูนย์กลาง")


@rule(r"^คอร์ด AB และ CD ของวงกลมตัดกันที่จุด P ภายในวงกลม ถ้า AP = (\d+) PB = (\d+) "
      r"และ CP = (\d+) จงหาความยาว PD")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(a * b, c), "สมบัติคอร์ดตัดกัน: ผลคูณของส่วนแบ่งเท่ากัน")


@rule(r"^รูปสามเหลี่ยม ABC แนบในวงกลม โดย BC เป็นเส้นผ่านศูนย์กลาง .*?จงหาขนาดของมุม BAC")
def _(q, m):
    # มุมในครึ่งวงกลมเป็นมุมฉากเสมอ ไม่ขึ้นกับมุม ABC ที่โจทย์ให้มา
    want(q, Fraction(360, 4), "มุมในครึ่งวงกลมเป็นมุมฉาก")


@rule(r"^รูปสี่เหลี่ยม ABCD แนบในวงกลม มีมุม A = \((\d+)x \+ (\d+)\) องศา "
      r"และมุม C = \((\d+)x \+ (\d+)\) องศา จงหาค่าของ x")
def _(q, m):
    a1, b1, a2, b2 = (int(m[i]) for i in range(1, 5))
    hits = [x for x in range(0, 361) if (a1 * x + b1) + (a2 * x + b2) == 180]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "มุมตรงข้ามในสี่เหลี่ยมแนบวงกลมรวมได้ 180 องศา")


@rule(r"^รูปสามเหลี่ยมมุมฉาก ABC มีมุม A เป็นมุมฉาก AB = (\d+) เซนติเมตร "
      r"AC = (\d+) เซนติเมตร ลากเส้นสูงจาก A .*?จงหาความยาว AD")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    bc = exact_root(a * a + b * b, 2)
    # พื้นที่คิดสองทาง: ครึ่งของ AB·AC และครึ่งของ BC·AD
    want(q, Fraction(a * b) / bc, "คิดพื้นที่สองทางแล้วให้เท่ากัน")


@rule(r"^รูปสามเหลี่ยม ABC มี AB = (\d+) เซนติเมตร AC = (\d+) เซนติเมตร "
      r"จุด D อยู่บน AB โดย AD = (\d+) เซนติเมตร .*?จงหาความยาว AE")
def _(q, m):
    ab, ac, ad = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(ad * ac, ab), "รูปคล้ายให้อัตราส่วนด้านที่สมนัยกันเท่ากัน")


@rule(r"^รูปสามเหลี่ยม ABC มีจุด D บน AB และ E บน AC โดย DE ขนานกับ BC "
      r"ถ้าพื้นที่ของรูปสามเหลี่ยม ADE เท่ากับ (\d+) .*?"
      r"รูปสี่เหลี่ยม DBCE เท่ากับ (\d+) .*?ในรูป 1 : k จงหาค่าของ k")
def _(q, m):
    inner, ring = int(m[1]), int(m[2])
    ratio2 = Fraction(inner, inner + ring)        # (AD/AB)²
    k = exact_root(1 / ratio2, 2)                 # AB/AD
    want(q, k - 1, "อัตราส่วนพื้นที่ของรูปคล้ายคือกำลังสองของอัตราส่วนด้าน")


@rule(r"^รูปสามเหลี่ยมสองรูปคล้ายกัน มีอัตราส่วนพื้นที่เป็น (\d+) : (\d+) "
      r"อัตราส่วนของเส้นรอบรูปเป็น (\d+) : k จงหาค่าของ k")
def _(q, m):
    a, b, p = (int(m[i]) for i in (1, 2, 3))
    want(q, p * exact_root(Fraction(b, a), 2), "เส้นรอบรูปเป็นรากที่สองของอัตราส่วนพื้นที่")


@rule(r"^แผนที่มาตราส่วน 1 : (\d+) พื้นที่จริง (\d+) ตารางกิโลเมตร "
      r"จะปรากฏบนแผนที่เป็นพื้นที่กี่ตารางเซนติเมตร")
def _(q, m):
    s, km2 = int(m[1]), int(m[2])
    cm2 = km2 * (100000 ** 2)                    # 1 ตร.กม. = (100000 ซม.)²
    want(q, Fraction(cm2, s * s), "อัตราส่วนพื้นที่คือกำลังสองของมาตราส่วนความยาว")


@rule(r"^รูปหลายเหลี่ยมด้านเท่ามุมเท่ารูปหนึ่งมีมุมภายในแต่ละมุมเป็น (\d+) "
      r"เท่าของมุมภายนอกแต่ละมุม จงหาจำนวนด้าน")
def _(q, m):
    k = int(m[1])
    ns = [n for n in range(3, 400) if Fraction(180 * (n - 2), n) == k * Fraction(360, n)]
    if len(ns) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, ns[0], "ไล่จำนวนด้านจนอัตราส่วนมุมในต่อมุมนอกตรง")


@rule(r"^ต้องการปูกระเบื้องรูปหลายเหลี่ยมด้านเท่ามุมเท่าชนิดเดียวให้เต็มพื้น"
      r"โดยไม่มีช่องว่าง จงหาจำนวนด้านที่มากที่สุด")
def _(q, m):
    # ปูเต็มได้เมื่อมุมภายในหาร 360 ลงตัว
    ns = [n for n in range(3, 400) if Fraction(360) % Fraction(180 * (n - 2), n) == 0]
    want(q, max(ns), "ไล่จำนวนด้านแล้วดูว่ามุมภายในหาร 360 ลงตัวไหม")


@rule(r"^รั้วยาว (\d+) เมตร ใช้ล้อมที่ดินรูปสี่เหลี่ยมผืนผ้าสามด้าน .*?"
      r"จงหาพื้นที่มากที่สุดที่ล้อมได้")
def _(q, m):
    total = int(m[1])
    # ไล่ความกว้างทีละครึ่งเมตรแล้วเอาพื้นที่มากสุด ไม่ใช้สูตรจุดยอด
    best = max(Fraction(w, 2) * (total - 2 * Fraction(w, 2))
               for w in range(1, total))
    want(q, best, "ไล่ความกว้างบนกริดแล้วเอาพื้นที่มากสุด")


@rule(r"^ระบบสมการ (\d+)x \+ (\d+)y = (\d+) และ (\d+)x \+ ky = (\d+) "
      r"มีคำตอบเป็นจำนวนจริงมากมายไม่จำกัด จงหาค่าของ k")
def _(q, m):
    a1, b1, c1, a2, c2 = (int(m[i]) for i in (1, 2, 3, 4, 5))
    if Fraction(a2, a1) != Fraction(c2, c1):
        raise NotPlainData("สมการสองบรรทัดไม่ได้เป็นตัวคูณของกัน")
    want(q, b1 * Fraction(a2, a1), "สมการทั้งสองต้องเป็นตัวคูณของกันทุกพจน์")


@rule(r"^กราฟของ y = x\^2 \+ bx \+ c ผ่านจุด \((-?\d+) (-?\d+)\) และ \((-?\d+) (-?\d+)\) "
      r"จงหาค่าของ b \+ c")
def _(q, m):
    x1, y1, x2, y2 = (int(m[i]) for i in range(1, 5))
    hits = [(b, c) for b in range(-100, 101) for c in range(-200, 201)
            if x1 * x1 + b * x1 + c == y1 and x2 * x2 + b * x2 + c == y2]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, sum(hits[0]), "ไล่ค่า b กับ c จนกราฟผ่านทั้งสองจุด")


@rule(r"^ถ้า x เป็นจำนวนจริงบวก จงหาค่าที่น้อยที่สุดของ x \+ \((\d+)\)/\(x\)")
def _(q, m):
    k = int(m[1])
    lows = [Fraction(t, 8) + Fraction(k * 8, t) for t in range(1, 8 * 200)]
    want(q, min(lows), "ไล่ค่า x บนกริดเศษส่วนแล้วเอาค่าน้อยสุด")


# ---------- ตรีโกณมิติจากอัตราส่วนที่กำหนด ----------
@rule(r"^ถ้า sin (?:θ|&theta;) \+ cos (?:θ|&theta;) = \((\d+)\)/\((\d+)\) "
      r"และ (?:θ|&theta;) เป็นมุมแหลม จงหาค่าของ sin (?:θ|&theta;) · cos")
def _(q, m):
    s = Fraction(int(m[1]), int(m[2]))
    want(q, (s * s - 1) / 2, "ยกกำลังสองผลบวกแล้วใช้ sin² + cos² = 1")


@rule(r"^ถ้า tan A = \((\d+)\)/\((\d+)\) และ A เป็นมุมแหลม จงหาค่าของ sin A \+ cos A")
def _(q, m):
    o, a = int(m[1]), int(m[2])
    h = exact_root(o * o + a * a, 2)
    want(q, Fraction(o) / h + Fraction(a) / h, "สร้างสามเหลี่ยมมุมฉากจากอัตราส่วนที่ให้")


@rule(r"^ถ้า sin (?:θ|&theta;) = \((\d+)\)/\((\d+)\) และ (?:θ|&theta;) เป็นมุมแหลม "
      r"จงหาค่าของ tan")
def _(q, m):
    o, h = int(m[1]), int(m[2])
    want(q, Fraction(o, exact_root(h * h - o * o, 2)), "หาด้านประชิดด้วยพีทาโกรัสก่อน")


@rule(r"^รูปสามเหลี่ยมมุมฉากมีมุมแหลม 60(?:&deg;|°) และด้านตรงข้ามมุมฉากยาว (\d+) หน่วย "
      r"จงหาความยาวของด้านที่ประชิดมุม 60")
def _(q, m):
    # สามเหลี่ยม 30-60-90 คือครึ่งหนึ่งของสามเหลี่ยมด้านเท่า ด้านประชิดมุม 60 จึงเป็นครึ่งของด้านตรงข้ามมุมฉาก
    want(q, Fraction(int(m[1]), 2), "ครึ่งหนึ่งของสามเหลี่ยมด้านเท่า")


# ---------- การแปลงจุดแล้วถามผลบวกพิกัด ----------
@rule(r"^จุด \((-?\d+) (-?\d+)\) สะท้อนข้ามแกน (X|Y) จงหาผลบวกของพิกัด x และ y ของจุดที่ได้")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    x, y = (x, -y) if m[3] == "X" else (-x, y)
    want(q, x + y, "สะท้อนข้ามแกนคือกลับเครื่องหมายของพิกัดอีกแกน")


@rule(r"^จุด \((-?\d+) (-?\d+)\) เลื่อนขนานไปทางซ้าย (\d+) หน่วย และขึ้นบน (\d+) หน่วย "
      r"จงหาผลบวกของพิกัด")
def _(q, m):
    x, y, dx, dy = (int(m[i]) for i in range(1, 5))
    want(q, (x - dx) + (y + dy), "ซ้ายคือลบในแกน X ขึ้นบนคือบวกในแกน Y")


@rule(r"^จุด \((-?\d+) (-?\d+)\) หมุนรอบจุดกำเนิด 180 องศา จงหาผลบวกของพิกัด")
def _(q, m):
    want(q, -int(m[1]) + -int(m[2]), "หมุนครึ่งรอบคือกลับเครื่องหมายทั้งสองพิกัด")


# ---------- สมบัติของค่าเฉลี่ยเมื่อแปลงข้อมูลทั้งชุด ----------
@rule(r"^ถ้าคูณข้อมูลทุกจำนวนด้วย (\d+) ค่าเฉลี่ยเลขคณิตจะเป็นกี่เท่าของเดิม")
def _(q, m):
    k = int(m[1])
    # ลองกับข้อมูลจริงหลายชุด ไม่ใช่ท่องสมบัติ
    sets = ([1, 2, 3], [4, 4, 9, 11], [7], [-3, 5, 2, 10, 6])
    ratios = set()
    for data in sets:
        base = Fraction(sum(data), len(data))
        if base == 0:
            continue
        ratios.add(Fraction(sum(x * k for x in data), len(data)) / base)
    if len(ratios) != 1:
        raise NotPlainData("อัตราส่วนไม่คงที่ในทุกชุดข้อมูลที่ลอง")
    want(q, ratios.pop(), "คูณข้อมูลจริงหลายชุดแล้วเทียบค่าเฉลี่ยก่อน-หลัง")


# ---------- มุมของรูปหลายเหลี่ยมและเส้นขนาน ----------
@rule(r"^ผลบวกของมุมภายในทั้งสามของรูปสามเหลี่ยมเท่ากับกี่องศา")
def _(q, m):
    want(q, 180 * (3 - 2), "แบ่งรูป n เหลี่ยมเป็นสามเหลี่ยม n-2 รูป")


@rule(r"^ผลบวกของมุมภายนอก(?:ทั้งสามของรูปสามเหลี่ยม|ของรูปหลายเหลี่ยมนูนใด ๆ ?)"
      r"เท่ากับกี่องศา")
def _(q, m):
    n = 3 if "สามเหลี่ยม" in txt(q) else 8      # รูปนูนกี่เหลี่ยมก็ได้ ลองด้วย 8 เหลี่ยม
    want(q, n * 180 - 180 * (n - 2), "มุมภายนอกคือ 180 ลบมุมภายในของทุกจุดยอด")


@rule(r"^ผลบวกของมุมแหลมสองมุมในรูปสามเหลี่ยมมุมฉากเท่ากับกี่องศา")
def _(q, m):
    want(q, 180 * (3 - 2) - 90, "มุมภายในรวม 180 หักมุมฉากออก")


@rule(r"^ในรูปสี่เหลี่ยมคางหมู มุมภายในสองมุมที่อยู่บนด้านที่ไม่ขนานเดียวกัน"
      r"รวมกันได้กี่องศา")
@rule(r"^ในรูปสี่เหลี่ยมด้านขนาน มุมสองมุมที่อยู่ติดกันบนด้านเดียวกันรวมกันได้กี่องศา")
@rule(r"^เมื่อเส้นตัดตัดเส้นขนาน มุมภายในที่อยู่บนข้างเดียวกันของเส้นตัดรวมกันได้กี่องศา")
@rule(r"^เส้นขนานสองเส้นถูกตัดด้วยเส้นตัด มุมภายในที่อยู่บนข้างเดียวกันของเส้นตัด "
      r"รวมกันได้กี่องศา")
def _(q, m):
    # ด้านที่ตัดเส้นขนานสองเส้นกับเส้นขนานคู่นั้นล้อมเป็นสี่เหลี่ยม มุมคู่นี้จึงเป็นครึ่งของ 360
    want(q, Fraction(180 * (4 - 2), 2), "มุมภายในของสี่เหลี่ยมรวม 360 แบ่งครึ่งให้สองด้านที่ขนาน")


@rule(r"^ถ้าสร้างมุมโดยสร้างเส้นตั้งฉาก จะได้มุมขนาดกี่องศา")
def _(q, m):
    want(q, Fraction(360, 4), "ตั้งฉากแบ่งมุมรอบจุดเป็นสี่ส่วนเท่ากัน")


@rule(r"^ถ้าสร้างมุมโดยแบ่งครึ่งมุมฉาก จะได้มุมขนาดกี่องศา")
def _(q, m):
    want(q, Fraction(360, 4) / 2, "มุมฉากหารสอง")


@rule(r"^ถ้าสร้างมุมโดยสร้างมุม (\d+) องศาสองมุมติดกัน จะได้มุมขนาดกี่องศา")
def _(q, m):
    want(q, 2 * int(m[1]), "มุมติดกันบวกกัน")


# ---------- สมบัติของระบบจำนวน: ไล่หาคำตอบจากตัวอย่างจริง ไม่ท่องนิยาม ----------
SAMPLE = [Fraction(v) for v in (-7, -3, Fraction(-1, 2), 1, 2, Fraction(5, 3), 9, 40)]


@rule(r"^รากที่สองของ (\d+) มีค่าเท่าใด")
def _(q, m):
    want(q, exact_root(int(m[1]), 2), "ไล่หาจำนวนที่ยกกำลังสองแล้วตรง")


@rule(r"^จำนวนจริงบวกทุกจำนวนมีรากที่สองกี่ราก")
def _(q, m):
    counts = {sum(1 for x in range(-100, 101) if x * x == n) for n in (1, 4, 36, 81)}
    if len(counts) != 1:
        raise NotPlainData("จำนวนรากไม่เท่ากันในทุกตัวอย่างที่ลอง")
    want(q, counts.pop(), "ไล่นับรากของกำลังสองสมบูรณ์หลายตัว")


@rule(r"^จำนวนจริงทุกจำนวนมีรากที่สามที่เป็นจำนวนจริงกี่ราก")
def _(q, m):
    counts = {sum(1 for x in range(-100, 101) if x ** 3 == n) for n in (-27, -8, 1, 64)}
    if len(counts) != 1:
        raise NotPlainData("จำนวนรากไม่เท่ากันในทุกตัวอย่างที่ลอง")
    want(q, counts.pop(), "ไล่นับรากที่สามของหลายตัวอย่าง")


@rule(r"^เอกลักษณ์การ(บวก|คูณ)ของจำนวนจริงคือจำนวนใด")
def _(q, m):
    add = m[1] == "บวก"
    hits = [e for e in SAMPLE + [Fraction(0)]
            if all((a + e if add else a * e) == a for a in SAMPLE)]
    if len(set(hits)) != 1:
        raise NotPlainData("ไล่แล้วไม่ได้เอกลักษณ์ค่าเดียว")
    want(q, hits[0], "ไล่หาจำนวนที่ดำเนินการกับตัวอย่างทุกตัวแล้วได้ค่าเดิม")


@rule(r"^จำนวนใดที่ไม่มีอินเวอร์สการคูณ")
@rule(r"^จำนวนตรรกยะคือจำนวนที่เขียนได้ในรูป \(a\)/\(b\) เมื่อ a และ b เป็นจำนวนเต็ม "
      r"โดย b ต้องไม่เท่ากับจำนวนใด")
def _(q, m):
    bad_ones = []
    for a in range(-5, 6):
        try:
            Fraction(1, a)
        except ZeroDivisionError:
            bad_ones.append(a)
    if len(bad_ones) != 1:
        raise NotPlainData("ไล่แล้วไม่ได้จำนวนเดียว")
    want(q, bad_ones[0], "ไล่หาจำนวนที่ใช้เป็นตัวส่วนไม่ได้")


@rule(r"^จำนวนใดก็ตามที่ไม่ใช่ศูนย์ เมื่อยกกำลังศูนย์จะมีค่าเท่าใด")
def _(q, m):
    vals = {mul_pow(a, 0) for a in SAMPLE}
    if len(vals) != 1:
        raise NotPlainData("ยกกำลังศูนย์แล้วได้ค่าไม่เท่ากัน")
    want(q, vals.pop(), "ยกกำลังศูนย์กับตัวอย่างหลายตัวแล้วเทียบกัน")


@rule(r"^การแปลงทางเรขาคณิตที่ทำให้รูปต้นแบบและภาพที่ได้เท่ากันทุกประการ "
      r"มีทั้งหมดกี่แบบ \((.+?)\)")
def _(q, m):
    want(q, len(re.split(r" และ | ", m[1])), "นับรายการที่โจทย์ยกมาในวงเล็บ")


@rule(r"^ความเท่ากันทุกประการแบบ ([ดม](?:\.[ดม])+)\. ใช้ข้อมูล.*?"
      r"จงตอบจำนวนคู่ของด้าน")
@rule(r"^ความเท่ากันทุกประการแบบ ([ดม](?:\.[ดม])+)\. ใช้ข้อมูลมุมกี่มุม")
def _(q, m):
    letters = m[1].split(".")
    # ชื่อเกณฑ์บอกลำดับข้อมูลอยู่ในตัว — นับตัวอักษรที่ตรงกับสิ่งที่ถาม
    want(q, letters.count("ด" if "คู่ของด้าน" in txt(q) else "ม"),
         "นับตัวอักษรในชื่อเกณฑ์")


@rule(r"^ขนาดของมุมภายนอกของรูปสามเหลี่ยมเท่ากับผลบวกของมุมภายในที่ไม่ประชิดกี่มุม")
def _(q, m):
    want(q, 3 - 1, "สามเหลี่ยมมีมุมภายในสามมุม หักมุมที่ประชิดออกหนึ่งมุม")


@rule(r"^รูป (\d+) เหลี่ยมด้านเท่ามุมเท่าแนบในวงกลม จากจุดยอดหนึ่งลากเส้นทแยงมุมสองเส้น "
      r"ไปยังจุดยอดที่อยู่ห่างออกไป (\d+) ด้าน และ (\d+) ด้าน ทางเดียวกัน "
      r"จงหาขนาดของมุมระหว่างเส้นทแยงมุมทั้งสอง")
def _(q, m):
    n, a, b = (int(m[i]) for i in (1, 2, 3))
    # มุมในวงกลมที่จุดยอดเดียวกันเท่ากับครึ่งหนึ่งของส่วนโค้งที่รองรับ
    arc = Fraction(360, n) * abs(b - a)
    want(q, arc / 2, "มุมในวงกลมเป็นครึ่งหนึ่งของส่วนโค้งที่รองรับ")


@rule(r"^เมื่อเส้นตัดตัดเส้นขนานสองเส้น จะเกิดมุมทั้งหมดกี่มุม")
def _(q, m):
    # เส้นตัดตัดเส้นขนานที่สองจุด แต่ละจุดมีสี่มุมรอบจุด
    want(q, 2 * (360 // 90), "จุดตัดสองจุด จุดละสี่มุม")


# ---------- การสร้างด้วยวงเวียนและสันตรง (ข้อคู่ขนานที่ตรวจได้ ดู tools/gen_construction.py) ----------
@rule(r"^ใช้วงเวียนกางเท่ากับส่วนของเส้นตรง AB ที่ยาว (\d+) เซนติเมตร แล้วถ่ายความยาวนี้ "
      r"ต่อกันบนรังสีเดียวกัน (\d+) ครั้ง")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "ถ่ายความยาวเท่าเดิมต่อกันหลายครั้ง")


@rule(r"^สร้างเส้นแบ่งครึ่งและตั้งฉากกับส่วนของเส้นตรง AB ที่ยาว (\d+) เซนติเมตร "
      r".*?จงหาความยาว AM")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "จุดที่เส้นแบ่งครึ่งตัดคือจุดกึ่งกลาง")


@rule(r"จากรูปการแบ่งครึ่งส่วนของเส้นตรง AB เส้น PQ ที่สร้างได้ทำมุมกับ AB กี่องศา")
@rule(r"จากรูปการสร้างเส้นตั้งฉากจากจุด P ที่อยู่นอกเส้นตรง เส้น PZ ที่สร้างได้ "
      r"ทำมุมกับเส้นตรงกี่องศา")
def _(q, m):
    want(q, Fraction(360, 4), "ตั้งฉากแบ่งมุมรอบจุดเป็นสี่ส่วนเท่ากัน")


@rule(r"^แบ่งครึ่งมุม ABC ที่มีขนาด (\d+) องศา ด้วยวงเวียนและสันตรง "
      r"เส้นแบ่งครึ่งมุมทำมุมกับแขน BC กี่องศา")
@rule(r"จากรูปการแบ่งครึ่งมุม ABC ถ้ามุม ABC มีขนาด (\d+) องศา จงหาขนาดของมุม FBC")
def _(q, m):
    want(q, Fraction(int(m[1]), 2), "เส้นแบ่งครึ่งมุมแบ่งมุมออกเป็นสองส่วนเท่ากัน")


@rule(r"^สร้างมุมขนาด 60 องศาด้วยวงเวียนและสันตรง แล้วสร้างต่อกันบนรังสีเดียวกัน "
      r"(\d+) มุม")
def _(q, m):
    want(q, 60 * int(m[1]), "มุมติดกันบวกกัน")


@rule(r"^สร้างมุมขนาด (\d+) องศา แล้วแบ่งครึ่งมุมด้วยวงเวียนและสันตรงติดต่อกัน (\d+) ครั้ง")
def _(q, m):
    v = Fraction(int(m[1]))
    for _ in range(int(m[2])):            # แบ่งครึ่งจริงทีละรอบ ไม่ใช้สูตร d/2^k
        v /= 2
    want(q, v, "แบ่งครึ่งซ้ำทีละรอบ")


@rule(r"^แบ่งมุมตรงออกเป็น (\d+) ส่วนเท่า ๆ กันด้วยวงเวียนและสันตรง")
def _(q, m):
    want(q, Fraction(180 * (3 - 2), int(m[1])), "มุมตรงคือผลบวกมุมภายในของสามเหลี่ยม")


@rule(r"^จุด P อยู่ห่างจากเส้นตรง L เป็นระยะ (\d+) เซนติเมตร กางวงเวียนจากจุด P "
      r"ด้วยรัศมี (\d+) เซนติเมตร ตัดเส้น L ที่จุด X และ Y จงหาความยาว XY")
def _(q, m):
    h, r = int(m[1]), int(m[2])
    if r <= h:
        raise NotPlainData("รัศมีสั้นเกินกว่าจะตัดเส้นตรงได้")
    want(q, 2 * exact_root(r * r - h * h, 2), "ครึ่งคอร์ดจากพีทาโกรัส แล้วคูณสอง")


@rule(r"^สร้างเส้นตรงผ่านจุด P ให้ขนานกับเส้นตรง L โดยคัดลอกมุมแย้ง "
      r"ถ้าเส้นตัดทำมุมกับเส้น L ขนาด (\d+) องศา มุมที่ต้องคัดลอก")
def _(q, m):
    want(q, int(m[1]), "มุมแย้งของเส้นขนานเท่ากัน")


@rule(r"^สร้างเส้นตรงผ่านจุด P ให้ขนานกับเส้นตรง L ถ้าเส้นตัดทำมุมกับเส้น L ขนาด (\d+) "
      r"องศา มุมภายในที่อยู่บนข้างเดียวกัน")
def _(q, m):
    want(q, Fraction(180 * (4 - 2), 2) - int(m[1]),
         "มุมภายในข้างเดียวกันของเส้นขนานรวมได้ 180 องศา")


@rule(r"^สร้างรูปสามเหลี่ยมด้านเท่า ABC ให้มีด้านยาวเท่ากับส่วนของเส้นตรง XY "
      r"ที่ยาว (\d+) เซนติเมตร จงหาความยาวรอบรูป")
def _(q, m):
    want(q, 3 * int(m[1]), "ด้านเท่ากันสามด้าน")


@rule(r"^สร้างรูปสามเหลี่ยมหน้าจั่วที่มีฐานยาวเท่ากับ AB คือ (\d+) เซนติเมตร "
      r"และด้านประกอบมุมยอดยาวเท่ากับ CD คือ (\d+) เซนติเมตร จงหาความยาวรอบรูป")
def _(q, m):
    want(q, int(m[1]) + 2 * int(m[2]), "ฐานบวกด้านประกอบสองด้าน")


@rule(r"^คัดลอกมุม ABC ที่มีขนาด (\d+) องศา ไปสร้างที่จุด P .*?จนครบ (\d+) มุม")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "มุมเท่ากันติดกันบวกกัน")


@rule(r"^สร้างรูปสี่เหลี่ยมจัตุรัสที่มีด้านยาวเท่ากับส่วนของเส้นตรง AB คือ (\d+) "
      r"เซนติเมตร จงหา(ความยาวรอบรูป|พื้นที่)")
def _(q, m):
    a = int(m[1])
    want(q, 4 * a if m[2] == "ความยาวรอบรูป" else a * a, f"{m[2]}ของรูปสี่เหลี่ยมจัตุรัส")


@rule(r"^แบ่งครึ่งส่วนของเส้นตรง AB ด้วยวงเวียนและสันตรง แล้วแบ่งครึ่งแต่ละส่วนย่อยต่อไป "
      r"อีกจนครบ (\d+) รอบ จะได้ส่วนย่อยที่เท่ากันทั้งหมดกี่ส่วน")
def _(q, m):
    parts = 1
    for _ in range(int(m[1])):
        parts *= 2
    want(q, parts, "แต่ละรอบทำให้จำนวนส่วนเป็นสองเท่า")


@rule(r"^ส่วนของเส้นตรง AB ยาว (\d+) เซนติเมตร แบ่งครึ่งด้วยวงเวียนและสันตรงติดต่อกัน "
      r"(\d+) รอบ แต่ละส่วนย่อยยาวกี่เซนติเมตร")
def _(q, m):
    v = Fraction(int(m[1]))
    for _ in range(int(m[2])):
        v /= 2
    want(q, v, "แบ่งครึ่งจริงทีละรอบ")


# ---------- ข้อระดับยากที่เติมเข้ามา (ดู tools/gen_hard.py) ----------
@rule(r"^จำนวนนับสองจำนวนมี ห\.ร\.ม\. เท่ากับ (\d+) และ ค\.ร\.น\. เท่ากับ (\d+) "
      r"ถ้าจำนวนหนึ่งคือ (\d+) อีกจำนวนหนึ่งคือจำนวนใด")
def _(q, m):
    g, l, a = (int(m[i]) for i in (1, 2, 3))
    # ไล่หาจำนวนที่เข้าเงื่อนไขจริงทั้งสองข้อ ไม่ใช้สูตร ห.ร.ม. × ค.ร.น. = ผลคูณ
    hits = [b for b in range(1, l + 1) if math.gcd(a, b) == g and a * b // math.gcd(a, b) == l]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่หาจำนวนที่ให้ ห.ร.ม. และ ค.ร.น. ตรงทั้งคู่")


@rule(r"^จำนวนเต็มบวกสองจำนวนมีผลบวกเท่ากับ (\d+) และผลคูณเท่ากับ (\d+) "
      r"จงหาผลต่างของสองจำนวนนั้น")
def _(q, m):
    s, p = int(m[1]), int(m[2])
    hits = [(u, s - u) for u in range(1, s) if u * (s - u) == p]
    if not hits:
        raise NotPlainData("ไม่มีจำนวนเต็มบวกคู่ใดเข้าเงื่อนไข")
    want(q, abs(hits[0][0] - hits[0][1]), "ไล่หาคู่จำนวนจริง ๆ แล้วลบกัน")


@rule(r"^จงหาผลบวกของจำนวนเต็มทั้งหมดที่อยู่ระหว่าง (-?\d+) และ (-?\d+)")
def _(q, m):
    lo, hi = sorted((int(m[1]), int(m[2])))
    want(q, sum(range(lo + 1, hi)), "ไล่บวกทีละจำนวน")


@rule(r"^มีจำนวนเต็ม x กี่จำนวนที่ทำให้ค่าสัมบูรณ์ของ x ([+-]) (\d+) ไม่เกิน (\d+)")
def _(q, m):
    c = int(m[2]) * (1 if m[1] == "+" else -1)
    want(q, sum(1 for x in range(-500, 501) if abs(x + c) <= int(m[3])),
         "ไล่แทนค่าจำนวนเต็มทีละตัว")


@rule(r"^จำนวนเฉพาะที่อยู่ระหว่าง (\d+) และ (\d+) มีทั้งหมดกี่จำนวน")
def _(q, m):
    lo, hi = int(m[1]), int(m[2])
    want(q, sum(1 for k in range(lo + 1, hi) if is_prime(k)), "ไล่ตรวจทีละจำนวน")


@rule(r"^ลิฟต์เริ่มที่ชั้นใต้ดินที่ \d+ \(แทนด้วย (-?\d+)\) ขึ้นไป (\d+) ชั้น "
      r"แล้วลงมา (\d+) ชั้น จากนั้นขึ้นไปอีกเป็น (\d+) เท่าของจำนวนชั้นที่เพิ่งลงมา")
def _(q, m):
    start, up, down, k = (int(m[i]) for i in range(1, 5))
    want(q, start + up - down + k * down, "เดินตามลำดับเหตุการณ์ทีละขั้น")


@rule(r"^ถ้า (\d+)\^x (?:&times;|×) (\d+)\^(\d+) = (\d+)\^(\d+) จงหาค่าของ x")
def _(q, m):
    a, b, be, c, ce = (int(m[i]) for i in range(1, 6))
    hits = [x for x in range(0, 200)
            if mul_pow(a, x) * mul_pow(b, be) == mul_pow(c, ce)]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0], "ไล่ค่า x จนสองข้างเท่ากันจริง")


@rule(r"^ผลคูณของ (\d+) (?:&times;|×) 10\^(-?\d+) กับ (\d+) (?:&times;|×) 10\^(-?\d+) "
      r"เขียนในรูปสัญกรณ์วิทยาศาสตร์ได้ [\d.]+ (?:&times;|×) 10 ยกกำลังเท่าใด")
def _(q, m):
    a, p, b, r = (int(m[i]) for i in range(1, 5))
    # คูณสัมประสิทธิ์จริง แล้วนับว่าต้องเลื่อนจุดอีกกี่ตำแหน่ง ไม่ใช่บวกเลขชี้กำลังเฉย ๆ
    want(q, p + r + sci_exp(str(a * b)), "คูณสัมประสิทธิ์แล้วจัดให้เหลือหลักเดียวหน้าจุด")


@rule(r"^ซื้อสินค้าราคาชิ้นละ ([\d.]+) บาท จำนวน (\d+) ชิ้น แล้วได้ส่วนลด ([\d.]+) บาท")
def _(q, m):
    want(q, Fraction(m[1]) * int(m[2]) - Fraction(m[3]), "ราคารวมลบส่วนลด")


@rule(r"^ทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร "
      r"จงหาความยาวเส้นทแยงมุมภายใน")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, exact_root(a * a + b * b + c * c, 2), "พีทาโกรัสสองชั้นในสามมิติ")


@rule(r"^ทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) เซนติเมตร "
      r"ถูกตัดลูกบาศก์ที่มีด้านยาว (\d+) เซนติเมตรออกไปหนึ่งก้อน")
def _(q, m):
    a, b, c, s = (int(m[i]) for i in range(1, 5))
    want(q, a * b * c - s ** 3, "ปริมาตรเดิมลบปริมาตรก้อนที่ตัดออก")


@rule(r"^ปริซึมสามเหลี่ยมมีฐานเป็นรูปสามเหลี่ยมมุมฉากที่ด้านประกอบมุมฉากยาว (\d+) และ "
      r"(\d+) เซนติเมตร และปริซึมสูง (\d+) เซนติเมตร จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    a, b, h = (int(m[i]) for i in (1, 2, 3))
    c = exact_root(a * a + b * b, 2)
    want(q, 2 * Fraction(a * b, 2) + (a + b + c) * h, "สองฐานบวกพื้นที่ผิวข้าง")


@rule(r"^นำลูกบาศก์เล็กด้านยาว 1 เซนติเมตร มาเรียงเป็นลูกบาศก์ใหญ่ด้านยาว (\d+) "
      r"เซนติเมตร แล้วทาสีเฉพาะผิวด้านนอก จงหาจำนวนลูกบาศก์เล็กที่ไม่ถูกทาสีเลย")
def _(q, m):
    n = int(m[1])
    # ไล่ทุกตำแหน่งในลูกบาศก์ แล้วนับเฉพาะก้อนที่ไม่ติดผิวด้านใดเลย
    want(q, sum(1 for x in range(n) for y in range(n) for z in range(n)
                if 0 < x < n - 1 and 0 < y < n - 1 and 0 < z < n - 1),
         "ไล่ตำแหน่งลูกบาศก์ทีละก้อน")


@rule(r"^ข้อมูล (\d+) จำนวนมีค่าเฉลี่ยเลขคณิต (\d+) ถ้าเพิ่มข้อมูลอีกหนึ่งจำนวน "
      r"แล้วค่าเฉลี่ยของทั้ง \d+ จำนวนเป็น (\d+)")
def _(q, m):
    n, a1, a2 = (int(m[i]) for i in (1, 2, 3))
    want(q, (n + 1) * a2 - n * a1, "ผลรวมใหม่ลบผลรวมเดิม")


@rule(r"^ข้อมูล \d+ จำนวนเรียงจากน้อยไปมาก มีมัธยฐาน \d+ พิสัย (\d+) "
      r"และค่าน้อยที่สุดเท่ากับ (\d+) จงหาค่ามากที่สุด")
def _(q, m):
    want(q, int(m[1]) + int(m[2]), "พิสัยคือค่ามากสุดลบค่าน้อยสุด")


@rule(r"^ค่าเฉลี่ยเลขคณิตของข้อมูล (\d+) จำนวนเท่ากับ (\d+) ต่อมาพบว่าข้อมูลตัวหนึ่ง "
      r"บันทึกผิดเป็น (\d+) ทั้งที่ค่าจริงคือ (\d+)")
def _(q, m):
    n, mean, wrong, right = (int(m[i]) for i in range(1, 5))
    want(q, Fraction(n * mean - wrong + right, n), "แก้ผลรวมแล้วหารใหม่")


@rule(r"^จุด [A-Z]\((-?\d+) (-?\d+)\) สะท้อนข้ามแกน ([XY]) แล้วเลื่อนขนานไปทางขวา "
      r"(\d+) หน่วย และลง (\d+) หน่วย จงหาผลบวกของพิกัด")
def _(q, m):
    x, y = int(m[1]), int(m[2])
    x, y = (x, -y) if m[3] == "X" else (-x, y)
    x, y = x + int(m[4]), y - int(m[5])
    want(q, x + y, "ทำทีละขั้นตามลำดับที่โจทย์บอก")


@rule(r"^จุด [A-Z]\((-?\d+) (-?\d+)\) หมุนรอบจุดกำเนิด 180 องศา แล้วสะท้อนข้ามแกน "
      r"([XY]) จงหาผลบวกของพิกัด")
def _(q, m):
    x, y = -int(m[1]), -int(m[2])
    x, y = (x, -y) if m[3] == "X" else (-x, y)
    want(q, x + y, "ทำทีละขั้นตามลำดับที่โจทย์บอก")


@rule(r"^จุด [A-Z]\((-?\d+) (-?\d+)\) เลื่อนขนานไปทางซ้าย (\d+) หน่วย และขึ้นบน (\d+) "
      r"หน่วย แล้วสะท้อนข้ามเส้นตรง x = (-?\d+) จงหาพิกัด x ของภาพสุดท้าย")
def _(q, m):
    x = int(m[1]) - int(m[3])
    want(q, 2 * int(m[5]) - x, "ทำทีละขั้นตามลำดับที่โจทย์บอก")


# ---------- แม่แบบระดับแข่งขันที่เพิ่มเข้ามา (ดู tools/gen_contest.py) ----------
@rule(r"^(?:ทรงกลมสองลูก|กรวยสองอันที่คล้ายกัน|พีระมิดสองอันที่คล้ายกัน)"
      r"มี(?:รัศมี|ความสูง)เป็นอัตราส่วน (\d+) : (\d+) "
      r"อัตราส่วน(ปริมาตร|พื้นที่ผิว)ของทั้งสองเป็น (\d+) : k จงหาค่าของ k")
def _(q, m):
    a, b, kind, shown = int(m[1]), int(m[2]), m[3], int(m[4])
    p = 3 if kind == "ปริมาตร" else 2
    # ยืนยันว่าเลขที่โจทย์แสดงไว้ฝั่งซ้ายคือ a ยกกำลัง p จริง ไม่งั้นโจทย์กับเฉลยคนละเรื่อง
    if mul_pow(a, p) != shown:
        raise NotPlainData(f"ฝั่งซ้ายของอัตราส่วนควรเป็น {a}^{p} ไม่ใช่ {shown}")
    want(q, mul_pow(b, p), f"อัตราส่วน{kind}คือกำลัง {p} ของอัตราส่วนความยาว")


@rule(r"^ขยายลูกบาศก์ให้ด้านยาวเป็น (\d+) เท่าของเดิม "
      r"ปริมาตรของลูกบาศก์ใหม่เป็นกี่เท่าของปริมาตรเดิม")
def _(q, m):
    k = int(m[1])
    # คิดจากปริมาตรจริงของลูกบาศก์สองขนาด ไม่ใช่ท่องว่ายกกำลังสาม
    want(q, Fraction((k * 7) ** 3, 7 ** 3), "เทียบปริมาตรของลูกบาศก์สองขนาดจริง")


@rule(r"^ถ้า cos A = \((\d+)\)/\((\d+)\) และ A เป็นมุมแหลม จงหาค่าของ tan A")
def _(q, m):
    a, h = int(m[1]), int(m[2])
    want(q, Fraction(exact_root(h * h - a * a, 2), a), "หาด้านตรงข้ามด้วยพีทาโกรัสก่อน")


@rule(r"^รูปสามเหลี่ยมมุมฉากมีมุมแหลม 30(?:&deg;|°) และด้านตรงข้ามมุมฉากยาว (\d+) หน่วย "
      r"จงหาความยาวของด้านตรงข้ามมุม 30")
def _(q, m):
    # สามเหลี่ยม 30-60-90 คือครึ่งหนึ่งของสามเหลี่ยมด้านเท่า ด้านตรงข้ามมุม 30 จึงเป็นครึ่งของด้านตรงข้ามมุมฉาก
    want(q, Fraction(int(m[1]), 2), "ครึ่งหนึ่งของสามเหลี่ยมด้านเท่า")


@rule(r"^ในฟาร์มมี(\S+?)และ(\S+?)รวมกัน (\d+) ตัว นับขาได้ทั้งหมด (\d+) ขา "
      r"จงหาจำนวน(\S+?)เป็นตัว")
def _(q, m):
    legs = {"ไก่": 2, "เป็ด": 2, "นก": 2, "วัว": 4, "แพะ": 4, "แกะ": 4, "หมู": 4}
    a, b, ask = m[1], m[2], m[5]
    if not {a, b, ask} <= set(legs) or ask not in (a, b):
        raise NotPlainData("ยังไม่รู้จำนวนขาของสัตว์ที่โจทย์เอ่ยถึง")
    n, total = int(m[3]), int(m[4])
    hits = [k for k in range(n + 1) if legs[a] * k + legs[b] * (n - k) == total]
    if len(hits) != 1:
        raise NotPlainData("ไล่แจงแล้วไม่ได้คำตอบเดียว")
    want(q, hits[0] if ask == a else n - hits[0], "ไล่จำนวนสัตว์ทีละตัวจนขาครบ")


# ---------- นิพจน์เลขคณิตล้วน (ครอบคลุมโจทย์คิดเลขของ ม.1/ม.2 จำนวนมาก) ----------
@rule(r"^จงหาผลลัพธ์ของ (.+?)\s*$")
def _(q, m):
    want(q, arith(m[1]), "คิดเลขตามนิพจน์")


@rule(r"^จงหาค่าของ ((?:[-+*/()\d.,×÷^ ]|&times;|&divide;)+)\s*$")
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


# รับทศนิยมด้วย โจทย์อย่าง "จงแก้สมการ 0.5x = 12" เคยตกหางยาวเพราะโทเคนไนเซอร์อ่านไม่ออก
_TOK = re.compile(r"\s*(\*\*|[-+*()^]|\d+\.\d+|\d+|[a-zA-Z])")


def _isnum(t):
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", t))


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
        if t and _isnum(t):
            eat()
            return {(): Fraction(t)}
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
            elif t == "(" or (t and (_isnum(t) or t.isalpha())):
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


# ต้องระบุหางประโยคไว้ ไม่งั้นกฎนี้จะคว้าโจทย์ที่หมุนแล้ว *ทำต่ออีกขั้น* ไปตอบแค่ขั้นแรก
@rule(r"จุด [A-Z]\((-?\d+) (-?\d+)\) หมุนรอบจุดกำเนิด 180 องศา ภาพที่ได้มีพิกัดใด")
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

    # ตัวช่วยของตระกูลกฎที่เพิ่มทีหลัง — เขียนเทสต์ไว้เพราะกฎเหล่านี้ใช้ตัวช่วยร่วมกันหลายกฎ
    # ถ้าตัวช่วยเพี้ยน จะพังพร้อมกันเป็นแถบโดยไม่มีอะไรชี้ว่าต้นตออยู่ตรงไหน
    for got, expect, label in [
        (mul_pow(2, 10), Fraction(1024), "mul_pow(2,10)"),
        (mul_pow(3, 0), Fraction(1), "mul_pow(3,0)"),
        (mul_pow(Fraction(1, 2), 3), Fraction(1, 8), "mul_pow(1/2,3)"),
        (digit_sum(9999 ** 2), 36, "digit_sum(9999²)"),
        (digit_sum(-102), 3, "digit_sum(-102)"),
        (len(divisors(60)), 12, "จำนวนตัวประกอบของ 60"),
        (divisors(12), [1, 2, 3, 4, 6, 12], "ตัวประกอบของ 12"),
        (dec_digit(1, 7, 1), 1, "หลักแรกของ 1/7"),
        (dec_digit(1, 7, 100), 8, "หลักที่ 100 ของ 1/7"),
        (dec_digit(3, 7, 100), 5, "หลักที่ 100 ของ 3/7"),
        (dec_digit(5, 8, 3), 5, "หลักที่ 3 ของ 5/8"),
        (round_half_up(Fraction("3.678"), 2), Fraction("3.68"), "ปัด 3.678 สองตำแหน่ง"),
        (round_half_up(Fraction("12.4499"), 1), Fraction("12.4"), "ปัด 12.4499 หนึ่งตำแหน่ง"),
        (round_half_up(Fraction("2.5"), 0), Fraction(3), "ปัด 2.5 เป็นจำนวนเต็ม"),
        (round_half_up(Fraction("-2.5"), 0), Fraction(-3), "ปัด -2.5 เป็นจำนวนเต็ม"),
        (read_numbers("-2.5 -2.05 -2.55"), [Fraction("-2.5"), Fraction("-2.05"),
                                            Fraction("-2.55")], "อ่านทศนิยมติดลบ"),
        (read_numbers("-(1)/(2) -(2)/(3) -(1)/(4)"),
         [Fraction(-1, 2), Fraction(-2, 3), Fraction(-1, 4)], "อ่านเศษส่วนติดลบ"),
        (sorted(int_pair(10, 21)), [3, 7], "int_pair(10,21)"),
        (sorted(int_pair(0, -9)), [-3, 3], "int_pair(0,-9)"),
    ]:
        if got != expect:
            fails.append(f"{label} -> {got} (ต้องได้ {expect})")

    # ตัวเลขที่ไม่มีคู่จำนวนเต็ม ต้องปฏิเสธ ไม่ใช่คืนคู่ที่ใกล้เคียง
    try:
        int_pair(1, 1)
        fails.append("int_pair(1,1) ควรถูกปฏิเสธแต่ผ่าน")
    except NotPlainData:
        pass
    # quad() ต้องปฏิเสธพหุนามที่ดีกรีเกินสอง ไม่ใช่ตัดพจน์ทิ้งเงียบ ๆ
    try:
        quad("x^3 + 2x + 1")
        fails.append("quad ควรปฏิเสธพหุนามดีกรีสาม")
    except (NotPoly, NotPlainData):
        pass
    if quad("2x^2 - 12x + 25")[:3] != (Fraction(2), Fraction(-12), Fraction(25)):
        fails.append(f"quad อ่านสัมประสิทธิ์ผิด -> {quad('2x^2 - 12x + 25')[:3]}")

    # ตัวช่วยของรอบตามเก็บหางยาว
    for got, expect, label in [
        (prism_parts(3), (5, 9, 6), "ปริซึมสามเหลี่ยม"),
        (prism_parts(4), (6, 12, 8), "ปริซึมสี่เหลี่ยม (ลูกบาศก์)"),
        (prism_parts(6), (8, 18, 12), "ปริซึมหกเหลี่ยม"),
        (pyramid_parts(4), (5, 8, 5), "พีระมิดฐานสี่เหลี่ยม"),
        (rect_axes(1, 1), 4, "แกนสมมาตรของจัตุรัส"),
        (rect_axes(2, 1), 2, "แกนสมมาตรของผืนผ้า"),
        (iroot(1728, 3), 12, "iroot(1728,3)"),
        (iroot(-1000, 3), -10, "iroot(-1000,3)"),
        (floor_root(100, 3), 4, "floor_root(100,3)"),
        (floor_root(62, 2), 7, "floor_root(62,2)"),
        (exact_root(Fraction("0.0016"), 2), Fraction("0.04"), "exact_root ของทศนิยม"),
        (seq_next([Fraction(3), Fraction(7), Fraction(11), Fraction(15)], 10),
         Fraction(39), "ลำดับเลขคณิตพจน์ที่ 10"),
        (seq_next([Fraction(5), Fraction(10), Fraction(20), Fraction(40)], 5),
         Fraction(80), "ลำดับเรขาคณิตพจน์ถัดไป"),
        (poly_eval_vars(poly_of("3a - 2b"), {"a": 4, "b": -2}), Fraction(16),
         "แทนค่าสองตัวแปร"),
        (poly_eval_vars(poly_of("a^2b"), {"a": -2, "b": 3}), Fraction(12),
         "แทนค่านิพจน์ที่มีเลขชี้กำลัง"),
        (uni_eval(poly_of("n^2 + n + 41"))(40), Fraction(1681), "uni_eval กับตัวแปร n"),
        (poly_of("0.5x")[(("x", 1),)], Fraction(1, 2), "สัมประสิทธิ์ทศนิยม"),
        (is_prime(1), False, "1 ไม่ใช่จำนวนเฉพาะ"),
        (is_prime(2), True, "2 เป็นจำนวนเฉพาะ"),
        (is_prime(1681), False, "41² ไม่ใช่จำนวนเฉพาะ"),
    ]:
        if got != expect:
            fails.append(f"{label} -> {got} (ต้องได้ {expect})")

    # txt() ต้องไม่กิน "<" ที่เป็นเครื่องหมายน้อยกว่า — เบราว์เซอร์ก็ไม่กิน (ตรวจกับ jsdom แล้ว)
    if txt({"text": "3x - 7 < 20 และ 5x + 4 > 9"}) != "3x - 7 < 20 และ 5x + 4 > 9":
        fails.append(f"txt กินเครื่องหมายน้อยกว่า -> {txt({'text': '3x - 7 < 20 และ 5x + 4 > 9'})}")
    if txt({"text": "a<sup>2</sup>b"}) != "a^2b":
        fails.append("txt ถอดแท็ก sup ไม่ถูก")
    # ลำดับที่ไม่ใช่ทั้งเลขคณิตและเรขาคณิต ต้องถูกปฏิเสธ ไม่ใช่เดาต่อ
    try:
        seq_next([Fraction(1), Fraction(2), Fraction(4), Fraction(7)], 5)
        fails.append("seq_next ควรปฏิเสธลำดับที่ไม่เข้าแบบรูป")
    except NotPlainData:
        pass
    try:
        iroot(50, 2)
        fails.append("iroot ควรปฏิเสธจำนวนที่ไม่เป็นกำลังสองสมบูรณ์")
    except NotPlainData:
        pass
    # ด่านนี้ไม่มีข้อไหนในคลังกระตุ้น ถ้าไม่เทสต์ตรง ๆ การถอดด่านทิ้งจะไม่มีอะไรจับได้
    try:
        uni_eval(poly_of("a + b"))
        fails.append("uni_eval ควรปฏิเสธพหุนามที่มีหลายตัวแปร")
    except NotPoly:
        pass

    # ป้อนโจทย์สังเคราะห์เข้ากฎจริง — ใช้ทดสอบด่านที่ไม่มีข้อไหนในคลังกระตุ้น
    def fire(text, answer):
        q = {"text": text, "answer": answer, "id": "selftest"}
        for pat, fn in RULES:
            mt = pat.search(txt(q))
            if mt:
                return fn(q, mt)
        raise LookupError("ไม่มีกฎไหนรับโจทย์นี้")

    before = len(bad)
    # ฝั่งซ้ายของอัตราส่วนต้องเป็น a ยกกำลังที่ถูกต้อง ไม่งั้นโจทย์กับเฉลยคนละเรื่อง
    try:
        fire("ทรงกลมสองลูกมีรัศมีเป็นอัตราส่วน 2 : 5 "
             "อัตราส่วนปริมาตรของทั้งสองเป็น 4 : k จงหาค่าของ k", "125")
        fails.append("กฎอัตราส่วนสเกลควรปฏิเสธฝั่งซ้ายที่เป็น 4 ทั้งที่ควรเป็น 2^3")
    except NotPlainData:
        pass
    if len(bad) != before:
        fails.append("โจทย์สังเคราะห์ของ selftest ไปโผล่ในรายการเฉลยผิด")
        del bad[before:]

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
    # สมการเชิงเส้น — พจน์เศษส่วนและเครื่องหมายนำหน้าพจน์แรกคือจุดที่พังง่ายที่สุด
    for lhs, rhs, expect in [("7x - 20", "x - 14", Fraction(1)),
                             ("5x - 10", "-x - 22", Fraction(-2)),
                             ("3(x + 2)", "18", Fraction(4)),
                             ("(x)/(3)", "9", Fraction(27)),
                             ("(x)/(2) + (x)/(3)", "10", Fraction(12)),
                             ("(3x)/(4)", "9", Fraction(12)),
                             ("2(3x + 1) - 5", "2(x + 4)", Fraction(11, 4)),
                             ("-x + 8", "3", Fraction(5))]:
        try:
            got = solve_linear(lhs, rhs)
        except (NotPoly, NotPlainData) as e:
            got = f"ปฏิเสธ({e})"
        if got != expect:
            fails.append(f"solve_linear({lhs!r}, {rhs!r}) -> {got} (ต้องได้ {expect})")
    # x^2 + 2x = 0 สำคัญกว่าที่เห็น: ถ้าการ์ด "ต้องเชิงเส้น" หายไป จะได้ x = 0 ออกมา
    # ซึ่งเป็นรากจริงข้อหนึ่งแต่ไม่ใช่คำตอบเดียว — ตอบผิดโดยไม่มีข้อยกเว้นให้จับ
    for lhs, rhs in [("2x + 1", "2x + 5"), ("x^2 + 1", "0"), ("(x)/(0)", "1"),
                     ("x^2 + 2x", "0")]:
        try:
            solve_linear(lhs, rhs)
            fails.append(f"solve_linear({lhs!r}, {rhs!r}) ควรถูกปฏิเสธแต่ผ่าน")
        except (NotPoly, NotPlainData):
            pass
    if _terms("5 - (x)/(3) + 2") != [(1, "5"), (-1, "(x)/(3)"), (1, "2")]:
        fails.append(f"_terms แยกพจน์ผิด -> {_terms('5 - (x)/(3) + 2')}")

    for src in ["3/x", "x^-2", "x^99"]:
        try:
            poly_of(src)
            fails.append(f"poly_of({src!r}) ควรถูกปฏิเสธแต่ผ่าน")
        except NotPoly:
            pass

    # เรขาคณิต — ค่าที่ "ไม่เข้าเงื่อนไข" ต้องถูกปฏิเสธ ไม่ใช่คิดต่อไปเงียบ ๆ
    for fn, args, expect in [(tri_third, (55, 65), 60), (tri_third, (90, 37), 53),
                             (leg, (25, 7), 24), (leg, (17, 15), 8),
                             (icbrt_exact, (512,), 8), (icbrt_exact, (27,), 3)]:
        got = fn(*args)
        if got != expect:
            fails.append(f"{fn.__name__}{args} -> {got} (ต้องได้ {expect})")
    for fn, args in [(tri_third, (120, 70)), (leg, (7, 25)), (leg, (10, 10)),
                     (icbrt_exact, (100,)), (icbrt_exact, (0,))]:
        try:
            fn(*args)
            fails.append(f"{fn.__name__}{args} ควรถูกปฏิเสธแต่ผ่าน")
        except NotPlainData:
            pass
    if leg(25, 20) != 15:                      # 15-20-25 ต้องได้ผลเป็นจำนวนเต็ม
        fails.append("leg(25, 20) ไม่ตรง")

    # ค่ากลาง — มัธยฐานของชุดคู่/คี่ และฐานนิยมที่ไม่ชัดเจนต้องถูกปฏิเสธ
    for fn, d, expect in [(median, [3, 7, 9, 12, 15], Fraction(9)),
                          (median, [4, 6, 10, 14], Fraction(8)),
                          (median, [12, 5, 9, 3, 20, 8], Fraction(17, 2)),
                          (mode, [2, 3, 3, 5, 7, 3, 8], Fraction(3)),
                          (mean, [12, 15, 18, 20, 25], Fraction(18))]:
        if fn(d) != expect:
            fails.append(f"{fn.__name__}({d}) -> {fn(d)} (ต้องได้ {expect})")
    for d in ([1, 2, 3, 4], [1, 1, 2, 2]):     # ไม่มีฐานนิยม / มีสองค่าเท่ากัน
        try:
            mode(d)
            fails.append(f"mode({d}) ควรถูกปฏิเสธแต่ผ่าน")
        except NotPlainData:
            pass

    # อ่านกลับจากตารางที่วาดไว้จริง
    sl = ('<table class="data-table"><tr><th>ต้น</th><th>ใบ</th></tr>'
          '<tr><td>2</td><td>4 6 8</td></tr><tr><td>3</td><td>2 5 5 5 9</td></tr>'
          '<tr><td>4</td><td>1 3 6 7</td></tr><tr><td>5</td><td>0 4</td></tr></table>')
    got = stem_leaf({"text": "จากแผนภาพต้น-ใบ" + sl})
    if sorted(got) != [24, 26, 28, 32, 35, 35, 35, 39, 41, 43, 46, 47, 50, 54]:
        fails.append(f"stem_leaf อ่านตารางผิด -> {sorted(got)}")
    ft = ('<table class="data-table"><tr><th>คะแนน</th><td>5</td><td>6</td><td>7</td></tr>'
          '<tr><th>จำนวน (คน)</th><td>2</td><td>1</td><td>3</td></tr></table>')
    got = freq_table({"text": "จากตารางแจกแจงความถี่" + ft})
    if sorted(got) != [5, 5, 6, 7, 7, 7]:
        fails.append(f"freq_table กระจายความถี่ผิด -> {sorted(got)}")
    # ร้อยละ — ฐานเป็นศูนย์ต้องถูกปฏิเสธ ไม่ใช่หารแล้วระเบิด
    for args, expect in [((25, 400), Fraction(25, 4)), ((-80, 800), Fraction(-10))]:
        if rel(*args) != expect:
            fails.append(f"rel{args} -> {rel(*args)} (ต้องได้ {expect})")
    try:
        rel(5, 0)
        fails.append("rel ที่ฐานศูนย์ควรถูกปฏิเสธแต่ผ่าน")
    except NotPlainData:
        pass
    for args, expect in [((1500, -20), Fraction(1200)), ((2000, 7), Fraction(2140)),
                         ((900, -10), Fraction(810))]:
        if after(*args) != expect:
            fails.append(f"after{args} -> {after(*args)} (ต้องได้ {expect})")
    if after(after(900, -10), -10) != Fraction(729):     # ลดซ้อนไม่ใช่ลดรวม 20%
        fails.append("ลดสองครั้งซ้อนกันคิดผิด")

    # พหุนาม — ดีกรีต้องรวมทุกตัวแปร และแทนค่าได้เฉพาะพหุนามตัวแปรเดียว
    for src, expect in [("3x^2y^3", 5), ("5x^2y + 3xy^4 - 2", 5), ("9", 0),
                        ("4x^3 - 2x^2 + 7x - 1", 3)]:
        got = max(deg(t) for t in poly_of(src))
        if got != expect:
            fails.append(f"ดีกรีของ {src!r} -> {got} (ต้องได้ {expect})")
    for src, x, expect in [("2x^2 + 3x - 5", 2, Fraction(9)),
                           ("x^2 - 4x + 7", -1, Fraction(12)),
                           ("3x^3 - 2x", 3, Fraction(75))]:
        got = poly_eval(poly_of(src), x)
        if got != expect:
            fails.append(f"แทนค่า {src!r} ที่ x={x} -> {got} (ต้องได้ {expect})")
    try:
        poly_eval(poly_of("5x^2y"), 2)
        fails.append("poly_eval ควรปฏิเสธพหุนามหลายตัวแปรแต่ผ่าน")
    except NotPoly:
        pass

    for bad_html in ('<table><tr><th>ก</th><th>ข</th></tr><tr><td>2</td><td>4</td></tr></table>',
                     '<table><tr><th>ต้น</th><th>ใบ</th></tr>'
                     '<tr><td>2</td><td>44</td></tr></table>'):
        try:
            stem_leaf({"text": bad_html})
            fails.append("stem_leaf ควรปฏิเสธตารางที่ไม่ใช่ต้น-ใบ")
        except NotPlainData:
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
@rule(r"จงหาค่าของ \|(-?\d+(?:\.\d+)?)\|$")
def _(q, m):
    want(q, abs(Fraction(m[1])), "ค่าสัมบูรณ์")


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


# ---------- ปริมาตรและพื้นที่ผิวของรูปสามมิติ ----------
CM = r"(?:เซนติเมตร|เมตร|หน่วย|นิ้ว)"


def icbrt_exact(n):
    r = round(int(n) ** (1 / 3))
    for c in (r - 1, r, r + 1):                 # float ปัดพลาดได้ที่ขอบ เลยลองข้างเคียงด้วย
        if c > 0 and c ** 3 == int(n):
            return c
    raise NotPlainData(f"{n} ไม่ใช่กำลังสามของจำนวนเต็ม")


@rule(rf"ลูกบาศก์มี(?:ความยาว)?ด้าน(?:ยาว|ละ) {DEC} {CM}.*?ปริมาตร")
def _(q, m):
    want(q, Fraction(m[1]) ** 3, "ปริมาตรลูกบาศก์ = ด้าน³")


@rule(rf"ลูกบาศก์ยาวด้านละ (\d+) {CM} มีพื้นที่ผิว")
def _(q, m):
    want(q, 6 * int(m[1]) ** 2, "ลูกบาศก์มี 6 หน้าเท่ากัน")


@rule(rf"ปริซึมสี่เหลี่ยมมุมฉาก(?:มี)?ขนาด (\d+) {X} (\d+) {X} (\d+) {CM} "
      rf".*?พื้นที่ผิว")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, 2 * (a * b + b * c + a * c), "ผลรวมพื้นที่ทั้งหกหน้า")


@rule(rf"(?:ปริซึมสี่เหลี่ยมมุมฉาก|สระน้ำทรงสี่เหลี่ยมมุมฉาก)(?:มี)?ขนาด "
      rf"(\d+) {X} (\d+) {X} (\d+) {CM}(?! .*?ใส่น้ำ).*?ปริมาตร")
def _(q, m):
    want(q, int(m[1]) * int(m[2]) * int(m[3]), "กว้าง × ยาว × สูง")


@rule(rf"สระน้ำทรงสี่เหลี่ยมมุมฉากขนาด (\d+) {X} (\d+) {X} (\d+) {CM} "
      rf"ใส่น้ำไว้ \((\d+)\)/\((\d+)\) ของสระ")
def _(q, m):
    a, b, c, p, r = (int(m[i]) for i in range(1, 6))
    want(q, Fraction(a * b * c * p, r), "ปริมาตรสระ × สัดส่วนที่ใส่น้ำ")


def cylinder(q, r, h, what):
    r, h = Fraction(r), Fraction(h)
    want(q, {"พื้นที่ผิวข้าง": 2 * PI * r * h,
             "ฉลากหุ้มรอบข้าง": 2 * PI * r * h,
             "พื้นที่ผิวทั้งหมด": 2 * PI * r * (r + h),
             "ปริมาตร": PI * r * r * h}[what], f"{what}ของทรงกระบอก")


@rule(rf"ทรงกระบอกรัศมี(?:ฐาน)? {DEC} {CM} (?:สูง|ลึก) {DEC} {CM}"
      rf".*?(พื้นที่ผิวข้าง|พื้นที่ผิวทั้งหมด|ฉลากหุ้มรอบข้าง|ปริมาตร)")
def _(q, m):
    cylinder(q, m[1], m[2], m[3])


@rule(rf"ทรงกระบอกยาว {DEC} {CM} รัศมี(?:ภายใน)? {DEC} {CM}.*?(ปริมาตร)")
def _(q, m):
    cylinder(q, m[2], m[1], m[3])           # ท่อวางนอน โจทย์บอกความยาวมาก่อนรัศมี


@rule(rf"ปริซึมสามเหลี่ยมมีฐานเป็นรูปสามเหลี่ยมมุมฉากที่มีด้านยาว (\d+) (\d+) และ (\d+) "
      rf"{CM} และมีความยาวของปริซึม (\d+) {CM} พื้นที่ผิวทั้งหมด")
def _(q, m):
    a, b, c, l = (int(m[i]) for i in (1, 2, 3, 4))
    if a * a + b * b != c * c:
        raise NotPlainData("ฐานไม่ใช่สามเหลี่ยมมุมฉาก")
    want(q, 2 * Fraction(a * b, 2) + (a + b + c) * l, "ฐานสองหน้า + ความยาวรอบฐาน × ความยาว")


@rule(rf"ปริซึมสามเหลี่ยมมีฐานเป็นรูปสามเหลี่ยมมุมฉากที่มีด้านประกอบมุมฉากยาว (\d+) และ "
      rf"(\d+) {CM} และมีความยาวของปริซึม (\d+) {CM} มีปริมาตร")
def _(q, m):
    a, b, l = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(a * b, 2) * l, "พื้นที่ฐาน × ความยาว")


@rule(rf"กล่องทรงลูกบาศก์มีปริมาตร (\d+) ลูกบาศก์{CM} ยาวด้านละ")
def _(q, m):
    want(q, icbrt_exact(m[1]), "ด้าน = รากที่สามของปริมาตร")


@rule(rf"กล่องทรงลูกบาศก์ใบหนึ่งมีพื้นที่ผิวทั้งหมด (\d+) ตาราง{CM} จงหาความยาวด้าน")
def _(q, m):
    s = Fraction(int(m[1]), 6)
    if s.denominator != 1:
        raise NotPlainData("พื้นที่ผิวหารด้วย 6 ไม่ลงตัว")
    want(q, isqrt_exact(s), "ด้าน = √(พื้นที่ผิว ÷ 6)")


@rule(rf"(?:กล่องทรงลูกบาศก์ยาวด้านละ|ลูกบาศก์ที่มีความยาวด้านละ) (\d+) {CM} "
      rf"(?:บรรจุลูกบาศก์เล็กยาวด้านละ|ถูกตัดแบ่งเป็นลูกบาศก์เล็กด้านละ) (\d+) {CM}")
def _(q, m):
    big, small = int(m[1]), int(m[2])
    if big % small:
        raise NotPlainData("ลูกบาศก์เล็กแบ่งลูกใหญ่ไม่ลงตัว")
    want(q, (big // small) ** 3, "จำนวนลูกบาศก์เล็กที่เรียงได้ทั้งสามแกน")


@rule(rf"ลูกบาศก์ด้านละ (\d+) {CM} ทาสีทั้ง 6 หน้า แล้วตัดเป็นลูกบาศก์หนึ่งหน่วย "
      rf"จงหาจำนวนลูกบาศก์เล็กที่ไม่มีสีเลย")
def _(q, m):
    n = int(m[1])
    if n < 3:
        raise NotPlainData("ลูกบาศก์เล็กเกินกว่าจะมีก้อนในสุด")
    want(q, (n - 2) ** 3, "ก้อนที่ไม่โดนสีคือแกนกลางที่หดเข้ามาด้านละ 1 ทุกทิศ")


@rule(rf"แท่งเหล็กทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) สูง (\d+) {CM} ถ้าเหล็ก 1 "
      rf"ลูกบาศก์{CM}หนัก {DEC} กรัม")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, a * b * c * Fraction(m[4]), "ปริมาตร × น้ำหนักต่อหนึ่งลูกบาศก์หน่วย")


@rule(rf"เทน้ำจากทรงกระบอกรัศมี (\d+) {CM} สูง (\d+) {CM} ลงในกล่องสี่เหลี่ยมกว้าง (\d+) "
      rf"ยาว (\d+) {CM} น้ำจะสูง")
def _(q, m):
    r, h, w, l = (int(m[i]) for i in (1, 2, 3, 4))
    want(q, PI * r * r * h / (w * l), "ปริมาตรน้ำเท่าเดิม หารด้วยพื้นที่ฐานใหม่")


@rule(rf"กล่องทรงสี่เหลี่ยมมุมฉากสองใบมีปริมาตรเท่ากัน ใบแรกกว้าง (\d+) ยาว (\d+) สูง "
      rf"(\d+) {CM} ใบที่สองกว้าง (\d+) ยาว (\d+) {CM} ใบที่สองสูง")
def _(q, m):
    a, b, c, d, e = (int(m[i]) for i in range(1, 6))
    want(q, Fraction(a * b * c, d * e), "ปริมาตรเท่ากัน หารด้วยพื้นที่ฐานของใบที่สอง")


@rule(rf"กล่องลูกบาศก์ด้านยาว (\d+) {CM} จำนวน (\d+) กล่อง บรรจุลงในลังทรงสี่เหลี่ยมมุมฉาก"
      rf"กว้าง (\d+) ยาว (\d+) สูง (\d+) {CM} จะเหลือที่ว่าง")
def _(q, m):
    d, n, w, l, h = (int(m[i]) for i in range(1, 6))
    want(q, w * l * h - n * d ** 3, "ปริมาตรลัง ลบด้วยปริมาตรกล่องทั้งหมด")


@rule(r"ทรงกระบอกสองใบมีรัศมีเท่ากัน แต่ใบที่สองสูงเป็น (\d+) เท่าของใบแรก "
      r"จงหาอัตราส่วนของปริมาตรใบแรกต่อใบที่สอง ในรูป 1 : k")
def _(q, m):
    want(q, int(m[1]), "รัศมีเท่ากัน ปริมาตรจึงแปรตามความสูงตรง ๆ")


@rule(rf"ถังทรงกรวยใบหนึ่งสูง (\d+) {CM} เมื่อเทน้ำลงไปจนน้ำสูง (\d+) {CM} "
      rf"จงหาอัตราส่วนของปริมาตรน้ำต่อปริมาตรของถังทั้งใบ ในรูป 1 : k")
def _(q, m):
    tall, water = int(m[1]), int(m[2])
    if tall % water:
        raise NotPlainData("ความสูงไม่เป็นอัตราส่วนลงตัว")
    want(q, (tall // water) ** 3, "กรวยคล้ายกัน ปริมาตรแปรตามกำลังสามของความสูง")


@rule(rf"ทรงกลมลูกหนึ่งมีปริมาตรเท่ากับปริมาตรของกรวยที่มีรัศมีฐาน (\d+) {CM} และสูง "
      rf"(\d+) {CM} จงหารัศมีของทรงกลม")
def _(q, m):
    r, h = int(m[1]), int(m[2])
    want(q, icbrt_exact(Fraction(r * r * h, 4)), "⅓πr²h = 4/3πR³ → R³ = r²h/4")


@rule(rf"ทรงกระบอกใบหนึ่งรัศมี (\d+) {CM} สูง (\d+) {CM} บรรจุน้ำเต็ม แล้วเทน้ำลงกรวย"
      rf"ที่มีรัศมีฐาน (\d+) {CM} สูง (\d+) {CM} จนเต็ม จงหาปริมาตรน้ำที่เหลือ")
def _(q, m):
    r, h, cr, ch = (int(m[i]) for i in (1, 2, 3, 4))
    want(q, PI * r * r * h - PI * cr * cr * ch / 3, "ปริมาตรทรงกระบอก ลบปริมาตรกรวย")


@rule(rf"ทรงกลมรัศมี (\d+) {CM} ถ้าเพิ่มรัศมีเป็น (\d+) เท่า ปริมาตรจะเพิ่มเป็นกี่เท่า")
def _(q, m):
    want(q, int(m[2]) ** 3, "ปริมาตรทรงกลมแปรตามกำลังสามของรัศมี")


@rule(rf"พีระมิดฐานสี่เหลี่ยมจัตุรัสมีด้านฐาน (\d+) {CM} สูง (\d+) {CM} "
      rf"จงหาพื้นที่ผิวทั้งหมด")
def _(q, m):
    b, h = int(m[1]), int(m[2])
    if b % 2:
        raise NotPlainData("ครึ่งด้านฐานไม่เป็นจำนวนเต็ม")
    slant = isqrt_exact(h * h + (b // 2) ** 2)
    want(q, b * b + 4 * Fraction(b * slant, 2), "ฐาน + สามเหลี่ยมสี่หน้า (สูงเอียงจากพีทาโกรัส)")


@rule(rf"ครึ่งทรงกลมตันรัศมี (\d+) {CM} จงหาพื้นที่ผิวทั้งหมด \(รวมหน้าตัดวงกลม\)")
def _(q, m):
    r = int(m[1])
    want(q, 2 * PI * r * r + PI * r * r, "ครึ่งผิวทรงกลม + หน้าตัดวงกลม")


# ---------- พีทาโกรัสและเส้นทแยงมุม ----------
def leg(hyp, other):
    """ด้านประกอบมุมฉากอีกด้าน — ต้องลงตัวเป็นจำนวนเต็ม ไม่งั้นเทียบกับเฉลยไม่ได้"""
    if other >= hyp:
        raise NotPlainData("ด้านตรงข้ามมุมฉากต้องยาวที่สุด")
    return isqrt_exact(hyp * hyp - other * other)


@rule(rf"สี่เหลี่ยมผืนผ้ากว้าง (\d+) {CM} (?:ยาว|สูง) (\d+) {CM} จงหาความยาวเส้นทแยงมุม")
def _(q, m):
    want(q, isqrt_exact(int(m[1]) ** 2 + int(m[2]) ** 2), "เส้นทแยงมุม = √(กว้าง² + ยาว²)")


@rule(rf"สี่เหลี่ยมจัตุรัสมีด้านยาว (\d+) {CM} จงหากำลังสองของความยาวเส้นทแยงมุม")
def _(q, m):
    want(q, 2 * int(m[1]) ** 2, "เส้นทแยงมุม² = ด้าน² + ด้าน²")


@rule(rf"สี่เหลี่ยมจัตุรัสมีเส้นทแยงมุมยาว (\d+) {CM} จงหาพื้นที่")
def _(q, m):
    want(q, Fraction(int(m[1]) ** 2, 2), "พื้นที่จัตุรัส = เส้นทแยงมุม² ÷ 2")


@rule(rf"สามเหลี่ยมมุมฉากมีด้านประกอบมุมฉากยาวด้านละ (\d+) {CM}เท่ากัน "
      rf"จงหาค่าของกำลังสองของด้านตรงข้ามมุมฉาก")
def _(q, m):
    want(q, 2 * int(m[1]) ** 2, "ด้านตรงข้ามมุมฉาก² = a² + a²")


@rule(rf"สนามรูปสี่เหลี่ยมผืนผ้ากว้าง (\d+) {CM} ยาว (\d+) {CM} "
      rf"การเดินตัดตามเส้นทแยงมุมสั้นกว่า")
def _(q, m):
    w, l = int(m[1]), int(m[2])
    want(q, w + l - isqrt_exact(w * w + l * l), "เดินสองด้าน ลบด้วยเส้นทแยงมุม")


@rule(rf"ทางลาดสำหรับรถเข็นยาว (\d+) {CM} ปลายทางลาดสูงจากพื้น (\d+) {CM}")
@rule(rf"ว่าวติดอยู่บนยอดเสาสูง (\d+) {CM} มีสายว่าวตึงยาว (\d+) {CM}")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, leg(max(a, b), min(a, b)), "ด้านที่เหลือของสามเหลี่ยมมุมฉาก")


@rule(rf"สี่เหลี่ยมขนมเปียกปูนมีเส้นทแยงมุมยาว (\d+) และ (\d+) {CM} จงหาความยาวด้าน")
def _(q, m):
    p, r = Fraction(int(m[1]), 2), Fraction(int(m[2]), 2)
    if (p.denominator, r.denominator) != (1, 1):
        raise NotPlainData("ครึ่งเส้นทแยงมุมไม่เป็นจำนวนเต็ม")
    want(q, isqrt_exact(p * p + r * r), "ด้าน = √(ครึ่งทแยง² + ครึ่งทแยง²)")


@rule(rf"กล่องทรงสี่เหลี่ยมมุมฉากกว้าง (\d+) ยาว (\d+) และสูง (\d+) {CM} "
      rf"จงหาความยาวเส้นทแยงมุมของกล่อง")
@rule(rf"กล่องทรงสี่เหลี่ยมมุมฉากขนาด (\d+) {X} (\d+) {X} (\d+) {CM} "
      rf"จงหาความยาวของเส้นทแยงมุมภายในกล่อง")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, isqrt_exact(a * a + b * b + c * c), "เส้นทแยงมุมในกล่อง = √(a² + b² + c²)")


@rule(rf"กล่องทรงลูกบาศก์มีด้านยาว (\d+) {CM} จงหากำลังสองของความยาวเส้นทแยงมุมของกล่อง")
def _(q, m):
    want(q, 3 * int(m[1]) ** 2, "เส้นทแยงมุมในลูกบาศก์² = 3 × ด้าน²")


@rule(r"ถ้า (\d+) (\d+) (\d+) เป็นสามสิ่งอันดับพีทาโกรัส แล้วคูณทุกจำนวนด้วย (\d+) "
      r"จะได้ด้านตรงข้ามมุมฉาก")
def _(q, m):
    a, b, c, k = (int(m[i]) for i in (1, 2, 3, 4))
    if a * a + b * b != c * c:
        raise NotPlainData(f"{a} {b} {c} ไม่ใช่สามสิ่งอันดับพีทาโกรัสจริง")
    want(q, c * k, "ขยายสามสิ่งอันดับด้วยตัวคูณเดียวกันทุกจำนวน")


@rule(rf"สามเหลี่ยมมุมฉากมีด้านตรงข้ามมุมฉากยาว (\d+) {CM} และด้านหนึ่งยาว (\d+) {CM} "
      rf"จงหาพื้นที่")
def _(q, m):
    h, a = int(m[1]), int(m[2])
    want(q, Fraction(a * leg(h, a), 2), "หาด้านที่เหลือด้วยพีทาโกรัส แล้วครึ่งฐานคูณสูง")


@rule(rf"สามเหลี่ยมมุมฉากมีด้านประกอบมุมฉากยาว (\d+) และ (\d+) {CM} "
      rf"จงหาความยาวของเส้นสูงที่ลากจากมุมฉาก")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    want(q, Fraction(a * b, isqrt_exact(a * a + b * b)),
         "พื้นที่คิดสองทาง: ½ab = ½ × ด้านตรงข้ามมุมฉาก × เส้นสูง")


@rule(rf"สามเหลี่ยมมุมฉากมีด้านตรงข้ามมุมฉากยาว (\d+) {CM} และด้านหนึ่งยาว (\d+) {CM} "
      rf"จงหาค่าของ (sin|cos|tan) θ เมื่อ θ เป็นมุมที่อยู่ตรงข้ามด้านยาว (\d+) {CM}")
def _(q, m):
    h, a = int(m[1]), int(m[2])
    if int(m[4]) != a:
        raise NotPlainData("ด้านที่โจทย์อ้างถึงตอนท้ายไม่ตรงกับด้านที่ให้มา")
    o = leg(h, a)
    want(q, {"sin": Fraction(a, h), "cos": Fraction(o, h),
             "tan": Fraction(a, o)}[m[3]], f"{m[3]} θ เมื่อ θ ตรงข้ามด้านยาว {a}")


# ---------- ขนาดของมุม ----------
# กลุ่มนี้ตั้งใจไม่เขียนกฎให้ข้อที่เฉลยเป็นค่าคงที่ล้วน ("ผลบวกมุมภายในสามเหลี่ยมกี่องศา")
# เพราะการเทียบกับ 180 ที่พิมพ์ไว้ในตัวตรวจเองไม่ใช่การคิดใหม่ เป็นการท่องซ้ำ
# ปล่อยให้ค้างในถัง "ยังไม่มีกฎรองรับ" ตรงไปตรงมากว่า

def tri_third(a, b):
    """มุมที่สามของรูปสามเหลี่ยม — และกันโจทย์ที่สองมุมแรกรวมกันเกิน 180 ไปแล้ว"""
    if a + b >= 180:
        raise NotPlainData(f"มุม {a}° กับ {b}° รวมกันไม่เหลือให้มุมที่สาม")
    return 180 - a - b


@rule(r"รูปสามเหลี่ยมมีมุมภายในขนาด (\d+) องศา และ (\d+) องศา มุมภายในที่สาม")
def _(q, m):
    want(q, tri_third(int(m[1]), int(m[2])), "มุมภายในรวมกันได้ 180°")


@rule(r"สามเหลี่ยมมุมฉากมีมุมแหลมมุมหนึ่งขนาด (\d+) องศา.*?มุมแหลมอีกมุม")
def _(q, m):
    want(q, tri_third(90, int(m[1])), "มุมแหลมสองมุมของสามเหลี่ยมมุมฉากรวมกันได้ 90°")


@rule(r"สามเหลี่ยมหน้าจั่วมีมุมยอด(?:ขนาด)? (\d+) องศา.*?มุมที่ฐาน")
def _(q, m):
    want(q, Fraction(tri_third(0, int(m[1])), 2), "มุมที่ฐานสองมุมเท่ากัน แบ่งส่วนที่เหลือ")


@rule(r"สามเหลี่ยมหน้าจั่วมีมุมที่ฐาน(?:ขนาด|มุมละ) (\d+) องศา.*?มุมยอด")
def _(q, m):
    b = int(m[1])
    want(q, tri_third(b, b), "มุมยอด = 180° - มุมที่ฐานสองมุม")


@rule(r"มุมภายในสองมุม(?:นั้นมีขนาด|ขนาด|คือ) (\d+) (?:องศา )?และ (\d+) องศา.*?มุมภายนอก")
@rule(r"สามเหลี่ยม ABC มีมุม A = (\d+) องศา และมุม B = (\d+) องศา "
      r"จงหาขนาดของมุมภายนอกที่จุด C")
def _(q, m):
    a, b = int(m[1]), int(m[2])
    tri_third(a, b)                     # ต้องเป็นสามเหลี่ยมได้จริงก่อน
    want(q, a + b, "มุมภายนอก = ผลบวกของมุมภายในที่ไม่ประชิด")


@rule(r"มุมภายนอกขนาด (\d+) องศา และมุมภายในที่ไม่ประชิดมุมหนึ่งขนาด (\d+) องศา")
def _(q, m):
    e, a = int(m[1]), int(m[2])
    if a >= e:
        raise NotPlainData("มุมภายในที่ไม่ประชิดต้องเล็กกว่ามุมภายนอก")
    want(q, e - a, "มุมภายในอีกมุม = มุมภายนอก - มุมภายในที่ไม่ประชิดอีกมุม")


@rule(r"สามเหลี่ยม.{0,20}มุมภายใน(?:เป็น)?อัตราส่วน (\d+) : (\d+) : (\d+)"
      r".*?มุมที่(ใหญ่|เล็ก)ที่สุด")
def _(q, m):
    parts = [int(m[i]) for i in (1, 2, 3)]
    pick = max(parts) if m[4] == "ใหญ่" else min(parts)
    want(q, Fraction(180 * pick, sum(parts)), f"แบ่ง 180° ตามอัตราส่วน แล้วเอามุมที่{m[4]}ที่สุด")


@rule(r"สามเหลี่ยมมีมุมภายในมุมหนึ่งเป็น (\d+) เท่าของมุมที่สอง และมุมที่สาม "
      r"มีขนาด (\d+) องศา มุมที่(เล็ก|ใหญ่)ที่สุด")
def _(q, m):
    k, third = int(m[1]), int(m[2])
    x = Fraction(tri_third(0, third), k + 1)            # x + kx = 180 - third
    want(q, min(x, k * x, third) if m[3] == "เล็ก" else max(x, k * x, third),
         f"แก้ x + {k}x + {third} = 180 แล้วเทียบทั้งสามมุม")


@rule(r"สี่เหลี่ยมด้านขนานมีมุมหนึ่งขนาด (\d+) องศา.*?มุม(?:ที่อยู่)?ตรงข้าม")
def _(q, m):
    want(q, int(m[1]), "มุมตรงข้ามของสี่เหลี่ยมด้านขนานเท่ากัน")


@rule(r"สี่เหลี่ยมด้านขนานมีมุมหนึ่งขนาด (\d+) องศา.*?มุมที่อยู่(?:ประชิด|ติดกัน)")
def _(q, m):
    want(q, tri_third(0, int(m[1])), "มุมประชิดของสี่เหลี่ยมด้านขนานรวมกันได้ 180°")


@rule(r"เส้นขนานสองเส้นถูกตัดด้วยเส้นตัด ถ้ามุม(?:ภายนอกมุม)?หนึ่งมีขนาด (\d+) องศา "
      r"มุม(?:ภายนอกที่สมนัย|ที่สมนัย|แย้ง)")
def _(q, m):
    want(q, int(m[1]), "มุมแย้ง/มุมสมนัยของเส้นขนานเท่ากัน")


@rule(r"มุมภายในที่อยู่ข้างเดียวกันของเส้นตัดมุมหนึ่งมีขนาด \((\d+)x \+ (\d+)\) องศา "
      r"และอีกมุมหนึ่งมีขนาด \((\d+)x \+ (\d+)\) องศา จงหาค่าของ x")
def _(q, m):
    a, b, c, d = (int(m[i]) for i in (1, 2, 3, 4))      # (ax+b) + (cx+d) = 180
    if a + c == 0:
        raise NotPlainData("สัมประสิทธิ์ของ x หักล้างกันหมด หา x ไม่ได้")
    want(q, Fraction(180 - b - d, a + c), "มุมภายในข้างเดียวกันรวมกันได้ 180°")


@rule(r"แบ่งครึ่งมุมกับมุมขนาด (\d+) องศา (หนึ่ง|สอง|สาม)ครั้ง")
def _(q, m):
    n = {"หนึ่ง": 1, "สอง": 2, "สาม": 3}[m[2]]
    want(q, Fraction(int(m[1]), 2 ** n), f"แบ่งครึ่ง {n} ครั้ง = หารด้วย 2^{n}")


@rule(r"สามเหลี่ยมหน้าจั่วที่มีมุมยอด (\d+) องศา แล้วแบ่งครึ่งมุมที่ฐานมุมหนึ่ง "
      r"จงหาขนาดของมุมที่เล็กที่สุด")
def _(q, m):
    apex = int(m[1])
    base = Fraction(tri_third(0, apex), 2)
    want(q, min(apex, base, base / 2), "มุมที่เล็กที่สุดในบรรดามุมยอด มุมที่ฐาน และครึ่งมุมที่ฐาน")


@rule(r"มุมสองมุมรวมกันได้ (\d+) องศา โดยมุมหนึ่งเป็น (\d+) เท่าของอีกมุม "
      r"มุมที่(เล็ก|ใหญ่)กว่า")
@rule(r"มุมสองมุมเป็นมุมประชิดกันบนเส้นตรงเดียวกัน ()ถ้ามุมหนึ่งมีขนาดเป็น (\d+) "
      r"เท่าของอีกมุมหนึ่ง จงหาขนาดของมุมที่(เล็ก|ใหญ่)กว่า")
def _(q, m):
    total = int(m[1]) if m[1] else 180        # มุมประชิดบนเส้นตรงรวมกันได้ 180° เสมอ
    k = int(m[2])
    small = Fraction(total, k + 1)
    want(q, small if m[3] == "เล็ก" else k * small, f"แบ่ง {total}° เป็น 1 : {k}")


@rule(r"นาฬิกาเรือนหนึ่งบอกเวลา (\d+) นาฬิกา(?: (\d+) นาที|ตรง)")
def _(q, m):
    h, mi = int(m[1]) % 12, int(m[2] or 0)
    gap = abs(Fraction(30 * h) + Fraction(mi, 2) - 6 * mi)   # เข็มสั้นเดิน 0.5°/นาที
    want(q, min(gap, 360 - gap), "ระยะเชิงมุมระหว่างเข็มสั้นกับเข็มยาว")


@rule(r"ผลบวกของมุมภายใน.{0,40}เท่ากับ (\d+) องศา.*?(?:มีกี่ด้าน|จำนวนด้าน)")
def _(q, m):
    s = int(m[1])
    if s % 180 or s < 180:
        raise NotPlainData(f"{s}° ไม่ใช่ผลบวกมุมภายในของรูปหลายเหลี่ยมใด")
    want(q, s // 180 + 2, "ผลบวกมุมภายใน = (n - 2) × 180°")


@rule(r"มุมภายนอกแต่ละมุมขนาด (\d+) องศา มีกี่ด้าน")
def _(q, m):
    a = int(m[1])
    if 360 % a:
        raise NotPlainData(f"มุมภายนอก {a}° หารกับ 360° ไม่ลงตัว")
    want(q, 360 // a, "มุมภายนอกของรูปหลายเหลี่ยมนูนรวมกันได้ 360°")


# ---------- ค่ากลางและการกระจาย (ชุดที่โจทย์วางข้อมูลไว้หน้าคำถาม) ----------
def data_list(s):
    """รายการข้อมูลในโจทย์ — ตัวสุดท้ายมักคั่นด้วย 'และ' แทนช่องว่าง"""
    return parse_data(re.sub(r"\s*และ\s*", " ", s))


def median(d):
    d, n = sorted(d), len(d)
    return Fraction(d[n // 2]) if n % 2 else Fraction(d[n // 2 - 1] + d[n // 2], 2)


def mode(d):
    top = max(d.count(v) for v in set(d))
    winners = {v for v in d if d.count(v) == top}
    if top < 2 or len(winners) > 1:
        raise NotPlainData("ไม่มีฐานนิยมเดียวที่ชัดเจน")
    return Fraction(winners.pop())


def mean(d):
    return Fraction(sum(d), len(d))


STAT = {"ค่าเฉลี่ยเลขคณิต": mean, "มัธยฐาน": median, "ฐานนิยม": mode,
        "พิสัย": lambda d: Fraction(max(d) - min(d)),
        "พิสัยของข้อมูลชุดนี้": lambda d: Fraction(max(d) - min(d))}


def want_round(q, value, why):
    """เฉลยของโจทย์ค่าเฉลี่ยปัดเป็นทศนิยม 2 ตำแหน่ง — รับได้ทั้งค่าตรงและค่าที่ปัดแล้ว"""
    exact = Fraction(value)
    rounded = Fraction(int(exact * 100 + (1 if exact >= 0 else -1) * Fraction(1, 2)), 100)
    got = num(q["answer"])
    if got is not None and got == rounded and got != exact:
        want(q, rounded, why)
    else:
        want(q, exact, why)


@rule(r"มีข้อมูลดังนี้ (-?\d.+?) "
      r"จงหา(ค่าเฉลี่ยเลขคณิต|มัธยฐาน|ฐานนิยม|พิสัยของข้อมูลชุดนี้)$")
@rule(r"^ข้อมูล (-?\d.+?) มี(ค่าเฉลี่ยเลขคณิต|มัธยฐาน|ฐานนิยม|พิสัย)เท่าใด$")
@rule(r"^จงหา(?:)(มัธยฐาน|ฐานนิยม|พิสัย)ของ (-?\d[\d ]*)$")
def _(q, m):
    key, raw = (m[1], m[2]) if m[1] in STAT else (m[2], m[1])
    want_round(q, STAT[key](data_list(raw)), key)


@rule(r"^ข้อมูล (-?\d[\d ]*) จงหาพิสัย$")
def _(q, m):
    d = data_list(m[1])
    want(q, max(d) - min(d), "พิสัย")


@rule(r"ข้อมูลชุดหนึ่งคือ (-?\d.+?) จงหาผลบวกของค่าเฉลี่ยเลขคณิต มัธยฐาน และฐานนิยม")
def _(q, m):
    d = data_list(m[1])
    want(q, mean(d) + median(d) + mode(d), "ค่าเฉลี่ย + มัธยฐาน + ฐานนิยม")


@rule(r"^ข้อมูล (-?\d[\d ]*) จงหาค่าเฉลี่ยเลขคณิตลบด้วยมัธยฐาน")
def _(q, m):
    d = data_list(m[1])
    want(q, mean(d) - median(d), "ค่าเฉลี่ย - มัธยฐาน")


@rule(r"ข้อมูลชุดหนึ่งคือ (-?\d[\d ]*) จงหาพิสัยระหว่างควอร์ไทล์ \(IQR\)")
def _(q, m):
    d = data_list(m[1])
    want(q, quart(d, 3) - quart(d, 1), "IQR")


# ---------- ค่าเฉลี่ยที่เปลี่ยนไปเมื่อชุดข้อมูลเปลี่ยน ----------
@rule(r"ข้อมูล (\d+) จำนวนมีค่าเฉลี่ยเลขคณิต (\d+) จงหาผลรวมของข้อมูลทั้งหมด")
def _(q, m):
    want(q, int(m[1]) * int(m[2]), "ผลรวม = จำนวนข้อมูล × ค่าเฉลี่ย")


@rule(r"ข้อมูล (\d+) จำนวนมีผลรวม (\d+) จงหาค่าเฉลี่ยเลขคณิต")
def _(q, m):
    want_round(q, Fraction(int(m[2]), int(m[1])), "ค่าเฉลี่ย = ผลรวม ÷ จำนวนข้อมูล")


@rule(r"นักเรียน (\d+) คนได้คะแนนเฉลี่ย (\d+) คะแนน ถ้ามีนักเรียนคนที่ \d+ ได้ (\d+) คะแนน "
      r"ค่าเฉลี่ยของทั้ง (\d+) คน")
@rule(r"นักเรียนกลุ่มหนึ่ง (\d+) คนมีค่าเฉลี่ยของส่วนสูง (\d+) เซนติเมตร ถ้ามีนักเรียนสูง "
      r"(\d+) เซนติเมตรเข้ามาเพิ่มอีก 1 คน ค่าเฉลี่ยใหม่()")
def _(q, m):
    n, avg, add = (int(m[i]) for i in (1, 2, 3))
    want_round(q, Fraction(n * avg + add, n + 1), "ผลรวมเดิม + ค่าใหม่ หารด้วยจำนวนที่เพิ่มขึ้น")


@rule(r"ข้อมูล (\d+) จำนวนมีค่าเฉลี่ยเลขคณิต (\d+) ถ้าตัดข้อมูลที่มีค่า (\d+) ออกหนึ่งจำนวน")
def _(q, m):
    n, avg, drop = (int(m[i]) for i in (1, 2, 3))
    if n < 2:
        raise NotPlainData("ตัดออกแล้วไม่เหลือข้อมูล")
    want_round(q, Fraction(n * avg - drop, n - 1), "ผลรวมเดิม - ค่าที่ตัด หารด้วยจำนวนที่เหลือ")


@rule(r"ข้อมูลชุดหนึ่งมี (\d+) จำนวน ค่าเฉลี่ยเลขคณิตเท่ากับ (\d+) "
      r"ถ้าเพิ่มข้อมูลอีกหนึ่งจำนวนแล้วค่าเฉลี่ยใหม่เป็น (\d+) จงหาข้อมูลที่เพิ่มเข้ามา")
def _(q, m):
    n, old, new = (int(m[i]) for i in (1, 2, 3))
    want(q, (n + 1) * new - n * old, "ผลรวมใหม่ - ผลรวมเดิม")


@rule(r"ข้อมูล (\d+) จำนวนมีค่าเฉลี่ยเลขคณิต (\d+) ถ้าเพิ่มข้อมูลอีก (\d+) "
      r"จำนวนที่มีค่าเฉลี่ย (\d+) จงหาค่าเฉลี่ยเลขคณิตของข้อมูลทั้ง (\d+) จำนวน")
def _(q, m):
    n, a, k, b, tot = (int(m[i]) for i in range(1, 6))
    if n + k != tot:
        raise NotPlainData("จำนวนข้อมูลรวมไม่ตรงกับที่โจทย์บอก")
    want_round(q, Fraction(n * a + k * b, tot), "รวมผลรวมของสองกลุ่ม หารด้วยจำนวนทั้งหมด")


@rule(r"นักเรียน (\d+) คนสอบได้ ([\d ]+?) และ x คะแนน ถ้าค่าเฉลี่ยเท่ากับ (\d+) จงหาค่าของ x")
def _(q, m):
    n, known, avg = int(m[1]), data_list(m[2]), int(m[3])
    if len(known) + 1 != n:
        raise NotPlainData("จำนวนคะแนนที่ให้มาไม่ตรงกับจำนวนคน")
    want(q, n * avg - sum(known), "ผลรวมที่ต้องได้ ลบด้วยคะแนนที่รู้แล้ว")


@rule(r"ข้อมูลชุดหนึ่งมีค่าเฉลี่ยเลขคณิตเท่ากับ (\d+) ถ้านำข้อมูลทุกจำนวนคูณด้วย (\d+) "
      r"แล้วลบด้วย (\d+)")
def _(q, m):
    want(q, int(m[1]) * int(m[2]) - int(m[3]), "ค่าเฉลี่ยแปลงตามการแปลงเชิงเส้นเดียวกัน")


@rule(r"ข้อมูลชุดหนึ่งมีพิสัย (\d+) และมีค่าสูงสุด (\d+) ค่าต่ำสุด")
def _(q, m):
    want(q, int(m[2]) - int(m[1]), "ค่าต่ำสุด = ค่าสูงสุด - พิสัย")


@rule(r"ข้อมูล (\d+) จำนวนเรียงจากน้อยไปมาก มีมัธยฐานเท่ากับ (\d+) พิสัยเท่ากับ (\d+) "
      r"และค่าน้อยที่สุดเท่ากับ (\d+) จงหาค่ามากที่สุด")
def _(q, m):
    med, rng, lo = (int(m[i]) for i in (2, 3, 4))
    if not lo <= med <= lo + rng:
        raise NotPlainData("มัธยฐานอยู่นอกช่วงของข้อมูล")
    want(q, lo + rng, "ค่ามากที่สุด = ค่าน้อยที่สุด + พิสัย")


# ---------- แผนภาพต้น-ใบ และตารางแจกแจงความถี่ (อ่านกลับจากตารางที่วาดไว้จริง) ----------
def _rows(html):
    return [re.findall(r"<t[dh]>(.*?)</t[dh]>", tr)
            for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S)]


def stem_leaf(q):
    """ประกอบค่าจริงกลับจากตารางต้น-ใบ — ต้นคือหลักสิบ ใบแต่ละตัวคือหลักหน่วย"""
    rows = _rows(q["text"])
    if not rows or rows[0][:2] != ["ต้น", "ใบ"]:
        raise NotPlainData("ไม่ใช่ตารางต้น-ใบ")
    out = []
    for row in rows[1:]:
        if len(row) != 2 or not row[0].strip().isdigit():
            raise NotPlainData("แถวของตารางต้น-ใบ ไม่เป็นรูปแบบที่อ่านได้")
        stem = int(row[0])
        for leaf in row[1].split():
            if len(leaf) != 1 or not leaf.isdigit():
                raise NotPlainData(f"ใบ {leaf!r} ไม่ใช่เลขหลักเดียว")
            out.append(stem * 10 + int(leaf))
    if not out:
        raise NotPlainData("ตารางต้น-ใบ ว่างเปล่า")
    return out


def freq_table(q):
    """กระจายตารางแจกแจงความถี่กลับเป็นข้อมูลดิบ แล้วคิดค่ากลางจากข้อมูลดิบตรง ๆ"""
    rows = _rows(q["text"])
    if len(rows) != 2 or len(rows[0]) != len(rows[1]):
        raise NotPlainData("ไม่ใช่ตารางแจกแจงความถี่สองแถว")
    vals, freqs = rows[0][1:], rows[1][1:]
    if not vals or not all(v.strip().lstrip("-").isdigit() for v in vals + freqs):
        raise NotPlainData("ตารางมีช่องที่ไม่ใช่ตัวเลข")
    out = []
    for v, f in zip(vals, freqs):
        out += [int(v)] * int(f)
    if not out:
        raise NotPlainData("ตารางแจกแจงความถี่ว่างเปล่า")
    return out


@rule(r"^จากแผนภาพต้น-ใบ (?:จงหา)?(มีข้อมูลทั้งหมดกี่จำนวน|ข้อมูลที่มีค่าน้อยที่สุด|"
      r"ข้อมูลที่มีค่ามากที่สุด|พิสัยของข้อมูล|ฐานนิยมของข้อมูล|มัธยฐานของข้อมูล)")
def _(q, m):
    d = stem_leaf(q)
    want(q, {"มีข้อมูลทั้งหมดกี่จำนวน": Fraction(len(d)),
             "ข้อมูลที่มีค่าน้อยที่สุด": Fraction(min(d)),
             "ข้อมูลที่มีค่ามากที่สุด": Fraction(max(d)),
             "พิสัยของข้อมูล": Fraction(max(d) - min(d)),
             "ฐานนิยมของข้อมูล": mode(d),
             "มัธยฐานของข้อมูล": median(d)}[m[1]], f"{m[1]} จากตารางต้น-ใบ")


@rule(r"^จากแผนภาพต้น-ใบ มีข้อมูลกี่จำนวนที่มีค่าตั้งแต่ (\d+) ขึ้นไป")
def _(q, m):
    want(q, sum(1 for v in stem_leaf(q) if v >= int(m[1])), "นับค่าที่ถึงเกณฑ์จากตารางต้น-ใบ")


@rule(r"^จากตารางแจกแจงความถี่ (?:จงหา)?(ฐานนิยม|ค่าเฉลี่ยเลขคณิต|มัธยฐาน)ของคะแนน")
def _(q, m):
    want_round(q, STAT[m[1]](freq_table(q)), f"{m[1]} จากตารางแจกแจงความถี่")


# ---------- ร้อยละในโจทย์ซื้อขาย ----------
def rel(part, whole):
    """คิดเป็นร้อยละของฐาน — ฐานศูนย์คือโจทย์ที่ผิดตั้งแต่ต้น ไม่ใช่ค่าที่ควรเดา"""
    if whole == 0:
        raise NotPlainData("ฐานของร้อยละเป็นศูนย์")
    return Fraction(100 * part, whole)


def after(price, pct):
    """ราคาหลังปรับ pct เปอร์เซ็นต์ (บวกคือขึ้น ลบคือลด)"""
    return Fraction(price) * (1 + Fraction(pct, 100))


@rule(r"ซื้อสินค้ามาราคา (\d+) บาท ขายไป (\d+) บาท ได้กำไรกี่บาท")
def _(q, m):
    want(q, int(m[2]) - int(m[1]), "กำไร = ราคาขาย - ราคาทุน")


@rule(r"ซื้อสินค้ามาราคา (\d+) บาท ขายไป (\d+) บาท ได้(กำไร|ขาดทุน)ร้อยละเท่าใด")
def _(q, m):
    cost, sell = int(m[1]), int(m[2])
    want(q, rel(sell - cost if m[3] == "กำไร" else cost - sell, cost),
         f"{m[3]}เทียบกับราคาทุน")


@rule(r"ซื้อสินค้ามาราคา (\d+) บาท ต้องการกำไรร้อยละ (\d+) ต้องขายราคากี่บาท")
def _(q, m):
    want(q, after(m[1], int(m[2])), "ราคาทุนบวกกำไรตามร้อยละที่ต้องการ")


@rule(r"ซื้อสินค้ามาราคา (\d+) บาท ขายขาดทุนร้อยละ (\d+) ขายได้กี่บาท")
@rule(r"แม่ค้าซื้อผลไม้มาราคาทุน (\d+) บาท แต่ขายขาดทุน (\d+)% ของราคาทุน")
def _(q, m):
    want(q, after(m[1], -int(m[2])), "ราคาทุนหักขาดทุนตามร้อยละ")


def cost_from_sale(q, sell, gain):
    want(q, Fraction(int(sell)) / (1 + Fraction(int(gain), 100)), "ราคาขาย ÷ (1 + อัตรากำไร)")


@rule(r"ขายสินค้าได้ (\d+) บาท โดยได้กำไรร้อยละ (\d+) ต้นทุนของสินค้ากี่บาท")
def _(q, m):
    cost_from_sale(q, m[1], m[2])


@rule(r"สินค้าชิ้นหนึ่งขายได้กำไร (\d+)% ของราคาทุน ถ้าขายได้เงิน (\d+) บาท จงหาราคาทุน")
def _(q, m):
    cost_from_sale(q, m[2], m[1])


@rule(r"สินค้าราคา (\d+) บาท ลดราคาร้อยละ (\d+) ต้องจ่ายกี่บาท")
def _(q, m):
    want(q, after(m[1], -int(m[2])), "ราคาป้ายหักส่วนลด")


@rule(r"สินค้าราคา (\d+) บาท ลดราคาร้อยละ (\d+) ลดไปกี่บาท")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 100), "ส่วนลด = ราคา × อัตราส่วนลด")


@rule(r"สินค้าราคา (\d+) บาท บวกภาษีมูลค่าเพิ่มร้อยละ (\d+) ต้องจ่ายรวมกี่บาท")
@rule(r"สินค้าชิ้นหนึ่งราคาก่อนภาษีมูลค่าเพิ่ม (\d+) บาท คิดภาษีมูลค่าเพิ่ม (\d+)%")
def _(q, m):
    want(q, after(m[1], int(m[2])), "ราคาก่อนภาษีบวกภาษีมูลค่าเพิ่ม")


@rule(r"ฝากเงิน (\d+) บาท ได้ดอกเบี้ยร้อยละ (\d+) ต่อปี(?: \(ดอกเบี้ยคงต้น\))? "
      r"ครบ (\d+) ปีได้ดอกเบี้ย")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]) * int(m[3]), 100), "ดอกเบี้ยคงต้น = เงินต้น × อัตรา × ปี")


@rule(r"เงินฝาก (\d+) บาท ได้ดอกเบี้ยทบต้นปีละ (\d+) เปอร์เซ็นต์ เมื่อครบ (\d+) ปี "
      r"จะมีเงินกี่บาท")
def _(q, m):
    v = Fraction(int(m[1]))
    for _ in range(int(m[3])):                  # ทบทีละปีจริง ๆ แทนการยกกำลัง
        v = after(v, int(m[2]))
    want(q, v, "ทบต้นปีต่อปี")


@rule(r"สินค้าติดป้ายราคา (\d+) บาท ลดร้อยละ (\d+) แล้วลดเพิ่มอีกร้อยละ (\d+) "
      r"จากราคาที่ลดแล้ว")
def _(q, m):
    want(q, after(after(m[1], -int(m[2])), -int(m[3])), "ลดสองครั้ง ครั้งที่สองคิดจากราคาที่ลดแล้ว")


@rule(r"ราคาสินค้า (\d+) บาท ขึ้นราคาร้อยละ (\d+) แล้วลดราคาร้อยละ (\d+) จากราคาใหม่")
def _(q, m):
    want(q, after(after(m[1], int(m[2])), -int(m[3])), "ขึ้นแล้วลด ฐานของการลดคือราคาใหม่")


@rule(r"สินค้าราคาป้าย (\d+) บาท ลดราคาร้อยละ (\d+) แล้วบวกภาษีมูลค่าเพิ่มร้อยละ (\d+) "
      r"จากราคาที่ลดแล้ว")
def _(q, m):
    want(q, after(after(m[1], -int(m[2])), int(m[3])), "ลดก่อน แล้วคิดภาษีจากราคาที่ลดแล้ว")


@rule(r"(?:จำนวนหนึ่ง|จำนวนนักเรียน)(เพิ่ม|ลด)จาก (\d+) (?:คน )?(?:เป็น|เหลือ) (\d+) "
      r"(?:คน )?(?:เพิ่มขึ้น|ลดลง)ร้อยละเท่าใด")
def _(q, m):
    a, b = int(m[2]), int(m[3])
    want(q, rel(b - a if m[1] == "เพิ่ม" else a - b, a), "ผลต่างเทียบกับค่าเดิม")


@rule(r"โรงเรียนมีนักเรียน (\d+) คน สำรวจความคิดเห็นจากนักเรียน (\d+) คน "
      r"กลุ่มตัวอย่างคิดเป็นร้อยละเท่าใดของประชากร")
def _(q, m):
    want(q, rel(int(m[2]), int(m[1])), "กลุ่มตัวอย่างเทียบกับประชากรทั้งหมด")


@rule(r"ผลสำรวจนักเรียน (\d+) คน พบว่าชอบฟุตบอลร้อยละ \d+ วอลเลย์บอลร้อยละ \d+ "
      r"แบดมินตันร้อยละ (\d+) และอื่น ๆ ร้อยละ \d+ มีนักเรียนที่ชอบแบดมินตันกี่คน")
def _(q, m):
    want(q, Fraction(int(m[1]) * int(m[2]), 100), "ร้อยละของจำนวนนักเรียนทั้งหมด")


@rule(r"จากตารางแจกแจงความถี่ นักเรียนที่ได้คะแนนตั้งแต่ (\d+) ขึ้นไปคิดเป็นร้อยละเท่าใด")
def _(q, m):
    d = freq_table(q)
    want(q, rel(sum(1 for v in d if v >= int(m[1])), len(d)), "นับจากข้อมูลดิบที่กระจายจากตาราง")


# ---------- อัตราส่วนและสัดส่วน ----------
@rule(r"แบ่งเงิน (\d+) บาท ให้สามคนตามอัตราส่วน (\d+) : (\d+) : (\d+) "
      r"คนที่ได้มากที่สุดได้เงินกี่บาท")
def _(q, m):
    parts = [int(m[i]) for i in (2, 3, 4)]
    want(q, Fraction(int(m[1]) * max(parts), sum(parts)), "ส่วนที่มากที่สุดของการแบ่งตามอัตราส่วน")


@rule(r"แบ่งเงิน (\d+) บาท ให้ ก ข ค ตามอัตราส่วน (\d+) : (\d+) : (\d+) "
      r"จงหาเงินที่ (ก|ข|ค) ได้รับ")
def _(q, m):
    parts = [int(m[i]) for i in (2, 3, 4)]
    want(q, Fraction(int(m[1]) * parts["กขค".index(m[5])], sum(parts)),
         f"ส่วนของ {m[5]} ตามอัตราส่วน")


@rule(r"น้ำหวานผสมจากน้ำ : น้ำเชื่อม : น้ำแข็ง เป็นอัตราส่วน (\d+) : (\d+) : (\d+) "
      r"ถ้าใช้น้ำเชื่อม (\d+) มิลลิลิตร ต้องใช้น้ำกี่มิลลิลิตร")
def _(q, m):
    water, syrup = int(m[1]), int(m[2])
    want(q, Fraction(int(m[4]) * water, syrup), "เทียบสัดส่วนจากส่วนที่รู้ค่า")


@rule(r"จากอัตราส่วนที่เท่ากัน (\d+) : (\d+) = (\d+) : ⬜")
def _(q, m):
    a, b, c = (int(m[i]) for i in (1, 2, 3))
    want(q, Fraction(b * c, a), "คูณไขว้")


@rule(r"(\d+) : (\d+) เขียนเป็นอัตราส่วนอย่างต่ำได้ (\d+) : ⬜")
def _(q, m):
    a, b, lo = (int(m[i]) for i in (1, 2, 3))
    g = math.gcd(a, b)
    if a // g != lo:
        raise NotPlainData("ส่วนแรกที่โจทย์ให้มาไม่ใช่รูปอย่างต่ำ")
    want(q, b // g, "หารทั้งคู่ด้วย ห.ร.ม.")


# ---------- เอกนามและพหุนาม ----------
def deg(term):
    """ดีกรีของพจน์ = ผลบวกของเลขชี้กำลังทุกตัวแปร"""
    return sum(e for _, e in term)


def poly_eval(p, x):
    total = Fraction(0)
    for term, coef in p.items():
        if any(v != "x" for v, _ in term):
            raise NotPoly("มีตัวแปรอื่นนอกจาก x แทนค่าไม่ได้")
        total += coef * Fraction(x) ** deg(term)
    return total


@rule(r"เอกนาม (\S+) มีสัมประสิทธิ์เท่ากับเท่าใด")
def _(q, m):
    p = poly_of(m[1])
    if len(p) != 1:
        raise NotPoly("ไม่ใช่เอกนามพจน์เดียว")
    want(q, next(iter(p.values())), "สัมประสิทธิ์ของเอกนาม")


@rule(r"(?:เอกนาม|พหุนาม) (.+?) มีดีกรีเท่ากับเท่าใด")
def _(q, m):
    want(q, max(deg(t) for t in poly_of(m[1])), "ดีกรีสูงสุดในบรรดาพจน์ทั้งหมด")


@rule(r"พหุนาม (.+?) มีกี่พจน์")
def _(q, m):
    want(q, len([c for c in poly_of(m[1]).values() if c]), "จำนวนพจน์ที่สัมประสิทธิ์ไม่เป็นศูนย์")


@rule(r"จงหาค่าของพหุนาม (.+?) เมื่อ x เท่ากับ (-?\d+)")
def _(q, m):
    want(q, poly_eval(poly_of(m[1]), int(m[2])), f"แทน x = {m[2]} แล้วคิดค่า")


@rule(r"จงหาผลคูณของ (.+?) แล้วตอบสัมประสิทธิ์ของ x\^(\d+)")
def _(q, m):
    want(q, poly_of(m[1]).get((("x", int(m[2])),), Fraction(0)),
         f"กระจายผลคูณแล้วอ่านสัมประสิทธิ์ของ x^{m[2]}")


@rule(r"ในการแยกตัวประกอบของ (x\^2 [+-] \d+x [+-] \d+) จำนวนสองจำนวนที่ต้องการคือ "
      r"(-?\d+) กับจำนวนใด")
def _(q, m):
    p = poly_of(m[1])
    b, c = p.get((("x", 1),), Fraction(0)), p.get((), Fraction(0))
    given = Fraction(m[2])
    if given + (b - given) != b or given * (b - given) != c:
        raise NotPlainData(f"{given} ไม่ใช่หนึ่งในคู่จำนวนที่บวกได้ {b} และคูณได้ {c}")
    want(q, b - given, f"อีกจำนวนต้องบวกกับ {given} ได้ {b} และคูณกันได้ {c}")


@rule(r"พหุนาม x\^2 \+ (\d+)x \+ c จะเป็นกำลังสองสมบูรณ์ เมื่อ c")
def _(q, m):
    b = int(m[1])
    if b % 2:
        raise NotPlainData("สัมประสิทธิ์กลางเป็นเลขคี่ กำลังสองสมบูรณ์จะไม่เป็นจำนวนเต็ม")
    want(q, (b // 2) ** 2, "(x + b/2)² ทำให้พจน์คงที่เป็น (b/2)²")


@rule(r"พหุนาม x\^2 \+ bx \+ (\d+) จะเป็นกำลังสองสมบูรณ์ เมื่อ b มีค่าเป็นบวก")
def _(q, m):
    want(q, 2 * isqrt_exact(int(m[1])), "b = 2√c")


@rule(r"พหุนาม x\^3 \+ ax\^2 \+ bx \+ (\d+) หารด้วย x - 1 เหลือเศษ (\d+) และหารด้วย x \+ 1 "
      r"เหลือเศษ (\d+) จงหาค่าของ a \+ b")
def _(q, m):
    c, r1, r2 = (int(m[i]) for i in (1, 2, 3))
    # ทฤษฎีบทเศษเหลือให้สองสมการ: p(1) = 1 + a + b + c = r1 · p(-1) = -1 + a - b + c = r2
    a = Fraction(r1 + r2, 2) - c
    b = Fraction(r1 - r2, 2) - 1
    if 1 + a + b + c != r1 or -1 + a - b + c != r2:
        raise NotPlainData("แก้ a กับ b แล้วยังไม่สอดคล้องกับเศษทั้งสองค่า")
    want(q, a + b, "แก้ระบบสมการจากเศษที่ x = 1 และ x = -1")


@rule(r"แยกตัวประกอบเฉพาะของ (\d+) ได้เป็น .+? จำนวนเฉพาะที่มากที่สุด")
def _(q, m):
    n, big = int(m[1]), 1
    d = 2
    while d * d <= n:
        while n % d == 0:
            n //= d
            big = d
        d += 1
    want(q, max(big, n), "ไล่หารด้วยจำนวนเฉพาะจากน้อยไปมาก")


def bucket(course, q):
    """จัดกลุ่มข้อที่ตรวจซ้ำไม่ได้ เพื่อให้เห็นชัดว่าเหลืออะไรที่ยังต้องเชื่อตัวสร้าง"""
    if course["subject"] != "คณิตศาสตร์":
        return "วิชาอื่น (ตัวตรวจนี้ดูเฉพาะคณิตศาสตร์)"
    if "figure" in q or "[[fig]]" in q["text"]:
        return "ตัวเลขอยู่ในรูป อ่านจากข้อความไม่ได้"
    if 'class="choices' in q["text"]:
        return "ปรนัยเชิงนิยาม/แนวคิด ไม่มีเลขให้คิด"
    # เฉลยที่เป็นข้อความ (เครื่องหมายเปรียบเทียบ · ขั้นตอนการสร้างด้วยวงเวียน · ชื่อสมบัติ)
    # ไม่มีทางคิดใหม่เป็นตัวเลขได้เลย แยกถังไว้เพื่อไม่ให้กองงานดูใหญ่เกินจริง
    # ถังนี้ "ปิดแล้ว" — ไม่ใช่งานค้าง ต่างจากถังที่เหลือซึ่งเขียนกฎเพิ่มได้
    if num(q["answer"]) is None:
        return "เฉลยเป็นข้อความ คิดใหม่เป็นตัวเลขไม่ได้"
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
