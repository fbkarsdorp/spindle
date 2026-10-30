"""Generate the Spindle papercut illustration set (writes to docs/art).

    python3 tools/artgen.py [names ...]
"""
import math
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "art")


# ---------------------------------------------------------------- geometry
def n(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pt(p):
    return f"{n(p[0])},{n(p[1])}"


def poly(pts, close=True):
    return "M" + " L".join(pt(p) for p in pts) + ("Z" if close else "")


def circ(cx, cy, r):
    return (f"M{n(cx - r)},{n(cy)}a{n(r)},{n(r)} 0 1,0 {n(2 * r)},0"
            f"a{n(r)},{n(r)} 0 1,0 {n(-2 * r)},0Z")


def rot(p, a, c=(0, 0)):
    ca, sa = math.cos(a), math.sin(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)


def ell(cx, cy, rx, ry, a=0.0, k=64):
    pts = [rot((cx + rx * math.cos(2 * math.pi * i / k), cy + ry * math.sin(2 * math.pi * i / k)), a, (cx, cy))
           for i in range(k)]
    return poly(pts)


def lens(cx, cy, L, W, a=0.0):
    """Leaf/lens: tips L apart along angle a (radians), max width ~W."""
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    t1 = (cx - ux * L / 2, cy - uy * L / 2)
    t2 = (cx + ux * L / 2, cy + uy * L / 2)
    c1 = (cx + px * W, cy + py * W)
    c2 = (cx - px * W, cy - py * W)
    return f"M{pt(t1)}Q{pt(c1)} {pt(t2)}Q{pt(c2)} {pt(t1)}Z"


def leaf(x0, y0, a, L, W):
    """Leaf growing from base (x0,y0) in direction a."""
    cx, cy = x0 + math.cos(a) * L / 2, y0 + math.sin(a) * L / 2
    return lens(cx, cy, L, W, a)


def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def dbez(p0, p1, p2, p3, t):
    u = 1 - t
    return (3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0]),
            3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1]))


def tapered(p0, p1, p2, p3, w0, w1, k=40, wf=None):
    left, right = [], []
    for i in range(k + 1):
        t = i / k
        x, y = bez(p0, p1, p2, p3, t)
        dx, dy = dbez(p0, p1, p2, p3, t)
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        w = (wf(t) if wf else w0 + (w1 - w0) * t) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return poly(left + right[::-1])


def sparkle(cx, cy, r, a=0.0, k=0.16):
    pts = [rot((cx, cy - r), a, (cx, cy)), rot((cx + r, cy), a, (cx, cy)),
           rot((cx, cy + r), a, (cx, cy)), rot((cx - r, cy), a, (cx, cy))]
    c = [rot((cx + r * k, cy - r * k), a, (cx, cy)), rot((cx + r * k, cy + r * k), a, (cx, cy)),
         rot((cx - r * k, cy + r * k), a, (cx, cy)), rot((cx - r * k, cy - r * k), a, (cx, cy))]
    return (f"M{pt(pts[0])}Q{pt(c[0])} {pt(pts[1])}Q{pt(c[1])} {pt(pts[2])}"
            f"Q{pt(c[2])} {pt(pts[3])}Q{pt(c[3])} {pt(pts[0])}Z")


def heart(cx, cy, s, a=0.0):
    raw = [(0, 1), (-0.15, 0.85), (-1, 0.35), (-1, -0.25), (-1, -0.65), (-0.7, -0.95), (-0.4, -0.95),
           (-0.15, -0.95), (0, -0.75), (0, -0.58), (0, -0.75), (0.15, -0.95), (0.4, -0.95),
           (0.7, -0.95), (1, -0.65), (1, -0.25), (1, 0.35), (0.15, 0.85), (0, 1)]
    p = [rot((cx + x * s, cy + y * s), a, (cx, cy)) for x, y in raw]
    d = f"M{pt(p[0])}"
    for i in range(1, len(p), 3):
        d += f"C{pt(p[i])} {pt(p[i + 1])} {pt(p[i + 2])}"
    return d + "Z"


def tulip(cx, cy, s):
    """Folk tulip, base at (cx,cy), opening upward, size s."""
    d = (f"M{pt((cx, cy))}C{pt((cx - s * .9, cy - s * .1))} {pt((cx - s * .95, cy - s * .8))} {pt((cx - s * .7, cy - s * 1.25))}"
         f"C{pt((cx - s * .55, cy - s * .9))} {pt((cx - s * .35, cy - s * .8))} {pt((cx - s * .22, cy - s * .78))}"
         f"C{pt((cx - s * .2, cy - s * 1.1))} {pt((cx - s * .1, cy - s * 1.3))} {pt((cx, cy - s * 1.45))}"
         f"C{pt((cx + s * .1, cy - s * 1.3))} {pt((cx + s * .2, cy - s * 1.1))} {pt((cx + s * .22, cy - s * .78))}"
         f"C{pt((cx + s * .35, cy - s * .8))} {pt((cx + s * .55, cy - s * .9))} {pt((cx + s * .7, cy - s * 1.25))}"
         f"C{pt((cx + s * .95, cy - s * .8))} {pt((cx + s * .9, cy - s * .1))} {pt((cx, cy))}Z")
    return d


# ---------------------------------------------------------------- elements
def P(d):
    return f'<path d="{d}"/>'


def H(d):  # hole (cut away)
    return f'<path fill="#000" d="{d}"/>'


def K(d):  # keep (restore inside a hole)
    return f'<path fill="#fff" d="{d}"/>'


def CUT(d, w=1.8):
    return f'<path fill="none" stroke="#000" stroke-width="{n(w)}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>'


def g(s, tr):
    return f'<g transform="{tr}">{s}</g>'


def mir(s, W):
    return g(s, f"matrix(-1 0 0 1 {n(W)} 0)")


def both(s, W):
    return s + mir(s, W)


def write(name, W, H_, ink, holes="", accent="", defs="", raw_after=""):
    mid = f"art-{name}-cut"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n(W)} {n(H_)}">']
    out.append("<defs>")
    if holes:
        out.append(f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="-20" y="-20" width="{n(W + 40)}" height="{n(H_ + 40)}">'
                   f'<rect x="-20" y="-20" width="{n(W + 40)}" height="{n(H_ + 40)}" fill="#fff"/>{holes}</mask>')
    out.append(defs + "</defs>")
    if holes:
        out.append(f'<g fill="currentColor" mask="url(#{mid})">{ink}</g>')
    else:
        out.append(f'<g fill="currentColor">{ink}</g>')
    out.append(raw_after)
    if accent:
        out.append(f'<g class="accent" fill="currentColor">{accent}</g>')
    out.append("</svg>")
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write("".join(out) + "\n")


# ---------------------------------------------------------------- components
def sun(cx, cy, s=1.0):
    """Radiant sun with a face. Returns (ink, holes, accent)."""
    ink, holes, acc = [], [], []
    R = 23 * s
    ink.append(P(circ(cx, cy, R)))
    for i in range(12):
        a = -math.pi / 2 + i * math.pi / 6
        b = 0.15
        r0, r1 = 27.5 * s, 54 * s
        p1 = (cx + r0 * math.cos(a - b), cy + r0 * math.sin(a - b))
        p2 = (cx + r0 * math.cos(a + b), cy + r0 * math.sin(a + b))
        tip = (cx + r1 * math.cos(a), cy + r1 * math.sin(a))
        mid_r = (r0 + r1) / 2
        c1 = (cx + mid_r * math.cos(a - b * 1.3), cy + mid_r * math.sin(a - b * 1.3))
        c2 = (cx + mid_r * math.cos(a + b * 0.3), cy + mid_r * math.sin(a + b * 0.3))
        # flame ray: curved like a wavy blade
        ink.append(P(f"M{pt(p1)}Q{pt(c1)} {pt(tip)}Q{pt(c2)} {pt(p2)}Z"))
        a2 = a + math.pi / 12
        q1 = (cx + r0 * math.cos(a2 - .09), cy + r0 * math.sin(a2 - .09))
        q2 = (cx + r0 * math.cos(a2 + .09), cy + r0 * math.sin(a2 + .09))
        t2 = (cx + 40 * s * math.cos(a2), cy + 40 * s * math.sin(a2))
        ink.append(P(poly([q1, t2, q2])))
        ink.append(P(circ(cx + 44.5 * s * math.cos(a2), cy + 44.5 * s * math.sin(a2), 2.3 * s)))
    # face
    holes.append(H(lens(cx - 8.5 * s, cy - 4 * s, 10 * s, 4.2 * s)))
    holes.append(H(lens(cx + 8.5 * s, cy - 4 * s, 10 * s, 4.2 * s)))
    holes.append(K(circ(cx - 8.5 * s, cy - 4 * s, 1.6 * s)))
    holes.append(K(circ(cx + 8.5 * s, cy - 4 * s, 1.6 * s)))
    holes.append(CUT(f"M{pt((cx - 14 * s, cy - 11 * s))}Q{pt((cx - 8.5 * s, cy - 14 * s))} {pt((cx - 3 * s, cy - 10.5 * s))}", 1.6 * s))
    holes.append(CUT(f"M{pt((cx + 14 * s, cy - 11 * s))}Q{pt((cx + 8.5 * s, cy - 14 * s))} {pt((cx + 3 * s, cy - 10.5 * s))}", 1.6 * s))
    holes.append(CUT(f"M{pt((cx - 3 * s, cy - 9 * s))}Q{pt((cx - 2 * s, cy + 3 * s))} {pt((cx, cy + 4 * s))}Q{pt((cx + 2 * s, cy + 4.5 * s))} {pt((cx + 3 * s, cy + 3 * s))}", 1.5 * s))
    holes.append(H(f"M{pt((cx - 9 * s, cy + 9 * s))}Q{pt((cx, cy + 17 * s))} {pt((cx + 9 * s, cy + 9 * s))}Q{pt((cx, cy + 13 * s))} {pt((cx - 9 * s, cy + 9 * s))}Z"))
    # ring cut separating disc from rays
    holes.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(25.3 * s)}" fill="none" stroke="#000" stroke-width="{n(1.6 * s)}"/>')
    acc.append(P(circ(cx - 14 * s, cy + 6 * s, 3 * s)))
    acc.append(P(circ(cx + 14 * s, cy + 6 * s, 3 * s)))
    return "".join(ink), "".join(holes), "".join(acc)


