"""تحلیل: گروه رقابتی، انتخاب ۳ رقیب بالا و ۳ پایین، شاخص‌ها، امتیاز موتور، بینش‌ها و هشدارها."""
import re, math, datetime as dt
from .config import SILVER_SYMBOLS, SILVER_PATTERN, PEERS_ABOVE, PEERS_BELOW, GROUP_NAMES

BT = 1e10   # ریال ← میلیارد تومان


def sym(x):
    return (x.get("smallSymbolName") or "").strip()


def key(x):
    return f"{x['regNo']}|{sym(x)}"


def group_of(x):
    if not x.get("fundSize") or not x.get("date") or str(x.get("date", "")).startswith("0001"):
        return None
    t, inv, name = x.get("fundType"), x.get("typeOfInvest"), x.get("name") or ""
    if t == 4:
        if "نیکوکاری" in name:
            return None
        return "tad" if inv == "Negotiable" else "ganj"
    if t == 5:
        return "silver" if (sym(x) in SILVER_SYMBOLS or re.search(SILVER_PATTERN, name + sym(x))) else "gold"
    return None


def build(items):
    """ردیف‌ها را تمیز و گروه‌بندی می‌کند. صندوق‌های چندکلاسه (یک شماره ثبت با چند نماد) علامت می‌خورند."""
    rows = {}
    for x in items:
        g = group_of(x)
        if not g:
            continue
        k = key(x)
        if k not in rows or (rows[k]["fundSize"] or 0) < (x["fundSize"] or 0):
            rows[k] = dict(x, g=g)
    per_reg = {}
    for r in rows.values():
        per_reg.setdefault(r["regNo"], set()).add(sym(r))
    # ردیف بدون نماد یک صندوق قابل معامله چندکلاسه، تکراریِ کل صندوق است
    for k in [k for k, r in rows.items() if r["fundType"] == 5 and not sym(r) and len(per_reg[r["regNo"]] - {""}) > 0]:
        rows.pop(k)
    for r in rows.values():
        r["multi"] = len(per_reg[r["regNo"]] - {""}) > 1
    groups = {}
    for r in rows.values():
        groups.setdefault(r["g"], []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: -(r["fundSize"] or 0))
    return rows, groups


def find_our(rows, f):
    if f.get("reg"):
        k = f"{f['reg']}|{f.get('sym', '')}"
        if k in rows:
            return rows[k]
        for r in rows.values():
            if r["regNo"] == f["reg"]:
                return r
    if f.get("find"):
        for r in rows.values():
            if re.search(f["find"], (r.get("name") or "") + sym(r)):
                return r
    return None


def pick_peers(group, our):
    """۳ صندوق بزرگ‌تر و ۳ صندوق کوچک‌تر در همان گروه (صندوق‌های چندکلاسه کنار گذاشته می‌شوند چون سابقه‌شان مجموع چند کلاس است)."""
    L = [r for r in group if r is our or not r.get("multi")]
    i = L.index(our)
    return L[max(0, i - PEERS_ABOVE):i] + L[i + 1:i + 1 + PEERS_BELOW]


def _d(s):
    return dt.date.fromisoformat(str(s)[:10])


def daily(detail):
    """سری روزانه یکپارچه: تاریخ، NAV آماری، NAV ابطال، خالص دارایی، واحدهای صادره و باطل‌شده."""
    by = {}
    for n in detail.get("nav") or []:
        by.setdefault(str(n["date"])[:10], {}).update(nav=n.get("statisticalNav"), cnav=n.get("cancelNav"))
    for a in detail.get("asset") or []:
        by.setdefault(str(a["date"])[:10], {}).update(na=a.get("netAsset"), sub=a.get("unitsSubDAY") or 0, red=a.get("unitsRedDAY") or 0)
    out = []
    for d, v in by.items():
        if v.get("na"):
            v["date"] = _d(d)
            v["flow"] = ((v.get("sub") or 0) - (v.get("red") or 0)) * (v.get("cnav") or 0) / BT
            out.append(v)
    out.sort(key=lambda v: v["date"], reverse=True)
    return out


def at(series, days):
    """مقدار خالص دارایی در «days» روز قبل از آخرین تاریخ (نزدیک‌ترین روز موجود قبل از آن)."""
    if not series:
        return None
    t = series[0]["date"] - dt.timedelta(days=days)
    for v in series:
        if v["date"] <= t:
            return v["na"] / BT
    return None


