"""دریافت داده از سرویس‌های عمومی فیپیران (همان سرویس‌هایی که صفحه fipiran.com/mf/list از آن‌ها استفاده می‌کند)."""
import os, time, json
import requests
from .config import FIPIRAN

HEAD = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Accept": "application/json, text/plain, */*", "Referer": FIPIRAN + "/mf/list", "Origin": FIPIRAN}


class FipiranError(RuntimeError):
    pass


class Client:
    def __init__(self, timeout=40, retries=4):
        self.s = requests.Session()
        self.s.headers.update(HEAD)
        proxy = os.environ.get("FIPIRAN_PROXY")          # اختیاری: اگر فیپیران آی‌پی خارج از ایران را نپذیرد
        if proxy:
            self.s.proxies = {"http": proxy, "https": proxy}
        self.timeout, self.retries = timeout, retries

    def _req(self, method, path, **kw):
        err = None
        for i in range(self.retries):
            try:
                r = self.s.request(method, FIPIRAN + path, timeout=self.timeout, **kw)
                if r.status_code == 200 and r.content:
                    return r.json()
                err = f"HTTP {r.status_code}"
            except (requests.RequestException, ValueError) as e:
                err = str(e)
            time.sleep(3 * (i + 1))
        raise FipiranError(f"{path}: {err}")

    def fund_list(self):
        """فهرست همه صندوق‌ها با اندازه، NAV، بازدهی‌ها و ترکیب دارایی."""
        j = self._req("POST", "/services/fund/fundcompare", data="{}", headers={"Content-Type": "application/json"})
        return j.get("items") or []

    def _series(self, path, reg, gid):
        j = self._req("GET", path, params={"regno": reg, "groupId": gid, "showAll": "true"})
        if isinstance(j, dict):
            j = j.get("items") or j.get("item") or []
        return j if isinstance(j, list) else []

    def fund_detail(self, reg, gid):
        """سری‌های روزانه یک صندوق. برای صندوق‌های قابل معامله گاهی سابقه کامل روی groupId دیگری است؛ طولانی‌ترین را برمی‌داریم."""
        best = None
        for g in [gid] + [x for x in (0, 1, 2) if x != gid]:
            try:
                nav = self._series("/services/chart/getfundchart", reg, g)
            except FipiranError:
                continue
            if best is None or len(nav) > len(best[1]):
                best = (g, nav)
            if len(nav) > 300:
                break
        if not best:
            raise FipiranError(f"history {reg}")
        g, nav = best
        out = {"groupId": g, "nav": nav}
        for key, path in [("asset", "/services/chart/getfundnetassetchart"), ("portfolio", "/services/chart/portfoliochart"),
                          ("possession", "/services/chart/possessionchart"), ("eff", "/services/chart/fundefficiencychart"),
                          ("profit", "/services/chart/fundprofitschart")]:
            try:
                out[key] = self._series(path, reg, g)
            except FipiranError:
                out[key] = []
        try:
            j = self._req("GET", "/services/fund/getfund", params={"regno": reg, "groupId": g})
            out["info"] = j.get("item") if isinstance(j, dict) else {}
        except FipiranError:
            out["info"] = {}
        return out