def bird(s=""):
    """Folk bird facing right, approx in box x 6..62, y 32..78. Returns (ink, holes)."""
    body = ("M50,46 C57,54 56,67 46,73 C38,78 28,77 22,71 "
            "L5,66 L13,60 L3,52 L15,53 L8,42 L24,56 C28,48 35,42 42,40 Z")
    ink = P(body) + P(circ(47, 40, 7.6)) + P("M53,36.5 L63,40.5 L53,44 Z")
    holes = (H(circ(48.2, 39, 1.9)) +
             H("M27,63 C31,54 40,52 47,56 C42,58 39,62 37,67 C34,66 30,65 27,63 Z") +
             CUT("M13,57 L22,61", 1.3) + CUT("M12,49 L22,58", 1.3) +
             H(circ(46, 63, 1.4)) + H(circ(42.5, 68, 1.4)) + H(circ(49.5, 58.5, 1.2)))
    return ink, holes


def fox():
    """Sitting fox facing left, tail curled right, box ~ 14..110 x 10..106."""
    body = ("M14,41 L29,33 L33,13 L42,26 L51,11 L55,31 "
            "C63,41 68,52 72,63 C78,77 80,92 74,105 L34,105 "
            "C33,92 32,75 38,61 C40,53 36,49 30,47 L20,45 Z")
    tail = "M68,104 C96,106 112,90 106,68 C103,56 92,54 90,63 C94,74 92,90 66,94 Z"
    ink = P(body) + P(tail)
    holes = (H(lens(37, 31.5, 7, 2.6, -0.35)) +
             H("M35,18 L40,26 L34,27 Z") + H("M50,17 L52,29 L46,27 Z") +
             CUT("M39,62 C45,72 46,88 42,101", 1.8) +
             CUT("M52,105 L52,86", 1.6) +
             CUT("M91,66 C96,62 104,62 107,66", 1.8) +
             H(circ(16.5, 41.5, 1.2)))
    return ink, holes


def mole(peek=False):
    """A mole (after Momfer de Mol) peeking out of the ground, facing left.
    Origin at ground level below its chest. With peek, there is no molehill and
    only the front paw is drawn (the rest is hidden behind something).
    Returns (ink, holes, accent)."""
    mound = "M-34,40 C-30,8 -20,-4 0,-5 C20,-4 30,8 34,40 Z"
    body = ("M15,-3 C17,-17 11,-28 -1,-29 C-9,-29.5 -15,-25 -19,-19.5 "
            "C-22,-17.5 -25,-16.5 -27.5,-15.8 C-29,-15.2 -29,-13 -27.5,-12.6 "
            "C-24,-11.8 -20,-11.2 -17,-10 C-14,-6 -9,-3.5 -4,-3.5 Z")
    # big spade-shaped digging paws resting on the rim of the hill
    paw_l = "M-21,-1.5 C-20,-6 -14,-8 -9,-6.5 C-6,-5.5 -5,-2.5 -7,-0.5 C-11,1.5 -17,1.5 -21,-1.5 Z"
    paw_r = "M4,-1.5 C5,-6 11,-8 16,-6.5 C19,-5.5 20,-2.5 18,-0.5 C14,1.5 8,1.5 4,-1.5 Z"
    whiskers = ""
    for (ex, ey) in ((-36, -19), (-37, -14.5), (-35, -10)):
        whiskers += P(tapered((-22, -14.5), ((-22 + ex) / 2, (-14.5 + ey) / 2 - 0.6),
                              ((-22 + ex) / 2, (-14.5 + ey) / 2 - 0.6), (ex, ey), 1.1, 0.3, k=12))
    crumbs = P(circ(-40, 0, 1.6)) + P(circ(-45, 5, 1.1)) + P(circ(39, -2, 1.4)) + P(circ(44, 4, 1.0)) + P(circ(36, -8, 0.9))
    if peek:
        ink = P(body) + P(paw_l) + whiskers
        holes = (CUT("M-26,-1.5 C-18,1.5 -8,1.5 -3,-0.5", 1.6) + CUT(paw_l, 1.3) +
                 CUT("M-14,-20.2 Q-11,-16.8 -8,-20.2", 1.7) +
                 "".join(CUT(f"M{n(x + 4.5)},{n(y)} L{n(x + 0.8)},{n(y + 0.9)}", 1.2)
                         for (x, y) in ((-21, -4.6), (-21.4, -2.6), (-20.6, -0.6))))
        return ink, holes, P(circ(-28.6, -14.2, 2.6))
    ink = P(mound) + P(body) + P(paw_l) + P(paw_r) + whiskers + crumbs
    holes = (
        # rim of the hole the mole looks out of, and the outlines of the paws
        CUT("M-24,-2.5 C-12,1 8,1 24,-2.5", 1.5) +
        CUT(paw_l, 1.2) + CUT(paw_r, 1.2) +
        # a contented, nearly-shut eye
        CUT("M-14,-20.2 Q-11,-16.8 -8,-20.2", 1.5) +
        # digging claws cut into the front of each paw
        "".join(CUT(f"M{n(x + 4.5)},{n(y)} L{n(x + 0.8)},{n(y + 0.9)}", 1.0)
                for x0 in (-21, 4) for (x, y) in ((x0, -4.6), (x0 - 0.4, -2.6), (x0 + 0.4, -0.6))) +
        # papercut fur: a row of little dots along the back
        H(circ(-1, -22.5, 1.1)) + H(circ(4, -21.5, 1.1)) + H(circ(8.5, -18.5, 1.1)) + H(circ(11, -13.5, 1.1)) +
        H(circ(2.5, -15.5, 1.0)) + H(circ(6.5, -11, 1.0)) +
        # the molehill: crumbs of earth cut out of it
        H(circ(-20, 12, 1.6)) + H(circ(-8, 8, 1.4)) + H(circ(6, 10, 1.6)) + H(circ(19, 13, 1.4)) +
        H(circ(-13, 20, 1.3)) + H(circ(12, 20, 1.3)) + H(circ(0, 17, 1.2))
    )
    acc = P(circ(-28.6, -14.2, 2.4))  # the nose
    return ink, holes, acc


def owl(cx, cy, s=1.0, sleepy=False):
    ink, holes, acc = [], [], []
    tr = f"translate({n(cx)} {n(cy)}) scale({n(s)})"
    half = ("M0,-40 C-16,-40 -24,-34 -27,-29 L-31,-46 L-36,-25 C-40,-14 -40,6 -36,20 "
            "C-31,34 -18,42 0,42 Z")
    i = P(half) + mir(P(half), 0)
    h = []
    for sx in (-1, 1):
        ex = 14 * sx
        h.append(H(circ(ex, -14, 13)))
        h.append(K(circ(ex, -14, 10.5)))
        if sleepy:
            h.append(CUT(f"M{n(ex - 7)},-13 Q{n(ex)},-7 {n(ex + 7)},-13", 2.2))
            h.append(CUT(f"M{n(ex - 5)},-9.5 L{n(ex - 6.5)},-6.5 M{n(ex)},-8 L{n(ex)},-5 M{n(ex + 5)},-9.5 L{n(ex + 6.5)},-6.5", 1.3))
        else:
            h.append(H(circ(ex, -14, 5.5)))
        # wing line
        h.append(CUT(f"M{n(27 * sx)},-4 C{n(31 * sx)},14 {n(26 * sx)},28 {n(14 * sx)},36", 2))
    h.append(H("M0,-6 L4,0 L0,9 L-4,0 Z"))
    for row, (y, xs) in enumerate([(15, (-12, 0, 12)), (23, (-18, -6, 6, 18)), (31, (-12, 0, 12))]):
        for x in xs:
            h.append(CUT(f"M{n(x - 3.2)},{n(y)} Q{n(x)},{n(y + 4)} {n(x + 3.2)},{n(y)}", 1.6))
    if not sleepy:
        acc.append(g(P(circ(-14, -14, 3)) + P(circ(14, -14, 3)), tr))
    ink.append(g(i, tr))
    holes.append(g("".join(h), tr))
    return "".join(ink), "".join(holes), "".join(acc)


