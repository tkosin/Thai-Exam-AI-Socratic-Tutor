#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""สร้าง inline SVG สำหรับรูปประกอบข้อสอบ

ทุกฟังก์ชันคืนค่าเป็นสตริง SVG ที่ฝังลงในฟิลด์ `text` ของข้อสอบได้ตรง ๆ
ไม่พึ่งไฟล์หรือฟอนต์ภายนอก และไม่ใช้ CSS จากหน้าเว็บ (กำหนดสีในแท็กเลย)
"""

INK = "#232323"
SOFT = "#5b5952"
NAVY = "#1E3A5F"
GRID = "#d8d4c6"
FONT = "'IBM Plex Sans Thai Looped', sans-serif"

# ชุดสีสำหรับชุดข้อมูล — คุมโทนให้เข้ากับหน้าเว็บและแยกกันได้ชัดเมื่อพิมพ์ขาวดำ
SERIES = ["#1E3A5F", "#E0A83D", "#2F8F6F", "#C0392B", "#7B6CA8", "#4A90A4"]


def _t(x, y, s, size=12, anchor="middle", fill=SOFT, weight="400"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>')


def _wrap(w, h, body, caption=None):
    svg = (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img">{body}</svg>')
    cap = f'<figcaption>{caption}</figcaption>' if caption else ''
    return f'<figure>{svg}{cap}</figure>'


def _nice_ticks(vmax, count=5):
    """เลือกค่าสูงสุดของแกนและระยะขีดให้เป็นเลขกลม"""
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if step * count >= vmax:
            return step * count, step
    step = 10 ** len(str(int(vmax)))
    return step * count, step


# ---------------------------------------------------------------- แผนภูมิแท่ง
def bar_chart(labels, values, y_title="", caption=None, series_names=None, width=520):
    """แผนภูมิแท่ง — values เป็น list ตัวเลข (แท่งเดี่ยว)
    หรือ list ของ list (แท่งเปรียบเทียบ พร้อม series_names)"""
    groups = values if isinstance(values[0], (list, tuple)) else [values]
    n_series = len(groups)
    pad_l, pad_r, pad_t, pad_b = 46, 14, 16, 46
    plot_h = 190
    h = pad_t + plot_h + pad_b + (22 if series_names else 0)
    plot_w = width - pad_l - pad_r
    vmax, step = _nice_ticks(max(max(g) for g in groups))

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    # แกน y + เส้นตาราง
    v = 0
    while v <= vmax:
        y = pad_t + plot_h - (v / vmax) * plot_h
        b.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        b.append(_t(pad_l - 7, y + 4, v, 11, "end"))
        v += step
    b.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    if y_title:
        b.append(f'<g transform="translate(13,{pad_t+plot_h/2}) rotate(-90)">'
                 f'{_t(0,0,y_title,11,"middle",SOFT,"600")}</g>')

    slot = plot_w / len(labels)
    bw = min(30, slot / (n_series + 0.8))
    for i, lab in enumerate(labels):
        cx = pad_l + slot * (i + 0.5)
        total_w = bw * n_series
        for s, g in enumerate(groups):
            bh = (g[i] / vmax) * plot_h
            x = cx - total_w / 2 + s * bw
            y = pad_t + plot_h - bh
            b.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                     f'fill="{SERIES[s]}" rx="2"/>')
            b.append(_t(x + bw / 2, y - 5, g[i], 11, "middle", INK, "600"))
        b.append(_t(cx, pad_t + plot_h + 17, lab, 11.5, "middle", INK))

    if series_names:
        lx = pad_l
        ly = pad_t + plot_h + 40
        for s, nm in enumerate(series_names):
            b.append(f'<rect x="{lx}" y="{ly-9}" width="12" height="12" fill="{SERIES[s]}" rx="2"/>')
            b.append(_t(lx + 17, ly + 1, nm, 11.5, "start", SOFT))
            lx += 22 + len(nm) * 8.5
    return _wrap(width, h, "".join(b), caption)


# ------------------------------------------------------------------ กราฟเส้น
def line_chart(labels, values, y_title="", caption=None, width=520, x_title=""):
    pad_l, pad_r, pad_t, pad_b = 46, 16, 18, 40
    plot_h = 180
    h = 238 + (16 if x_title else 0)
    plot_w = width - pad_l - pad_r
    vmin_data = min(values)
    vmax, step = _nice_ticks(max(values))
    vmin = 0 if vmin_data < step * 2 else (int(vmin_data / step) - 1) * step

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    v = vmin
    while v <= vmax:
        y = pad_t + plot_h - ((v - vmin) / (vmax - vmin)) * plot_h
        b.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        b.append(_t(pad_l - 7, y + 4, v, 11, "end"))
        v += step
    b.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    if y_title:
        b.append(f'<g transform="translate(13,{pad_t+plot_h/2}) rotate(-90)">'
                 f'{_t(0,0,y_title,11,"middle",SOFT,"600")}</g>')

    slot = plot_w / len(labels)
    pts = []
    for i, val in enumerate(values):
        x = pad_l + slot * (i + 0.5)
        y = pad_t + plot_h - ((val - vmin) / (vmax - vmin)) * plot_h
        pts.append((x, y))
        b.append(_t(x, pad_t + plot_h + 17, labels[i], 11.5, "middle", INK))
    b.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
             f'" fill="none" stroke="{SERIES[0]}" stroke-width="2.2" '
             'stroke-linejoin="round" stroke-linecap="round"/>')
    for (x, y), val in zip(pts, values):
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#fff" '
                 f'stroke="{SERIES[0]}" stroke-width="2.2"/>')
        b.append(_t(x, y - 10, val, 11, "middle", INK, "600"))
    if x_title:
        b.append(_t(pad_l + plot_w / 2, pad_t + plot_h + 38, x_title, 11, "middle", SOFT, "600"))
    return _wrap(width, h, "".join(b), caption)


# ------------------------------------------------------------------- เส้นจำนวน
def number_line(lo, hi, marks=None, caption=None, step=1, width=520):
    """เส้นจำนวนจาก lo ถึง hi · marks = {ค่า: 'ป้าย'} จุดที่ต้องการทำเครื่องหมาย"""
    marks = marks or {}
    pad, h = 26, 74
    span = hi - lo
    sx = lambda v: pad + (v - lo) / span * (width - pad * 2)
    y = 40
    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    b.append(f'<line x1="{pad-14}" y1="{y}" x2="{width-pad+14}" y2="{y}" '
             f'stroke="{INK}" stroke-width="1.6"/>')
    for arrow in ((pad - 14, -1), (width - pad + 14, 1)):
        x0, d = arrow
        b.append(f'<polygon points="{x0},{y} {x0-6*d},{y-4} {x0-6*d},{y+4}" fill="{INK}"/>')
    v = lo
    while v <= hi:
        x = sx(v)
        big = v in marks
        b.append(f'<line x1="{x:.1f}" y1="{y-6}" x2="{x:.1f}" y2="{y+6}" '
                 f'stroke="{INK}" stroke-width="{1.6 if big else 1}"/>')
        b.append(_t(x, y + 21, v, 11.5, "middle", INK if big else SOFT))
        v += step
    for v, lab in marks.items():
        x = sx(v)
        b.append(f'<circle cx="{x:.1f}" cy="{y}" r="5.5" fill="{SERIES[3]}"/>')
        b.append(_t(x, y - 13, lab, 13, "middle", SERIES[3], "700"))
    return _wrap(width, h, "".join(b), caption)


# ------------------------------------------------------------- ระนาบพิกัดฉาก
def coord_plane(points, lo=-5, hi=5, caption=None, cell=26):
    """points = {'A': (x, y), ...} วาดจุดบนระนาบพิกัดฉาก"""
    n = hi - lo
    size = n * cell
    pad = 22
    w = h = size + pad * 2
    px = lambda x: pad + (x - lo) * cell
    py = lambda y: pad + (hi - y) * cell
    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for i in range(lo, hi + 1):
        b.append(f'<line x1="{px(i)}" y1="{pad}" x2="{px(i)}" y2="{pad+size}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        b.append(f'<line x1="{pad}" y1="{py(i)}" x2="{pad+size}" y2="{py(i)}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
    b.append(f'<line x1="{pad}" y1="{py(0)}" x2="{pad+size}" y2="{py(0)}" '
             f'stroke="{INK}" stroke-width="1.6"/>')
    b.append(f'<line x1="{px(0)}" y1="{pad}" x2="{px(0)}" y2="{pad+size}" '
             f'stroke="{INK}" stroke-width="1.6"/>')
    for i in range(lo, hi + 1):
        if i == 0:
            continue
        b.append(_t(px(i), py(0) + 13, i, 9.5, "middle", SOFT))
        b.append(_t(px(0) - 8, py(i) + 3.5, i, 9.5, "end", SOFT))
    b.append(_t(pad + size + 8, py(0) + 4, "X", 12, "middle", NAVY, "700"))
    b.append(_t(px(0), pad - 8, "Y", 12, "middle", NAVY, "700"))
    for name, (x, y) in points.items():
        # ป้ายชื่อจุดวางออกด้านนอก (ห่างจากแกน) เพื่อไม่ทับตัวเลขกำกับแกน
        dx = 11 if x >= 0 else -11
        dy = -8 if y >= 0 else 16
        b.append(f'<circle cx="{px(x)}" cy="{py(y)}" r="4.5" fill="{SERIES[3]}"/>')
        b.append(_t(px(x) + dx, py(y) + dy, name, 13, "middle", SERIES[3], "700"))
    return _wrap(w, h, "".join(b), caption)


# ------------------------------------------------- เส้นตรงสองเส้นตัดกัน (มุม)
def intersecting_lines(angle_label, caption=None):
    """เส้นตรงสองเส้นตัดกัน ทำเครื่องหมายมุมหนึ่งมุมด้วย angle_label"""
    w, h, cx, cy, r = 300, 170, 150, 85, 66
    import math
    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for deg in (0, 130):
        a = math.radians(deg)
        dx, dy = r * math.cos(a), -r * math.sin(a)
        b.append(f'<line x1="{cx-dx:.1f}" y1="{cy-dy:.1f}" x2="{cx+dx:.1f}" y2="{cy+dy:.1f}" '
                 f'stroke="{NAVY}" stroke-width="2"/>')
    a1, a2 = 0, math.radians(130)
    ar = 26
    b.append(f'<path d="M {cx+ar} {cy} A {ar} {ar} 0 0 0 '
             f'{cx+ar*math.cos(a2):.1f} {cy-ar*math.sin(a2):.1f}" fill="none" '
             f'stroke="{SERIES[3]}" stroke-width="2"/>')
    b.append(_t(cx + 34, cy - 26, angle_label, 14, "middle", SERIES[3], "700"))
    b.append(_t(cx + 40, cy + 22, "?", 15, "middle", SERIES[0], "700"))
    b.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="{INK}"/>')
    return _wrap(w, h, "".join(b), caption)


# --------------------------------------------------- รูปสามเหลี่ยมพร้อมมุม
def triangle_fig(angle_a, angle_b, angle_c, unknown="B", caption=None):
    """รูปสามเหลี่ยม ABC ที่วาดตามขนาดมุมจริง (A, B อยู่บนฐาน, C เป็นยอด)

    มุมที่ระบุใน `unknown` จะแสดงเป็น "?" — รูปจึงตรงกับตัวเลขที่กำกับไว้เสมอ
    """
    import math
    assert angle_a + angle_b + angle_c == 180, "ผลบวกของมุมภายในต้องเท่ากับ 180 องศา"
    ta, tb = math.tan(math.radians(angle_a)), math.tan(math.radians(angle_b))
    base = 1.0
    cy = base * ta * tb / (ta + tb)      # ความสูงจากฐาน
    cx = cy / ta
    scale = min(232 / base, 190 / cy) if cy > 0 else 232 / base   # คุมทั้งกว้างและสูง
    pts = [(0.0, 0.0), (base * scale, 0.0), (cx * scale, cy * scale)]
    top = max(p[1] for p in pts)
    padx, pady = 44, 30
    w = int(base * scale + padx * 2)
    h = int(top + pady * 2 + 12)
    P = [(x + padx, h - pady - y) for x, y in pts]   # พลิกแกน y ให้ฐานอยู่ล่าง

    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    b.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in P) +
             f'" fill="#f4f2ea" stroke="{NAVY}" stroke-width="2"/>')
    # ป้ายมุม: เยื้องเข้าด้านในรูปจากจุดยอดแต่ละจุด
    cxm = sum(x for x, _ in P) / 3
    cym = sum(y for _, y in P) / 3
    names = "ABC"
    for i, (x, y) in enumerate(P):
        val = (angle_a, angle_b, angle_c)[i]
        is_unknown = names[i] == unknown
        lab = "?" if is_unknown else f"{val}°"
        vx, vy = cxm - x, cym - y
        d = math.hypot(vx, vy) or 1
        b.append(_t(x + vx / d * 36, y + vy / d * 36 + 5, lab, 14, "middle",
                    SERIES[3] if is_unknown else INK, "700"))
        b.append(_t(x - vx / d * 15, y - vy / d * 15 + 5, names[i], 13, "middle", NAVY, "700"))
    return _wrap(w, h, "".join(b), caption)


# ------------------------------------------------------------ แผนภูมิรูปวงกลม
def pie_chart(parts, caption=None, width=470, show_pct=True):
    """parts = [(ชื่อ, ร้อยละ), ...] — ผลรวมต้องเป็น 100"""
    import math
    assert abs(sum(p for _, p in parts) - 100) < 1e-6, "ร้อยละต้องรวมได้ 100"
    r, cx, cy = 86, 104, 106
    h = 212
    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    ang = -90.0
    for i, (name, pct) in enumerate(parts):
        sweep = pct * 3.6
        a1, a2 = math.radians(ang), math.radians(ang + sweep)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        x2, y2 = cx + r * math.cos(a2), cy + r * math.sin(a2)
        large = 1 if sweep > 180 else 0
        b.append(f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 '
                 f'{x2:.1f} {y2:.1f} Z" fill="{SERIES[i]}" stroke="#fff" stroke-width="1.5"/>')
        if show_pct and pct >= 8:
            am = math.radians(ang + sweep / 2)
            b.append(_t(cx + r * 0.62 * math.cos(am), cy + r * 0.62 * math.sin(am) + 4,
                        f"{pct:g}%", 12, "middle", "#fff", "700"))
        ang += sweep
    ly = 34
    for i, (name, pct) in enumerate(parts):
        b.append(f'<rect x="212" y="{ly-10}" width="13" height="13" fill="{SERIES[i]}" rx="2"/>')
        b.append(_t(232, ly + 1, f"{name} ({pct:g}%)", 12.5, "start", INK))
        ly += 25
    return _wrap(width, h, "".join(b), caption)


# ----------------------------------------------------------- แผนภูมิรูปภาพ
def pictograph(rows, unit_label, caption=None, width=500):
    """rows = [(ชื่อแถว, จำนวนรูป), ...] — จำนวนรูปเป็น .5 ได้"""
    row_h, r = 30, 9
    h = 26 + row_h * len(rows) + 10
    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    b.append(_t(8, 15, unit_label, 12, "start", SOFT, "600"))
    for i, (name, cnt) in enumerate(rows):
        y = 30 + row_h * i + row_h / 2
        b.append(_t(8, y + 4, name, 12.5, "start", INK))
        x = 96
        full = int(cnt)
        for _ in range(full):
            b.append(f'<circle cx="{x+r}" cy="{y}" r="{r}" fill="{SERIES[1]}" '
                     f'stroke="{NAVY}" stroke-width="1"/>')
            x += r * 2 + 6
        if cnt - full >= 0.5:   # ครึ่งรูป = ครึ่งหน่วย
            b.append(f'<path d="M {x+r} {y-r} A {r} {r} 0 0 0 {x+r} {y+r} Z" '
                     f'fill="{SERIES[1]}" stroke="{NAVY}" stroke-width="1"/>')
            b.append(f'<path d="M {x+r} {y-r} A {r} {r} 0 0 1 {x+r} {y+r} Z" '
                     f'fill="#fff" stroke="{NAVY}" stroke-width="1"/>')
    return _wrap(width, h, "".join(b), caption)


# --------------------------------------------- ภาพลูกบาศก์ซ้อน (isometric)
def iso_cubes(cells, caption=None, labels=True):
    """cells = [(x, y, z), ...] ตำแหน่งลูกบาศก์หนึ่งหน่วย (z คือความสูง)

    การฉาย: +x ไปขวา-ล่าง, +y ไปซ้าย-ล่าง, +z ขึ้น
    ดังนั้นหน้าที่หันมาทางซ้าย-ล่างคือ "ด้านหน้า" (ภาพด้านหน้า = ระนาบ x-z)
    และหน้าที่หันมาทางขวา-ล่างคือ "ด้านข้าง" (ภาพด้านข้าง = ระนาบ y-z)
    """
    W, H, V = 26.0, 15.0, 30.0
    TOP, LEFT, RIGHT = "#dfe6ee", "#b8c6d4", "#8fa3b8"

    def P(a, b, c):
        return ((a - b) * W, (a + b) * H - c * V)

    pts = [P(a, b, c)
           for (x, y, z) in cells
           for a in (x, x + 1) for b in (y, y + 1) for c in (z, z + 1)]
    minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
    pad = 34 if labels else 12
    ox, oy = pad - minx, 12 - miny
    w = int(maxx - minx + pad * 2)
    h = int(maxy - miny + 12 + (pad if labels else 12))

    def poly(coords, fill):
        d = " ".join(f"{x+ox:.1f},{y+oy:.1f}" for x, y in coords)
        return f'<polygon points="{d}" fill="{fill}" stroke="{NAVY}" stroke-width="1.1"/>'

    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    # วาดจากหลังไปหน้า: (x+y) น้อยอยู่ไกลกว่า, z น้อยอยู่ล่างกว่า
    for (x, y, z) in sorted(cells, key=lambda c: (c[0] + c[1], c[2])):
        b.append(poly([P(x, y, z+1), P(x+1, y, z+1), P(x+1, y+1, z+1), P(x, y+1, z+1)], TOP))
        b.append(poly([P(x, y+1, z+1), P(x+1, y+1, z+1), P(x+1, y+1, z), P(x, y+1, z)], LEFT))
        b.append(poly([P(x+1, y, z+1), P(x+1, y+1, z+1), P(x+1, y+1, z), P(x+1, y, z)], RIGHT))

    if labels:
        b.append(_t(pad - 14, h - 10, "◤ ด้านหน้า", 11.5, "start", NAVY, "600"))
        b.append(_t(w - pad + 14, h - 10, "ด้านข้าง ◥", 11.5, "end", NAVY, "600"))
    return _wrap(w, h, "".join(b), caption)


# ------------------------------------------------------- รูปคลี่ของลูกบาศก์
def cube_net(grid, caption=None, cell=44):
    """grid = {(col, row): 'ตัวอักษรบนหน้า'} — วาดรูปคลี่จากตารางช่องสี่เหลี่ยม"""
    cols = max(c for c, _ in grid) + 1
    rows = max(r for _, r in grid) + 1
    w, h = cols * cell + 16, rows * cell + 16
    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for (c, r), lab in sorted(grid.items()):
        x, y = 8 + c * cell, 8 + r * cell
        b.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="#f4f2ea" '
                 f'stroke="{NAVY}" stroke-width="1.4"/>')
        b.append(_t(x + cell / 2, y + cell / 2 + 6, lab, 17, "middle", NAVY, "700"))
    return _wrap(w, h, "".join(b), caption)
