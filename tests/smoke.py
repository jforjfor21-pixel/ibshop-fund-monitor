"""آزمون دود: کل زنجیره (تحلیل، تصویر، متن تلگرام) را روی داده نمونه اجرا می‌کند؛ بدون اینترنت و بدون ارسال.
اجرا: python -m tests.smoke tests/sample_detail.json tests/sample_list.txt"""
import sys, json, datetime as dt
from monitor import main


class Fake:
    def __init__(self, detail, raw):
        self.D = json.load(open(detail, encoding="utf-8"))
        self.items = []
        for ln in open(raw, encoding="utf-8"):
            p = [x.strip() for x in ln.split("|")]
            if len(p) < 12:
                continue
            reg, t, inv, sym, name, ym, size, m1, m3, m6, y1, mgr = p[:12]
            f = lambda v: float(v) if v else None
            k = f"{reg}|{sym}"
            d = self.D["F"].get(k, {})
            c = d.get("c") or [None] * 6
            self.items.append(dict(regNo=reg, groupId=d.get("g", 0), name=name, smallSymbolName=sym, fundType=int(t),
                                   typeOfInvest="Negotiable" if inv == "N" else "IssuanceAndCancellation", fundSize=float(size) * 1e10,
                                   date="2026-10-12T00:00:00", monthlyEfficiency=f(m1), quarterlyEfficiency=f(m3), sixMonthEfficiency=f(m6),
                                   annualEfficiency=f(y1), manager=mgr, statisticalNav=1, issueNav=1, cancelNav=1,
                                   fiveBest=c[0], stock=c[1], bond=c[2], other=c[3], cash=c[4], deposit=c[5]))

    def fund_list(self):
        return self.items

    def fund_detail(self, reg, gid):
        d = next((v for k, v in self.D["F"].items() if k.split("|")[0] == reg), None)
        if not d:
            return {}
        nav, asset = [], []
        for (date, n, na), fl in zip(d["W"], d["F"] + [0] * 60):
            iso = f"20{date[:2]}-{date[2:4]}-{date[4:6]}T00:00:00"
            nav.append({"date": iso, "statisticalNav": n, "cancelNav": n})
            u = (fl or 0) * 1e10 / (n or 1)
            asset.append({"date": iso, "netAsset": na * 1e10, "unitsSubDAY": max(u, 0), "unitsRedDAY": max(-u, 0)})
        eff = [{"date": f"20{m[0][:2]}-{m[0][2:]}-15", "monthlyEfficiency": m[10], "annualEfficiency": m[9]} for m in d.get("M", [])]
        return {"groupId": gid, "nav": nav, "asset": asset, "eff": eff,
                "info": {"retInvNo": d.get("ri"), "insInvNo": d.get("ii"), "insInvPercent": d.get("ip"), "fundUnit": d.get("fu"), "commodity": d.get("co"), "manager": d.get("m")}}


if __name__ == "__main__":
    tg, reps = main.run(dry=True, fixture=Fake(sys.argv[1], sys.argv[2]))
    print("reports:", len(reps), "| telegram calls:", len(tg.sent))
    for r in reps:
        print(r["label"], r["rank"], "/", r["of"], [m["key"] for m in r["ms"]])