# ---------------------------------------------------------------- emblems
def emblem_A():
    ink, holes, acc = sun(60, 60)
    write("A", 120, 120, ink, holes, acc)


def emblem_B():
    b_ink, b_holes = bird()
    branch = tapered((6, 88), (35, 82), (85, 82), (114, 88), 5, 5, wf=lambda t: 2.5 + 3.5 * math.sin(math.pi * t))
    leaves = ""
    lh = ""
    for x, a in ((16, 2.2), (30, 1.3), (90, 1.84), (104, 0.94)):
        leaves += P(leaf(x, 86, a, 16, 6.5))
    legs = P(poly([(36, 74), (38.5, 74), (40, 86), (37.5, 86)])) + P(poly([(42, 72), (44.5, 72), (44.5, 86), (42, 86)]))
    half = g(b_ink + legs, "translate(-4 0)")
    stalk = P(poly([(59, 84), (61, 84), (61, 54), (59, 54)]))
    ink = both(half, 120) + P(branch) + leaves + stalk + P(leaf(60, 76, -2.4, 14, 6)) + P(leaf(60, 76, -0.74, 14, 6))
    holes = both(g(b_holes, "translate(-4 0)"), 120)
    for x, a in ((16, 2.2), (30, 1.3), (90, 1.84), (104, 0.94)):
        lh += CUT(f"M{n(x + math.cos(a) * 3)},{n(86 + math.sin(a) * 3)} L{n(x + math.cos(a) * 12)},{n(86 + math.sin(a) * 12)}", 1.1)
    acc = P(tulip(60, 54, 9)) + P(heart(60, 24, 4.5))
    write("B", 120, 120, ink, holes + lh, acc)


def emblem_C():
    frame = "M24,110 L24,46 A36,36 0 0 1 96,46 L96,110 Z"
    ink = P(frame) + P("M16,108 L104,108 L104,115 L16,115 Z")
    holes = H("M30,110 L30,47 A30,30 0 0 1 90,47 L90,110 Z")
    holes += K("M34,108 L34,48 A26,26 0 0 1 86,48 L86,108 Z")
    for x in (51, 69):
        holes += H(f"M{n(x - .9)},28 L{n(x + .9)},28 L{n(x + .9)},104 L{n(x - .9)},104 Z")
    # hinges: cut outlines of strap hinges
    for y in (46, 88):
        holes += CUT(f"M37,{y} L60,{y} L64,{y - 3} M60,{y} L64,{y + 3}", 1.6)
    # keyhole
    holes += H(circ(76, 70, 3.6)) + H("M74.4,72 L77.6,72 L79,81 L73,81 Z")
    # ring handle
    holes += f'<circle cx="76" cy="58" r="4" fill="none" stroke="#000" stroke-width="1.5"/>'
    # voussoir notches on frame
    for i in range(1, 8):
        a = math.pi + i * math.pi / 8
        p1 = (60 + 30 * math.cos(a), 46 + 30 * math.sin(a))
        p2 = (60 + 36 * math.cos(a), 46 + 36 * math.sin(a))
        holes += CUT(f"M{pt(p1)} L{pt(p2)}", 1.4)
    for y in (62, 78, 94):
        holes += CUT(f"M24,{y} L30,{y} M90,{y} L96,{y}", 1.4)
    acc = P(heart(60, 31, 5))
    write("C", 120, 120, ink, holes, acc)


def emblem_D():
    ink = P(circ(60, 74, 31)) + P("M48,42 L72,42 L66,51 L54,51 Z")
    holes = H(circ(60, 74, 23.5))
    for i in range(16):
        a = i * math.pi / 8
        holes += H(circ(60 + 27.3 * math.cos(a), 74 + 27.3 * math.sin(a), 1.35))
    ink += P(sparkle(20, 26, 11)) + P(sparkle(100, 30, 8)) + P(sparkle(103, 102, 7)) + P(sparkle(16, 100, 6)) + P(sparkle(88, 10, 4.5))
    gem = "M60,17 L76,32 L60,47 L44,32 Z"
    acc = P(gem)
    raw = (f'<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round">'
           f'<path d="M44,32 L76,32 M52,24.5 L60,32 L68,24.5 M60,32 L60,47"/></g>')
    write("D", 120, 120, ink, holes, acc, raw_after="")
    # facet lines drawn as cuts through the accent: emulate by masking accent
    path = os.path.join(OUT, "D.svg")
    s = open(path).read()
    s = s.replace("</defs>", '<mask id="art-D-gem" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">'
                  '<rect width="120" height="120" fill="#fff"/><path fill="none" stroke="#000" stroke-width="1.4" '
                  'stroke-linejoin="round" d="M46,32 L74,32 M52,24.5 L60,32 L68,24.5 M60,32 L60,45"/></mask></defs>')
    s = s.replace('<g class="accent" fill="currentColor">', '<g class="accent" fill="currentColor" mask="url(#art-D-gem)">')
    open(path, "w").write(s)


def emblem_E():
    ink = (P(circ(60, 11, 6)) + P("M33,39 C35,26 47,19 60,19 C73,19 85,26 87,39 Z") +
           P("M36,38 L84,38 L84,93 L36,93 Z") + P("M31,92 L89,92 L82,103 L38,103 Z") +
           P("M30,37 L90,37 L90,42 L30,42 Z"))
    for x in (42, 52, 60, 68, 78):
        ink += P(circ(x, 104, 3.4))
    holes = H(circ(60, 11, 3.2))
    holes += H("M45,88 L45,57 A15,15 0 0 1 75,57 L75,88 Z")
    holes += CUT("M40,26 Q60,14 80,26", 1.4) + CUT("M45,32 Q60,24 75,32", 1.4)
    holes += H(circ(40, 66, 1.6)) + H(circ(80, 66, 1.6)) + H(circ(40, 76, 1.6)) + H(circ(80, 76, 1.6))
    holes += K("M55,88 L65,88 L65,81 L55,81 Z") + K("M52,88 L68,88 L68,86 L52,86 Z")
    ink += P(sparkle(16, 30, 7)) + P(sparkle(104, 52, 6)) + P(sparkle(20, 74, 4.5)) + P(sparkle(101, 22, 4))
    acc = P("M60,58 C67,66 69,74 60,80 C51,74 53,66 60,58 Z")
    write("E", 120, 120, ink, holes, acc)


def emblem_F():
    cloud = ""
    for x, y, r in ((24, 94, 9), (37, 88, 12), (53, 85, 13), (69, 85, 13), (84, 88, 12), (97, 94, 9),
                    (30, 101, 7), (46, 103, 8), (62, 104, 8), (78, 103, 8), (91, 101, 7)):
        cloud += P(circ(x, y, r))
    cloud += P("M24,94 L97,94 L97,101 L24,101 Z")
    castle_half = ("M30,86 L30,48 L27,48 L36,30 L45,48 L42,48 L42,60 L45,60 L45,56 L48,56 L48,60 "
                   "L51,60 L51,34 L48,34 L60,9 L60,86 Z")
    ink = cloud + both(P(castle_half), 120)
    ink += P("M59.3,3 L60.7,3 L60.7,11 L59.3,11 Z") + P("M60.7,3 L69,5.5 L60.7,8.5 Z")
    holes = H("M55,86 L55,77 A5,5 0 0 1 65,77 L65,86 Z")
    holes += H("M57.5,48 L57.5,43 A2.5,2.5 0 0 1 62.5,43 L62.5,48 Z")
    holes += H("M57.5,64 L57.5,59 A2.5,2.5 0 0 1 62.5,59 L62.5,64 Z")
    for x in (36, 84):
        holes += H(f"M{x - 2},66 L{x - 2},62 A2,2 0 0 1 {x + 2},62 L{x + 2},66 Z")
    holes += CUT("M30,86 L90,86", 1.6)
    # cloud swirls
    holes += CUT("M40,96 Q46,91 52,96", 1.4) + CUT("M68,96 Q74,91 80,96", 1.4) + CUT("M55,100 Q60,96 65,100", 1.4)
    ink += P(sparkle(14, 22, 7)) + P(sparkle(104, 20, 6)) + P(sparkle(100, 62, 4)) + P(sparkle(18, 62, 4))
    acc = P(circ(60, 24, 2.6))
    write("F", 120, 120, ink, holes, acc)


def emblem_G():
    half = ("M60,24 C44,24 30,34 27,50 C25,64 28,80 36,90 C43,98 52,102 60,102 Z")
    horn = "M34,38 C20,34 12,22 17,6 C20,17 28,24 44,27 Z"
    ear = "M29,50 L9,44 C12,54 18,62 28,68 Z"
    tufts = "M44,27 L46,15 L52,24 L55,12 L60,22 Z"
    ink = both(P(half) + P(horn) + P(ear) + P(tufts), 120)
    hl = (H(circ(47, 53, 7)) + K(circ(47, 53, 5)) +
          CUT("M37,43 L55,47", 3) +
          H(circ(55.5, 74, 2)) +
          CUT("M22,49 L13,46", 1.3) +
          CUT("M18,15 C20,22 26,26 33,29", 1.2) +
          H("M46,93 L50,77 L54,93 Z"))
    hl_keep = K("M47.5,92 L50,80 L52.5,92 Z")
    nose = CUT("M54,58 C50,68 50,78 56,79 C58,80 62,80 64,79 C70,78 70,68 66,58", 1.8)
    mouth = H("M38,85 Q60,98 82,85 Q60,93 38,85 Z")
    holes = both(hl, 120) + nose + mouth + both(hl_keep, 120)
    acc = P(circ(47, 53, 2.6)) + P(circ(73, 53, 2.6))
    write("G", 120, 120, ink, holes, acc)


