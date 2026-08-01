#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""สร้างคลังรูปประกอบ -> questions/figures.json

รูปแต่ละรูปมี "ชื่อ" ให้ข้อสอบอ้างถึงด้วยฟิลด์ `figure` แทนการฝัง SVG ซ้ำ ๆ
เมื่อต้องการรูปใหม่ ให้เพิ่มรายการในไฟล์นี้แล้วรัน:

    python3 tools/build_figures.py && python3 tools/build.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg_helpers import (bar_chart, line_chart, pie_chart, pictograph, iso_cubes,
                         cube_net, number_line, coord_plane, intersecting_lines,
                         triangle_fig, parallel_lines, top_view_heights)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "questions", "figures.json")

CAP_PLAN = "แผนผังด้านบน — ตัวเลขคือจำนวนลูกบาศก์ที่วางซ้อนกันในแต่ละตำแหน่ง"
CAP_CUBES = "ลูกบาศก์หนึ่งหน่วยวางซ้อนกัน"

FIGURES = {
    # ── หน่วย 1 · จำนวนเต็ม ──────────────────────────────────────────────
    "number-line-a-b": number_line(-6, 6, {-4: "A", 3: "B"}, "เส้นจำนวน"),

    # ── หน่วย 4 · การสร้างทางเรขาคณิต ───────────────────────────────────
    "intersecting-lines-130": intersecting_lines("130°", "เส้นตรงสองเส้นตัดกัน"),
    "triangle-70-65-45": triangle_fig(70, 65, 45, unknown="B", caption="รูปสามเหลี่ยม ABC"),
    "parallel-lines-70": parallel_lines(70, "เส้นขนานสองเส้นถูกตัดด้วยเส้นตัด"),

    # ── หน่วย 5 · รูปเรขาคณิตสองมิติและสามมิติ ──────────────────────────
    "cubes-solid-a": iso_cubes([(x, y, 0) for x in range(3) for y in range(2)]
                               + [(0, 0, 1), (0, 0, 2)], f"รูป ก &mdash; {CAP_CUBES}"),
    "cubes-solid-b": iso_cubes([(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 0, 1), (2, 0, 1),
                                (2, 0, 2)], f"รูป ข &mdash; {CAP_CUBES}"),
    "cubes-solid-c": iso_cubes([(x, y, 0) for x in range(2) for y in range(2)]
                               + [(0, 0, 1), (1, 0, 1), (0, 0, 2)], f"รูป ค &mdash; {CAP_CUBES}"),
    "cube-net-abcdef": cube_net({(1, 0): "B", (0, 1): "A", (1, 1): "C", (2, 1): "D",
                                 (3, 1): "E", (1, 2): "F"}, "รูปคลี่ของลูกบาศก์"),
    "top-view-3x2": top_view_heights([[3, 1, 2], [1, 2, 1]], CAP_PLAN),
    "top-view-2x2": top_view_heights([[2, 2], [1, 3]], CAP_PLAN),

    # ── หน่วย 8 · กราฟและความสัมพันธ์เชิงเส้น ───────────────────────────
    "coord-plane-abcde": coord_plane({"A": (3, 2), "B": (-2, 4), "C": (-3, -1),
                                      "D": (4, -3), "E": (0, 3)}, caption="ระนาบพิกัดฉาก"),
    "line-distance-time": line_chart(["0", "1", "2", "3", "4", "5"],
                                     [0, 60, 120, 120, 180, 240], "ระยะทาง (กม.)",
                                     "ระยะทางที่รถแล่นได้ในแต่ละช่วงเวลา",
                                     x_title="เวลา (ชั่วโมง)"),
    "line-phone-cost": line_chart(["0", "10", "20", "30", "40"],
                                  [100, 150, 200, 250, 300], "ค่าบริการ (บาท)",
                                  "ค่าบริการโทรศัพท์ตามเวลาที่ใช้",
                                  x_title="เวลาที่ใช้ (นาที)"),

    # ── หน่วย 9 · สถิติ ─────────────────────────────────────────────────
    "pictograph-fruit": pictograph([("มะม่วง", 6), ("ส้ม", 4), ("เงาะ", 3),
                                    ("ทุเรียน", 2), ("ชมพู่", 1)],
                                   "กำหนดให้ 1 รูป แทนนักเรียน 5 คน",
                                   "แผนภูมิรูปภาพแสดงผลไม้ที่นักเรียนชอบ"),
    "bar-late-students": bar_chart(["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"],
                                   [12, 8, 5, 9, 16], "จำนวน (คน)",
                                   "จำนวนนักเรียนที่มาสายในแต่ละวัน"),
    "bar-sports-by-gender": bar_chart(["ฟุตบอล", "วอลเลย์บอล", "แบดมินตัน", "บาสเกตบอล"],
                                      [[18, 8, 10, 12], [6, 14, 12, 8]], "จำนวน (คน)",
                                      "จำนวนนักเรียนที่เลือกเล่นกีฬาแต่ละชนิด จำแนกตามเพศ",
                                      series_names=["ชาย", "หญิง"]),
    "line-temperature-week": line_chart(["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."],
                                        [31, 33, 35, 34, 32, 30, 29], "อุณหภูมิ (°C)",
                                        "อุณหภูมิสูงสุดของแต่ละวันในหนึ่งสัปดาห์"),
    "line-exhibition-visitors": line_chart(["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย."],
                                           [120, 180, 150, 240, 300, 270], "จำนวน (คน)",
                                           "จำนวนผู้เข้าชมนิทรรศการของโรงเรียนในแต่ละเดือน"),
    "pie-travel-to-school": pie_chart([("รถโรงเรียน", 40), ("รถส่วนตัว", 25),
                                       ("เดิน", 20), ("จักรยาน", 15)],
                                      "วิธีเดินทางมาโรงเรียนของนักเรียน 400 คน"),
    "pie-family-expenses": pie_chart([("อาหาร", 35), ("ที่พัก", 30), ("เดินทาง", 15),
                                      ("การศึกษา", 12), ("อื่น ๆ", 8)],
                                     "ค่าใช้จ่ายต่อเดือนของครอบครัวหนึ่ง รวม 20,000 บาท"),
}

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(FIGURES, f, ensure_ascii=False, indent=1)
    total = sum(len(v) for v in FIGURES.values())
    print(f"เขียนรูป {len(FIGURES)} รูป ({total/1024:.1f} KB) -> {OUT}")
