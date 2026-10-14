"""اجرای روزانه: دریافت داده فیپیران ← به‌روزرسانی پایگاه داده ← تحلیل هر صندوق در برابر ۳ رقیب بالا و ۳ رقیب پایین ← گزارش تلگرام.

اجرا:   python -m monitor.main              (ارسال واقعی؛ نیازمند TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID)
        python -m monitor.main --dry-run    (فقط ساخت گزارش در پوشه out/)
"""
import os, sys, json, gzip, glob, argparse, datetime as dt, traceback
from .config import OUR_FUNDS, GROUP_NAMES
from .fipiran import Client, FipiranError
from . import analytics as A
from .charts import render, COL
from .telegram import Telegram, esc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
F, fmt = A.fmt, A.fmt


def save_snapshot(items, day):
    os.makedirs(os.path.join(DATA, "snapshots"), exist_ok=True)
    p = os.path.join(DATA, "snapshots", f"{day}.json.gz")
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    return p


def prev_snapshot(day):
    files = sorted(f for f in glob.glob(os.path.join(DATA, "snapshots", "*.json.gz")) if os.path.basename(f)[:10] < day)
    if not files:
        return None
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        return json.load(f)


def append_history(day, ms_all):
    p = os.path.join(DATA, "history.csv")
    new = not os.path.exists(p)
    seen = set()
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("date,reg,symbol,name,size_btoman,nav,flow7_btoman,ret_1m,ret_3m,ret_6m,ret_12m,ret_investors,ins_investors\n")
        for m in ms_all:
            if m["key"] in seen:
                continue
            seen.add(m["key"])
            row = [day, m["reg"], m["sym"], m["name"].replace(",", " "), round(m["size"], 1), m["nav"], round(m["f7"] or 0, 1),
                   m["r1m"], m["r3m"], m["r6m"], None if m["r1y"] is None else round(m["r1y"], 2), m["ret_inv"], m["ins_inv"]]
            f.write(",".join("" if v is None else str(v) for v in row) + "\n")