def emblem_H():
    body = ("M12,94 C12,78 18,66 32,63 C46,61 58,63 69,58 "
            "L70,42 C70,34 74,26 84,24 C94,23 99,31 99,40 L99,47 L101,52 L97,53 C96,57 93,59 90,60 "
            "L91,70 C93,80 97,84 108,86 C111,87 112,90 110,94 Z")
    tail = tapered((15, 90), (2, 82), (2, 64), (12, 60), 3.5, 2)
    ink = P(body) + P(tail) + P(circ(13, 59, 3.5)) + P("M6,94 L114,94 L114,104 L6,104 Z") + P("M10,104 L110,104 L106,110 L14,110 Z")
    holes = (H(lens(92, 39, 6, 2.2, 0)) +
             CUT("M85,27 C82,38 83,50 88,58", 1.8) +
             CUT("M73,36 L83,34 M72,43 L83,42 M72,50 L84,50", 1.4) +
             CUT("M22,92 C21,78 30,70 44,72", 1.7) +
             CUT("M76,92 C79,84 88,82 99,87", 1.6) +
             CUT("M92,40 L97,41", 1.0))
    for i in range(9):
        x = 14 + i * 11.5
        holes += H(f"M{n(x)},97 L{n(x + 7)},97 L{n(x + 7)},101 L{n(x)},101 Z")
    acc = P(lens(92, 39, 4.6, 1.4, 0))
    write("H", 120, 120, ink, holes, acc)


def emblem_J():
    ink, holes, acc = owl(60, 56, 1.12)
    branch = tapered((8, 108), (40, 104), (80, 104), (112, 108), 5, 5, wf=lambda t: 3 + 3 * math.sin(math.pi * t))
    ink += P(branch) + P(leaf(14, 107, 2.5, 14, 6)) + P(leaf(106, 107, 0.64, 14, 6))
    for x in (49, 54, 66, 71):
        ink += P(circ(x, 103, 2.6))
    write("J", 120, 120, ink, holes, acc)


def emblem_K():
    ink, holes = fox()
    ink += P("M8,106 L112,106 L112,110 L8,110 Z")
    acc = P(heart(98, 22, 5, 0.2))
    write("K", 120, 120, g(ink, "translate(2 2)"), g(holes, "translate(2 2)"), "")


def emblem_L():
    cx, cy = 60, 60
    ink = f'<path fill-rule="evenodd" d="{circ(cx, cy, 42)}{circ(cx, cy, 34.5)}"/>'
    holes = ""
    sp = ""
    for i in range(8):
        a = i * math.pi / 4
        sp += P(lens(cx + 22 * math.cos(a), cy + 22 * math.sin(a), 30, 7, a))
        sp += P(circ(cx + 49 * math.cos(a), cy + 49 * math.sin(a), 5.2))
        sp += P(lens(cx + 44.5 * math.cos(a), cy + 44.5 * math.sin(a), 8, 4, a))
    ink += sp + P(circ(cx, cy, 11))
    for i in range(16):
        a = i * math.pi / 8 + math.pi / 16
        holes += H(circ(cx + 38.3 * math.cos(a), cy + 38.3 * math.sin(a), 1.5))
    for i in range(8):
        a = i * math.pi / 4
        holes += H(lens(cx + 22 * math.cos(a), cy + 22 * math.sin(a), 12, 2.4, a))
        holes += H(circ(cx + 49 * math.cos(a), cy + 49 * math.sin(a), 2))
    holes += H(circ(cx, cy, 5.5))
    acc = P(circ(cx, cy, 3))
    write("L", 120, 120, ink, holes, acc)


def emblem_M():
    ink = ""
    # three-strand plait
    for i in range(9):
        y = 22 + i * 7.2
        if i % 2 == 0:
            ink += P(lens(56.6, y, 15, 6.4, -0.95))
        else:
            ink += P(lens(63.4, y, 15, 6.4, 0.95))
    ink += P(circ(60, 12, 7))
    # scissors
    blade = "M58.5,96 C52,92 44,84 38,74 C46,80 54,86 61.5,93 Z"
    ink += both(P(blade), 120)
    ink += both(P(poly([(57, 95), (60, 97), (52, 106), (49, 104)])), 120)
    ink += P(circ(46, 109, 7)) + P(circ(74, 109, 7))
    ink += P(circ(60, 95, 3.2))
    # drop spindles either side (the Fates), their threads running into the knot
    for x in (20, 100):
        ink += P(tapered((x, 16), (x, 40), (x, 70), (x, 100), 2.6, 2.6))
        ink += P(lens(x, 50, 44, 17, math.pi / 2))
        ink += P(ell(x, 82, 10, 3.6))
        ink += P(tapered((x, 18), (x + (60 - x) * .3, 4), (x + (60 - x) * .7, 4), (60 + (x - 60) * 0.12, 11), 1.8, 1.8))
    holes = H(circ(60, 12, 3.5)) + H(circ(46, 109, 4)) + H(circ(74, 109, 4)) + H(circ(60, 95, 1.2))
    for x in (20, 100):
        for y in (38, 45, 52, 59):
            w = 5 - abs(y - 49) * 0.12
            holes += CUT(f"M{n(x - w)},{y + 2} L{n(x + w)},{y - 2}", 1.3)
    acc = P(circ(60, 12, 2))
    write("M", 120, 120, ink, holes, acc)


def emblem_N():
    def die(cx, cy, a):
        s = 17
        pts = [rot((cx + x, cy + y), a, (cx, cy)) for x, y in ((-s, -s), (s, -s), (s, s), (-s, s))]
        # rounded square via quadratic corners
        d = ""
        for i in range(4):
            p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % 4]
            a0 = (p1[0] + (p0[0] - p1[0]) * .2, p1[1] + (p0[1] - p1[1]) * .2)
            a1 = (p1[0] + (p2[0] - p1[0]) * .2, p1[1] + (p2[1] - p1[1]) * .2)
            d += ("M" if i == 0 else "L") + pt(a0) + "Q" + pt(p1) + " " + pt(a1)
        d += "Z"
        pips = ""
        for x, y in ((-9, -9), (9, -9), (0, 0), (-9, 9), (9, 9)):
            p = rot((cx + x, cy + y), a, (cx, cy))
            pips += H(circ(p[0], p[1], 3.3))
        return P(d), pips
    di, dh = die(37, 74, -0.26)
    ink = both(di, 120)
    holes = both(dh, 120)
    stem = tapered((60, 54), (61, 46), (58, 40), (60, 33), 2.4, 1.6)
    clover = ""
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        clover += P(heart(60 + 8.5 * math.cos(a), 24 + 8.5 * math.sin(a), 8, a + math.pi / 2))
    ink += P(stem)
    ink += P(sparkle(16, 28, 6)) + P(sparkle(104, 28, 6)) + P(sparkle(60, 106, 5))
    write("N", 120, 120, ink, holes, clover)


def emblem_P():
    half = "M60,96 L22,96 Q19,96 19,92 L19,76 L14,40 L34,60 L42,28 L52,56 L60,18 Z"
    ink = both(P(half) + P(circ(14, 37, 5)) + P(circ(42, 25, 5)), 120) + P(circ(60, 14, 5.5))
    ink += P("M17,96 L103,96 L103,102 L17,102 Z")
    hh = (H(lens(42, 46, 12, 4, math.pi / 2)) + H(lens(20, 60, 9, 3, 1.1)) + H(circ(32, 86, 3)) +
          H(circ(44, 86, 2.2)) + CUT("M19,76 L101,76", 1.6))
    holes = both(hh, 120) + H(lens(60, 44, 16, 4.5, math.pi / 2)) + H("M60,79 L67,86 L60,93 L53,86 Z")
    holes += CUT("M19,99 L101,99", 1.2)
    acc = P("M60,81.5 L64.5,86 L60,90.5 L55.5,86 Z") + P(circ(60, 14, 3))
    write("P", 120, 120, ink, holes, acc)


def emblem_Q():
    half = (P("M57,22 L60,22 L60,100 L56,100 Z") +
            P("M42,112 L60,112 L60,98 L50,98 Q46,104 42,106 Z") + P("M30,106 L60,106 L60,114 L30,114 Z") +
            P(tapered((60, 28), (40, 26), (22, 26), (12, 30), 6, 3.4)) + P(circ(12, 30, 4)) +
            P(poly([(11.2, 33), (12.8, 33), (24.5, 74), (23.5, 74)])) + P(poly([(11.2, 33), (12.8, 33), (0.5, 74), (-0.5, 74)])) +
            P("M-4,73 L28,73 Q22,90 12,90 Q2,90 -4,73 Z"))
    ink = both(g(half, "translate(6 0)") if False else half, 120)
    hl = CUT("M3,78 Q12,86 21,78", 1.3) + H(circ(12, 30, 1.6))
    holes = both(hl, 120) + H("M60,40 L62.2,46 L60,52 L57.8,46 Z") + H("M60,62 L62.2,68 L60,74 L57.8,68 Z")
    holes += CUT("M34,110 L86,110", 1.2)
    ink += P(circ(60, 17, 6.5))
    acc = P(heart(60, 17, 4.2))
    # pull pans inward a bit so the emblem sits within the box
    write("Q", 120, 120, g(ink, "translate(6 0) scale(0.9 1)"), g(holes, "translate(6 0) scale(0.9 1)"),
          g(acc, "translate(6 0) scale(0.9 1)"))