def flow(series, days):
    if not series:
        return None
    t = series[0]["date"] - dt.timedelta(days=days)
    return sum(v["flow"] for v in series if v["date"] > t)


def ann_from_eff(eff):
    """اگر فیپیران بازده ۱۲ ماهه را صفر ثبت کرده باشد، از ترکیب بازده ماهانه ۱۲ ماه اخیر ساخته می‌شود."""
    if not eff:
        return None
    eff = sorted(eff, key=lambda e: str(e["date"]), reverse=True)
    p, n = 1.0, 0
    for i in range(0, min(len(eff), 12 * 30), 30):
        m = eff[i].get("monthlyEfficiency")
        if m is None:
            break
        p *= 1 + m / 100
        n += 1
    return (p - 1) * 100 if n >= 12 else None


def metrics(row, detail):
    s = daily(detail)
    info = detail.get("info") or {}
    size = (s[0]["na"] if s else row["fundSize"]) / BT
    ch = lambda d: (size / at(s, d) - 1) * 100 if at(s, d) else None
    y1 = row.get("annualEfficiency") or ann_from_eff(detail.get("eff"))
    eff = sorted(detail.get("eff") or [], key=lambda e: str(e["date"]), reverse=True)
    monthly = [eff[i].get("monthlyEfficiency") for i in range(0, min(len(eff), 360), 30) if eff[i].get("monthlyEfficiency") is not None]
    sd = None
    if len(monthly) >= 3:
        mu = sum(monthly[:12]) / len(monthly[:12])
        sd = math.sqrt(sum((m - mu) ** 2 for m in monthly[:12]) / len(monthly[:12]))
    return dict(
        key=key(row), reg=row["regNo"], sym=sym(row), name=(row.get("name") or "").strip(), manager=row.get("manager") or info.get("manager") or "",
        date=str(row.get("date"))[:10], size=size, d1=ch(1), w1=ch(7), w4=ch(28), w13=ch(91), w52=ch(364),
        f1=flow(s, 1), f7=flow(s, 7), f28=flow(s, 28), f91=flow(s, 91),
        r1d=row.get("dailyEfficiency"), r1w=row.get("weeklyEfficiency"), r1m=row.get("monthlyEfficiency"), r3m=row.get("quarterlyEfficiency"),
        r6m=row.get("sixMonthEfficiency"), r1y=y1, sd=sd,
        nav=row.get("statisticalNav"), issue=row.get("issueNav"), cancel=row.get("cancelNav"),
        bond=row.get("bond"), deposit=row.get("deposit"), stock=row.get("stock"), cash=row.get("cash"), other=row.get("other"),
        fund_unit=info.get("fundUnit"), commodity=info.get("commodity"),
        ret_inv=info.get("retInvNo"), ins_inv=info.get("insInvNo"), ins_pct=info.get("insInvPercent"),
        guarantor=info.get("guarantor"), series=s, eff=eff,
    )


def short(m):
    if m["sym"]:
        return m["sym"]
    n = re.sub(r"^(صندوق سرمايه[‌ ]?گذاري|صندوق سرمایه[‌ ]?گذاری)\s*", "", m["name"])
    n = re.sub(r"^(مشترک|مشترك|با درآمد ثابت|در اوراق بهادار با درآمد ثابت)\s+", "", n)
    return n.replace("کارگزاری بانک", "کارگزاری").strip()[:28]


def score(ms):
    """امتیاز موتور: میانگین ۶ شاخص نرمال‌شده (۲۰ تا ۱۰۰) در همین جمع ۷ صندوقی."""
    axes = [("اندازه", lambda m: m["size"]), ("رشد دارایی", lambda m: m["w52"] if m["w52"] is not None else m["w13"]),
            ("جذب نقدینگی", lambda m: (m["f91"] or 0) / m["size"] * 100 if m["size"] else 0), ("بازده ۱۲ماهه", lambda m: m["r1y"]),
            ("بازده ۳ماهه", lambda m: m["r3m"]), ("ثبات بازدهی", lambda m: -m["sd"] if m["sd"] is not None else None)]
    out = {m["key"]: [] for m in ms}
    for _, f in axes:
        vals = [f(m) for m in ms]
        ok = [v for v in vals if v is not None]
        lo, hi = (min(ok), max(ok)) if ok else (0, 0)
        for m, v in zip(ms, vals):
            out[m["key"]].append(50 if v is None else 60 if hi == lo else 20 + 80 * (v - lo) / (hi - lo))
    return [a for a, _ in axes], {k: (sum(v) / len(v), v) for k, v in out.items()}


