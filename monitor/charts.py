"""تصویر گزارش هر صندوق (PNG) با Pillow. متن فارسی با موتور چیدمان RAQM (در گیت‌هاب libraqm نصب می‌شود)."""
import os, datetime as dt
from PIL import Image, ImageDraw, ImageFont, features
from .analytics import fmt, short, jstr, at

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = {w: os.path.join(HERE, "fonts", f"Vazirmatn-{w}.ttf") for w in ("Regular", "Bold", "Black")}
RAQM = features.check("raqm")
BG, P1, LN, TX, MU = (6, 11, 19), (13, 22, 34), (34, 48, 62), (233, 241, 244), (147, 166, 179)
COL = [(224, 69, 122), (57, 135, 229), (217, 89, 38), (25, 158, 112), (201, 133, 0), (46, 158, 62), (144, 133, 233)]
_cache = {}


def font(sz, w="Regular"):
    k = (sz, w)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(FONT[w], sz, layout_engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC)
    return _cache[k]


def T(d, xy, s, sz=20, fill=TX, w="Regular", anchor="ra"):
    kw = {"direction": "rtl", "language": "fa"} if RAQM else {}
    d.text(xy, str(s), font=font(sz, w), fill=fill, anchor=anchor, **kw)


def panel(d, box, title, sub=""):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, 22, fill=P1, outline=LN, width=2)
    T(d, (x1 - 22, y0 + 18), title, 24, TX, "Bold")
    if sub:
        T(d, (x1 - 22, y0 + 54), sub, 16, MU)
    return (x0 + 24, y0 + 90, x1 - 24, y1 - 24)