def emblem_R():
    body = "M44,36 L76,36 L81,110 L39,110 Z"
    ink = P(body) + P("M37,28 L83,28 L83,38 L37,38 Z") + P("M35,29 L60,3 L85,29 Z")
    for x in (37, 47, 57, 67, 77):
        ink += P(f"M{x},23 L{x + 6},23 L{x + 6},29 L{x},29 Z")
    ink += P("M30,110 L90,110 L90,115 L30,115 Z")
    ink += P("M59.3,0 L60.7,0 L60.7,6 L59.3,6 Z")
    holes = H("M55,58 L55,49 A5,5 0 0 1 65,49 L65,58 Z") + CUT("M42,33 L78,33", 1.3)
    holes += H("M54,110 L54,98 A6,6 0 0 1 66,98 L66,110 Z")
    for row in range(5):
        y = 66 + row * 7
        off = 0 if row % 2 else 5
        for x in range(44 + off, 78, 10):
            if abs(x + 3 - 60) < 9 and y > 92:
                continue
            holes += H(f"M{x},{y} L{x + 6},{y} L{x + 6},{y + 2.6} L{x},{y + 2.6} Z")
    holes += CUT("M44,12 L60,4 L76,12", 1.0) if False else ""
    holes += CUT("M47,22 L73,22", 1.0) if False else ""
    # hair braid from the window
    acc = ""
    pts = [(57, 58 + i * 5.4) for i in range(0)]
    for i in range(10):
        t = i / 9
        x = 55 - 22 * t ** 1.6
        y = 60 + 48 * t
        acc += P(lens(x, y, 8.5, 4.2 - t * 1.2, math.pi / 2 + (0.5 if i % 2 else -0.5) - t * 0.4))
    acc += P(circ(55, 57, 4))
    write("R", 120, 120, ink, holes, acc)


def emblem_S():
    stem = tapered((60, 112), (59, 90), (61, 70), (60, 48), 4.5, 3.4)
    half = ""
    half += P(leaf(59, 74, -2.55, 24, 11)) + P(leaf(59, 96, -2.9, 20, 9))
    for y in (62, 84, 103):
        half += P(poly([(58.5, y), (51, y - 4.5), (58.5, y - 2.8)]))
    bramble = tapered((58, 110), (40, 108), (22, 96), (14, 76), 4, 1.6)
    half += P(bramble)
    for t in (0.35, 0.6, 0.82):
        x, y = bez((58, 110), (40, 108), (22, 96), (14, 76), t)
        dx, dy = dbez((58, 110), (40, 108), (22, 96), (14, 76), t)
        L = math.hypot(dx, dy)
        nx, ny = dy / L, -dx / L
        half += P(poly([(x - dx / L * 2.2, y - dy / L * 2.2), (x + nx * 6 - dx / L * 2, y + ny * 6 - dy / L * 2), (x + dx / L * 2.2, y + dy / L * 2.2)]))
    half += P(circ(14, 74, 3)) + P(leaf(20, 90, -2.1, 12, 5))
    half += P(leaf(58, 50, 2.6, 13, 5))
    ink = both(half, 120) + P(stem)
    lh = CUT(f"M{n(58 - 3)},{n(73)} L{n(42)},{n(65)}", 1.2) + CUT("M56,95 L42,92", 1.1)
    holes = both(lh, 120)
    # rose bloom (accent) with cut spiral via mask
    bloom = ""
    for i in range(7):
        a = -math.pi / 2 + i * 2 * math.pi / 7
        bloom += P(circ(60 + 13 * math.cos(a), 32 + 13 * math.sin(a), 9.5))
    bloom += P(circ(60, 32, 15))
    spiral = "M60,32 C63,30 64,35 60,36 C55,37 54,30 59,27 C65,24 70,31 67,37 C64,43 54,43 51,36"
    defs = ('<mask id="art-S-bloom" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">'
            '<rect width="120" height="120" fill="#fff"/>'
            f'<path d="{spiral}" fill="none" stroke="#000" stroke-width="2" stroke-linecap="round"/>'
            '<path d="M44,22 Q48,26 49,32 M76,22 Q72,26 71,32 M50,46 Q55,43 60,45 Q65,43 70,46" fill="none" stroke="#000" stroke-width="1.6" stroke-linecap="round"/>'
            '</mask>')
    write("S", 120, 120, ink, holes, "", defs=defs)
    path = os.path.join(OUT, "S.svg")
    s = open(path).read().replace("</svg>", f'<g class="accent" fill="currentColor" mask="url(#art-S-bloom)">{bloom}</g></svg>')
    open(path, "w").write(s)


def emblem_T():
    hl = heart(45, 60, 27, -0.2)
    hr = heart(75, 60, 27, 0.2)
    sw = 7
    defs = (
        '<clipPath id="art-T-top"><rect x="0" y="0" width="120" height="55"/></clipPath>'
        '<clipPath id="art-T-bot"><rect x="0" y="55" width="120" height="65"/></clipPath>'
        '<mask id="art-T-mr" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">'
        '<rect width="120" height="120" fill="#fff"/>'
        f'<path d="{hl}" fill="none" stroke="#000" stroke-width="{sw + 6}" clip-path="url(#art-T-top)"/></mask>'
        '<mask id="art-T-ml" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">'
        '<rect width="120" height="120" fill="#fff"/>'
        f'<path d="{hr}" fill="none" stroke="#000" stroke-width="{sw + 6}" clip-path="url(#art-T-bot)"/></mask>'
    )
    rings = (f'<g fill="none" stroke="currentColor" stroke-width="{sw}" stroke-linejoin="round">'
             f'<path d="{hr}" mask="url(#art-T-mr)"/><path d="{hl}" mask="url(#art-T-ml)"/></g>')
    ink = ""
    for x, a in ((60, -math.pi / 2),):
        pass
    sprig = P(leaf(60, 104, -2.2, 14, 6)) + P(leaf(60, 104, -0.94, 14, 6)) + P("M59,96 L61,96 L61,112 L59,112 Z")
    sprig += P(leaf(60, 112, -2.8, 12, 5)) + P(leaf(60, 112, -0.34, 12, 5))
    ink = sprig + P(sparkle(12, 18, 6)) + P(sparkle(108, 18, 6)) + P(circ(60, 18, 2.5))
    write("T", 120, 120, ink, "", P(heart(60, 63, 6.5)), defs=defs, raw_after=rings)


def emblem_U():
    plate = "M22,10 L98,10 Q102,10 102,14 L102,18 Q102,22 98,22 L22,22 Q18,22 18,18 L18,14 Q18,10 22,10 Z"
    ink = P(plate) + g(P(plate), "translate(0 88)")
    for x in (29, 91):
        ink += P(f"M{x - 2.5},20 L{x + 2.5},20 L{x + 2.5},100 L{x - 2.5},100 Z")
        for y in (36, 60, 84):
            ink += P(ell(x, y, 5, 4.2))
    glass = ("M39,22 C39,44 53,52 56.5,60 C53,68 39,76 39,98 L81,98 C81,76 67,68 63.5,60 "
             "C67,52 81,44 81,22 Z")
    ink += P(glass)
    for x in (18, 102):
        ink += P(circ(x, 16, 4.5)) + P(circ(x, 104, 4.5))
    holes = H("M43.5,24 C43.5,44 56,51 58.6,60 C56,69 43.5,76 43.5,96 L76.5,96 C76.5,76 64,69 61.4,60 "
              "C64,51 76.5,44 76.5,24 Z")
    holes += CUT("M24,16 L96,16", 1.2) + CUT("M24,104 L96,104", 1.2)
    for x in (29, 91):
        for y in (36, 60, 84):
            holes += H(circ(x, y, 1.5))
    acc = (P("M46,38 C50,47 56,53 60,58 C64,53 70,47 74,38 Z") + P("M59.3,57 L60.7,57 L60.7,92 L59.3,92 Z") +
           P("M45,96 Q60,74 75,96 Z"))
    write("U", 120, 120, ink, holes, acc)