def insights(our, ms, rank, of, prev_rank, gname):
    """بینش‌ها (سبز = خوب، قرمز = هشدار، زرد = نکته)."""
    out = []
    peers = [m for m in ms if m is not our]
    tot = sum(m["size"] for m in ms)
    share = our["size"] / tot * 100 if tot else 0
    if prev_rank and prev_rank != rank:
        out.append(("g" if rank < prev_rank else "r", f"رتبه اندازه در گروه {gname} از {fmt(prev_rank, 0)} به {fmt(rank, 0)} {'رسید (صعود)' if rank < prev_rank else 'رسید (سقوط)'}."))
    over = [m for m in peers if m["size"] > our["size"] and at(m["series"], 7) is not None and at(our["series"], 7) is not None and at(m["series"], 7) <= at(our["series"], 7)]
    for m in over:
        out.append(("r", f"{short(m)} در هفته گذشته از نظر اندازه از ما جلو زد."))
    passed = [m for m in peers if m["size"] < our["size"] and at(m["series"], 7) is not None and at(our["series"], 7) is not None and at(m["series"], 7) > at(our["series"], 7)]
    for m in passed:
        out.append(("g", f"در هفته گذشته از {short(m)} جلو زدیم."))
    if our["f7"] is not None:
        best = max(ms, key=lambda m: m["f7"] or -1e18)
        out.append(("g" if our["f7"] >= 0 else "r", f"جریان خالص ۷ روز: {fmt(our['f7'], 0, sign=True)} میلیارد تومان؛ بیشترین جذب پول در این جمع: {short(best)} ({fmt(best['f7'], 0, sign=True)})."))
    streak = 0
    for v in our["series"][:10]:
        if v["flow"] < 0:
            streak += 1
        else:
            break
    if streak >= 3:
        out.append(("r", f"{fmt(streak, 0)} روز متوالی خروج خالص پول."))
    if our["r1y"] is not None:
        rr = sorted([m for m in ms if m["r1y"] is not None], key=lambda m: -m["r1y"])
        pos = rr.index(our) + 1 if our in rr else None
        if pos == 1:
            out.append(("g", f"بازده ۱۲ ماهه ({fmt(our['r1y'])}٪) بهترین در این جمع است."))
        elif pos:
            out.append(("n", f"بازده ۱۲ ماهه {fmt(our['r1y'])}٪، رتبه {fmt(pos, 0)} در این جمع؛ بهترین: {short(rr[0])} با {fmt(rr[0]['r1y'])}٪."))
    out_flow = [short(m) for m in peers if (m["f28"] or 0) < 0]
    if out_flow:
        out.append(("n", "رقبای دارای خروج خالص پول در ۲۸ روز اخیر: " + "، ".join(out_flow) + "؛ فرصت جذب مشتریانشان در شعب."))
    out.append(("n", f"سهم ما از مجموع دارایی این {fmt(len(ms), 0)} صندوق: {fmt(share)}٪."))
    return out


FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fmt(v, d=1, sign=False):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    s = f"{abs(v):,.{d}f}".replace(",", "٬").replace(".", "٫").translate(FA)
    if sign:
        s = ("+" if v > 0 else "−" if v < 0 else "") + s
    elif v < 0:
        s = "−" + s
    return s


def g2j(d):
    """تبدیل تاریخ میلادی به شمسی."""
    gy, gm, gd = d.year, d.month, d.day
    g = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    jy = 0 if gy <= 1600 else 979
    gy -= 621 if gy <= 1600 else 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g[gm - 1]
    jy += 33 * (days // 12053); days %= 12053
    jy += 4 * (days // 1461); days %= 1461
    if days > 365:
        jy += (days - 1) // 365; days = (days - 1) % 365
    jm = 1 + days // 31 if days < 186 else 7 + (days - 186) // 30
    jd = 1 + (days % 31 if days < 186 else (days - 186) % 30)
    return jy, jm, jd


MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def jstr(d, long=True):
    y, m, dd = g2j(d)
    return f"{dd} {MONTHS[m - 1]} {y}".translate(FA) if long else f"{y}/{m:02d}/{dd:02d}".translate(FA)
