"""ارسال به تلگرام با Bot API. توکن و شناسه گفت‌وگو فقط از متغیرهای محیطی (Secrets گیت‌هاب) خوانده می‌شود."""
import os, time, html
import requests

API = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")


class Telegram:
    def __init__(self, token=None, chat=None, dry=None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat = chat or os.environ.get("TELEGRAM_CHAT_ID")
        self.dry = dry if dry is not None else not (self.token and self.chat)
        self.sent = []

    def _post(self, method, data, files=None):
        if self.dry:
            self.sent.append((method, data, files and list(files)))
            return {"ok": True, "dry": True}
        for i in range(4):
            r = requests.post(f"{API}/bot{self.token}/{method}", data=data, files=files, timeout=60)
            j = r.json() if r.content else {}
            if j.get("ok"):
                return j
            if r.status_code == 429:
                time.sleep(j.get("parameters", {}).get("retry_after", 5) + 1)
                continue
            time.sleep(2)
        raise RuntimeError(f"telegram {method}: {r.status_code} {j.get('description')}")

    def text(self, s):
        # محدودیت ۴۰۹۶ نویسه: پیام‌های بلند در مرز خط شکسته می‌شوند
        parts, cur = [], ""
        for line in s.split("\n"):
            if len(cur) + len(line) + 1 > 3900:
                parts.append(cur)
                cur = ""
            cur += line + "\n"
        if cur.strip():
            parts.append(cur)
        for p in parts:
            self._post("sendMessage", {"chat_id": self.chat, "text": p, "parse_mode": "HTML", "disable_web_page_preview": "true"})
            time.sleep(0.6)

    def photo(self, path, caption=""):
        with open(path, "rb") as f:
            self._post("sendPhoto", {"chat_id": self.chat, "caption": caption[:1000], "parse_mode": "HTML"}, files={"photo": f})
        time.sleep(0.6)


def esc(s):
    return html.escape(str(s), quote=False)