def emblem_V():
    half = ("M60,8 L60,104 L28,104 L28,66 L22,66 L44,46 L50,46 L50,30 L48,30 Z")
    tree = P(lens(12, 82, 44, 11, math.pi / 2)) + P("M11,96 L13,96 L13,106 L11,106 Z")
    ink = both(P(half) + tree, 120)
    ink += P("M59,0 L61,0 L61,12 L59,12 Z") + P("M55.5,3 L64.5,3 L64.5,5 L55.5,5 Z")
    ink += P("M4,104 L116,104 L116,109 L4,109 Z")
    hl = (H("M36,92 L36,80 A4,4 0 0 1 44,80 L44,92 Z") + CUT("M30,66 L50,66", 1.4) +
          CUT("M12,66 L12,98", 1.1) + CUT("M12,74 L7,68 M12,82 L6,75 M12,90 L6,83", 1.0))
    holes = both(hl, 120) + H("M54,104 L54,92 A6,6 0 0 1 66,92 L66,104 Z") + H(circ(60, 46, 6))
    holes += CUT("M50,58 L70,58", 1.4) + CUT("M52,30 L68,30", 1.4)
    for x in (42, 48, 72, 78):
        pass
    acc = P(circ(60, 46, 3.6)) + P(heart(60, 74, 4))
    write("V", 120, 120, ink, holes, acc)


def emblem_W():
    cx, cy = 60, 44
    ink = P(ell(cx, cy, 29, 36))
    for i in range(22):
        a = i * 2 * math.pi / 22
        ink += P(circ(cx + 29 * math.cos(a), cy + 36 * math.sin(a), 3.6))
    ink += P("M56,78 L64,78 L64,108 L56,108 Z") + P(ell(60, 86, 6.5, 4.5)) + P(ell(60, 100, 5, 4)) + P(circ(60, 112, 5))
    ink += P(lens(60, 5, 8, 6, math.pi / 2))
    holes = H(ell(cx, cy, 23, 30)) + K(ell(cx, cy, 20, 27))
    for i in range(22):
        a = i * 2 * math.pi / 22 + math.pi / 22
        holes += H(circ(cx + 26 * math.cos(a), cy + 33 * math.sin(a), 1.1))
    holes += H(lens(51.5, 39, 7, 2.6)) + H(lens(68.5, 39, 7, 2.6))
    holes += CUT("M47,32 Q51.5,29 56,32", 1.4) + CUT("M64,32 Q68.5,29 73,32", 1.4)
    holes += CUT("M60,40 L58.5,49 L61,50", 1.4)
    holes += CUT("M52,57 Q60,62 68,57", 1.8)
    holes += H(circ(60, 112, 2)) + CUT("M54,86 L66,86", 1.1)
    acc = P(circ(49, 51, 2.6)) + P(circ(71, 51, 2.6)) + P(circ(60, 5, 1.6))
    write("W", 120, 120, ink, holes, acc)


def emblem_X():
    half = ("M60,82 L26,82 C24,68 20,58 12,52 C8,49 5,50 4,54 "
            "C4,40 12,30 24,34 C32,37 38,48 42,58 C44,44 50,30 60,16 Z")
    band = "M24,82 L96,82 Q99,82 99,85 L99,97 Q99,100 96,100 L24,100 Q21,100 21,97 L21,85 Q21,82 24,82 Z"
    ink = both(P(half), 120) + P(band)
    bells_ink = ""
    hl = CUT("M42,58 C40,66 38,74 36,82", 1.8) + H("M30,68 L33,63 L36,68 L33,73 Z") + H("M44,40 L47,35 L50,40 L47,45 Z")
    holes = both(hl, 120) + H("M60,50 L63.5,56 L60,62 L56.5,56 Z") + H("M60,32 L62.5,36 L60,40 L57.5,36 Z")
    for x in (32, 46, 60, 74, 88):
        holes += H(f"M{x},86 L{x + 4},91 L{x},96 L{x - 4},91 Z")
    acc = P(circ(60, 12, 6)) + P(circ(6, 58, 6)) + P(circ(114, 58, 6))
    acc_cut = ('<mask id="art-X-bell" maskUnits="userSpaceOnUse" x="-10" y="-10" width="140" height="140">'
               '<rect x="-10" y="-10" width="140" height="140" fill="#fff"/>'
               '<path stroke="#000" stroke-width="1.4" stroke-linecap="round" fill="none" '
               'd="M56.5,13 L63.5,13 M2.5,59 L9.5,59 M110.5,59 L117.5,59"/>'
               '<path fill="#000" d="' + circ(60, 9.5, 1.3) + circ(6, 55.5, 1.3) + circ(114, 55.5, 1.3) + '"/></mask>')
    write("X", 120, 120, g(ink, "translate(0 6)"), g(holes, "translate(0 6)"), "", defs=acc_cut)
    path = os.path.join(OUT, "X.svg")
    s = open(path).read().replace("</svg>", f'<g class="accent" fill="currentColor" transform="translate(0 6)" mask="url(#art-X-bell)">{acc}</g></svg>')
    open(path, "w").write(s)


def emblem_Z():
    cx, cy, R, r = 60, 62, 25, 15
    cs = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (-math.pi / 2, math.pi / 6, 5 * math.pi / 6)]
    sw = 7
    ring = [circ(x, y, R) for x, y in cs]
    defs = ""
    # Borromean: A over B, B over C, C over A
    over = {1: 0, 2: 1, 0: 2}  # ring i is masked by ring over[i]
    for i in range(3):
        defs += (f'<mask id="art-Z-m{i}" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">'
                 '<rect width="120" height="120" fill="#fff"/>'
                 f'<path d="{ring[over[i]]}" fill="none" stroke="#000" stroke-width="{sw + 5}"/></mask>')
    rings = f'<g fill="none" stroke="currentColor" stroke-width="{sw}">'
    for i in range(3):
        rings += f'<path d="{ring[i]}" mask="url(#art-Z-m{i})"/>'
    rings += "</g>"
    ink = ""
    for k in range(6):
        a = -math.pi / 2 + k * math.pi / 3 + math.pi / 6
        ink += P(lens(cx + 50 * math.cos(a), cy + 50 * math.sin(a), 11, 5, a))
    for k in range(6):
        a = -math.pi / 2 + k * math.pi / 3
        ink += P(circ(cx + 53 * math.cos(a), cy + 53 * math.sin(a), 2.4))
    write("Z", 120, 120, g(ink, "translate(60 60) scale(0.96) translate(-60 -62)"), "", P(circ(cx, cy, 3.4)),
          defs=defs, raw_after=f'<g transform="translate(60 60) scale(0.96) translate(-60 -62)">{rings}</g>')


# ---------------------------------------------------------------- others
def spindle_logo():
    shaft = tapered((60, 4), (60, 40), (60, 80), (60, 116), 4, 4, wf=lambda t: 4.2 + 3.5 * math.sin(math.pi * t))
    cop = P(lens(60, 52, 54, 34, math.pi / 2))
    whorl = P(ell(60, 88, 27, 9.5)) + P("M33,88 L87,88 L84,93 L36,93 Z")
    hook = tapered((60, 6), (60, 0), (68, 0), (68, 7), 3, 2.4)
    thread = tapered((72, 34), (90, 22), (100, 10), (108, 18), 4.6, 3.2)
    thread2 = tapered((108, 18), (114, 26), (104, 36), (98, 28), 3.2, 2.4)
    ink = P(shaft) + cop + whorl + P(hook) + P(thread) + P(thread2)
    holes = ""
    for k in range(5):
        y = 34 + k * 7.5
        holes += CUT(f"M{n(48 + abs(k - 2) * 1.5)},{n(y + 5)} L{n(72 - abs(k - 2) * 1.5)},{n(y - 3)}", 1.8)
    holes += H(ell(60, 88, 20, 5)) + K(ell(60, 88, 4.5, 2.2))
    acc = ""
    write("spindle", 120, 120, ink, holes, acc)
    # accent whorl inner band
    path = os.path.join(OUT, "spindle.svg")
    s = open(path).read().replace("</svg>", '<g class="accent" fill="currentColor">' +
                                    P(ell(60, 88, 20, 5)) + "</g></svg>")
    # keep the shaft visible through the accent band
    s = s.replace("</svg>", f'<g fill="currentColor">{P("M57.5,82 L62.5,82 L62.5,94 L57.5,94 Z")}</g></svg>')
    open(path, "w").write(s)


def owl_empty():
    ink, holes, acc = owl(100, 76, 1.0, sleepy=True)
    branch = tapered((6, 126), (60, 120), (140, 120), (194, 126), 5, 5, wf=lambda t: 3 + 4 * math.sin(math.pi * t))
    ink += P(branch)
    for x, a in ((18, 2.4), (34, 1.0), (150, 2.1), (172, 0.8), (186, 2.6)):
        y = 125 if x < 30 or x > 180 else 121.5
        ink += P(leaf(x, y, a, 16, 6.5))
    for x in (88, 94, 106, 112):
        ink += P(circ(x, 119, 2.8))
    # moon & stars
    moon = H(circ(170, 30, 13))
    ink += P(circ(166, 30, 14)) + P(sparkle(140, 20, 5)) + P(sparkle(30, 30, 6)) + P(sparkle(46, 56, 4)) + P(sparkle(188, 60, 4))
    holes += moon
    write("owl-empty", 200, 160, ink, holes, "")


