#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""สร้าง inline SVG สำหรับรูปประกอบข้อสอบ

ทุกฟังก์ชันคืนค่าเป็นสตริง SVG ที่ฝังลงในฟิลด์ `text` ของข้อสอบได้ตรง ๆ
ไม่พึ่งไฟล์หรือฟอนต์ภายนอก และไม่ใช้ CSS จากหน้าเว็บ (กำหนดสีในแท็กเลย)
"""

import math

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


# ------------------------------------------------ เส้นขนานและเส้นตัด (มุม)
def parallel_lines(given, caption=None):
    """เส้นขนานสองเส้นถูกตัดด้วยเส้นตัด

    ทำเครื่องหมายมุมที่กำหนด (`given`) ที่จุดตัดบน และมุม x (มุมแย้ง)
    กับมุม y (มุมภายในบนข้างเดียวกันของเส้นตัด) ที่จุดตัดล่าง
    """
    import math
    w, h = 340, 178
    y1, y2 = 48, 122
    P1, P2 = (112.0, float(y1)), (206.0, float(y2))
    dx, dy = P2[0] - P1[0], P2[1] - P1[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    ext = 42

    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for y in (y1, y2):
        b.append(f'<line x1="24" y1="{y}" x2="{w-24}" y2="{y}" stroke="{NAVY}" stroke-width="2"/>')
        b.append(f'<polygon points="{w-24},{y} {w-32},{y-4} {w-32},{y+4}" fill="{NAVY}"/>')
        b.append(f'<polygon points="24,{y} 32,{y-4} 32,{y+4}" fill="{NAVY}"/>')
    b.append(f'<line x1="{P1[0]-ux*ext:.1f}" y1="{P1[1]-uy*ext:.1f}" '
             f'x2="{P2[0]+ux*ext:.1f}" y2="{P2[1]+uy*ext:.1f}" '
             f'stroke="{SERIES[0]}" stroke-width="2"/>')

    def arc(V, u1, u2, lab, col, r=24):
        a = (V[0] + u1[0] * r, V[1] + u1[1] * r)
        c = (V[0] + u2[0] * r, V[1] + u2[1] * r)
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        sweep = 1 if cross > 0 else 0
        bx = (u1[0] + u2[0]) / 2
        by = (u1[1] + u2[1]) / 2
        m = math.hypot(bx, by) or 1
        out = [f'<path d="M {a[0]:.1f} {a[1]:.1f} A {r} {r} 0 0 {sweep} {c[0]:.1f} {c[1]:.1f}" '
               f'fill="none" stroke="{col}" stroke-width="2"/>']
        out.append(_t(V[0] + bx / m * 40, V[1] + by / m * 40 + 5, lab, 13.5, "middle", col, "700"))
        return out

    b += arc(P1, (1, 0), (ux, uy), f"{given}°", INK)               # มุมที่กำหนด (ล่าง-ขวาของจุดตัดบน)
    b += arc(P2, (-1, 0), (-ux, -uy), "x", SERIES[3])              # มุมแย้ง (บน-ซ้ายของจุดตัดล่าง)
    b += arc(P2, (1, 0), (-ux, -uy), "y", SERIES[2])               # มุมภายในข้างเดียวกัน
    for P in (P1, P2):
        b.append(f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="3" fill="{INK}"/>')
    return _wrap(w, h, "".join(b), caption)


# --------------------------------- แผนผังด้านบนแสดงจำนวนลูกบาศก์ที่วางซ้อน
def top_view_heights(rows, caption=None, cell=42):
    """rows = [[ความสูงแต่ละตำแหน่ง], ...] แถวแรกคือแถวหลังสุด

    ใช้แทนภาพสามมิติ เมื่อต้องการให้ผู้เรียนสร้างภาพ 3 ด้านจากตัวเลขความสูง
    """
    nr, nc = len(rows), len(rows[0])
    pad_l, pad_t = 14, 14
    w = nc * cell + pad_l * 2 + 92
    h = nr * cell + pad_t + 40
    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            x, y = pad_l + c * cell, pad_t + r * cell
            fill = "#f4f2ea" if v else "#fafaf7"
            b.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" '
                     f'stroke="{NAVY}" stroke-width="1.4"/>')
            b.append(_t(x + cell / 2, y + cell / 2 + 7, v if v else "", 18, "middle", NAVY, "700"))
    base_y = pad_t + nr * cell
    b.append(_t(pad_l + nc * cell / 2, base_y + 24, "▲ ด้านหน้า", 12, "middle", NAVY, "600"))
    b.append(_t(pad_l + nc * cell + 12, pad_t + nr * cell / 2 + 5,
                "◀ ด้านข้าง", 12, "start", NAVY, "600"))
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


# ------------------------------------------- รูปสามเหลี่ยมมุมฉาก (พีทาโกรัส)
def right_triangle(base, height, base_label=None, height_label=None, hyp_label=None,
                   names=("A", "B", "C"), caption=None, box=185):
    """สามเหลี่ยมมุมฉาก วาดตามสัดส่วนจริงของ base:height

    จุดยอด: A บนซ้าย · B ล่างซ้าย (มุมฉาก) · C ล่างขวา
    ป้ายกำกับด้านรับสตริง จึงใส่ทั้งตัวเลข หน่วย หรือเครื่องหมาย ? ได้
    """
    pad_l, pad_r, pad_t, pad_b = 62, 58, 26, 36
    s = box / max(base, height)
    bw, bh = base * s, height * s
    w, h = round(pad_l + bw + pad_r), round(pad_t + bh + pad_b)
    ax, ay = pad_l, pad_t
    bx, by = pad_l, pad_t + bh
    cx, cy = pad_l + bw, pad_t + bh

    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>',
         f'<polygon points="{ax:.1f},{ay:.1f} {bx:.1f},{by:.1f} {cx:.1f},{cy:.1f}" '
         f'fill="#eef1f4" stroke="{NAVY}" stroke-width="2" stroke-linejoin="round"/>']
    m = 13                                   # เครื่องหมายมุมฉากที่จุด B
    b.append(f'<path d="M {bx:.1f} {by-m:.1f} L {bx+m:.1f} {by-m:.1f} L {bx+m:.1f} {by:.1f}" '
             f'fill="none" stroke="{NAVY}" stroke-width="1.6"/>')
    b.append(_t(ax - 12, ay + 3, names[0], 13, "middle", NAVY, "700"))
    b.append(_t(bx - 12, by + 14, names[1], 13, "middle", NAVY, "700"))
    b.append(_t(cx + 12, cy + 14, names[2], 13, "middle", NAVY, "700"))
    if height_label is not None:
        b.append(_t(ax - 9, (ay + by) / 2 + 4, height_label, 13, "end", SERIES[3], "700"))
    if base_label is not None:
        b.append(_t((bx + cx) / 2, by + 21, base_label, 13, "middle", SERIES[3], "700"))
    if hyp_label is not None:
        b.append(_t((ax + cx) / 2 + 15, (ay + cy) / 2 - 5, hyp_label, 13, "middle",
                    SERIES[3], "700"))
    return _wrap(w, h, "".join(b), caption)


# ------------------------------------------ ระนาบพิกัดฉากสำหรับการแปลงเรขาคณิต
def transform_grid(shape, image=None, names=("A", "B", "C", "D", "E"),
                   lo=-6, hi=6, caption=None, cell=21, extra_lines=()):
    """รูปหลายเหลี่ยมต้นแบบและภาพที่ได้จากการแปลง บนระนาบพิกัดฉากเดียวกัน

    shape/image เป็นลิสต์ของจุดยอด [(x, y), ...] · ภาพที่ได้ใช้ชื่อจุดติดเครื่องหมาย '
    extra_lines ใช้วาดแกนสะท้อนที่ไม่ใช่แกน X หรือ Y เช่น (("x", 2),) คือเส้น x = 2
    """
    n = hi - lo
    size = n * cell
    pad = 20
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
        if i == 0 or i % 2:
            continue
        b.append(_t(px(i), py(0) + 12, i, 9, "middle", SOFT))
        b.append(_t(px(0) - 7, py(i) + 3.5, i, 9, "end", SOFT))
    b.append(_t(pad + size + 8, py(0) + 4, "X", 12, "middle", NAVY, "700"))
    b.append(_t(px(0), pad - 8, "Y", 12, "middle", NAVY, "700"))

    for axis, at in extra_lines:                  # แกนสะท้อนที่กำหนดเอง
        if axis == "x":
            b.append(f'<line x1="{px(at)}" y1="{pad}" x2="{px(at)}" y2="{pad+size}" '
                     f'stroke="{SERIES[4]}" stroke-width="1.8" stroke-dasharray="6 4"/>')
            b.append(_t(px(at), pad - 8, f"x = {at}", 11, "middle", SERIES[4], "700"))
        else:
            b.append(f'<line x1="{pad}" y1="{py(at)}" x2="{pad+size}" y2="{py(at)}" '
                     f'stroke="{SERIES[4]}" stroke-width="1.8" stroke-dasharray="6 4"/>')
            b.append(_t(pad + size - 18, py(at) - 6, f"y = {at}", 11, "middle", SERIES[4], "700"))

    def poly(pts, color, dashed, tag):
        d = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pts)
        dash = ' stroke-dasharray="7 4"' if dashed else ''
        b.append(f'<polygon points="{d}" fill="{color}" fill-opacity="0.14" '
                 f'stroke="{color}" stroke-width="2" stroke-linejoin="round"{dash}/>')
        for i, (x, y) in enumerate(pts):
            b.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.4" fill="{color}"/>')
            dx = 11 if x >= 0 else -11
            dy = -8 if y >= 0 else 15
            b.append(_t(px(x) + dx, py(y) + dy, names[i] + tag, 12, "middle", color, "700"))

    poly(shape, NAVY, False, "")
    if image:
        poly(image, SERIES[3], True, "&#8242;")
    return _wrap(w, h, "".join(b), caption)


# ---------------------------------------- ทรงสี่เหลี่ยมมุมฉาก / ปริซึมสี่เหลี่ยม
def prism_box(width_label=None, depth_label=None, height_label=None, caption=None,
              fw=150, fh=100, dx=52, dy=36):
    """ทรงสี่เหลี่ยมมุมฉากแบบภาพเฉียง — เส้นที่ถูกบังวาดเป็นเส้นประ"""
    pad_l, pad_t, pad_r, pad_b = 68, 22, 52, 36
    w, h = round(pad_l + fw + dx + pad_r), round(pad_t + dy + fh + pad_b)
    x0, y0 = pad_l, pad_t + dy                       # มุมบนซ้ายของหน้าด้านหน้า
    f = [(x0, y0), (x0 + fw, y0), (x0 + fw, y0 + fh), (x0, y0 + fh)]
    k = [(x + dx, y - dy) for x, y in f]             # หน้าด้านหลัง

    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    b.append(f'<polygon points="{f[0][0]},{f[0][1]} {k[0][0]},{k[0][1]} '
             f'{k[1][0]},{k[1][1]} {f[1][0]},{f[1][1]}" fill="#dfe5ec" '
             f'stroke="{NAVY}" stroke-width="1.8" stroke-linejoin="round"/>')
    b.append(f'<polygon points="{f[1][0]},{f[1][1]} {k[1][0]},{k[1][1]} '
             f'{k[2][0]},{k[2][1]} {f[2][0]},{f[2][1]}" fill="#cfd8e3" '
             f'stroke="{NAVY}" stroke-width="1.8" stroke-linejoin="round"/>')
    b.append(f'<polygon points="{f[0][0]},{f[0][1]} {f[1][0]},{f[1][1]} '
             f'{f[2][0]},{f[2][1]} {f[3][0]},{f[3][1]}" fill="#eef1f4" '
             f'stroke="{NAVY}" stroke-width="2" stroke-linejoin="round"/>')
    hidden = (f'M {k[3][0]},{k[3][1]} L {k[0][0]},{k[0][1]} '
              f'M {k[3][0]},{k[3][1]} L {k[2][0]},{k[2][1]} '
              f'M {k[3][0]},{k[3][1]} L {f[3][0]},{f[3][1]}')
    b.append(f'<path d="{hidden}" fill="none" stroke="{NAVY}" stroke-width="1.2" '
             f'stroke-dasharray="5 4" opacity="0.55"/>')

    if width_label is not None:
        b.append(_t(x0 + fw / 2, y0 + fh + 21, width_label, 12.5, "middle", SERIES[3], "700"))
    if height_label is not None:
        b.append(_t(x0 - 8, y0 + fh / 2 + 4, height_label, 12.5, "end", SERIES[3], "700"))
    if depth_label is not None:
        b.append(_t(x0 + fw + dx / 2 + 16, y0 + fh - dy / 2 + 14, depth_label, 12.5,
                    "middle", SERIES[3], "700"))
    return _wrap(w, h, "".join(b), caption)


# ------------------------------------------------------------------ ทรงกระบอก
def cylinder_fig(radius_label=None, height_label=None, caption=None,
                 rw=64, ry=20, ch=130):
    """ทรงกระบอกตั้ง — ขอบฐานที่ถูกบังวาดเป็นเส้นประ · รัศมีชี้จากจุดศูนย์กลางฝาบน"""
    pad_l, pad_t, pad_r, pad_b = 86, 34, 62, 32
    w, h = round(pad_l + rw * 2 + pad_r), round(pad_t + ry + ch + ry + pad_b)
    cx = pad_l + rw
    ty = pad_t + ry
    by = ty + ch

    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    b.append(f'<path d="M {cx-rw},{ty} L {cx-rw},{by} A {rw},{ry} 0 0 0 {cx+rw},{by} '
             f'L {cx+rw},{ty} Z" fill="#eef1f4" stroke="{NAVY}" stroke-width="2"/>')
    b.append(f'<path d="M {cx-rw},{by} A {rw},{ry} 0 0 1 {cx+rw},{by}" fill="none" '
             f'stroke="{NAVY}" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.55"/>')
    b.append(f'<ellipse cx="{cx}" cy="{ty}" rx="{rw}" ry="{ry}" fill="#dfe5ec" '
             f'stroke="{NAVY}" stroke-width="2"/>')
    if radius_label is not None:
        b.append(f'<line x1="{cx}" y1="{ty}" x2="{cx+rw}" y2="{ty}" stroke="{SERIES[3]}" '
                 f'stroke-width="1.8"/>')
        b.append(f'<circle cx="{cx}" cy="{ty}" r="2.6" fill="{SERIES[3]}"/>')
        b.append(_t(cx + rw / 2, ty - ry - 9, radius_label, 12.5, "middle", SERIES[3], "700"))
    if height_label is not None:
        b.append(f'<line x1="{cx-rw-13}" y1="{ty}" x2="{cx-rw-13}" y2="{by}" '
                 f'stroke="{SERIES[3]}" stroke-width="1.4"/>')
        b.append(_t(cx - rw - 17, (ty + by) / 2 + 4, height_label, 12.5, "end",
                    SERIES[3], "700"))
    return _wrap(w, h, "".join(b), caption)


# ------------------------------------------------------------------ แผนภาพจุด
def dot_plot(values, caption=None, x_title="", width=520):
    """แผนภาพจุด — จุดหนึ่งจุดแทนข้อมูลหนึ่งค่า วางซ้อนขึ้นไปตามความถี่"""
    lo, hi = min(values), max(values)
    counts = {v: values.count(v) for v in range(lo, hi + 1)}
    peak = max(counts.values())
    pad_l, pad_r, pad_b = 26, 26, 40
    plot_w = width - pad_l - pad_r
    gap = plot_w / max(hi - lo, 1)
    r, step = 5.2, 13
    h = round(24 + peak * step + pad_b)
    axis_y = h - pad_b
    px = lambda v: pad_l + (v - lo) * gap

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>',
         f'<line x1="{pad_l-14}" y1="{axis_y}" x2="{pad_l+plot_w+14}" y2="{axis_y}" '
         f'stroke="{INK}" stroke-width="1.5"/>']
    for v in range(lo, hi + 1):
        x = px(v)
        b.append(f'<line x1="{x:.1f}" y1="{axis_y}" x2="{x:.1f}" y2="{axis_y+5}" '
                 f'stroke="{INK}" stroke-width="1.2"/>')
        b.append(_t(x, axis_y + 19, v, 11, "middle", SOFT))
        for i in range(counts[v]):
            b.append(f'<circle cx="{x:.1f}" cy="{axis_y-9-i*step:.1f}" r="{r}" '
                     f'fill="{NAVY}"/>')
    if x_title:
        b.append(_t(pad_l + plot_w / 2, axis_y + 34, x_title, 11.5, "middle", SOFT, "600"))
    return _wrap(width, h, "".join(b), caption)


# ------------------------------------------------------------------ ฮิสโทแกรม
def histogram(labels, freqs, y_title="", caption=None, x_title="", width=520):
    """ฮิสโทแกรม — แท่งติดกันเพราะข้อมูลต่อเนื่อง ต่างจากแผนภูมิแท่งที่แท่งแยกกัน"""
    pad_l, pad_r, pad_t, pad_b = 46, 16, 16, 52
    plot_h, plot_w = 190, width - pad_l - pad_r
    h = pad_t + plot_h + pad_b
    vmax, step = _nice_ticks(max(freqs))

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    v = 0
    while v <= vmax:
        y = pad_t + plot_h - (v / vmax) * plot_h
        b.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        b.append(_t(pad_l - 7, y + 4, v, 11, "end"))
        v += step
    bw = plot_w / len(freqs)
    for i, fq in enumerate(freqs):
        bh = (fq / vmax) * plot_h
        x = pad_l + i * bw
        b.append(f'<rect x="{x:.1f}" y="{pad_t+plot_h-bh:.1f}" width="{bw:.1f}" '
                 f'height="{bh:.1f}" fill="{NAVY}" fill-opacity="0.82" '
                 f'stroke="#fff" stroke-width="1"/>')
        b.append(_t(x + bw / 2, pad_t + plot_h - bh - 6, fq, 11, "middle", NAVY, "700"))
        b.append(_t(x + bw / 2, pad_t + plot_h + 16, labels[i], 10.5, "middle", SOFT))
    b.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" '
             f'y2="{pad_t+plot_h}" stroke="{INK}" stroke-width="1.5"/>')
    if y_title:
        b.append(f'<g transform="translate(13,{pad_t+plot_h/2}) rotate(-90)">'
                 f'{_t(0,0,y_title,11,"middle",SOFT,"600")}</g>')
    if x_title:
        b.append(_t(pad_l + plot_w / 2, h - 12, x_title, 11.5, "middle", SOFT, "600"))
    return _wrap(width, h, "".join(b), caption)


# --------------------------------------------------------------- แผนภาพกล่อง
def _axis_span(vmin, vmax):
    """เลือกช่วงและระยะขีดของแกนให้ครอบข้อมูล โดยขีดเป็นเลขกลมและมี 5-12 ช่อง"""
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        lo = (vmin // step) * step
        hi = -((-vmax) // step) * step
        if lo == hi:
            hi = lo + step
        if 5 <= (hi - lo) / step <= 12:
            return lo, hi, step
    step = 10 ** max(len(str(int(vmax))) - 1, 1)
    return (vmin // step) * step, -((-vmax) // step) * step + step, step


def box_plot(five, caption=None, x_title="", width=520, outliers=()):
    """แผนภาพกล่อง — ค่าต่ำสุด, Q1, มัธยฐาน, Q3, ค่าสูงสุด บนแกนเดียวกัน

    ตั้งใจ**ไม่**พิมพ์ตัวเลขห้าค่ากำกับไว้บนรูป เพราะโจทย์ ม.3 คือการอ่านค่าจากแกน
    ถ้าเขียนคำตอบไว้บนรูปเสียแล้วก็ไม่เหลืออะไรให้อ่าน
    ค่านอกเกณฑ์วาดเป็นจุดแยกออกมา หนวดจึงลากถึงแค่ค่าสุดท้ายที่ยังอยู่ในเกณฑ์
    """
    lo_v, q1, med, q3, hi_v = five
    pad_l, pad_r, pad_t, pad_b = 30, 30, 22, 46
    plot_w = width - pad_l - pad_r
    box_h, h = 44, 22 + 44 + 46
    mid = pad_t + box_h / 2
    axis_y = h - pad_b + 6
    lo, hi, step = _axis_span(min([lo_v] + list(outliers)), max([hi_v] + list(outliers)))
    px = lambda v: pad_l + (v - lo) / (hi - lo) * plot_w

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    v = lo
    while v <= hi:                              # เส้นตารางแนวตั้งช่วยกวาดสายตาจากแกนขึ้นมา
        b.append(f'<line x1="{px(v):.1f}" y1="{pad_t-6}" x2="{px(v):.1f}" y2="{axis_y}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        v += step
    for a, z in ((lo_v, q1), (q3, hi_v)):       # หนวดซ้าย-ขวา
        b.append(f'<line x1="{px(a):.1f}" y1="{mid:.1f}" x2="{px(z):.1f}" y2="{mid:.1f}" '
                 f'stroke="{INK}" stroke-width="1.5"/>')
    for v in (lo_v, hi_v):                      # ขีดปิดปลายหนวด
        b.append(f'<line x1="{px(v):.1f}" y1="{pad_t+9:.1f}" x2="{px(v):.1f}" '
                 f'y2="{pad_t+box_h-9:.1f}" stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<rect x="{px(q1):.1f}" y="{pad_t}" width="{px(q3)-px(q1):.1f}" '
             f'height="{box_h}" fill="{NAVY}" fill-opacity="0.16" stroke="{NAVY}" '
             f'stroke-width="1.6"/>')
    b.append(f'<line x1="{px(med):.1f}" y1="{pad_t}" x2="{px(med):.1f}" '
             f'y2="{pad_t+box_h}" stroke="{NAVY}" stroke-width="2.6"/>')
    for v in outliers:
        b.append(f'<circle cx="{px(v):.1f}" cy="{mid:.1f}" r="4" fill="#fff" '
                 f'stroke="{INK}" stroke-width="1.4"/>')
    b.append(f'<line x1="{pad_l-10}" y1="{axis_y}" x2="{pad_l+plot_w+10}" y2="{axis_y}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    v = lo
    while v <= hi:
        b.append(f'<line x1="{px(v):.1f}" y1="{axis_y}" x2="{px(v):.1f}" y2="{axis_y+5}" '
                 f'stroke="{INK}" stroke-width="1.2"/>')
        b.append(_t(px(v), axis_y + 19, v, 11, "middle", SOFT))
        v += step
    if x_title:
        b.append(_t(pad_l + plot_w / 2, h - 4, x_title, 11.5, "middle", SOFT, "600"))
    return _wrap(width, h, "".join(b), caption)


# ============================================================================
# คณิตศาสตร์ ม.3 — อสมการ · กราฟ · รูปทรงสามมิติ · ความคล้าย · วงกลม
# ============================================================================

DASH = 'stroke-dasharray="5 4"'
FILL = f'fill="#eef1f4" stroke="{NAVY}" stroke-width="2" stroke-linejoin="round"'


def _dim_v(x, y0, y1, label):
    """เส้นบอกระยะแนวตั้งพร้อมขีดปิดหัวท้าย — ใช้บอกความสูงของรูปทรงสามมิติ

    ความสูงของพีระมิด/กรวยเป็นเส้นที่อยู่ "ข้างใน" รูป ป้ายกำกับจึงชนเส้นอื่นเสมอ
    วาดเป็นเส้นบอกระยะไว้ข้างนอกแบบหนังสือเรียนแทน
    """
    t = 5
    return (f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" '
            f'stroke="{SERIES[3]}" stroke-width="1.4"/>'
            + "".join(f'<line x1="{x-t:.1f}" y1="{yy:.1f}" x2="{x+t:.1f}" y2="{yy:.1f}" '
                      f'stroke="{SERIES[3]}" stroke-width="1.4"/>' for yy in (y0, y1))
            + _lab(x - 8, (y0 + y1) / 2 + 4, label, anchor="end"))


def _lab(x, y, s, size=13, anchor="middle"):
    """ป้ายกำกับความยาว/มุม ใช้สีเดียวกันทุกรูปเพื่อให้ผู้เรียนจับได้ว่าอันไหนคือ "ตัวเลขที่ให้มา" """
    return _t(x, y, s, size, anchor, SERIES[3], "700")


# ------------------------------------------------- เส้นจำนวนแสดงคำตอบของอสมการ
def ineq_line(lo, hi, point, op, caption=None, width=520, step=1):
    """เส้นจำนวนที่แรเงาช่วงคำตอบของอสมการ · op = '<' '≤' '>' '≥'

    จุดปลายเป็นวงกลมโปร่ง = ไม่รวมค่านั้น (< >) · ทึบ = รวม (≤ ≥)
    ซึ่งเป็นจุดที่ผู้เรียน ม.3 พลาดบ่อยที่สุดของหน่วยนี้
    """
    pad, h, y = 30, 82, 42
    sx = lambda v: pad + (v - lo) / (hi - lo) * (width - pad * 2)
    right = op in (">", "≥")
    closed = op in ("≤", "≥")
    x0, end = sx(point), (width - pad + 12) if right else (pad - 12)

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    b.append(f'<line x1="{x0:.1f}" y1="{y}" x2="{end:.1f}" y2="{y}" '
             f'stroke="{SERIES[3]}" stroke-width="5" stroke-opacity="0.45"/>')
    b.append(f'<line x1="{pad-16}" y1="{y}" x2="{width-pad+16}" y2="{y}" '
             f'stroke="{INK}" stroke-width="1.6"/>')
    for x1, d in ((pad - 16, -1), (width - pad + 16, 1)):
        b.append(f'<polygon points="{x1},{y} {x1-6*d},{y-4} {x1-6*d},{y+4}" fill="{INK}"/>')
    v = lo
    while v <= hi:
        x = sx(v)
        b.append(f'<line x1="{x:.1f}" y1="{y-6}" x2="{x:.1f}" y2="{y+6}" '
                 f'stroke="{INK}" stroke-width="1"/>')
        b.append(_t(x, y + 22, v, 11.5, "middle", SOFT))
        v += step
    b.append(f'<circle cx="{x0:.1f}" cy="{y}" r="6" '
             + (f'fill="{SERIES[3]}"/>' if closed
                else f'fill="#fff" stroke="{SERIES[3]}" stroke-width="2.4"/>'))
    return _wrap(width, h, "".join(b), caption)


# ------------------------------------------------------- กราฟฟังก์ชันกำลังสอง
def parabola(a, b, c, caption=None, lo=None, hi=None, cell=24, mark_vertex=True):
    """กราฟ y = ax² + bx + c พร้อมทำเครื่องหมายจุดยอด

    ช่วงแกน x เลือกจากความชันของกราฟเอง — พาราโบลาที่ |a| มาก ชันเร็ว ต้องมองช่วงแคบ
    ไม่งั้นได้กราฟผอมสูงที่ดูไม่ออกว่าจุดยอดอยู่ตรงไหน
    """
    vx0 = -b / (2 * a)
    if lo is None or hi is None:
        d = max(3, min(7, round(math.sqrt(9 / abs(a)))))
        lo, hi = round(vx0) - d, round(vx0) + d
    xs = [lo + i / 8 for i in range(int((hi - lo) * 8) + 1)]
    f = lambda x: a * x * x + b * x + c
    vx = -b / (2 * a)
    # ตรึงกรอบไว้ 12 ช่องแล้ววางให้จุดยอดอยู่ใกล้ขอบด้านที่กราฟเปิดออก
    # ถ้าปล่อยให้กรอบยืดตามค่าสูงสุดจริง กราฟที่ |a| มากจะกลายเป็นเส้นผอมสูงจนดูไม่ออก
    vy = f(vx)
    if a > 0:
        ylo = math.floor(vy) - 1
        yhi = ylo + 12
    else:
        yhi = math.ceil(vy) + 1
        ylo = yhi - 12

    pad = 24
    w = (hi - lo) * cell + pad * 2
    h = (yhi - ylo) * cell + pad * 2
    px = lambda x: pad + (x - lo) * cell
    py = lambda y: pad + (yhi - y) * cell

    g = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for i in range(lo, hi + 1):
        g.append(f'<line x1="{px(i):.1f}" y1="{pad}" x2="{px(i):.1f}" y2="{h-pad}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
    for j in range(ylo, yhi + 1):
        g.append(f'<line x1="{pad}" y1="{py(j):.1f}" x2="{w-pad}" y2="{py(j):.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
    if ylo <= 0 <= yhi:
        g.append(f'<line x1="{pad}" y1="{py(0):.1f}" x2="{w-pad}" y2="{py(0):.1f}" '
                 f'stroke="{INK}" stroke-width="1.6"/>')
    if lo <= 0 <= hi:
        g.append(f'<line x1="{px(0):.1f}" y1="{pad}" x2="{px(0):.1f}" y2="{h-pad}" '
                 f'stroke="{INK}" stroke-width="1.6"/>')
    for i in range(lo, hi + 1):
        if i and ylo <= 0 <= yhi:
            g.append(_t(px(i), py(0) + 13, i, 9.5, "middle", SOFT))
    for j in range(ylo, yhi + 1):
        if j and lo <= 0 <= hi:
            g.append(_t(px(0) - 7, py(j) + 3.5, j, 9.5, "end", SOFT))

    pts = [(px(x), py(f(x))) for x in xs if ylo - 0.5 <= f(x) <= yhi + 0.5]
    g.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
             + f'" fill="none" stroke="{NAVY}" stroke-width="2.4" stroke-linejoin="round"/>')
    if mark_vertex and lo <= vx <= hi and ylo <= f(vx) <= yhi:
        g.append(f'<circle cx="{px(vx):.1f}" cy="{py(f(vx)):.1f}" r="4.5" fill="{SERIES[3]}"/>')
    return _wrap(round(w), round(h), "".join(g), caption)


# --------------------------------------------- เส้นตรงสองเส้นบนระนาบเดียวกัน
def two_lines(lines, caption=None, lo=-6, hi=6, cell=24, mark_cross=True):
    """lines = [(m, c, 'ชื่อเส้น'), ...] วาด y = mx + c หลายเส้นบนระนาบเดียวกัน

    ใช้กับระบบสมการเชิงเส้นสองตัวแปร — จุดตัดคือคำตอบของระบบ
    """
    pad = 26
    size = (hi - lo) * cell
    w = h = size + pad * 2
    px = lambda x: pad + (x - lo) * cell
    py = lambda y: pad + (hi - y) * cell
    clip = lambda y: max(lo, min(hi, y))

    g = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for i in range(lo, hi + 1):
        g.append(f'<line x1="{px(i)}" y1="{pad}" x2="{px(i)}" y2="{pad+size}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        g.append(f'<line x1="{pad}" y1="{py(i)}" x2="{pad+size}" y2="{py(i)}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
    g.append(f'<line x1="{pad}" y1="{py(0)}" x2="{pad+size}" y2="{py(0)}" '
             f'stroke="{INK}" stroke-width="1.6"/>')
    g.append(f'<line x1="{px(0)}" y1="{pad}" x2="{px(0)}" y2="{pad+size}" '
             f'stroke="{INK}" stroke-width="1.6"/>')
    for i in range(lo, hi + 1):
        if i:
            g.append(_t(px(i), py(0) + 13, i, 9.5, "middle", SOFT))
            g.append(_t(px(0) - 7, py(i) + 3.5, i, 9.5, "end", SOFT))
    g.append(_t(pad + size + 9, py(0) + 4, "X", 12, "middle", NAVY, "700"))
    g.append(_t(px(0), pad - 9, "Y", 12, "middle", NAVY, "700"))

    for k, (m, c, name) in enumerate(lines):
        col = SERIES[k % len(SERIES)]
        pts = [(x / 4, m * x / 4 + c) for x in range(lo * 4, hi * 4 + 1)]
        pts = [(px(x), py(y)) for x, y in pts if lo <= y <= hi]
        if not pts:
            continue
        g.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                 + f'" fill="none" stroke="{col}" stroke-width="2.4"/>')
        ex, ey = pts[-1]
        g.append(_t(min(ex + 4, w - 12), max(ey - 7, pad + 10), name, 12, "middle", col, "700"))

    if mark_cross and len(lines) == 2:
        (m1, c1, _), (m2, c2, _) = lines
        if m1 != m2:
            x = (c2 - c1) / (m1 - m2)
            y = m1 * x + c1
            if lo <= x <= hi and lo <= y <= hi:
                g.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="5" fill="#fff" '
                         f'stroke="{INK}" stroke-width="2.2"/>')
    return _wrap(w, h, "".join(g), caption)


# ------------------------------------------------------ พีระมิด กรวย ทรงกลม
def pyramid_fig(base_label=None, slant_label=None, height_label=None, caption=None,
                height=230):
    """พีระมิดฐานสี่เหลี่ยมจัตุรัส · เส้นที่ถูกบัง (ขอบหลังกับสันสูงตรง) วาดเป็นเส้นประ"""
    bw, ox, oy, top = 150, 52, 34, 34
    left = 96 if height_label else 46      # เผื่อที่ให้เส้นบอกระยะความสูงด้านซ้าย
    width = 254 + left
    x0, y0 = left, height - 46
    A, B = (x0, y0), (x0 + bw, y0)
    C, D = (x0 + bw + ox, y0 - oy), (x0 + ox, y0 - oy)
    cx, cy = (A[0] + C[0]) / 2, (A[1] + C[1]) / 2
    E = (cx, top)

    line = lambda p, q, extra="": (f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" '
                                   f'x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="{NAVY}" '
                                   f'stroke-width="2" {extra}/>')
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<polygon points="{A[0]:.0f},{A[1]:.0f} {B[0]:.0f},{B[1]:.0f} {E[0]:.0f},{E[1]:.0f}" '
         f'{FILL}/>',
         f'<polygon points="{B[0]:.0f},{B[1]:.0f} {C[0]:.0f},{C[1]:.0f} {E[0]:.0f},{E[1]:.0f}" '
         f'fill="#dde3ea" stroke="{NAVY}" stroke-width="2" stroke-linejoin="round"/>']
    g += [line(A, D, DASH), line(D, C, DASH), line(D, E, DASH),
          line(A, B), line(B, C), line(A, E), line(C, E)]
    g.append(line((cx, cy), E, DASH))                       # ความสูงของพีระมิด
    g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.6" fill="{NAVY}"/>')
    if height_label:                      # เส้นบอกระยะนอกตัวรูป — ในรูปมันชนเส้นประเสมอ
        g.append(_dim_v(A[0] - 28, top, cy, height_label))
    if base_label:
        g.append(_lab((A[0] + B[0]) / 2, y0 + 20, base_label))
    if slant_label:                       # สันเอียงอยู่ขอบขวาของรูป วางป้ายไว้นอกตัวพีระมิด
        g.append(_lab(C[0] + 4, (B[1] + E[1]) / 2 - 4, slant_label, anchor="start"))
    return _wrap(width, height, "".join(g), caption)


def cone_fig(radius_label=None, height_label=None, slant_label=None, caption=None,
             height=240):
    """กรวยกลมตรง · ครึ่งหลังของฐานเป็นเส้นประเพราะถูกตัวกรวยบัง"""
    rx, ry, top = 78, 24, 30
    left = 92 if height_label else 30      # เผื่อที่ให้เส้นบอกระยะความสูงด้านซ้าย
    width = left + rx * 2 + 58
    cx, cy = left + rx, height - 62
    L, R, T = (cx - rx, cy), (cx + rx, cy), (cx, top)
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<path d="M {L[0]:.1f} {L[1]:.1f} L {T[0]:.1f} {T[1]:.1f} L {R[0]:.1f} {R[1]:.1f} '
         f'A {rx} {ry} 0 0 1 {L[0]:.1f} {L[1]:.1f} Z" {FILL}/>',
         f'<path d="M {L[0]:.1f} {L[1]:.1f} A {rx} {ry} 0 0 1 {R[0]:.1f} {R[1]:.1f}" '
         f'fill="none" stroke="{NAVY}" stroke-width="1.6" {DASH}/>',
         f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{top}" stroke="{NAVY}" '
         f'stroke-width="1.6" {DASH}/>',
         f'<line x1="{cx}" y1="{cy}" x2="{R[0]:.1f}" y2="{cy}" stroke="{NAVY}" '
         f'stroke-width="1.6" {DASH}/>']
    m = 11
    g.append(f'<path d="M {cx} {cy-m} L {cx+m} {cy-m} L {cx+m} {cy}" fill="none" '
             f'stroke="{NAVY}" stroke-width="1.4"/>')
    if radius_label:                      # ใต้ฐาน ไม่ให้ทับเส้นวงรี
        g.append(_lab(cx + rx / 2, cy + ry + 18, radius_label))
    if height_label:
        g.append(_dim_v(cx - rx - 20, top, cy, height_label))
    if slant_label:                       # สันเอียงอยู่ขอบขวา วางป้ายนอกตัวกรวย
        g.append(_lab(R[0] - 2, (cy + top) / 2 + 6, slant_label, anchor="start"))
    return _wrap(width, height, "".join(g), caption)


def sphere_fig(radius_label=None, caption=None, width=250, height=220):
    """ทรงกลม · เส้นศูนย์สูตรวาดครึ่งหน้าทึบ ครึ่งหลังประ ให้เห็นว่าเป็นทรงกลมไม่ใช่วงกลม"""
    cx, cy, r = width / 2, height / 2, 78
    ry = r * 0.3
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{r}" {FILL}/>',
         f'<path d="M {cx-r} {cy} A {r} {ry} 0 0 0 {cx+r} {cy}" fill="none" '
         f'stroke="{NAVY}" stroke-width="1.6"/>',
         f'<path d="M {cx-r} {cy} A {r} {ry} 0 0 1 {cx+r} {cy}" fill="none" '
         f'stroke="{NAVY}" stroke-width="1.6" {DASH}/>',
         f'<line x1="{cx}" y1="{cy}" x2="{cx+r*0.71:.1f}" y2="{cy-r*0.71:.1f}" '
         f'stroke="{SERIES[3]}" stroke-width="2"/>',
         f'<circle cx="{cx}" cy="{cy}" r="2.8" fill="{NAVY}"/>']
    if radius_label:                      # ดันออกไปนอกวงกลม ไม่ให้ทับเส้นศูนย์สูตร
        g.append(_lab(cx + r * 0.71 + 20, cy - r * 0.71 - 8, radius_label))
    return _wrap(width, height, "".join(g), caption)


# -------------------------------------------------------------------- ความคล้าย
def similar_triangles(sides_a, sides_b, labels_a, labels_b, caption=None,
                      names=("A", "B", "C"), names2=("D", "E", "F"), box=120):
    """รูปสามเหลี่ยมคล้ายสองรูปวางเทียบกัน — sides = (ฐาน, สูง) ใช้กำหนดรูปร่างที่วาด

    วาดสองรูปด้วยสัดส่วนจริง ผู้เรียนจึงเห็นได้เองว่า "รูปร่างเดียวกัน ขนาดต่างกัน"
    """
    gap, pad_t, pad_b, pad_x = 54, 30, 40, 40
    scale = box / max(max(sides_a), max(sides_b))
    tri = lambda s: (s[0] * scale, s[1] * scale)
    (w1, h1), (w2, h2) = tri(sides_a), tri(sides_b)
    w = round(pad_x * 2 + w1 + gap + w2)
    h = round(pad_t + max(h1, h2) + pad_b)
    base_y = h - pad_b

    g = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for x0, (bw, bh), nm, labs in ((pad_x, (w1, h1), names, labels_a),
                                   (pad_x + w1 + gap, (w2, h2), names2, labels_b)):
        apex = (x0 + bw * 0.34, base_y - bh)
        p = [(x0, base_y), (x0 + bw, base_y), apex]
        g.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in p)
                 + f'" {FILL}/>')
        g.append(_t(p[0][0] - 11, base_y + 14, nm[0], 13, "middle", NAVY, "700"))
        g.append(_t(p[1][0] + 11, base_y + 14, nm[1], 13, "middle", NAVY, "700"))
        g.append(_t(apex[0], apex[1] - 9, nm[2], 13, "middle", NAVY, "700"))
        if labs[0]:                       # ป้ายฐาน
            g.append(_lab((p[0][0] + p[1][0]) / 2, base_y + 21, labs[0]))
        if len(labs) > 1 and labs[1]:     # ป้ายด้านซ้าย
            g.append(_lab((p[0][0] + apex[0]) / 2 - 16, (base_y + apex[1]) / 2, labs[1]))
    return _wrap(w, h, "".join(g), caption)


# --------------------------------------------------------------------- วงกลม
def circle_fig(kind, labels=None, caption=None, size=250):
    """วงกลมพร้อมองค์ประกอบตามทฤษฎีบทที่ต้องใช้

    kind = 'central-inscribed' มุมที่จุดศูนย์กลางกับมุมในส่วนโค้งที่รองรับส่วนโค้งเดียวกัน
           'chord-perp'        คอร์ดกับเส้นตั้งฉากจากจุดศูนย์กลาง (แบ่งครึ่งคอร์ด)
           'tangent'           เส้นสัมผัสตั้งฉากกับรัศมี ณ จุดสัมผัส
           'cyclic-quad'       สี่เหลี่ยมแนบในวงกลม (มุมตรงข้ามรวมกันได้ 180°)
    """
    labels = labels or {}
    cx = cy = size / 2
    r = size * 0.34
    at = lambda deg: (cx + r * math.cos(math.radians(deg)),
                      cy - r * math.sin(math.radians(deg)))
    g = [f'<rect x="0" y="0" width="{size}" height="{size}" fill="#fff"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="{NAVY}" '
         f'stroke-width="2"/>']
    seg = lambda p, q, col=NAVY, wd=1.8: (f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" '
                                          f'x2="{q[0]:.1f}" y2="{q[1]:.1f}" '
                                          f'stroke="{col}" stroke-width="{wd}"/>')
    dot = lambda p, col=NAVY: f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3.4" fill="{col}"/>'
    name = lambda p, s, dx=0, dy=0: _t(p[0] + dx, p[1] + dy, s, 12.5, "middle", NAVY, "700")

    if kind == "central-inscribed":
        A, B, C = at(210), at(330), at(80)
        g += [seg((cx, cy), A), seg((cx, cy), B), seg(C, A), seg(C, B),
              dot((cx, cy)), dot(A), dot(B), dot(C),
              name((cx, cy), "O", -12, 4), name(A, "A", -12, 6),
              name(B, "B", 12, 6), name(C, "C", 0, -9)]
        if labels.get("center"):
            g.append(_lab(cx, cy + 26, labels["center"], 12))
        if labels.get("inscribed"):
            g.append(_lab(C[0], C[1] + 26, labels["inscribed"], 12))
    elif kind == "chord-perp":
        A, B = at(205), at(335)
        M = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
        g += [seg(A, B), seg((cx, cy), M, SERIES[3], 2), dot((cx, cy)), dot(A), dot(B), dot(M),
              name((cx, cy), "O", 0, -10), name(A, "A", -12, 4), name(B, "B", 12, 4),
              name(M, "M", 0, 17)]
        m = 10
        g.append(f'<path d="M {M[0]-m} {M[1]-m*0.2} L {M[0]-m*0.8} {M[1]-m} L {M[0]+0.2} '
                 f'{M[1]-m*0.9}" fill="none" stroke="{SERIES[3]}" stroke-width="1.5"/>')
        if labels.get("chord"):
            g.append(_lab((A[0] + B[0]) / 2, A[1] + 30, labels["chord"], 12))
        if labels.get("dist"):
            g.append(_lab(cx + 16, (cy + M[1]) / 2, labels["dist"], 12))
    elif kind == "tangent":
        P = at(270)
        g += [seg((P[0] - r * 1.05, P[1]), (P[0] + r * 1.05, P[1]), SERIES[3], 2.2),
              seg((cx, cy), P), dot((cx, cy)), dot(P),
              name((cx, cy), "O", 0, -10), name(P, "P", -14, 6)]
        m = 11
        g.append(f'<path d="M {P[0]+2} {P[1]-m} L {P[0]+m} {P[1]-m} L {P[0]+m} {P[1]-2}" '
                 f'fill="none" stroke="{NAVY}" stroke-width="1.5"/>')
        if labels.get("radius"):
            g.append(_lab(cx + 12, (cy + P[1]) / 2 + 4, labels["radius"], 12, "start"))
    elif kind == "cyclic-quad":
        pts = [at(d) for d in (150, 40, 320, 220)]
        g.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                 + f'" fill="#eef1f4" stroke="{NAVY}" stroke-width="1.8"/>')
        for p, nm, (dx, dy) in zip(pts, "ABCD", ((-13, -2), (13, -4), (13, 10), (-13, 10))):
            g += [dot(p), name(p, nm, dx, dy)]
        if labels.get("A"):
            g.append(_lab(pts[0][0] + 22, pts[0][1] + 18, labels["A"], 12))
        if labels.get("C"):
            g.append(_lab(pts[2][0] - 24, pts[2][1] - 14, labels["C"], 12))
    elif kind == "radius":
        # วงกลมกับรัศมีที่ทำป้ายไว้ — ใช้กับโจทย์ความยาวรอบรูปและพื้นที่ของชั้นประถม
        P = at(35)
        g += [seg((cx, cy), P), dot((cx, cy)), dot(P),
              name((cx, cy), "O", -12, 4), name(P, "P", 12, -4)]
        if labels.get("radius"):
            g.append(_lab((cx + P[0]) / 2 + 6, (cy + P[1]) / 2 - 8, labels["radius"], 12.5))
    else:
        raise ValueError(f"ไม่รู้จักรูปวงกลมชนิด {kind}")
    return _wrap(size, size, "".join(g), caption)


# ------------------------------------------- สามเหลี่ยมมุมฉากที่ทำเครื่องหมายมุม
def trig_triangle(base, height, angle_label, base_label=None, height_label=None,
                  hyp_label=None, at_vertex="C", caption=None, box=170):
    """สามเหลี่ยมมุมฉากพร้อมส่วนโค้งกำกับมุมที่โจทย์อ้างถึง

    A บนซ้าย · B ล่างซ้าย (มุมฉาก) · C ล่างขวา — ทำเครื่องหมายมุมที่ A หรือ C
    """
    pad_l, pad_r, pad_t, pad_b = 58, 56, 28, 38
    s = box / max(base, height)
    bw, bh = base * s, height * s
    w, h = round(pad_l + bw + pad_r), round(pad_t + bh + pad_b)
    A, B, C = (pad_l, pad_t), (pad_l, pad_t + bh), (pad_l + bw, pad_t + bh)

    g = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>',
         f'<polygon points="{A[0]:.1f},{A[1]:.1f} {B[0]:.1f},{B[1]:.1f} '
         f'{C[0]:.1f},{C[1]:.1f}" {FILL}/>']
    m = 13
    g.append(f'<path d="M {B[0]:.1f} {B[1]-m:.1f} L {B[0]+m:.1f} {B[1]-m:.1f} '
             f'L {B[0]+m:.1f} {B[1]:.1f}" fill="none" stroke="{NAVY}" stroke-width="1.6"/>')
    for p, nm, (dx, dy) in ((A, "A", (-12, 3)), (B, "B", (-12, 14)), (C, "C", (12, 14))):
        g.append(_t(p[0] + dx, p[1] + dy, nm, 13, "middle", NAVY, "700"))
    if at_vertex == "C":
        rr = min(44, bw * 0.5)
        g.append(f'<path d="M {C[0]-rr:.1f} {C[1]:.1f} A {rr} {rr} 0 0 1 '
                 f'{C[0]-rr*bw/math.hypot(bw,bh):.1f} '
                 f'{C[1]-rr*bh/math.hypot(bw,bh):.1f}" fill="none" '
                 f'stroke="{SERIES[3]}" stroke-width="2"/>')
        g.append(_lab(C[0] - rr * 0.72, C[1] - 12, angle_label, 12.5))
    else:
        rr = min(44, bh * 0.5)
        g.append(f'<path d="M {A[0]:.1f} {A[1]+rr:.1f} A {rr} {rr} 0 0 0 '
                 f'{A[0]+rr*bw/math.hypot(bw,bh):.1f} '
                 f'{A[1]+rr*bh/math.hypot(bw,bh):.1f}" fill="none" '
                 f'stroke="{SERIES[3]}" stroke-width="2"/>')
        g.append(_lab(A[0] + 16, A[1] + rr * 0.78, angle_label, 12.5, "start"))
    if height_label:
        g.append(_lab(A[0] - 9, (A[1] + B[1]) / 2, height_label, anchor="end"))
    if base_label:
        g.append(_lab((B[0] + C[0]) / 2, B[1] + 22, base_label))
    if hyp_label:
        g.append(_lab((A[0] + C[0]) / 2 + 18, (A[1] + C[1]) / 2 - 6, hyp_label))
    return _wrap(w, h, "".join(g), caption)


# ============================================================================
# วิทยาศาสตร์ — คลื่น · วงจรไฟฟ้า · แผนภาพแสง · ตารางพันเนตต์ · สายใยอาหาร
# ============================================================================

def wave_fig(marks=(), caption=None, width=520, cycles=2, amp=42):
    """คลื่นรูปไซน์พร้อมชี้ส่วนประกอบ · marks = ชื่อส่วนที่ต้องการทำเครื่องหมาย

    'crest' สันคลื่น · 'trough' ท้องคลื่น · 'wavelength' ความยาวคลื่น · 'amplitude' แอมพลิจูด
    """
    pad, h = 40, 190
    mid = h / 2 - 8
    plot_w = width - pad * 2
    per = plot_w / cycles
    pts = [(pad + i / 400 * plot_w,
            mid - amp * math.sin(2 * math.pi * cycles * i / 400)) for i in range(401)]

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>',
         f'<line x1="{pad-14}" y1="{mid}" x2="{width-pad+14}" y2="{mid}" '
         f'stroke="{SOFT}" stroke-width="1.2" stroke-dasharray="5 4"/>',
         '<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
         + f'" fill="none" stroke="{NAVY}" stroke-width="2.6" stroke-linejoin="round"/>']
    c1x = pad + per / 4                      # สันคลื่นลูกแรก
    t1x = pad + per * 3 / 4                  # ท้องคลื่นลูกแรก
    if "crest" in marks:
        b.append(f'<circle cx="{c1x:.1f}" cy="{mid-amp:.1f}" r="4.5" fill="{SERIES[3]}"/>')
        b.append(_lab(c1x, mid - amp - 12, "ก", 13))
    if "trough" in marks:
        b.append(f'<circle cx="{t1x:.1f}" cy="{mid+amp:.1f}" r="4.5" fill="{SERIES[3]}"/>')
        b.append(_lab(t1x, mid + amp + 20, "ข", 13))
    if "wavelength" in marks:                # วัดจากสันถึงสันที่อยู่ติดกัน
        y = mid - amp - 26
        b.append(f'<line x1="{c1x:.1f}" y1="{y:.1f}" x2="{c1x+per:.1f}" y2="{y:.1f}" '
                 f'stroke="{SERIES[3]}" stroke-width="1.4"/>')
        for x in (c1x, c1x + per):
            b.append(f'<line x1="{x:.1f}" y1="{y-5:.1f}" x2="{x:.1f}" y2="{y+5:.1f}" '
                     f'stroke="{SERIES[3]}" stroke-width="1.4"/>')
        b.append(_lab(c1x + per / 2, y - 8, "ค", 13))
    if "amplitude" in marks:                 # วัดจากแนวกลางถึงสันคลื่น
        x = pad + per * 1.25
        b.append(f'<line x1="{x:.1f}" y1="{mid:.1f}" x2="{x:.1f}" y2="{mid-amp:.1f}" '
                 f'stroke="{SERIES[3]}" stroke-width="1.4"/>')
        for y in (mid, mid - amp):
            b.append(f'<line x1="{x-5:.1f}" y1="{y:.1f}" x2="{x+5:.1f}" y2="{y:.1f}" '
                     f'stroke="{SERIES[3]}" stroke-width="1.4"/>')
        b.append(_lab(x + 10, mid - amp / 2 + 4, "ง", 13, "start"))
    return _wrap(width, h, "".join(b), caption)


# -------------------------------------------------------------- วงจรไฟฟ้า
def _res(x, y, label, horiz=True):
    """สัญลักษณ์ตัวต้านทาน — สี่เหลี่ยมผืนผ้าคร่อมเส้นลวด"""
    w, t = 46, 18
    if horiz:
        box = (f'<rect x="{x-w/2:.1f}" y="{y-t/2:.1f}" width="{w}" height="{t}" '
               f'fill="#fff" stroke="{NAVY}" stroke-width="2"/>')
        lab = _lab(x, y - t / 2 - 7, label, 12)
    else:
        box = (f'<rect x="{x-t/2:.1f}" y="{y-w/2:.1f}" width="{t}" height="{w}" '
               f'fill="#fff" stroke="{NAVY}" stroke-width="2"/>')
        lab = _lab(x + t / 2 + 6, y + 4, label, 12, "start")
    return box + lab


def _battery(x, y):
    """สัญลักษณ์เซลล์ไฟฟ้า — ขีดยาว (ขั้วบวก) สลับขีดสั้น (ขั้วลบ) ในแนวตั้ง"""
    return (f'<line x1="{x-13}" y1="{y-4}" x2="{x+13}" y2="{y-4}" stroke="{INK}" '
            f'stroke-width="2.4"/>'
            f'<line x1="{x-7}" y1="{y+4}" x2="{x+7}" y2="{y+4}" stroke="{INK}" '
            f'stroke-width="4"/>')


def _meter(x, y, letter):
    return (f'<circle cx="{x}" cy="{y}" r="15" fill="#fff" stroke="{NAVY}" stroke-width="2"/>'
            + _t(x, y + 5, letter, 14, "middle", NAVY, "700"))


def circuit_fig(kind, labels=None, caption=None, width=380, height=230):
    """แผนภาพวงจรไฟฟ้าอย่างง่าย

    kind = 'series'   ตัวต้านทานสองตัวต่ออนุกรม
           'parallel' ตัวต้านทานสองตัวต่อขนาน
           'meters'   แอมมิเตอร์ต่ออนุกรม โวลต์มิเตอร์ต่อขนานคร่อมตัวต้านทาน
    """
    labels = labels or {}
    L, R, T, B = 46, width - 46, 46, height - 46
    wire = lambda x1, y1, x2, y2: (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                                   f'y2="{y2:.1f}" stroke="{INK}" stroke-width="2"/>')
    mid_y = (T + B) / 2
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']

    if kind == "series":
        g += [wire(L, T, R, T), wire(R, T, R, B), wire(R, B, L, B),
              wire(L, B, L, mid_y + 6), wire(L, mid_y - 6, L, T)]
        g.append(_battery(L, mid_y))
        g.append(_lab(L - 12, mid_y + 4, labels.get("v", ""), 12, "end"))
        g.append(_res((L + R) / 2 - 55, T, labels.get("r1", "R₁")))
        g.append(_res((L + R) / 2 + 55, T, labels.get("r2", "R₂")))
    elif kind == "parallel":
        my2 = B - 30
        g += [wire(L, T, R, T), wire(R, T, R, my2), wire(R, my2, L, my2),
              wire(L, my2, L, mid_y + 6), wire(L, mid_y - 6, L, T)]
        g.append(_battery(L, mid_y))
        g.append(_lab(L - 12, mid_y + 4, labels.get("v", ""), 12, "end"))
        bx = (L + R) / 2
        g += [wire(bx - 40, T, bx - 40, my2), wire(bx + 40, T, bx + 40, my2)]
        g.append(_res(bx - 40, (T + my2) / 2, labels.get("r1", "R₁"), horiz=False))
        g.append(_res(bx + 40, (T + my2) / 2, labels.get("r2", "R₂"), horiz=False))
    elif kind == "meters":
        g += [wire(L, T, R, T), wire(R, T, R, B), wire(R, B, L, B),
              wire(L, B, L, mid_y + 6), wire(L, mid_y - 6, L, T)]
        g.append(_battery(L, mid_y))
        g.append(_res((L + R) / 2 + 40, T, labels.get("r1", "R")))
        g.append(_meter((L + R) / 2 - 45, T, "A"))
        vy = T + 66                          # โวลต์มิเตอร์คร่อมตัวต้านทานแบบขนาน
        x1, x2 = (L + R) / 2 + 40 - 42, (L + R) / 2 + 40 + 42
        g += [wire(x1, T, x1, vy), wire(x2, T, x2, vy),
              wire(x1, vy, (x1 + x2) / 2 - 15, vy), wire((x1 + x2) / 2 + 15, vy, x2, vy)]
        g.append(_meter((x1 + x2) / 2, vy, "V"))
    elif kind == "electronic":
        g += [wire(L, T, R, T), wire(R, T, R, B), wire(R, B, L, B),
              wire(L, B, L, mid_y + 6), wire(L, mid_y - 6, L, T)]
        g.append(_battery(L, mid_y))
        g.append(_res((L + R) / 2 - 52, T, labels.get("r1", "R")))
        dx = (L + R) / 2 + 46                # ไดโอดเปล่งแสง — สามเหลี่ยมชนขีด ปล่อยผ่านทางเดียว
        g.append(f'<polygon points="{dx-13},{T-11} {dx-13},{T+11} {dx+9},{T}" '
                 f'fill="#eef1f4" stroke="{NAVY}" stroke-width="2"/>')
        g.append(f'<line x1="{dx+9}" y1="{T-12}" x2="{dx+9}" y2="{T+12}" stroke="{NAVY}" '
                 f'stroke-width="2.4"/>')
        for k in range(2):
            ax0 = dx + 2 + k * 9
            g.append(f'<line x1="{ax0}" y1="{T-18}" x2="{ax0+9}" y2="{T-28}" '
                     f'stroke="{SERIES[3]}" stroke-width="1.6"/>')
            g.append(f'<polygon points="{ax0+12},{T-31} {ax0+5},{T-27} {ax0+10},{T-22}" '
                     f'fill="{SERIES[3]}"/>')
        g.append(_lab(dx, T + 28, "LED", 12))
    else:
        raise ValueError(f"ไม่รู้จักวงจรชนิด {kind}")
    return _wrap(width, height, "".join(g), caption)


# ------------------------------------------------------- แผนภาพการเดินทางของแสง
def lens_ray(kind="convex", caption=None, width=460, height=220):
    """แผนภาพรังสีแสงผ่านเลนส์ · kind = 'convex' วัตถุไกลกว่า 2F หรือ 'concave'"""
    cx, cy = width / 2, height / 2
    f, lens_h = 62, 74
    axis = f'<line x1="14" y1="{cy}" x2="{width-14}" y2="{cy}" stroke="{SOFT}" ' \
           f'stroke-width="1.2" stroke-dasharray="6 4"/>'
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>', axis]
    if kind == "convex":
        g.append(f'<ellipse cx="{cx}" cy="{cy}" rx="13" ry="{lens_h}" fill="#eef1f4" '
                 f'stroke="{NAVY}" stroke-width="2"/>')
    else:
        g.append(f'<path d="M {cx-13} {cy-lens_h} Q {cx+2} {cy} {cx-13} {cy+lens_h} '
                 f'L {cx+13} {cy+lens_h} Q {cx-2} {cy} {cx+13} {cy-lens_h} Z" '
                 f'fill="#eef1f4" stroke="{NAVY}" stroke-width="2"/>')
    for d, nm in ((-f, "F"), (f, "F"), (-2 * f, "2F"), (2 * f, "2F")):
        x = cx + d
        if 20 < x < width - 20:
            g.append(f'<circle cx="{x:.1f}" cy="{cy}" r="3" fill="{INK}"/>')
            g.append(_t(x, cy + 17, nm, 11, "middle", SOFT))
    ox, oh = cx - 2.4 * f, 46                # วัตถุอยู่ไกลกว่า 2F
    arrow = lambda x, y0, y1, col: (
        f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" stroke="{col}" '
        f'stroke-width="2.6"/>'
        f'<polygon points="{x:.1f},{y1:.1f} {x-5:.1f},{y1+(7 if y1>y0 else -7):.1f} '
        f'{x+5:.1f},{y1+(7 if y1>y0 else -7):.1f}" fill="{col}"/>')
    g.append(arrow(ox, cy, cy - oh, NAVY))
    g.append(_t(ox, cy + 17, "วัตถุ", 11.5, "middle", NAVY, "700"))
    ray = lambda x1, y1, x2, y2: (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                                  f'y2="{y2:.1f}" stroke="{SERIES[3]}" stroke-width="1.8"/>')
    if kind == "convex":
        u = 2.4 * f
        v = 1 / (1 / f - 1 / u)              # 1/f = 1/u + 1/v
        ix, ih = cx + v, oh * v / u
        # รังสีที่ 1 ขนานแกน → หักเหผ่านโฟกัส · รังสีที่ 2 ผ่านกึ่งกลางเลนส์เป็นเส้นตรง
        g += [ray(ox, cy - oh, cx, cy - oh), ray(cx, cy - oh, ix, cy + ih),
              ray(ox, cy - oh, ix, cy + ih)]
        g.append(arrow(ix, cy, cy + ih, SERIES[2]))
        g.append(_t(ix + 4, cy - 9, "ภาพ", 11.5, "start", SERIES[2], "700"))
    else:
        # เลนส์เว้ากระจายแสง รังสีจริงไม่ไปรวมกัน ต้องต่อย้อนกลับ (เส้นประ) จึงได้ภาพเสมือน
        u = 2.4 * f
        v = 1 / (-1 / f - 1 / u)                    # เลนส์เว้าใช้ f เป็นลบ ได้ v ติดลบ
        ix, ih = cx + v, oh * abs(v) / u
        ex = width - 22
        g += [ray(ox, cy - oh, cx, cy - oh),
              ray(cx, cy - oh, ex, cy - oh + (cy - oh - (cy - ih)) / (cx - ix) * (ex - cx)),
              ray(ox, cy - oh, cx, cy - oh)]
        g.append(f'<line x1="{cx:.1f}" y1="{cy-oh:.1f}" x2="{ix:.1f}" y2="{cy-ih:.1f}" '
                 f'stroke="{SERIES[3]}" stroke-width="1.4" stroke-dasharray="5 4"/>')
        g.append(arrow(ix, cy, cy - ih, SERIES[2]))
        g.append(_t(ix - 6, cy - ih - 8, "ภาพ", 11.5, "end", SERIES[2], "700"))
    return _wrap(width, height, "".join(g), caption)


def mirror_ray(angle, caption=None, width=340, height=210):
    """แสงตกกระทบกระจกเงาราบ พร้อมเส้นแนวฉากและมุมตกกระทบ/มุมสะท้อน"""
    cx, my = width / 2, height - 58
    r = 118
    a = math.radians(angle)
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<line x1="26" y1="{my}" x2="{width-26}" y2="{my}" stroke="{INK}" '
         f'stroke-width="2.6"/>']
    for x in range(30, int(width) - 26, 14):  # ขีดเฉียงใต้กระจก บอกว่าเป็นผิวสะท้อน
        g.append(f'<line x1="{x}" y1="{my}" x2="{x-7}" y2="{my+9}" stroke="{SOFT}" '
                 f'stroke-width="1.2"/>')
    g.append(f'<line x1="{cx}" y1="{my}" x2="{cx}" y2="{my-r-10}" stroke="{SOFT}" '
             f'stroke-width="1.4" stroke-dasharray="5 4"/>')
    g.append(_t(cx, my - r - 18, "เส้นแนวฉาก", 11, "middle", SOFT))
    inx, iny = cx - r * math.sin(a), my - r * math.cos(a)
    rfx, rfy = cx + r * math.sin(a), my - r * math.cos(a)
    for (x, y), col in (((inx, iny), NAVY), ((rfx, rfy), SERIES[3])):
        g.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{cx}" y2="{my}" stroke="{col}" '
                 f'stroke-width="2.2"/>' if col == NAVY else
                 f'<line x1="{cx}" y1="{my}" x2="{x:.1f}" y2="{y:.1f}" stroke="{col}" '
                 f'stroke-width="2.2"/>')
    mid = lambda x, y: ((x + cx) / 2, (y + my) / 2)
    mx, myy = mid(inx, iny)
    g.append(f'<polygon points="{mx:.1f},{myy:.1f} {mx-4:.1f},{myy-8:.1f} '
             f'{mx+7:.1f},{myy-5:.1f}" fill="{NAVY}"/>')
    rr = 46
    g.append(f'<path d="M {cx-rr*math.sin(a):.1f} {my-rr*math.cos(a):.1f} '
             f'A {rr} {rr} 0 0 1 {cx} {my-rr}" fill="none" stroke="{NAVY}" '
             f'stroke-width="1.6"/>')
    g.append(f'<path d="M {cx} {my-rr} A {rr} {rr} 0 0 1 '
             f'{cx+rr*math.sin(a):.1f} {my-rr*math.cos(a):.1f}" fill="none" '
             f'stroke="{SERIES[3]}" stroke-width="1.6"/>')
    g.append(_lab(cx - rr * 0.62, my - rr * 0.92, "ก", 12.5))
    g.append(_lab(cx + rr * 0.62, my - rr * 0.92, "ข", 12.5))
    return _wrap(width, height, "".join(g), caption)


# -------------------------------------------------------------- ตารางพันเนตต์
def punnett(top, left, caption=None, cell=56, show=None):
    """ตารางพันเนตต์ 2×2 · top/left = แอลลีลของพ่อและแม่ · show = ช่องที่ต้องซ่อนเป็น '?'"""
    show = show if show is not None else [[True] * len(top) for _ in left]
    pad_l, pad_t = 52, 46
    w = pad_l + cell * len(top) + 16
    h = pad_t + cell * len(left) + 16
    g = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for j, a in enumerate(top):
        g.append(_t(pad_l + cell * (j + 0.5), pad_t - 12, a, 15, "middle", NAVY, "700"))
    for i, b_ in enumerate(left):
        g.append(_t(pad_l - 14, pad_t + cell * (i + 0.5) + 6, b_, 15, "end", NAVY, "700"))
    for i, b_ in enumerate(left):
        for j, a in enumerate(top):
            x, y = pad_l + cell * j, pad_t + cell * i
            g.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                     f'fill="#eef1f4" stroke="{NAVY}" stroke-width="1.6"/>')
            gt = "".join(sorted(a + b_, key=lambda c: (c.islower(), c)))
            g.append(_t(x + cell / 2, y + cell / 2 + 6,
                        gt if show[i][j] else "?", 16, "middle",
                        INK if show[i][j] else SERIES[3], "700"))
    return _wrap(round(w), round(h), "".join(g), caption)


# --------------------------------------------------------------- สายใยอาหาร
def food_web(nodes, links, caption=None, width=520, height=240):
    """โซ่/สายใยอาหาร · nodes = {ชื่อ: (x, y)} พิกัด 0-1 · links = [(จาก, ไป)]

    ลูกศรชี้ตามทิศทางการถ่ายทอดพลังงาน คือชี้จากผู้ถูกกินไปยังผู้กิน
    """
    px = lambda t: 40 + t * (width - 80)
    py = lambda t: 34 + t * (height - 78)
    pos = {n: (px(x), py(y)) for n, (x, y) in nodes.items()}
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    for a, b_ in links:
        (x1, y1), (x2, y2) = pos[a], pos[b_]
        dx, dy = x2 - x1, y2 - y1
        d = math.hypot(dx, dy) or 1
        gap = 34
        sx, sy = x1 + dx / d * gap, y1 + dy / d * gap
        ex, ey = x2 - dx / d * (gap + 7), y2 - dy / d * (gap + 7)
        ux, uy = dx / d, dy / d
        g.append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
                 f'stroke="{SOFT}" stroke-width="1.8"/>')
        g.append(f'<polygon points="{ex+ux*7:.1f},{ey+uy*7:.1f} '
                 f'{ex-uy*4.5:.1f},{ey+ux*4.5:.1f} {ex+uy*4.5:.1f},{ey-ux*4.5:.1f}" '
                 f'fill="{SOFT}"/>')
    for n, (x, y) in pos.items():
        g.append(f'<rect x="{x-33:.1f}" y="{y-15:.1f}" width="66" height="30" rx="15" '
                 f'fill="#eef1f4" stroke="{NAVY}" stroke-width="1.8"/>')
        g.append(_t(x, y + 5, n, 12, "middle", NAVY, "700"))
    return _wrap(width, height, "".join(g), caption)


# ------------------------------------------------------ ผังลำดับ (ใช้กล่อง-ลูกศรชุดเดียวกับสายใยอาหาร)
def flow_chart(steps, caption=None, width=540, per_row=3, box_w=140):
    """ผังลำดับขั้นตอน — กล่องเรียงพร้อมลูกศรชี้ขั้นถัดไป ขึ้นบรรทัดใหม่เมื่อเต็มแถว"""
    rows = [steps[i:i + per_row] for i in range(0, len(steps), per_row)]
    bh, gap_y, pad = 40, 34, 20
    height = pad * 2 + len(rows) * bh + (len(rows) - 1) * gap_y
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    gap_x = (width - pad * 2 - per_row * box_w) / max(per_row - 1, 1)
    pos = []
    for r, row in enumerate(rows):
        y = pad + r * (bh + gap_y)
        for c, name in enumerate(row):
            x = pad + c * (box_w + gap_x)
            pos.append((x, y, name))
            g.append(f'<rect x="{x:.1f}" y="{y}" width="{box_w}" height="{bh}" rx="8" '
                     f'fill="#eef1f4" stroke="{NAVY}" stroke-width="1.8"/>')
            g.append(_t(x + box_w / 2, y + bh / 2 + 5, name, 12, "middle", NAVY, "700"))
    arrow = lambda x1, y1, x2, y2: (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{SOFT}" '
        f'stroke-width="1.8"/>'
        + (f'<polygon points="{x2:.1f},{y2:.1f} {x2-5:.1f},{y2-7:.1f} {x2+5:.1f},{y2-7:.1f}" '
           f'fill="{SOFT}"/>' if x1 == x2 else
           f'<polygon points="{x2:.1f},{y2:.1f} {x2-7:.1f},{y2-4.5:.1f} {x2-7:.1f},{y2+4.5:.1f}" '
           f'fill="{SOFT}"/>'))
    for i in range(len(pos) - 1):
        (x1, y1, _), (x2, y2, _) = pos[i], pos[i + 1]
        if y1 == y2:
            g.append(arrow(x1 + box_w + 3, y1 + bh / 2, x2 - 4, y2 + bh / 2))
        else:                                  # ขึ้นแถวใหม่ — ลากอ้อมลงมาทางซ้าย
            my = y1 + bh + gap_y / 2
            g += [f'<line x1="{x1+box_w/2:.1f}" y1="{y1+bh}" x2="{x1+box_w/2:.1f}" '
                  f'y2="{my:.1f}" stroke="{SOFT}" stroke-width="1.8"/>',
                  f'<line x1="{x1+box_w/2:.1f}" y1="{my:.1f}" x2="{x2+box_w/2:.1f}" '
                  f'y2="{my:.1f}" stroke="{SOFT}" stroke-width="1.8"/>',
                  arrow(x2 + box_w / 2, my, x2 + box_w / 2, y2 - 4)]
    return _wrap(width, round(height), "".join(g), caption)


# ------------------------------------------------------------- แบบจำลองอนุภาค
def particle_model(kind, caption=None, width=170, height=170):
    """แบบจำลองอนุภาคของสสาร · kind = 'solid' | 'liquid' | 'gas' | 'mixture'"""
    pad, r = 16, 9
    g = [f'<rect x="{pad/2}" y="{pad/2}" width="{width-pad}" height="{height-pad}" '
         f'fill="#fff" stroke="{INK}" stroke-width="1.8"/>']
    dot = lambda x, y, col=NAVY: (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" '
                                  f'fill-opacity="0.75" stroke="{col}" stroke-width="1.4"/>')
    inner = width - pad * 2 - r * 2
    if kind == "solid":                       # เรียงชิดเป็นระเบียบ สั่นอยู่กับที่
        for i in range(4):
            for j in range(4):
                g.append(dot(pad + r + 6 + i * (inner / 3.4), pad + r + 6 + j * (inner / 3.4)))
    elif kind == "liquid":                    # อยู่ชิดกันแต่ไม่เป็นระเบียบ เลื่อนที่ได้
        off = [(0, .12), (.3, 0), (.62, .1), (.9, .02), (.1, .38), (.42, .3),
               (.72, .42), (.98, .34), (.04, .66), (.34, .72), (.66, .64), (.94, .74)]
        for a, b in off:
            g.append(dot(pad + r + 6 + a * inner, pad + r + 26 + b * inner * 0.78))
        g.append(f'<line x1="{pad/2}" y1="{pad/2+34}" x2="{width-pad/2}" y2="{pad/2+34}" '
                 f'stroke="{SOFT}" stroke-width="1.2" stroke-dasharray="5 4"/>')
    elif kind == "gas":                       # อยู่ห่างกันมาก ฟุ้งเต็มภาชนะ
        for a, b in [(.05, .1), (.55, .02), (.92, .22), (.28, .38), (.72, .55),
                     (.02, .62), (.45, .82), (.88, .9)]:
            g.append(dot(pad + r + 6 + a * inner, pad + r + 6 + b * inner))
    elif kind == "mixture":                   # สารสองชนิดผสมกันในระดับอนุภาค
        for a, b, c in [(.06, .1, 0), (.4, .05, 1), (.75, .18, 0), (.15, .42, 1),
                        (.5, .38, 0), (.85, .5, 1), (.1, .74, 0), (.45, .8, 1),
                        (.8, .84, 0)]:
            g.append(dot(pad + r + 6 + a * inner, pad + r + 6 + b * inner,
                         NAVY if c == 0 else SERIES[3]))
    else:
        raise ValueError(f"ไม่รู้จักแบบจำลองอนุภาคชนิด {kind}")
    return _wrap(width, height, "".join(g), caption)


# ------------------------------------------------------------- แผนภาพแรง
def force_diagram(forces, caption=None, width=380, height=200, label=None):
    """วัตถุกับแรงที่กระทำ · forces = [(ทิศ, ป้ายกำกับ)] ทิศ = 'left' 'right' 'up' 'down'"""
    cx, cy, bw, bh = width / 2, height / 2, 74, 56
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<rect x="{cx-bw/2}" y="{cy-bh/2}" width="{bw}" height="{bh}" rx="5" '
         f'fill="#eef1f4" stroke="{NAVY}" stroke-width="2"/>']
    if label:
        g.append(_t(cx, cy + 5, label, 13, "middle", NAVY, "700"))
    L = 82
    for i, (d, lab) in enumerate(forces):
        col = SERIES[i % len(SERIES)]
        if d in ("left", "right"):
            sgn = 1 if d == "right" else -1
            x0 = cx + sgn * bw / 2
            x1 = x0 + sgn * L
            g.append(f'<line x1="{x0:.1f}" y1="{cy}" x2="{x1-sgn*8:.1f}" y2="{cy}" '
                     f'stroke="{col}" stroke-width="2.6"/>')
            g.append(f'<polygon points="{x1:.1f},{cy} {x1-sgn*10:.1f},{cy-6} '
                     f'{x1-sgn*10:.1f},{cy+6}" fill="{col}"/>')
            g.append(_t(x0 + sgn * L / 2, cy - 12, lab, 12.5, "middle", col, "700"))
        else:
            sgn = 1 if d == "down" else -1
            y0 = cy + sgn * bh / 2
            y1 = y0 + sgn * (L - 20)
            g.append(f'<line x1="{cx}" y1="{y0:.1f}" x2="{cx}" y2="{y1-sgn*8:.1f}" '
                     f'stroke="{col}" stroke-width="2.6"/>')
            g.append(f'<polygon points="{cx},{y1:.1f} {cx-6},{y1-sgn*10:.1f} '
                     f'{cx+6},{y1-sgn*10:.1f}" fill="{col}"/>')
            g.append(_t(cx + 12, y0 + sgn * (L - 20) / 2, lab, 12.5, "start", col, "700"))
    return _wrap(width, height, "".join(g), caption)


# ============================================================================
# วิทยาศาสตร์ ม.3 — โครโมโซม · การแบ่งเซลล์ · ปฏิกิริยา · สเปกตรัม · แสง · อวกาศ
# ============================================================================

def reaction_model(caption=None, width=470, height=170):
    """แบบจำลองการจัดเรียงอะตอมใหม่ · 2H₂ + O₂ → 2H₂O (จำนวนอะตอมก่อนและหลังเท่ากัน)"""
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    H, O = "#4A90A4", "#C0392B"
    atom = lambda x, y, col, r=11: (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" '
                                    f'fill-opacity="0.8" stroke="{col}" stroke-width="1.4"/>')
    bond = lambda x1, y1, x2, y2: (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                                   f'y2="{y2:.1f}" stroke="{SOFT}" stroke-width="3"/>')
    cy = height / 2 - 4
    for i, bx in enumerate((44, 44)):            # H₂ สองโมเลกุล
        y = cy - 32 + i * 64
        g += [bond(bx, y, bx + 22, y), atom(bx, y, H), atom(bx + 22, y, H)]
    g.append(_t(102, cy + 5, "+", 20, "middle", INK, "700"))
    g += [bond(132, cy, 158, cy), atom(132, cy, O, 14), atom(158, cy, O, 14)]  # O₂
    g.append(f'<line x1="196" y1="{cy}" x2="242" y2="{cy}" stroke="{INK}" stroke-width="2.2"/>')
    g.append(f'<polygon points="252,{cy} 240,{cy-7} 240,{cy+7}" fill="{INK}"/>')
    for i in range(2):                           # H₂O สองโมเลกุล
        bx, y = 300, cy - 32 + i * 64
        g += [bond(bx, y, bx + 24, y - 12), bond(bx, y, bx + 24, y + 12),
              atom(bx, y, O, 14), atom(bx + 24, y - 12, H), atom(bx + 24, y + 12, H)]
    g.append(_t(120, height - 8, "ก่อนเกิดปฏิกิริยา", 11.5, "middle", SOFT, "600"))
    g.append(_t(340, height - 8, "หลังเกิดปฏิกิริยา", 11.5, "middle", SOFT, "600"))
    return _wrap(width, height, "".join(g), caption)


def em_spectrum(caption=None, width=520, height=140):
    """สเปกตรัมคลื่นแม่เหล็กไฟฟ้า เรียงตามความยาวคลื่นจากมากไปน้อย"""
    bands = [("คลื่นวิทยุ", "#7B6CA8"), ("ไมโครเวฟ", "#4A90A4"), ("อินฟราเรด", "#C0392B"),
             ("แสงที่มองเห็นได้", "#E0A83D"), ("อัลตราไวโอเลต", "#2F8F6F"),
             ("รังสีเอกซ์", "#1E3A5F"), ("รังสีแกมมา", "#5b5952")]
    pad, bh = 26, 40
    bw = (width - pad * 2) / len(bands)
    y = 46
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    for i, (name, col) in enumerate(bands):
        x = pad + i * bw
        g.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="{bh}" fill="{col}" '
                 f'fill-opacity="0.55" stroke="#fff" stroke-width="1.2"/>')
        g.append(f'<g transform="translate({x+bw/2:.1f},{y+bh+8}) rotate(38)">'
                 + _t(0, 0, name, 10.5, "start", SOFT) + '</g>')
        # ป้าย ก-ช วางในแถบสี ไม่ใช่เหนือแถบ เพราะไปชนคำอธิบายแกน
        g.append(_t(x + bw / 2, y + bh / 2 + 5, "กขคงจฉช"[i], 13, "middle", "#fff", "700"))
    g.append(_t(pad, 30, "ความยาวคลื่นมาก", 11, "start", SOFT))
    g.append(_t(width - pad, 30, "ความยาวคลื่นน้อย", 11, "end", SOFT))
    g.append(f'<line x1="{pad+96}" y1="26" x2="{width-pad-100}" y2="26" stroke="{SOFT}" '
             f'stroke-width="1.2"/>')
    g.append(f'<polygon points="{width-pad-92},26 {width-pad-102},22 {width-pad-102},30" '
             f'fill="{SOFT}"/>')
    return _wrap(width, height, "".join(g), caption)


def mirror_image(caption=None, width=400, height=200):
    """ภาพจากกระจกเงาราบ — ภาพเสมือนอยู่หลังกระจก ห่างเท่ากับวัตถุ"""
    mx, cy = width / 2, height / 2
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<line x1="{mx}" y1="26" x2="{mx}" y2="{height-40}" stroke="{INK}" '
         f'stroke-width="3"/>']
    for y in range(30, int(height) - 40, 13):
        g.append(f'<line x1="{mx}" y1="{y}" x2="{mx+9}" y2="{y+7}" stroke="{SOFT}" '
                 f'stroke-width="1.2"/>')
    d = 92
    arrow = lambda x, col, dash="": (
        f'<line x1="{x}" y1="{cy+30}" x2="{x}" y2="{cy-30}" stroke="{col}" '
        f'stroke-width="2.6" {dash}/>'
        f'<polygon points="{x},{cy-38} {x-6},{cy-26} {x+6},{cy-26}" fill="{col}"/>')
    g.append(arrow(mx - d, NAVY))
    g.append(arrow(mx + d, SERIES[2], 'stroke-dasharray="6 4"'))
    g.append(_t(mx - d, cy + 48, "วัตถุ", 12, "middle", NAVY, "700"))
    g.append(_t(mx + d, cy + 48, "ภาพ", 12, "middle", SERIES[2], "700"))
    for x0, x1, lab in ((mx - d, mx, "ก"), (mx, mx + d, "ข")):
        yy = height - 26
        g.append(f'<line x1="{x0}" y1="{yy}" x2="{x1}" y2="{yy}" stroke="{SERIES[3]}" '
                 f'stroke-width="1.4"/>')
        for xx in (x0, x1):
            g.append(f'<line x1="{xx}" y1="{yy-5}" x2="{xx}" y2="{yy+5}" '
                     f'stroke="{SERIES[3]}" stroke-width="1.4"/>')
        g.append(_lab((x0 + x1) / 2, yy - 8, lab, 12.5))
    return _wrap(width, height, "".join(g), caption)


def prism_fig(caption=None, width=420, height=210):
    """แสงขาวผ่านปริซึมแล้วกระจายออกเป็นแถบสี"""
    cx, cy = width / 2 - 20, height / 2
    r = 62
    p = [(cx, cy - r), (cx - r * 0.87, cy + r * 0.5), (cx + r * 0.87, cy + r * 0.5)]
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in p)
         + f'" fill="#eef1f4" stroke="{NAVY}" stroke-width="2"/>',
         f'<line x1="18" y1="{cy-6}" x2="{cx-24:.1f}" y2="{cy+6:.1f}" stroke="{INK}" '
         f'stroke-width="2.6"/>',
         _t(60, cy - 16, "แสงขาว", 11.5, "middle", INK, "700")]
    cols = ["#C0392B", "#E07A2D", "#E0A83D", "#2F8F6F", "#1E3A5F", "#3B4A9B", "#7B6CA8"]
    for i, col in enumerate(cols):
        y2 = cy - 34 + i * 15
        g.append(f'<line x1="{cx+30:.1f}" y1="{cy+14:.1f}" x2="{width-16}" y2="{y2:.1f}" '
                 f'stroke="{col}" stroke-width="2.4"/>')
    g.append(_t(width - 16, cy - 52, "แดง", 11, "end", SOFT))
    g.append(_t(width - 16, cy + 68, "ม่วง", 11, "end", SOFT))
    return _wrap(width, height, "".join(g), caption)


def orbit_fig(caption=None, width=380, height=240):
    """ดาวเคราะห์โคจรรอบดวงอาทิตย์ พร้อมลูกศรแรงโน้มถ่วงที่ชี้เข้าหาดวงอาทิตย์"""
    cx, cy = width / 2, height / 2
    rx, ry = 138, 84
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
         f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="{SOFT}" '
         f'stroke-width="1.6" stroke-dasharray="6 5"/>',
         f'<circle cx="{cx}" cy="{cy}" r="26" fill="#E0A83D" stroke="#C88E22" '
         f'stroke-width="2"/>',
         _t(cx, cy + 46, "ดวงอาทิตย์", 11.5, "middle", SOFT, "600")]
    a = math.radians(38)
    px, py = cx + rx * math.cos(a), cy - ry * math.sin(a)
    g.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="13" fill="#4A90A4" '
             f'stroke="{NAVY}" stroke-width="1.8"/>')
    g.append(_t(px + 6, py - 20, "ดาวเคราะห์", 11.5, "middle", SOFT, "600"))
    dx, dy = cx - px, cy - py
    d = math.hypot(dx, dy)
    ex, ey = px + dx / d * 58, py + dy / d * 58
    g.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
             f'stroke="{SERIES[3]}" stroke-width="2.4"/>')
    g.append(f'<polygon points="{ex+dx/d*8:.1f},{ey+dy/d*8:.1f} '
             f'{ex-dy/d*5:.1f},{ey+dx/d*5:.1f} {ex+dy/d*5:.1f},{ey-dx/d*5:.1f}" '
             f'fill="{SERIES[3]}"/>')
    g.append(_lab((px + ex) / 2 + 26, (py + ey) / 2 - 4, "F", 13))
    return _wrap(width, height, "".join(g), caption)


def moon_phase(caption=None, width=380, height=340):
    """ตำแหน่งดวงจันทร์รอบโลก · ครึ่งที่หันเข้าหาดวงอาทิตย์สว่างเสมอ"""
    cx, cy, R, r = width / 2 + 24, height / 2, 108, 19
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    for i in range(5):                            # แสงอาทิตย์มาจากทางซ้าย
        y = cy - 76 + i * 38
        g.append(f'<line x1="10" y1="{y}" x2="52" y2="{y}" stroke="#E0A83D" '
                 f'stroke-width="2.2"/>')
        g.append(f'<polygon points="60,{y} 50,{y-5} 50,{y+5}" fill="#E0A83D"/>')
    g.append(_t(34, cy - 100, "แสงจาก", 10.5, "middle", SOFT))
    g.append(_t(34, cy - 88, "ดวงอาทิตย์", 10.5, "middle", SOFT))
    g.append(f'<circle cx="{cx}" cy="{cy}" r="26" fill="#4A90A4" stroke="{NAVY}" '
             f'stroke-width="2"/>')
    g.append(_t(cx, cy + 5, "โลก", 11.5, "middle", "#fff", "700"))
    g.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{SOFT}" '
             f'stroke-width="1.4" stroke-dasharray="5 4"/>')
    for i, tag in enumerate("กขคง"):
        ang = math.radians(180 - i * 90)          # ซ้าย บน ขวา ล่าง
        mx, my = cx + R * math.cos(ang), cy - R * math.sin(ang)
        g.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{r}" fill="{INK}" '
                 f'stroke="{INK}" stroke-width="1.4"/>')
        g.append(f'<path d="M {mx:.1f} {my-r} A {r} {r} 0 0 0 {mx:.1f} {my+r} Z" '
                 f'fill="#F2EFE6"/>')            # ครึ่งซ้ายสว่างเสมอ
        g.append(_t(mx, my - r - 9, tag, 13, "middle", SERIES[3], "700"))
    return _wrap(width, height, "".join(g), caption)


# ------------------------------------------- กราฟอุณหภูมิ-เวลา (สารบริสุทธิ์/สารผสม)
def heating_curve(curves, caption=None, x_title="เวลา (นาที)",
                  y_title="อุณหภูมิ (°C)", width=520, vmin=0, vmax=120, vstep=20):
    """กราฟให้ความร้อนสองเส้นเทียบกัน · curves = [(ชื่อเส้น, [(เวลา, อุณหภูมิ), …]), …]

    ใช้กับ ว 2.1 ม.1/4 — สารบริสุทธิ์เดือดที่อุณหภูมิคงที่ (กราฟราบ)
    ส่วนสารผสมอุณหภูมิยังไต่ขึ้นเรื่อย ๆ ความต่างนี้ต้องมองเห็นจากรูปได้ตรง ๆ
    """
    pad_l, pad_r, pad_t = 46, 14, 18
    plot_h, plot_w = 190, width - 46 - 14
    legend_h = 24 if len(curves) > 1 else 0
    h = pad_t + plot_h + 40 + legend_h
    tmax = max(t for _, pts in curves for t, _ in pts)

    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    sy = lambda v: pad_t + plot_h - (v - vmin) / (vmax - vmin) * plot_h
    sx = lambda t: pad_l + t / tmax * plot_w
    v = vmin
    while v <= vmax:
        b.append(f'<line x1="{pad_l}" y1="{sy(v):.1f}" x2="{pad_l+plot_w}" y2="{sy(v):.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        b.append(_t(pad_l - 7, sy(v) + 4, v, 11, "end"))
        v += vstep
    for t in range(0, tmax + 1, max(1, tmax // 6)):
        b.append(_t(sx(t), pad_t + plot_h + 17, t, 11.5, "middle", INK))
    b.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
             f'stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" '
             f'y2="{pad_t+plot_h}" stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<g transform="translate(13,{pad_t+plot_h/2}) rotate(-90)">'
             f'{_t(0,0,y_title,11,"middle",SOFT,"600")}</g>')
    b.append(_t(pad_l + plot_w / 2, pad_t + plot_h + 38, x_title, 11, "middle", SOFT, "600"))

    # ช่วงต้นของสองเส้นมักทับกันสนิท (ให้ความร้อนเท่ากันก่อนถึงจุดเดือด)
    # เส้นที่สองจึงวาดเป็นเส้นประ ไม่งั้นเส้นแรกหายไปใต้เส้นที่สองทั้งเส้น
    shared = {t for t, _ in curves[0][1]} if len(curves) > 1 else set()
    for i, (name, pts) in enumerate(curves):
        col = SERIES[i]
        dash = ' stroke-dasharray="7 5"' if i else ""
        b.append('<polyline points="' +
                 " ".join(f"{sx(t):.1f},{sy(v):.1f}" for t, v in pts) +
                 f'" fill="none" stroke="{col}" stroke-width="2.4"{dash} '
                 'stroke-linejoin="round" stroke-linecap="round"/>')
        base = dict(curves[0][1])
        for t, v in pts:
            b.append(f'<circle cx="{sx(t):.1f}" cy="{sy(v):.1f}" r="3.4" fill="#fff" '
                     f'stroke="{col}" stroke-width="2"/>')
            # ติดป้ายเฉพาะจุดที่สองเส้นแยกกันแล้ว — ไม่งั้นป้ายซ้อนกันตรงช่วงที่ทับกัน
            # และวางคนละฝั่งของจุด เพราะช่วงที่เพิ่งแยกกันสองค่ายังห่างกันไม่กี่พิกเซล
            if i == 0 or base.get(t) != v:
                first = t == pts[0][0]      # จุดซ้ายสุดชนป้ายขีดของแกน y ถ้าจัดกึ่งกลาง
                b.append(_t(sx(t) + (7 if first else 0), sy(v) + (17 if i == 0 else -9),
                            v, 10.5, "start" if first else "middle", INK, "600"))
        if legend_h:
            lx = pad_l + 6 + i * (plot_w / len(curves))
            ly = pad_t + plot_h + 40 + legend_h - 8
            b.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+22}" y2="{ly-4}" '
                     f'stroke="{col}" stroke-width="3" stroke-linecap="round"/>')
            b.append(_t(lx + 28, ly, name, 11.5, "start", INK, "600"))
    return _wrap(width, h, "".join(b), caption)


# ------------------------------------------ แบบจำลองอะตอม ธาตุ และสารประกอบ
def substance_model(kind, caption=None, width=180, height=170):
    """แบบจำลองระดับอนุภาค · kind = 'atoms' | 'element' | 'compound' | 'mixture'

    ต่างจาก particle_model() ที่เล่าเรื่อง *สถานะ* — อันนี้เล่าเรื่อง *ชนิดของสาร*
    ว่าอนุภาคเป็นอะตอมเดี่ยว โมเลกุลของธาตุชนิดเดียว หรือโมเลกุลของธาตุต่างชนิดที่ยึดกัน
    """
    pad, r = 16, 8.5
    A, B = NAVY, SERIES[3]
    g = [f'<rect x="{pad/2}" y="{pad/2}" width="{width-pad}" height="{height-pad}" '
         f'fill="#fff" stroke="{INK}" stroke-width="1.8"/>']

    def dot(x, y, col):
        return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}" '
                f'fill-opacity="0.8" stroke="{col}" stroke-width="1.4"/>')

    def pair(x, y, c1, c2):
        return (f'<line x1="{x-r*0.8:.1f}" y1="{y:.1f}" x2="{x+r*0.8:.1f}" y2="{y:.1f}" '
                f'stroke="{INK}" stroke-width="2.4"/>' +
                dot(x - r * 0.8, y, c1) + dot(x + r * 0.8, y, c2))

    spots = [(.08, .1), (.62, .04), (.3, .44), (.86, .46), (.06, .82), (.58, .86)]
    inner_w = width - pad * 2 - r * 4 - 8       # เผื่อที่ให้โมเลกุลคู่ไม่ล้นกรอบ
    inner_h = height - pad * 2 - r * 2 - 8
    for i, (a, c) in enumerate(spots):
        x = pad + r * 2 + 6 + a * inner_w
        y = pad + r + 8 + c * inner_h
        if kind == "atoms":                       # อะตอมเดี่ยวของธาตุชนิดเดียว
            g.append(dot(x, y, A))
        elif kind == "element":                   # โมเลกุลของธาตุ — อะตอมชนิดเดียวยึดกัน
            g.append(pair(x, y, A, A))
        elif kind == "compound":                  # โมเลกุลของสารประกอบ — ต่างชนิดยึดกัน
            g.append(pair(x, y, A, B))
        elif kind == "mixture":                   # โมเลกุลสองชนิดปนกัน แต่ไม่ยึดกัน
            g.append(pair(x, y, A, A) if i % 2 else pair(x, y, A, B))
        else:
            raise ValueError(f"ไม่รู้จักแบบจำลองสารชนิด {kind}")
    return _wrap(width, height, "".join(g), caption)


# ------------------------------------------------ การขยายตัวเมื่อได้รับความร้อน
def expansion_fig(cold_label, hot_label, caption=None, width=470, height=210):
    """แท่งโลหะก่อน/หลังได้รับความร้อน — อนุภาคเท่าเดิม แต่ห่างกันมากขึ้น (ว 2.3 ม.1/3)"""
    b = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    panel_w, y0, bar_h = (width - 40) / 2, 54, 44

    for k, (title, gap, cols) in enumerate(
            [("ก่อนได้รับความร้อน", 20, 8), ("หลังได้รับความร้อน", 25, 8)]):
        x0 = 14 + k * (panel_w + 12)
        bw = gap * cols + 14
        b.append(_t(x0 + panel_w / 2, 26, title, 12.5, "middle", INK, "600"))
        b.append(f'<rect x="{x0}" y="{y0}" width="{bw:.1f}" height="{bar_h}" rx="4" '
                 f'fill="#fff" stroke="{NAVY}" stroke-width="2"/>')
        for i in range(cols):
            for j in range(2):
                b.append(f'<circle cx="{x0+9+i*gap:.1f}" cy="{y0+14+j*16}" r="5" '
                         f'fill="{NAVY}" fill-opacity="0.75" stroke="{NAVY}" '
                         'stroke-width="1.2"/>')
        # เส้นบอกความยาว วางใต้แท่ง ไม่ทับตัวแท่ง
        yd = y0 + bar_h + 22
        b.append(f'<line x1="{x0}" y1="{yd}" x2="{x0+bw:.1f}" y2="{yd}" stroke="{SOFT}" '
                 'stroke-width="1.4" marker-start="url(#exar)" marker-end="url(#exar)"/>')
        b.append(f'<line x1="{x0}" y1="{y0+bar_h}" x2="{x0}" y2="{yd+5}" '
                 f'stroke="{SOFT}" stroke-width="1"/>')
        b.append(f'<line x1="{x0+bw:.1f}" y1="{y0+bar_h}" x2="{x0+bw:.1f}" y2="{yd+5}" '
                 f'stroke="{SOFT}" stroke-width="1"/>')
        b.append(_t(x0 + bw / 2, yd + 20, cold_label if k == 0 else hot_label,
                    12, "middle", INK, "600"))
    b.append(_t(width / 2, height - 12,
                "จำนวนอนุภาคเท่าเดิม · ระยะห่างระหว่างอนุภาคเปลี่ยนไป", 11.5, "middle", SOFT))
    defs = (f'<defs><marker id="exar" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" '
            f'orient="auto"><path d="M0,3.5 L7,1 L7,6 Z" fill="{SOFT}"/></marker></defs>')
    return _wrap(width, height, defs + "".join(b), caption)


# ------------------------------------------------------- การถ่ายโอนความร้อน 3 แบบ
def heat_transfer(caption=None, width=520, height=200):
    """สามแผงเทียบกัน — การนำ · การพา · การแผ่รังสี (ว 2.3 ม.1/6)"""
    b = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    pw, y0 = (width - 32) / 3, 42
    flame = lambda x, y: (f'<path d="M{x-7},{y} q3,-12 7,-16 q4,4 7,16 q-7,5 -14,0 z" '
                          f'fill="{SERIES[3]}" fill-opacity="0.85"/>')
    for k, name in enumerate(["ก", "ข", "ค"]):
        x0 = 10 + k * (pw + 6)
        b.append(f'<rect x="{x0}" y="{y0-22}" width="{pw:.1f}" height="{height-y0-14}" '
                 f'rx="6" fill="#fff" stroke="{GRID}" stroke-width="1.4"/>')
        b.append(_t(x0 + pw / 2, 26, name, 13, "middle", INK, "700"))
        cx, cy = x0 + pw / 2, y0 + 52
        if k == 0:                                   # การนำความร้อน — แท่งโลหะบนเปลวไฟ
            b.append(f'<rect x="{cx-56}" y="{cy-8}" width="112" height="16" rx="3" '
                     f'fill="#fff" stroke="{NAVY}" stroke-width="2"/>')
            b.append(flame(cx - 44, cy + 34))
            for i in range(4):
                b.append(f'<circle cx="{cx-30+i*22}" cy="{cy+20}" r="3.6" '
                         f'fill="{SOFT}"/>')
            b.append(f'<path d="M{cx-40},{cy} L{cx+42},{cy}" stroke="{SERIES[3]}" '
                     'stroke-width="2.4" stroke-dasharray="6 4" marker-end="url(#htar)"/>')
        elif k == 1:                                 # การพาความร้อน — น้ำหมุนวนในบีกเกอร์
            b.append(f'<path d="M{cx-34},{cy-32} L{cx-30},{cy+30} L{cx+30},{cy+30} '
                     f'L{cx+34},{cy-32}" fill="none" stroke="{NAVY}" stroke-width="2"/>')
            b.append(f'<path d="M{cx-27},{cy-14} L{cx+27},{cy-14}" stroke="{SERIES[5]}" '
                     'stroke-width="2"/>')
            b.append(f'<path d="M{cx-16},{cy+20} A16,16 0 1,1 {cx+16},{cy+2}" fill="none" '
                     f'stroke="{SERIES[3]}" stroke-width="2.2" marker-end="url(#htar)"/>')
            b.append(flame(cx, cy + 48))
        else:                                        # การแผ่รังสีความร้อน — ไม่ต้องมีตัวกลาง
            b.append(f'<circle cx="{cx-30}" cy="{cy}" r="15" fill="{SERIES[1]}" '
                     f'fill-opacity="0.9" stroke="{SERIES[1]}" stroke-width="1.5"/>')
            for j in range(3):
                yy = cy - 18 + j * 18
                b.append(f'<path d="M{cx-10},{yy} L{cx+30},{yy}" stroke="{SERIES[3]}" '
                         'stroke-width="2.2" marker-end="url(#htar)"/>')
            b.append(f'<rect x="{cx+34}" y="{cy-24}" width="12" height="48" rx="3" '
                     f'fill="#fff" stroke="{NAVY}" stroke-width="2"/>')
    defs = (f'<defs><marker id="htar" markerWidth="8" markerHeight="8" refX="7" refY="4" '
            f'orient="auto"><path d="M0,1 L8,4 L0,7 Z" fill="{SERIES[3]}"/></marker></defs>')
    return _wrap(width, height, defs + "".join(b), caption)


# --------------------------------------------------- ชั้นของสิ่งต่าง ๆ (บรรยากาศ ดิน ฯลฯ)
def layers_fig(bands, bottom_label, caption=None, band_h=48, edge_w=86, box_w=266):
    """ชั้นซ้อนกันพร้อมป้ายขอบเขต · bands = [(ชื่อชั้น, ป้ายขอบบน, หมายเหตุ), …] เรียงจากบนลงล่าง

    วาดทุกชั้นสูงเท่ากันโดยตั้งใจ เพราะความหนาจริงต่างกันหลายสิบเท่า
    ถ้าวาดตามสเกลจริงชั้นล่าง ๆ จะบางจนอ่านชื่อไม่ออก — ป้ายตัวเลขที่ขอบเป็นตัวบอกความสูงจริง
    """
    # กว้างพอสำหรับโน้ตที่ยาวที่สุดเสมอ — เคยตั้งความกว้างตายตัวแล้วโน้ตโดนตัดขอบ
    x0, x1 = edge_w, edge_w + box_w
    longest = max((len(n) for _, _, n in bands if n), default=0)
    width = x1 + (16 + int(longest * 7.4) if longest else 12)
    h = 18 + band_h * len(bands) + 34
    b = [f'<rect x="0" y="0" width="{width}" height="{h}" fill="#fff"/>']
    for i, (name, edge, note) in enumerate(bands):
        y = 18 + i * band_h
        b.append(f'<rect x="{x0}" y="{y}" width="{x1-x0}" height="{band_h}" '
                 f'fill="{SERIES[i % len(SERIES)]}" fill-opacity="0.16" '
                 f'stroke="{INK}" stroke-width="1.4"/>')
        b.append(_t((x0 + x1) / 2, y + band_h / 2 + 5, name, 13, "middle", INK, "600"))
        b.append(_t(x0 - 10, y + 5, edge, 11.5, "end", SOFT))
        if note:
            b.append(_t(x1 + 10, y + band_h / 2 + 5, note, 11.5, "start", SOFT))
    y = 18 + band_h * len(bands)
    b.append(_t(x0 - 10, y + 5, bottom_label, 11.5, "end", SOFT))
    return _wrap(width, h, "".join(b), caption)


# --------------------------------------------------- โครงสร้างภายในโลก (ชั้นซ้อนศูนย์กลาง)
def concentric_layers(rings, caption=None, width=520, height=250):
    """ชั้นซ้อนจากศูนย์กลางออกมา · rings = [(ชื่อชั้น, รัศมีสัมพัทธ์ 0-1, ป้ายความหนา), …]
    เรียงจากชั้นนอกสุดเข้าไปหาศูนย์กลาง

    ชื่อชั้นวางเป็นรายการข้าง ๆ พร้อมแถบสี ไม่เขียนทับลงบนวง เพราะชั้นนอกสุดบางมาก
    จนไม่มีที่ให้ตัวอักษร (ลองเขียนทับแล้วชื่อล้นออกนอกวงทุกครั้ง)
    """
    cx, cy, R = 118, height / 2, min(96, height / 2 - 16)
    b = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    for i, (name, frac, _) in enumerate(rings):
        col = SERIES[i % len(SERIES)]
        b.append(f'<circle cx="{cx}" cy="{cy:.1f}" r="{R*frac:.1f}" '
                 f'fill="{col}" fill-opacity="{0.22 + 0.16*i:.2f}" '
                 f'stroke="{INK}" stroke-width="1.4"/>')
    lx, ly = cx + R + 34, cy - (len(rings) * 34) / 2 + 20
    for i, (name, _, note) in enumerate(rings):
        y = ly + i * 34
        b.append(f'<rect x="{lx}" y="{y-11}" width="16" height="16" rx="3" '
                 f'fill="{SERIES[i % len(SERIES)]}" fill-opacity="{0.22 + 0.16*i:.2f}" '
                 f'stroke="{INK}" stroke-width="1.2"/>')
        b.append(_t(lx + 24, y + 2, name, 13, "start", INK, "600"))
        if note:
            b.append(_t(lx + 24, y + 17, note, 11, "start", SOFT))
    return _wrap(width, height, "".join(b), caption)


# ------------------------------------------ แรงจากสนามสามชนิด (แม่เหล็ก · ไฟฟ้า · โน้มถ่วง)
def field_forces(caption=None, width=520, height=200):
    """สามแผงเทียบกัน — ไม่เขียนชื่อแรงลงในรูป เพราะโจทย์ให้ระบุเองว่าแผงไหนคือแรงอะไร"""
    b = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']
    pw = (width - 32) / 3
    arrow = (f'<defs><marker id="ffar" markerWidth="9" markerHeight="9" refX="8" refY="4.5" '
             f'orient="auto"><path d="M0,1 L9,4.5 L0,8 Z" fill="{SERIES[3]}"/></marker></defs>')
    for k, name in enumerate(["ก", "ข", "ค"]):
        x0 = 10 + k * (pw + 6)
        b.append(f'<rect x="{x0}" y="22" width="{pw:.1f}" height="{height-38}" rx="6" '
                 f'fill="#fff" stroke="{GRID}" stroke-width="1.4"/>')
        b.append(_t(x0 + pw / 2, 16, name, 13, "middle", INK, "700"))
        cx, cy = x0 + pw / 2, 108
        if k == 0:                                  # แท่งแม่เหล็กดูดตะปูเหล็ก
            b.append(f'<rect x="{cx-62}" y="{cy-16}" width="46" height="32" rx="3" '
                     f'fill="{SERIES[3]}" fill-opacity="0.3" stroke="{INK}" stroke-width="1.6"/>')
            b.append(_t(cx - 51, cy + 5, "N", 13, "middle", INK, "700"))
            b.append(_t(cx - 27, cy + 5, "S", 13, "middle", INK, "700"))
            b.append(f'<rect x="{cx+30}" y="{cy-5}" width="30" height="10" rx="2" '
                     f'fill="#c9ccd1" stroke="{INK}" stroke-width="1.4"/>')
            b.append(f'<line x1="{cx+26}" y1="{cy}" x2="{cx-4}" y2="{cy}" '
                     f'stroke="{SERIES[3]}" stroke-width="2.6" marker-end="url(#ffar)"/>')
        elif k == 1:                                # แท่งพลาสติกถูผ้าดูดเศษกระดาษ
            b.append(f'<rect x="{cx-58}" y="{cy-30}" width="16" height="62" rx="4" '
                     f'fill="#e8e2f2" stroke="{INK}" stroke-width="1.6"/>')
            for j in range(3):
                b.append(_t(cx - 50, cy - 14 + j * 20, "+", 13, "middle", NAVY, "700"))
            for j, (dx, dy) in enumerate([(34, -16), (44, 6), (32, 24)]):
                b.append(f'<rect x="{cx+dx}" y="{cy+dy-5}" width="13" height="9" '
                         f'fill="#fff" stroke="{INK}" stroke-width="1.2"/>')
            b.append(f'<line x1="{cx+28}" y1="{cy}" x2="{cx-32}" y2="{cy}" '
                     f'stroke="{SERIES[3]}" stroke-width="2.6" marker-end="url(#ffar)"/>')
        else:                                       # วัตถุตกสู่พื้นโลก
            b.append(f'<circle cx="{cx}" cy="{cy-32}" r="13" fill="{NAVY}" '
                     f'fill-opacity="0.7" stroke="{NAVY}" stroke-width="1.6"/>')
            b.append(f'<line x1="{cx}" y1="{cy-14}" x2="{cx}" y2="{cy+24}" '
                     f'stroke="{SERIES[3]}" stroke-width="2.6" marker-end="url(#ffar)"/>')
            b.append(f'<path d="M{cx-56},{cy+62} A70,70 0 0,1 {cx+56},{cy+62}" fill="none" '
                     f'stroke="{INK}" stroke-width="2"/>')
            b.append(_t(cx, cy + 58, "ผิวโลก", 11.5, "middle", SOFT))
    return _wrap(width, height, arrow + "".join(b), caption)


# ------------------------------------------------------ การกระจัดเทียบกับระยะทาง
def displacement_fig(east, north, caption=None, cell=34):
    """เดินไปทางตะวันออก east ช่อง แล้วขึ้นเหนือ north ช่อง · เส้นประคือการกระจัด (ว 2.2 ม.2/15)"""
    pad_l, pad_b, pad_t, pad_r = 76, 46, 26, 96   # ซ้ายต้องกว้างพอให้ป้ายจุดเริ่มต้นไม่โดนตัด
    w = pad_l + east * cell + pad_r
    h = pad_t + north * cell + pad_b
    ox, oy = pad_l, pad_t + north * cell          # จุดเริ่มต้นอยู่มุมซ้ายล่าง
    b = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']
    for i in range(east + 1):
        b.append(f'<line x1="{ox+i*cell}" y1="{pad_t}" x2="{ox+i*cell}" y2="{oy}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
    for j in range(north + 1):
        b.append(f'<line x1="{ox}" y1="{oy-j*cell}" x2="{ox+east*cell}" y2="{oy-j*cell}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
    ex, ny = ox + east * cell, oy - north * cell
    arrow = (f'<defs><marker id="dsar" markerWidth="9" markerHeight="9" refX="8" refY="4.5" '
             f'orient="auto"><path d="M0,1 L9,4.5 L0,8 Z" fill="{NAVY}"/></marker>'
             f'<marker id="dsar2" markerWidth="9" markerHeight="9" refX="8" refY="4.5" '
             f'orient="auto"><path d="M0,1 L9,4.5 L0,8 Z" fill="{SERIES[3]}"/></marker></defs>')
    b.append(f'<line x1="{ox}" y1="{oy}" x2="{ex}" y2="{oy}" stroke="{NAVY}" '
             'stroke-width="2.8" marker-end="url(#dsar)"/>')
    b.append(f'<line x1="{ex}" y1="{oy}" x2="{ex}" y2="{ny}" stroke="{NAVY}" '
             'stroke-width="2.8" marker-end="url(#dsar)"/>')
    b.append(f'<line x1="{ox}" y1="{oy}" x2="{ex}" y2="{ny}" stroke="{SERIES[3]}" '
             'stroke-width="2.6" stroke-dasharray="7 5" marker-end="url(#dsar2)"/>')
    b.append(_t(ox + east * cell / 2, oy + 34, f"{east} เมตร ไปทางตะวันออก",
                12, "middle", NAVY, "600"))
    b.append(_t(ex + 8, oy - north * cell / 2 + 4, f"{north} เมตร", 12, "start", NAVY, "600"))
    b.append(_t(ox + 4, ny - 8, "เส้นประ = การกระจัด", 12, "start", SERIES[3], "600"))
    b.append(f'<circle cx="{ox}" cy="{oy}" r="4.5" fill="{INK}"/>')
    # ป้ายจุดเริ่มต้นเคยวางใต้จุดแล้วชนป้ายระยะทางที่จัดกึ่งกลางลูกศร จึงย้ายมาไว้ซ้ายจุด
    b.append(_t(ox - 8, oy + 5, "จุดเริ่มต้น", 11, "end", SOFT))
    b.append(f'<circle cx="{ex}" cy="{ny}" r="4.5" fill="{INK}"/>')
    b.append(_t(ex + 8, ny - 8, "จุดสุดท้าย", 11, "start", SOFT))
    return _wrap(w, h, arrow + "".join(b), caption)


# ------------------------------------------------- การสร้างด้วยวงเวียนและสันตรง
def _circ_cross(c0, r0, c1, r1, upper=True):
    """จุดตัดของวงกลมสองวง — คืนจุดบนหรือจุดล่างตามที่ขอ

    การสร้างทุกแบบวางอยู่บนจุดตัดนี้ ถ้าเดามุมของส่วนโค้งเอาเอง ส่วนโค้งจะไม่ผ่านจุด
    ที่ทำเครื่องหมายไว้ (พลาดมาแล้วทั้งสามรูป) จึงคิดจุดตัดก่อน แล้วค่อยกลับไปหามุม
    """
    (x0, y0), (x1, y1) = c0, c1
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    if dist > r0 + r1 or dist < abs(r0 - r1) or dist == 0:
        raise ValueError("วงกลมสองวงนี้ไม่ตัดกัน — รัศมีวงเวียนไม่เหมาะกับระยะที่กำหนด")
    a = (r0 * r0 - r1 * r1 + dist * dist) / (2 * dist)
    hh = math.sqrt(max(r0 * r0 - a * a, 0))
    mx, my = x0 + a * dx / dist, y0 + a * dy / dist
    ux, uy = -dy / dist, dx / dist                 # เวกเตอร์ตั้งฉากกับแนวศูนย์กลาง
    sign = -1 if upper else 1                      # แกน y ในภาพชี้ลง "บน" คือ y น้อยกว่า
    return (mx + sign * hh * ux, my + sign * hh * uy)


def _ang(centre, pt):
    """มุมของจุด pt เมื่อมองจาก centre (องศา · ระบบเดียวกับ _arc)"""
    return math.degrees(math.atan2(centre[1] - pt[1], pt[0] - centre[0]))


def _arc(cx, cy, r, a0, a1):
    """ส่วนโค้งจากมุม a0 ถึง a1 (องศา · วัดทวนเข็มจากแกน x บวก · แกน y ในภาพชี้ลง)

    สุ่มจุดบนส่วนโค้งแล้วต่อเป็นเส้น แทนการใช้คำสั่ง A ของ SVG — flag large-arc/sweep
    ของ SVG อ่านทิศจากระบบพิกัดที่แกน y ชี้ลง ซึ่งกลับด้านกับมุมที่คิดมา
    เคยวาดออกมาโค้งไปคนละทางจนล้นกรอบมาแล้ว การสุ่มจุดไม่มีทางกำกวมแบบนั้น
    """
    lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
    n = max(8, int(abs(hi - lo) / 4))
    pts = []
    for i in range(n + 1):
        a = math.radians(lo + (hi - lo) * i / n)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy - r * math.sin(a):.1f}")
    return (f'<polyline points="{" ".join(pts)}" fill="none" stroke="{SERIES[3]}" '
            'stroke-width="1.6" stroke-dasharray="5 4"/>')


def _arc_through(centre, r, pts, pad=14):
    """ส่วนโค้งรอบ centre ที่กินช่วงมุมของทุกจุดใน pts พร้อมเผื่อปลายไว้ pad องศา

    atan2 คืนค่าในช่วง (-180, 180] จุดสองจุดที่คร่อมมุม 180° จึงได้ +143 กับ -143
    ซึ่งถ้าเอามาลบกันตรง ๆ จะได้ช่วง 286° คือวาดอ้อมไปอีกด้านของวงกลม (เคยล้นกรอบมาแล้ว)
    """
    angs = [_ang(centre, p) for p in pts]
    if max(angs) - min(angs) > 180:
        angs = [a + 360 if a < 0 else a for a in angs]
    return _arc(centre[0], centre[1], r, max(angs) + pad, min(angs) - pad)


# ขนาดมุม ABC ที่ construction_fig('bisect_angle') วาดจริง
# โจทย์ที่อ้างรูปนี้ต้องอ่านค่าจากตรงนี้ ไม่ใช่พิมพ์ตัวเลขเอง ไม่งั้นรูปกับโจทย์เพี้ยนจากกัน
BISECT_ANGLE_DEG = 58


def construction_fig(kind, caption=None, width=360, height=280):
    """รอยวงเวียนของการสร้างพื้นฐาน · kind = 'bisect_segment' | 'bisect_angle' | 'perpendicular'

    ส่วนโค้งวาดเป็นเส้นประสีต่างจากเส้นที่สร้างเสร็จ เพื่อให้แยกออกว่าอะไรคือ
    "รอยวงเวียนที่ใช้ระหว่างทาง" กับอะไรคือ "เส้นที่เป็นคำตอบ"
    ตำแหน่งทุกจุดคิดจากจุดตัดของวงกลมจริง ไม่ได้วางด้วยสายตา
    """
    dot = lambda p, s, dy=-11: (
        f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4" fill="{INK}"/>' +
        _t(p[0], p[1] + dy, s, 13, "middle", INK, "700"))
    seg = lambda a, b, col=INK, wd=2.4: (
        f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
        f'stroke="{col}" stroke-width="{wd}"/>')
    g = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>']

    if kind == "bisect_segment":
        A, B = (70, 150), (290, 150)
        r = 138                                    # ต้องเกินครึ่งของ AB ส่วนโค้งจึงตัดกัน
        P = _circ_cross(A, r, B, r, upper=True)
        Q = _circ_cross(A, r, B, r, upper=False)
        M = ((A[0] + B[0]) / 2, A[1])
        g += [seg(A, B), _arc_through(A, r, [P, Q]), _arc_through(B, r, [P, Q]),
              seg((P[0], P[1] - 18), (Q[0], Q[1] + 18), NAVY),
              dot(A, "A", 24), dot(B, "B", 24), dot(P, "P"), dot(Q, "Q", 24),
              dot(M, "M", -13)]
    elif kind == "bisect_angle":
        B, L, up = (70, 210), 190, BISECT_ANGLE_DEG
        C = (B[0] + L, B[1])
        A = (B[0] + L * math.cos(math.radians(up)), B[1] - L * math.sin(math.radians(up)))
        r, r2 = 92, 74
        D = (B[0] + r, B[1])
        E = (B[0] + r * math.cos(math.radians(up)), B[1] - r * math.sin(math.radians(up)))
        # จุดตัดสองจุดของวงเวียนจาก D และ E — ต้องเอาจุดที่ไกลจากมุม B
        # ไม่ใช่จุดใกล้ ไม่งั้นเส้นแบ่งครึ่งสั้นจนไม่เห็นว่าแบ่งมุมจริง
        F = _circ_cross(D, r2, E, r2, upper=False)
        g += [seg(B, C), seg(B, A), _arc_through(B, r, [D, E]),
              _arc_through(D, r2, [F], 22), _arc_through(E, r2, [F], 22),
              seg(B, (F[0] * 1.28 - B[0] * 0.28, F[1] * 1.28 - B[1] * 0.28), NAVY),
              dot(B, "B", 24), dot(C, "C", 24), dot(A, "A"),
              dot(D, "D", 24), dot(E, "E"), dot(F, "F")]
    elif kind == "perpendicular":
        height = 320              # เผื่อที่ให้ป้ายจุด Z ใต้เส้น ไม่ชนบรรทัดอธิบายท้ายรูป
        y0, P = 200, (180, 62)
        r = 150                                    # ต้องยาวกว่าระยะจาก P ถึงเส้น
        if r <= y0 - P[1]:
            raise ValueError("รัศมีวงเวียนสั้นเกินกว่าจะตัดเส้นตรงได้")
        d = math.sqrt(r * r - (y0 - P[1]) ** 2)
        X, Y = (P[0] - d, y0), (P[0] + d, y0)
        r2 = 90
        Z = _circ_cross(X, r2, Y, r2, upper=False)
        M = (P[0], y0)
        g += [seg((40, y0), (width - 40, y0)),
              _arc_through(P, r, [X, Y]),
              _arc_through(X, r2, [Z], 22), _arc_through(Y, r2, [Z], 22),
              seg((P[0], P[1] - 16), (Z[0], Z[1] + 12), NAVY),
              f'<rect x="{M[0]}" y="{y0-13}" width="13" height="13" fill="none" '
              f'stroke="{NAVY}" stroke-width="1.6"/>',
              dot(P, "P"), dot(X, "X", 24), dot(Y, "Y", 24), dot(Z, "Z", 24)]
    elif kind == "parallel":
        # สร้างเส้นขนานผ่านจุด P ด้วยวิธีลอกมุม: ลากเส้นตัด แล้วย้ายมุมที่จุด A ไปที่ P
        # จุดตัดทุกจุดคิดจากวงกลมจริง เช่นเดียวกับการสร้างแบบอื่นในไฟล์นี้
        y0, P = 208, (196, 78)
        A = (86, y0)
        # เส้นตัดผ่าน A และ P — ยืดออกทั้งสองข้างให้เห็นว่าเป็นเส้นตัดจริง
        dx, dy = P[0] - A[0], P[1] - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        T0 = (A[0] - ux * 46, y0 - uy * 46)
        T1 = (P[0] + ux * 58, P[1] + uy * 58)
        r = 66                                     # ส่วนโค้งลอกมุม ใช้รัศมีเดียวกันทั้งสองจุด
        # ส่วนโค้งที่ A ตัดเส้นตรงที่ X และตัดเส้นตัดที่ Y
        X, Y = (A[0] + r, y0), (A[0] + ux * r, y0 + uy * r)
        # ส่วนโค้งที่ P ตัดเส้นตัดที่ Y2 แล้ววัดระยะ XY มากางที่ P ได้จุด Z
        Y2 = (P[0] - ux * r, P[1] - uy * r)
        span = math.dist(X, Y)
        Z = _circ_cross(Y2, span, P, r, upper=True)
        g += [seg((40, y0), (width - 40, y0)), seg(T0, T1, SOFT, 1.8),
              _arc_through(A, r, [X, Y], 20), _arc_through(P, r, [Y2, Z], 20),
              _arc_through(Y2, span, [Z], 22),
              seg((P[0] + (Z[0] - P[0]) * 2.4, P[1] + (Z[1] - P[1]) * 2.4),
                  (P[0] - (Z[0] - P[0]) * 1.5, P[1] - (Z[1] - P[1]) * 1.5), NAVY),
              dot(A, "A", 24), dot(X, "X", 24), dot(P, "P"), dot(Z, "Z")]
    else:
        raise ValueError(f"ไม่รู้จักการสร้างชนิด {kind}")
    g.append(_t(width / 2, height - 8, "เส้นประ = รอยวงเวียน · เส้นทึบน้ำเงิน = เส้นที่สร้างได้",
                11, "middle", SOFT))
    return _wrap(width, height, "".join(g), caption)


# ------------------------------------------------- รูปสี่เหลี่ยมของชั้นประถม
def quad_fig(kind, labels=None, caption=None, box=190):
    """รูปสี่เหลี่ยมด้านขนาน · ขนมเปียกปูน · คางหมู · รูปประกอบ พร้อมเส้นแสดงส่วนสูง

    labels รับสตริง จึงใส่ตัวเลข หน่วย หรือ ? ก็ได้ · คีย์ที่ใช้ต่างกันตามชนิด
      parallelogram/rhombus : base · height · side
      trapezoid             : top · bottom · height
      l_shape               : a · b · c · d  (รูปตัวแอลที่ประกอบจากสี่เหลี่ยมสองผืน)
    สัดส่วนที่วาดคุมด้วย box เท่านั้น ตัวเลขจริงอ่านจากป้าย ไม่ใช่จากการวัดรูป
    """
    labels = labels or {}
    pad_l, pad_r, pad_t, pad_b = 46, 46, 24, 40
    lab = lambda x, y, s, anchor="middle": _t(x, y, s, 13, anchor, SERIES[3], "700")

    if kind in ("parallelogram", "rhombus"):
        bw, bh, skew = box, box * 0.55, box * (0.30 if kind == "parallelogram" else 0.42)
        w, h = round(pad_l + bw + skew + pad_r), round(pad_t + bh + pad_b)
        x0, y1 = pad_l, pad_t + bh
        pts = [(x0, y1), (x0 + bw, y1), (x0 + bw + skew, pad_t), (x0 + skew, pad_t)]
        body = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>',
                '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                + f'" fill="#eef1f4" stroke="{NAVY}" stroke-width="2" '
                'stroke-linejoin="round"/>']
        # ส่วนสูงตั้งฉากกับฐาน — ลากเป็นเส้นประเพื่อไม่ให้สับสนกับด้านของรูป
        hx = x0 + skew
        body.append(f'<line x1="{hx:.1f}" y1="{pad_t:.1f}" x2="{hx:.1f}" y2="{y1:.1f}" '
                    f'stroke="{SERIES[3]}" stroke-width="1.6" stroke-dasharray="5 4"/>')
        m = 11
        body.append(f'<path d="M {hx:.1f} {y1-m:.1f} L {hx+m:.1f} {y1-m:.1f} '
                    f'L {hx+m:.1f} {y1:.1f}" fill="none" stroke="{SERIES[3]}" '
                    'stroke-width="1.4"/>')
        if labels.get("base"):
            body.append(lab(x0 + bw / 2, y1 + 21, labels["base"]))
        if labels.get("height"):
            body.append(lab(hx + 8, (pad_t + y1) / 2 + 4, labels["height"], "start"))
        if labels.get("side"):
            body.append(lab(x0 + bw + skew / 2 + 30, (pad_t + y1) / 2, labels["side"],
                            "start"))
        return _wrap(w, h, "".join(body), caption)

    if kind == "trapezoid":
        bw, bh = box, box * 0.52
        tw = bw * 0.55
        w, h = round(pad_l + bw + pad_r), round(pad_t + bh + pad_b)
        x0, y1 = pad_l, pad_t + bh
        pts = [(x0, y1), (x0 + bw, y1), (x0 + (bw + tw) / 2, pad_t),
               (x0 + (bw - tw) / 2, pad_t)]
        body = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>',
                '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                + f'" fill="#eef1f4" stroke="{NAVY}" stroke-width="2" '
                'stroke-linejoin="round"/>']
        hx = x0 + (bw - tw) / 2
        body.append(f'<line x1="{hx:.1f}" y1="{pad_t:.1f}" x2="{hx:.1f}" y2="{y1:.1f}" '
                    f'stroke="{SERIES[3]}" stroke-width="1.6" stroke-dasharray="5 4"/>')
        if labels.get("bottom"):
            body.append(lab(x0 + bw / 2, y1 + 21, labels["bottom"]))
        if labels.get("top"):
            body.append(lab(x0 + bw / 2, pad_t - 8, labels["top"]))
        if labels.get("height"):
            body.append(lab(hx + 8, (pad_t + y1) / 2 + 4, labels["height"], "start"))
        return _wrap(w, h, "".join(body), caption)

    if kind == "l_shape":
        # รูปตัวแอล: กว้าง a สูง b แล้วเว้ามุมขวาบนออกเป็นสี่เหลี่ยม c × d
        a, b, c, d = (float(labels.get(k + "_len", v))
                      for k, v in (("a", 6), ("b", 4), ("c", 3), ("d", 2)))
        s = box / max(a, b)
        aw, bh, cw, dh = a * s, b * s, c * s, d * s
        w, h = round(pad_l + aw + pad_r), round(pad_t + bh + pad_b)
        x0, y0, y1 = pad_l, pad_t, pad_t + bh
        pts = [(x0, y1), (x0 + aw, y1), (x0 + aw, y0 + dh),
               (x0 + aw - cw, y0 + dh), (x0 + aw - cw, y0), (x0, y0)]
        body = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>',
                '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                + f'" fill="#eef1f4" stroke="{NAVY}" stroke-width="2" '
                'stroke-linejoin="round"/>']
        if labels.get("a"):
            body.append(lab(x0 + aw / 2, y1 + 21, labels["a"]))
        if labels.get("b"):
            body.append(lab(x0 - 8, (y0 + y1) / 2 + 4, labels["b"], "end"))
        if labels.get("c"):
            body.append(lab(x0 + aw - cw / 2, y0 - 8, labels["c"]))
        if labels.get("d"):
            body.append(lab(x0 + aw + 8, y0 + dh / 2 + 4, labels["d"], "start"))
        return _wrap(w, h, "".join(body), caption)

    raise ValueError(f"quad_fig: ไม่รู้จักชนิด '{kind}'")