def lines(d, box, series, labels):
    x0, y0, x1, y1 = box
    x0 += 64
    x1 -= 190
    vals = [v for s in series for v in s["v"] if v is not None]
    if not vals:
        return
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * .08 or 1
    lo, hi = lo - pad, hi + pad
    n = max(len(s["v"]) for s in series)
    X = lambda i: x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0)
    Y = lambda v: y1 - 28 - (y1 - 28 - y0) * (v - lo) / (hi - lo)
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        d.line([(x0, Y(v)), (x1, Y(v))], fill=(24, 34, 46), width=1)
        T(d, (x0 - 8, Y(v) - 10), fmt(v), 15, MU)
    for i in range(0, n, max(1, n // 6)):
        if i < len(labels):
            T(d, (X(i), y1 - 22), labels[i], 15, MU, anchor="ma")
    ends = []
    for s in sorted(series, key=lambda s: s["me"]):
        pts = [(X(i), Y(v)) for i, v in enumerate(s["v"]) if v is not None]
        if len(pts) > 1:
            d.line(pts, fill=s["c"], width=5 if s["me"] else 3, joint="curve")
        if pts:
            ends.append([pts[-1][1], pts[-1], s])
    ends.sort(key=lambda e: e[0])
    for i in range(1, len(ends)):
        if ends[i][0] - ends[i - 1][0] < 20:
            ends[i][0] = ends[i - 1][0] + 20
    for y, p, s in ends:
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=s["c"], outline=P1, width=2)
        T(d, (p[0] + 12, y - 10), s["n"], 15, s["c"], "Bold", anchor="la")


def bars_div(d, box, vals, labels):
    x0, y0, x1, y1 = box
    x1 -= 70
    if not vals:
        return
    lo, hi = min(0, min(vals)), max(0, max(vals))
    if lo == hi:
        hi = lo + 1
    Y = lambda v: y1 - 28 - (y1 - 28 - y0) * (v - lo) / (hi - lo)
    bw = (x1 - x0) / len(vals)
    d.line([(x0, Y(0)), (x1, Y(0))], fill=(80, 96, 110), width=2)
    for v in (lo, hi):
        T(d, (x1 + 64, Y(v) - 10), fmt(v, 0), 15, MU)
    for i, v in enumerate(vals):
        a, b = sorted([Y(0), Y(v)])
        d.rounded_rectangle([x0 + i * bw + 2, a, x0 + (i + 1) * bw - 2, max(a + 2, b)], 3, fill=(75, 227, 165) if v >= 0 else (255, 122, 156))
    for i in range(0, len(labels), max(1, len(labels) // 6)):
        T(d, (x0 + i * bw + bw / 2, y1 - 22), labels[i], 15, MU, anchor="ma")


def hbars(d, box, rows, unit="٪"):
    x0, y0, x1, y1 = box
    rows = [r for r in rows if r["v"] is not None]
    if not rows:
        return
    vs = [r["v"] for r in rows]
    mx, mn = max(vs), min(vs)
    base = 0 if mn <= 0 or mn < mx * .5 else mn - (mx - mn) * .6 - 1e-9
    rh = min(46, (y1 - y0) / len(rows))
    for i, r in enumerate(rows):
        y = y0 + i * rh
        T(d, (x1, y + rh / 2 - 12), r["n"], 18, TX if r["me"] else MU, "Bold" if r["me"] else "Regular")
        lo2, hi2 = mn - (mx - mn) * .1 - 1e-9, mx + (mx - mn) * .1 + 1e-9
        px = x0 + 90 + (x1 - 200 - x0 - 90) * (r["v"] - lo2) / (hi2 - lo2)
        cy = y + rh / 2
        d.line([(x0 + 90, cy), (x1 - 200, cy)], fill=(34, 48, 62), width=2)
        rad = 11 if r["me"] else 8
        d.ellipse([px - rad, cy - rad, px + rad, cy + rad], fill=r["c"], outline=P1, width=3)
        T(d, (x0 + 80, cy - 11), fmt(r["v"]) + unit, 17, TX if r["me"] else MU, "Bold" if r["me"] else "Regular")


def render(path, our, ms, colors, label, gname, rank, of, ret_key="r1y"):
    W, H = 1200, 1560
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for y in range(0, 190):
        a = y / 190
        d.line([(0, y), (W, y)], fill=(int(36 + (6 - 36) * a), int(48 + (11 - 48) * a), int(143 + (19 - 143) * a)))
    T(d, (W - 40, 34), "موتور هوشمند رصد بازار | آی‌بی‌شاپ", 22, (159, 245, 227), "Bold")
    T(d, (W - 40, 72), label, 46, (255, 255, 255), "Black")
    T(d, (W - 40, 138), f"گروه {gname} | داده فیپیران تا {jstr(dt.date.fromisoformat(our['date']))}", 20, (200, 214, 222))
    k = [("خالص دارایی", fmt(our["size"] / 1000) + " هزار میلیارد", fmt(our["w1"], 2, True) + "٪ هفته"),
         ("رتبه اندازه در گروه", f"{rank} از {of}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")), ""),
         ("جریان خالص ۷ روز", fmt(our["f7"], 0, True) + " میلیارد", "تومان"),
         ("بازده ۱۲ ماهه" if ret_key == "r1y" else "بازده ۳ ماهه", fmt(our[ret_key]) + "٪", "")]
    bw = (W - 80 - 3 * 16) / 4
    for i, (a, b, c) in enumerate(k):
        x1 = W - 40 - i * (bw + 16)
        d.rounded_rectangle([x1 - bw, 210, x1, 330], 18, fill=P1, outline=LN, width=2)
        T(d, (x1 - 18, 224), a, 17, MU)
        T(d, (x1 - 18, 254), b, 27, TX, "Black")
        if c:
            T(d, (x1 - 18, 294), c, 16, (75, 227, 165) if c.startswith("+") else (255, 122, 156) if c.startswith("−") else MU)
    # ۱) روند خالص دارایی ۵۲ هفته
    box = panel(d, (40, 356, W - 40, 816), "روند خالص دارایی ۵۲ هفته", "هزار میلیارد تومان؛ صندوق ما خط ضخیم")
    weeks = list(range(52, -1, -4))
    series = []
    for m in ms:
        series.append({"n": short(m), "c": colors[m["key"]], "me": m is our, "v": [(at(m["series"], w * 7) or 0) / 1000 or None for w in weeks]})
    labs = [jstr(our["series"][0]["date"] - dt.timedelta(days=w * 7)).split(" ")[1] if our["series"] else "" for w in weeks]
    lines(d, box, series, labs)
    # ۲) جریان روزانه ۳۰ روز
    box = panel(d, (40, 840, W - 40, 1150), "جریان خالص روزانه ۳۰ روز اخیر | " + label, "صدور منهای ابطال، میلیارد تومان")
    s30 = list(reversed(our["series"][:30]))
    bars_div(d, box, [v["flow"] for v in s30], [jstr(v["date"]).rsplit(" ", 1)[0] for v in s30])
    # ۳) بازده
    box = panel(d, (40, 1174, W - 40, 1500), "مقایسه بازده " + ("۱۲ ماهه" if ret_key == "r1y" else "۳ ماهه"), "صندوق ما با رقبای بالا و پایین خود")
    hbars(d, box, sorted([{"n": short(m), "v": m[ret_key], "c": colors[m["key"]], "me": m is our} for m in ms], key=lambda r: -(r["v"] or -1e9)))
    T(d, (W - 40, H - 44), "منبع: fipiran.com | امور شعب آی‌بی‌شاپ", 15, MU)
    im.save(path, optimize=True)
    return path