def divider():
    W, Hh, cx, cy = 600, 40, 300, 20
    half = ""
    vine_pts = ((318, 20), (370, 4), (420, 36), (470, 20))
    vine2 = ((470, 20), (510, 8), (545, 30), (585, 20))
    half += P(tapered(*vine_pts, 3.4, 2.4)) + P(tapered(*vine2, 2.4, 1))
    for t, side, L in ((0.2, -1, 18), (0.45, 1, 17), (0.7, -1, 16), (0.92, 1, 15)):
        x, y = bez(*vine_pts, t)
        dx, dy = dbez(*vine_pts, t)
        a = math.atan2(dy, dx) + side * 0.9
        half += P(leaf(x, y, a, L, 6.5))
    for t, side, L in ((0.25, 1, 13), (0.55, -1, 11), (0.8, 1, 9)):
        x, y = bez(*vine2, t)
        dx, dy = dbez(*vine2, t)
        a = math.atan2(dy, dx) + side * 0.9
        half += P(leaf(x, y, a, L, 5))
    half += P(circ(588, 20, 2.4)) + P(circ(396, 30, 2.5)) + P(circ(446, 10, 2.5))
    half += P(lens(330, 20, 14, 4, 0))
    ink = both(half, W)
    for i in range(8):
        a = i * math.pi / 4
        ink += P(lens(cx + 9 * math.cos(a), cy + 9 * math.sin(a), 15, 6, a))
    ink += P(circ(cx, cy, 5.5))
    holes = H(circ(cx, cy, 2.2))
    for i in range(8):
        a = i * math.pi / 4
        holes += H(lens(cx + 10 * math.cos(a), cy + 10 * math.sin(a), 6, 1.8, a))
    write("divider", W, Hh, ink, holes, P(circ(cx, cy, 1.6)))


def corner():
    half = ""
    v = ((6, 6), (30, 3), (52, 3), (74, 8))
    half += P(tapered(*v, 4, 1.2))
    half += P(circ(74, 9, 2))
    for t, L in ((0.3, 12), (0.55, 10), (0.8, 8)):
        x, y = bez(*v, t)
        half += P(leaf(x, y + 1, 0.75, L, 4.5))
    ink = half + g(half, "matrix(0 1 1 0 0 0)")
    ink += P(circ(6, 6, 5)) + P(tapered((8, 8), (14, 14), (20, 20), (25, 25), 3, 2.4))
    ink += P(leaf(15, 15, 0.1, 15, 5.5)) + P(leaf(15, 15, math.pi / 2 - 0.1, 15, 5.5))
    holes = H(circ(6, 6, 1.8)) + CUT("M18,15.5 L26,16.4", 1) + CUT("M15.5,18 L16.4,26", 1)
    acc = g(P(tulip(0, 0, 12)), "translate(24 24) rotate(135)")
    write("corner", 80, 80, ink, holes, acc)


def hero():
    W = 640
    half, hh, acc = "", "", ""
    trunk = tapered((320, 330), (318, 260), (322, 180), (320, 74), 36, 7)
    ink = P(trunk) + P("M296,330 C304,320 312,314 320,314 C328,314 336,320 344,330 Z")
    for side in (-1, 1):
        ink += P(tapered((320, 320), (320 + side * 16, 325), (320 + side * 30, 330), (320 + side * 46, 336), 10, 2))
    branches = [
        (((318, 252), (268, 250), (200, 258), (164, 214)), 14, 3.5, 7),
        (((318, 208), (266, 208), (210, 200), (186, 148)), 12, 3, 7),
        (((318, 166), (282, 164), (240, 152), (228, 102)), 10, 2.6, 6),
        (((318, 128), (298, 124), (272, 106), (270, 70)), 7, 2.2, 4),
    ]
    for bi, (pts, w0, w1, nl) in enumerate(branches):
        half += P(tapered(*pts, w0, w1))
        for j in range(nl):
            t = 0.22 + 0.7 * j / max(1, nl - 1)
            side = 1 if j % 2 == 0 else -1
            if bi in (0, 2) and abs(t - {0: 0.45, 2: 0.48}[bi]) < 0.16:
                continue
            x, y = bez(*pts, t)
            dx, dy = dbez(*pts, t)
            a = math.atan2(dy, dx) + side * 0.75
            if bi == 1 and math.sin(a) > 0 and t < 0.6:
                continue
            L = 36 - t * 12 - bi * 2
            half += P(leaf(x, y, a, L, L * 0.38))
            hh += CUT(f"M{pt((x + math.cos(a) * 5, y + math.sin(a) * 5))} L{pt((x + math.cos(a) * (L - 7), y + math.sin(a) * (L - 7)))}", 1.4)
        x, y = pts[3]
        dx, dy = dbez(*pts, 1)
        ang = math.degrees(math.atan2(dy, dx)) + 90
        acc += g(P(tulip(0, 0, 14 - bi)), f"translate({n(x)} {n(y)}) rotate({n(ang)})")
        if bi in (1, 2):
            for t in ((0.5,) if bi == 2 else (0.8,)):
                fx, fy = bez(*pts, t)
                half += P(f"M{pt((fx - 0.6, fy))} L{pt((fx + 0.6, fy))} L{pt((fx + 0.6, fy + 9))} L{pt((fx - 0.6, fy + 9))}Z")
                acc += P(circ(fx, fy + 14, 5.5))
    b_ink, b_holes = bird()
    for (bi, t, sc) in ((0, 0.45, 0.85), (2, 0.48, 0.8)):
        pts = branches[bi][0]
        x, y = bez(*pts, t)
        tr = f"translate({n(x - 40 * sc)} {n(y - 3 - 84 * sc)}) scale({n(sc)})"
        legs = P(poly([(36, 74), (38.5, 74), (40, 86), (37.5, 86)])) + P(poly([(42, 72), (44.5, 72), (44.5, 86), (42, 86)]))
        half += g(b_ink + legs, tr)
        hh += g(b_holes, tr)
    f_ink, f_holes = fox()
    tr = "translate(262 270) scale(-0.6 0.6)"
    half += g(f_ink, tr)
    hh += g(f_holes, tr)
    hill = "M90,360 C150,328 230,318 320,318 L320,360 Z"
    half += P(hill)
    for x in (160, 200, 240, 280):
        hh += H(tulip(x, 352, 7)) if x != 240 else H(heart(x, 343, 5))
    half += P(sparkle(150, 150, 7)) + P(sparkle(104, 214, 5)) + P(sparkle(196, 54, 6)) + P(sparkle(252, 34, 4)) + P(sparkle(130, 286, 4))
    ink += both(half, W)
    holes = both(hh, W)
    acc_full = both(acc, W) + g(P(tulip(0, 0, 20)), "translate(320 78)")
    ink += P(leaf(320, 100, -2.45, 30, 11)) + P(leaf(320, 100, -0.69, 30, 11))
    hole_l = CUT("M316,96 L298,84", 1.4) + CUT("M324,96 L342,84", 1.4)
    holes += hole_l
    s_ink, s_holes, s_acc = sun(0, 0, 0.9)
    ink += g(s_ink, "translate(72 74)")
    holes += g(s_holes, "translate(72 74)")
    acc_full += g(s_acc, "translate(72 74)")
    ink += P(circ(566, 72, 38))
    holes += H(circ(584, 62, 36))
    holes += H(lens(548, 66, 8, 3, 0)) + CUT("M546,84 Q552,90 560,88", 1.8)
    ink += P(sparkle(600, 120, 6)) + P(sparkle(520, 30, 5))
    # one asymmetry: a small mole (for MOMFER, after Momfer de Mol) peeking out
    # from behind the trunk, facing right
    m_ink, m_holes, m_acc = mole(peek=True)
    tr = "translate(337.5 319) scale(-0.55 0.55)"
    ink += g(m_ink, tr)
    holes += g(m_holes, tr)
    acc_full += g(m_acc, tr)
    holes += CUT("M335.3,297.7 L336.12,308.47 L337.02,319.08", 1.3)  # the trunk's edge, in front of the mole
    write("hero", W, 360, ink, holes, acc_full)


# ---------------------------------------------------------------- atlas: figures in the sea
def waves(x0, x1, y, step=10.0, amp=5.0, depth=6.0):
    """A band of scalloped water, crests up, from x0 to x1 with its crest line at y.
    Returns (ink, holes): the band, and a cut along it."""
    d = f"M{n(x0)},{n(y + depth)} L{n(x0)},{n(y)}"
    cut = f"M{n(x0 + step * .2)},{n(y + depth * .55)}"
    x = x0
    while x < x1 - 1e-6:
        w = min(step, x1 - x)
        d += f" Q{n(x + w / 2)},{n(y - amp)} {n(x + w)},{n(y)}"
        x += w
    d += f" L{n(x1)},{n(y + depth)} Z"
    x = x0 + step * .2
    while x < x1 - step * .7:
        cut += f" Q{n(x + step * .3)},{n(y + depth * .55 - amp * .35)} {n(x + step * .6)},{n(y + depth * .55)}"
        cut += f" M{n(x + step)},{n(y + depth * .55)}"
        x += step
    return P(d), CUT(cut, 1.1)


def spikes(pts, t_list, side, L, W):
    """Little triangular spikes standing out from a cubic curve."""
    out = ""
    for t in t_list:
        x, y = bez(*pts, t)
        dx, dy = dbez(*pts, t)
        l = math.hypot(dx, dy) or 1
        nx, ny = -dy / l * side, dx / l * side
        ux, uy = dx / l, dy / l
        out += P(poly([(x - ux * W, y - uy * W), (x + nx * L - ux * W * .6, y + ny * L - uy * W * .6), (x + ux * W, y + uy * W)]))
    return out


