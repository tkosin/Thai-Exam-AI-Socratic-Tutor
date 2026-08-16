#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ทำฟอนต์ฝังในไฟล์สำหรับสำเนาออฟไลน์ -> questions/font-embed.css

README บอกว่าสำเนาชื่อไทยเปิดออฟไลน์ได้ แต่ฟอนต์ IBM Plex Sans Thai Looped
โหลดจาก Google Fonts CDN — เปิดออฟไลน์จริงแล้วฟอนต์ไม่มา ตกไปใช้ sans-serif ของระบบ
สคริปต์นี้ย่อฟอนต์ให้เหลือเฉพาะช่วงอักขระที่ภาษาไทยต้องใช้ แล้วฝัง base64 ไว้ในไฟล์เดียว

**ฝังเฉพาะสำเนาออฟไลน์ ไม่ฝังใน index.html** — หน้าเว็บออนไลน์โหลดจาก CDN ได้อยู่แล้ว
และ base64 ราว 156 KB จะดันหน้าแรกจาก 218 KB เป็น 374 KB ซึ่งกินผลของการแยกข้อมูล
ออกจาก index.html ไปเกือบหมด (2.34 MB -> 0.22 MB) ส่วนสำเนาออฟไลน์ใหญ่ 4.4 MB อยู่แล้ว
เพิ่มอีก 3% จึงไม่มีผลอะไร

ต้องต่อเน็ตและต้องมี fonttools + brotli · รันเมื่อเปลี่ยนน้ำหนักฟอนต์หรือช่วงอักขระ
ผลลัพธ์ commit ไว้ในคลัง `tools/build.py` จึงไม่ต้องต่อเน็ต

    pip install fonttools brotli
    python3 tools/build_font.py && python3 tools/build.py
"""
import base64
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "questions", "font-embed.css")

FAMILY = "IBM Plex Sans Thai Looped"
WEIGHTS = (400, 500, 600, 700)          # ตรงกับ font-weight ที่ CSS ในหน้าเว็บใช้จริง

# ย่อด้วย "ช่วงยูนิโคด" ไม่ใช่ "อักขระที่ข้อสอบใช้อยู่ตอนนี้"
# ถ้าย่อตามอักขระที่ใช้จริง ข้อสอบใหม่ที่มีอักขระนอกชุดจะกลายเป็นสี่เหลี่ยมเปล่า
# โดยไม่มีด่านไหนฟ้อง — เป็นความเสียหายที่เงียบและหาต้นตอยาก
RANGES = ",".join([
    "U+0020-007E", "U+00A0-00FF",                  # ละตินพื้นฐาน
    "U+0E00-0E7F",                                  # ไทยทั้งบล็อก
    "U+2010-2027", "U+2030-205E",                   # เครื่องหมายวรรคตอน
    "U+00D7", "U+00F7", "U+00B0", "U+00B1",         # × ÷ ° ±
    "U+2212", "U+221A", "U+2248", "U+2260",         # − √ ≈ ≠
    "U+2264", "U+2265",                             # ≤ ≥
    "U+03B1", "U+03B2", "U+03B8", "U+03C0",         # α β θ π
    "U+2070-209F",                                  # ตัวยก/ตัวห้อย
])

CSS_URL = ("https://fonts.googleapis.com/css2?family="
           "IBM+Plex+Sans+Thai+Looped:wght@{w}&display=swap")


def fetch(url, binary=False):
    r = subprocess.run(["curl", "-sSL", "-A", "Mozilla/5.0", url],
                       capture_output=True, timeout=120)
    if r.returncode:
        raise SystemExit(f"ดาวน์โหลดไม่สำเร็จ: {url}\n{r.stderr.decode()[:200]}")
    return r.stdout if binary else r.stdout.decode()


def main():
    try:
        from fontTools import subset
        import brotli                                   # noqa: F401 — woff2 ต้องใช้
    except ImportError:
        raise SystemExit("ต้องมี fonttools กับ brotli ก่อน: pip install fonttools brotli")

    faces, total = [], 0
    for w in WEIGHTS:
        css = fetch(CSS_URL.format(w=w))
        m = re.search(r"https://[^)]+\.(?:ttf|woff2)", css)
        if not m:
            raise SystemExit(f"อ่าน URL ของฟอนต์น้ำหนัก {w} จาก CSS ไม่ได้")
        raw = fetch(m.group(0), binary=True)

        src = os.path.join(ROOT, f".font-{w}.tmp")
        dst = os.path.join(ROOT, f".font-{w}.woff2")
        open(src, "wb").write(raw)
        try:
            subset.main([src, f"--unicodes={RANGES}", "--layout-features=*",
                         "--flavor=woff2", f"--output-file={dst}"])
            data = open(dst, "rb").read()
        finally:
            for p in (src, dst):
                if os.path.exists(p):
                    os.remove(p)

        total += len(data)
        b64 = base64.b64encode(data).decode()
        faces.append(
            "@font-face{font-family:'%s';font-style:normal;font-weight:%d;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2');}"
            % (FAMILY, w, b64))
        print(f"  น้ำหนัก {w}: {len(raw)/1024:.0f} KB -> {len(data)/1024:.0f} KB (woff2)")

    header = ("/* สร้างจาก tools/build_font.py — อย่าแก้ด้วยมือ\n"
              "   ฝังเฉพาะในสำเนาออฟไลน์ ไม่ได้อยู่ใน index.html ที่เสิร์ฟออนไลน์ */\n")
    open(OUT, "w", encoding="utf-8").write(header + "\n".join(faces) + "\n")
    print(f"เขียน {OUT} · woff2 รวม {total/1024:.0f} KB "
          f"(base64 ~{total*4/3/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