def export_dashboard(day, reports, groups):
    """خروجی هم‌قالب داشبورد «موتور هوشمند رصد بازار» (data/dashboard.json)."""
    D = {"date": A.jstr(dt.date.fromisoformat(day), long=False), "ours": [], "F": {}, "G": {}}
    for g, L in groups.items():
        ys = [r["annualEfficiency"] for r in L if r.get("annualEfficiency")]
        D["G"][g] = {"name": GROUP_NAMES[g], "n": len(L), "tot": round(sum(r["fundSize"] for r in L) / A.BT, 1),
                     "avg": {"y1": round(sum(ys) / len(ys), 2) if ys else None}}
    for rep in reports:
        D["ours"].append({"key": rep["our"]["key"], "label": rep["label"], "g": rep["g"], "rank": rep["rank"], "of": rep["of"],
                          "peers": [m["key"] for m in rep["ms"] if m is not rep["our"]]})
        for m in rep["ms"]:
            s = m["series"]
            W = [[(s[0]["date"] - dt.timedelta(days=7 * w)).strftime("%y%m%d"), None, round((A.at(s, 7 * w) or 0) / 1, 1)] for w in range(53)] if s else []
            Fw = [round(sum(v["flow"] for v in s if s[0]["date"] - dt.timedelta(days=7 * (w + 1)) < v["date"] <= s[0]["date"] - dt.timedelta(days=7 * w)), 1) for w in range(53)] if s else []
            eff = m["eff"]
            M = [[str(eff[i]["date"])[2:7].replace("-", ""), m["bond"], m["deposit"], m["stock"], m["fund_unit"], m["commodity"], m["cash"], m["other"], m["ins_pct"],
                  eff[i].get("annualEfficiency"), eff[i].get("monthlyEfficiency")] for i in range(0, min(len(eff), 390), 30)]
            D["F"][m["key"]] = {"n": m["name"], "s": m["sym"], "sh": A.short(m), "m": m["manager"], "own": "تمدن" in m["manager"], "ri": m["ret_inv"], "ii": m["ins_inv"],
                                "ip": m["ins_pct"], "e": [m["r1d"], m["r1w"], m["r1m"], m["r3m"], m["r6m"], m["r1y"], None], "sz": round(m["size"], 1),
                                "c": [None, m["stock"], m["bond"], m["other"], m["cash"], m["deposit"]], "W": W, "F": Fw, "M": M}
    with open(os.path.join(DATA, "dashboard.json"), "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, separators=(",", ":"))


def fund_text(rep):
    our, ms, sc = rep["our"], rep["ms"], rep["score"]
    tot = sum(m["size"] for m in ms)
    rk = lambda k: sorted(ms, key=lambda m: -(m[k] if m[k] is not None else -1e18)).index(our) + 1
    srank = sorted(ms, key=lambda m: -sc[m["key"]][0]).index(our) + 1
    up = "\n"
    L = [f"<b>📊 رصد روزانه | {esc(rep['label'])}</b>",
         f"<i>{esc(GROUP_NAMES[rep['g']])} | داده فیپیران: {A.jstr(dt.date.fromisoformat(our['date']))}</i>", "",
         "<b>وضعیت صندوق</b>",
         f"💰 خالص دارایی: <b>{F(our['size'] / 1000, 2)}</b> هزار میلیارد تومان",
         f"     روز {F(our['d1'], 2, True)}٪ | هفته {F(our['w1'], 2, True)}٪ | ماه {F(our['w4'], 1, True)}٪ | سال {F(our['w52'], 1, True)}٪",
         f"🏆 رتبه اندازه در گروه: <b>{F(rep['rank'], 0)} از {F(rep['of'], 0)}</b>" + (f" (روز قبل {F(rep['prev_rank'], 0)})" if rep.get("prev_rank") and rep["prev_rank"] != rep["rank"] else ""),
         f"🥧 سهم در جمع {F(len(ms), 0)} صندوق: <b>{F(our['size'] / tot * 100)}٪</b>",
         f"💸 جریان خالص (میلیارد تومان): روز {F(our['f1'], 0, True)} | ۷ روز <b>{F(our['f7'], 0, True)}</b> | ۲۸ روز {F(our['f28'], 0, True)} | ۹۱ روز {F(our['f91'], 0, True)}",
         f"📈 بازده: ۱ ماه {F(our['r1m'])}٪ | ۳ ماه {F(our['r3m'])}٪ | ۶ ماه {F(our['r6m'])}٪ | ۱۲ ماه <b>{F(our['r1y'])}٪</b> (رتبه {F(rk('r1y'), 0)} از {F(len(ms), 0)})"]
    comp = [("اوراق", our["bond"]), ("سپرده", our["deposit"]), ("سهام", our["stock"]), ("واحد صندوق", our["fund_unit"]), ("کالا", our["commodity"]), ("نقد", our["cash"])]
    comp = [f"{a} {F(v)}٪" for a, v in comp if v]
    if comp:
        L.append("🧩 پرتفوی: " + " | ".join(comp))
    if our["ret_inv"]:
        L.append(f"👥 سرمایه‌گذاران: حقیقی {F(our['ret_inv'], 0)} | حقوقی {F(our['ins_inv'], 0)} | سهم حقوقی {F(our['ins_pct'], 0)}٪")
    L.append(f"⭐ امتیاز موتور: <b>{F(sc[our['key']][0], 0)}</b> از ۱۰۰ (رتبه {F(srank, 0)} از {F(len(ms), 0)})")
    L += ["", "<b>رقبا</b> (⬆ بزرگ‌تر | ⬇ کوچک‌تر)"]
    for m in ms:
        if m is our:
            L.append(f"▶️ <b>{esc(rep['label'])}</b> — {F(m['size'] / 1000, 1)}")
            continue
        arrow = "⬆" if m["size"] > our["size"] else "⬇"
        L.append(f"{arrow} <b>{esc(A.short(m))}</b> — {F(m['size'] / 1000, 1)} | هفته {F(m['w1'], 1, True)}٪ | جریان ۷ روز {F(m['f7'], 0, True)} | بازده ۱۲ ماه {F(m['r1y'])}٪ | امتیاز {F(sc[m['key']][0], 0)}")
    L += ["", "<b>🤖 بینش‌ها و هشدارها</b>"]
    ic = {"g": "🟢", "r": "🔴", "n": "🟡"}
    L += [f"{ic[c]} {esc(t)}" for c, t in rep["ins"]]
    return "\n".join(L)


def overview(reports, day):
    L = [f"<b>☀️ گزارش صبحگاهی رصد بازار صندوق‌ها</b>", f"<i>{A.jstr(dt.date.fromisoformat(day))} | منبع: فیپیران</i>", ""]
    for rep in reports:
        o = rep["our"]
        L.append(f"<b>{esc(rep['label'])}</b>: {F(o['size'] / 1000, 1)} هزار میلیارد | هفته {F(o['w1'], 1, True)}٪ | جریان ۷ روز {F(o['f7'], 0, True)} | رتبه {F(rep['rank'], 0)}/{F(rep['of'], 0)} | ۱۲ ماه {F(o['r1y'])}٪")
    L.append("")
    L.append("گزارش کامل هر صندوق در پیام‌های بعدی می‌آید.")
    return "\n".join(L)


def run(dry=False, fixture=None):
    os.makedirs(OUT, exist_ok=True)
    tg = Telegram(dry=dry or None)
    cli = fixture or Client()
    try:
        items = cli.fund_list()
    except FipiranError as e:
        tg.text(f"⚠️ <b>موتور رصد بازار</b>\nدسترسی به فیپیران برقرار نشد ({esc(e)}). اگر این خطا تکرار شد، اجرای کار را روی رانر داخل ایران یا با FIPIRAN_PROXY تنظیم کنید.")
        raise
    rows, groups = A.build(items)
    day = max(str(r["date"])[:10] for r in rows.values())
    if not fixture:
        save_snapshot(items, day)
    prev = prev_snapshot(day)
    prev_rank = {}
    if prev:
        _, pg = A.build(prev)
        for g, L in pg.items():
            for i, r in enumerate(L, 1):
                prev_rank[A.key(r)] = i
    reports, details, missing = [], {}, []
    for f in OUR_FUNDS:
        our_row = A.find_our(rows, f)
        if not our_row:
            missing.append(f)
            continue
        g = our_row["g"]
        G = groups[g]
        peers = A.pick_peers(G, our_row)
        ms = []
        for r in sorted(peers + [our_row], key=lambda r: -r["fundSize"]):
            k = A.key(r)
            if k not in details:
                try:
                    details[k] = cli.fund_detail(r["regNo"], r.get("groupId", 0))
                except FipiranError:
                    details[k] = {}
            ms.append(A.metrics(r, details[k]))
        our = next(m for m in ms if m["key"] == A.key(our_row))
        rank = G.index(our_row) + 1
        axes, sc = A.score(ms)
        reports.append(dict(label=f["label"], g=g, our=our, ms=ms, rank=rank, of=len(G), prev_rank=prev_rank.get(our["key"]), score=sc,
                            ins=A.insights(our, ms, rank, len(G), prev_rank.get(our["key"]), GROUP_NAMES[g])))
    tg.text(overview(reports, day))
    for i, rep in enumerate(reports):
        colors, j = {}, 1
        for m in rep["ms"]:
            if m is rep["our"]:
                colors[m["key"]] = COL[0]
            else:
                colors[m["key"]] = COL[j % len(COL)]
                j += 1
        png = render(os.path.join(OUT, f"{i + 1}_{rep['our']['reg']}.png"), rep["our"], rep["ms"], colors, rep["label"], GROUP_NAMES[rep["g"]], rep["rank"], rep["of"])
        tg.photo(png, f"<b>{esc(rep['label'])}</b> | رصد بازار")
        txt = fund_text(rep)
        open(os.path.join(OUT, f"{i + 1}_{rep['our']['reg']}.txt"), "w", encoding="utf-8").write(txt)
        tg.text(txt)
    for f in missing:
        if f["group"] in groups:
            L = groups[f["group"]]
            lines = [f"<b>🔎 {esc(f['label'])}</b> هنوز در فیپیران ثبت نشده است. وضعیت گروه {esc(GROUP_NAMES[f['group']])}:"]
            lines += [f"{F(i, 0)}. <b>{esc(A.sym(r) or r['name'])}</b> — {F(r['fundSize'] / A.BT / 1000, 1)} هزار میلیارد | ۳ ماه {F(r.get('quarterlyEfficiency'))}٪ | ماه {F(r.get('monthlyEfficiency'))}٪"
                      for i, r in enumerate(L, 1)]
            tg.text("\n".join(lines))
    if not fixture:
        append_history(day, [m for rep in reports for m in rep["ms"]])
        export_dashboard(day, reports, groups)
    return tg, reports


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    def status(ok, msg):
        os.makedirs(DATA, exist_ok=True)
        with open(os.path.join(DATA, "status.json"), "w", encoding="utf-8") as f:
            json.dump({"ok": ok, "time_utc": dt.datetime.utcnow().isoformat(timespec="seconds"), "message": msg}, f, ensure_ascii=False, indent=1)
    try:
        if not a.dry_run and not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
            print("هشدار: TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده؛ گزارش فقط در پوشه out ساخته می‌شود.")
        tg, reps = run(dry=a.dry_run)
        status(True, f"{len(reps)} گزارش" + (" (بدون ارسال: توکن تلگرام تنظیم نشده)" if tg.dry else " ارسال شد"))
        print(f"OK: {len(reps)} گزارش، {len(tg.sent) if tg.dry else 'ارسال شد'}")
    except Exception as e:
        traceback.print_exc()
        status(False, f"{type(e).__name__}: {e}"[:1500])
        sys.exit(1)