def atlas_serpent():
    neck = ((44, 62), (42, 40), (32, 22), (19, 20))
    hump1 = ((60, 62), (62, 22), (94, 22), (96, 62))
    hump2 = ((108, 62), (110, 32), (134, 32), (136, 62))
    tail = ((146, 62), (150, 40), (162, 32), (166, 42))
    ink = P(tapered(*neck, 13, 9)) + P(lens(10, 20, 28, 8, -0.12))
    ink += P(tapered(*hump1, 11, 11, wf=lambda t: 9 + 3 * math.sin(math.pi * t)))
    ink += P(tapered(*hump2, 9, 9, wf=lambda t: 8 + 2 * math.sin(math.pi * t)))
    ink += P(tapered(*tail, 8, 2))
    ink += P(leaf(166, 42, 1.2, 11, 4)) + P(leaf(166, 42, 2.4, 9, 3.5))
    ink += spikes(neck, (0.45, 0.62, 0.78), 1, 11.5, 2.4) + spikes(hump1, (0.3, 0.42, 0.54, 0.66, 0.78), -1, 12, 2.6)
    ink += spikes(hump2, (0.36, 0.5, 0.64), -1, 10.5, 2.2)
    ink += P(leaf(17, 14, -2.2, 10, 2.6)) + P(leaf(21, 15, -1.75, 9, 2.4))   # horns
    w_ink, w_holes = waves(28, 172, 60)
    ink += w_ink
    holes = H(circ(13, 17.8, 2)) + CUT("M-3,22 C3,24.5 9,24.5 15,22.5", 1.4)
    for pts, ts in ((hump1, (0.2, 0.32, 0.44, 0.56, 0.68, 0.8)), (hump2, (0.25, 0.4, 0.55, 0.7)), (neck, (0.15, 0.3))):
        for t in ts:
            x, y = bez(*pts, t)
            holes += H(circ(x, y, 1.15))
    holes += w_holes + CUT("M28,60.2 L172,60.2", 1.2)
    write("atlas-serpent", 180, 72, g(ink, "translate(8 0)"), g(holes, "translate(8 0)"), "")


def atlas_whale():
    body = "M10,58 C10,38 38,28 72,30 C104,32 126,42 140,54 C128,64 108,70 76,70 C40,70 10,72 10,58 Z"
    ink = P(body)
    ink += P(tapered((130, 57), (146, 50), (152, 40), (153, 30), 13, 5))
    ink += P(lens(146, 24, 20, 5.5, -2.5)) + P(lens(161, 25, 20, 5.5, -0.65))
    ink += P(lens(66, 69, 22, 5, 0.75))
    for side in (-1, 1):
        ink += P(tapered((40 + side * 1.5, 31), (40 + side * 2, 21), (40 + side * 7, 12), (40 + side * 13, 8), 3.4, 1.4))
    w_ink, w_holes = waves(0, 172, 74)
    ink += w_ink
    holes = H(circ(29, 49, 2.3)) + CUT("M10,58 C22,61 38,61 50,57", 1.5)
    for k in range(4):
        holes += CUT(f"M{n(20 + k * 3)},{n(63 + k * 1.6)} C{n(40)},{n(66 + k * 1.6)} {n(70)},{n(66 + k * 1.4)} {n(96 - k * 6)},{n(64 + k * 1.2)}", 1.1)
    for x, y in ((58, 37), (70, 36), (82, 37), (94, 39), (106, 42), (64, 43), (76, 42.5), (88, 44)):
        holes += H(circ(x, y, 1.2))
    holes += CUT("M146,24 L139,16", 1) + CUT("M161,25 L168,17", 1) + w_holes + CUT("M0,74.2 L172,74.2", 1.2)
    acc = P(circ(25, 6, 2.2)) + P(circ(55, 6, 2.2)) + P(circ(33, 1.5, 1.7)) + P(circ(47, 1.5, 1.7)) + P(circ(40, 4.5, 1.5))
    write("atlas-whale", 172, 82, g(ink, "translate(0 4)"), g(holes, "translate(0 4)"), g(acc, "translate(0 4)"))


def atlas_ship():
    ink = P("M14,80 L118,80 C112,95 100,101 84,101 L46,101 C30,101 20,95 14,80 Z")
    ink += P("M12,80 L12,69 L32,69 L35,80 Z")
    ink += P(tapered((114, 81), (124, 76), (130, 72), (136, 66), 3.4, 1.6))
    for x, top, bot in ((68, 10, 80), (101, 24, 80), (24, 32, 69)):
        ink += P(poly([(x - 1.3, bot), (x - 1.1, top), (x + 1.1, top), (x + 1.3, bot)]))
    ink += P("M51,20 Q68,16 85,20 L83,38 Q68,42 53,38 Z") + P("M47,43 Q68,39 89,43 L87,67 Q68,72 49,67 Z")
    ink += P("M90,33 Q101,30 112,33 L110,49 Q101,52 92,49 Z") + P("M89,53 Q101,50 114,53 L112,72 Q101,75 91,72 Z")
    ink += P("M24,33 L24,64 L8,62 Z")
    w_ink, w_holes = waves(0, 140, 102)
    ink += w_ink
    holes = CUT("M17,86 C40,88 92,88 115,86", 1.2) + CUT("M12,74 L33,74", 1)
    for x in range(40, 100, 11):
        holes += H(circ(x, 93, 1.9))
    holes += H(heart(68, 55, 5.2)) + H(sparkle(68, 29, 4.5)) + H(sparkle(101, 41, 3.8)) + H(sparkle(101.5, 62, 4.2))
    holes += CUT("M24,36 L13,60", 1) + w_holes + CUT("M0,102.2 L140,102.2", 1.2)
    acc = P("M68,10 L80,13 L68,16.5 Z") + P("M101,24 L111,27 L101,30 Z") + P("M24,32 L32,34.5 L24,37 Z")
    write("atlas-ship", 140, 112, ink, holes, acc)


def atlas_compass():
    cx, cy = 60, 70
    # the ring is one even-odd path, so cutting it does not cut the star inside
    ink = f'<path fill-rule="evenodd" d="{circ(cx, cy, 45)}{circ(cx, cy, 41)}"/>'
    holes = ""
    for k in range(32):
        if k % 8 == 0:
            continue  # where the long points cross the ring
        a = k * math.pi / 16
        holes += H(circ(cx + 43 * math.cos(a), cy + 43 * math.sin(a), 1.3 if k % 4 == 0 else 0.8))
    for k in range(8):
        a = -math.pi / 2 + k * math.pi / 4
        L, w = (56, 8) if k % 2 == 0 else (34, 6)
        tip = (cx + L * math.cos(a), cy + L * math.sin(a))
        s1 = (cx + w * math.cos(a + math.pi / 2), cy + w * math.sin(a + math.pi / 2))
        s2 = (cx + w * math.cos(a - math.pi / 2), cy + w * math.sin(a - math.pi / 2))
        ink += P(poly([s1, tip, s2, (cx, cy)]))
        # one half of each point cut away, as on old compass roses
        half = [s1, tip, (cx, cy)]
        holes += H(poly([((x - cx) * .78 + cx + (tip[0] - cx) * .1, (y - cy) * .78 + cy + (tip[1] - cy) * .1) for x, y in half]))
    holes += H(circ(cx, cy, 4.2)) + K(circ(cx, cy, 2))
    acc = P(tulip(cx, cy - 57, 8))
    write("atlas-compass", 120, 130, ink, holes, acc)


def atlas_isle():
    ink = P("M4,72 C18,62 34,55 60,53 C86,55 102,62 116,72 Z")
    m_ink, m_holes, m_acc = mole()
    tr = "translate(56 56) scale(0.52)"
    ink += g(m_ink, tr)
    ink += P(poly([(87.4, 60), (87.6, 33), (88.6, 33), (88.8, 60)])) + P(sparkle(104, 18, 5)) + P(sparkle(16, 30, 3.5))
    w_ink, w_holes = waves(0, 120, 72, step=9, amp=4, depth=6)
    ink += w_ink
    holes = g(m_holes, tr) + w_holes + CUT("M0,72.2 L120,72.2", 1.1)
    holes += H(circ(28, 66, 1.2)) + H(circ(96, 66, 1.2)) + H(circ(104, 69, 1)) + H(circ(18, 69, 1))
    acc = g(m_acc, tr) + P("M88.6,33 L99,36.5 L88.6,40 Z")
    write("atlas-isle", 120, 80, ink, holes, acc)


if __name__ == "__main__":
    which = sys.argv[1:] or None
    fns = {k[7:]: v for k, v in globals().items() if k.startswith("emblem_")}
    for k, f in fns.items():
        if not which or k in which:
            f()
    for k, f in (("spindle", spindle_logo), ("owl-empty", owl_empty), ("divider", divider), ("corner", corner), ("hero", hero),
                 ("atlas-serpent", atlas_serpent), ("atlas-whale", atlas_whale), ("atlas-ship", atlas_ship),
                 ("atlas-compass", atlas_compass), ("atlas-isle", atlas_isle)):
        if not which or k in which:
            f()
