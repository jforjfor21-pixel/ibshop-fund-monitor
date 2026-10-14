"""ساخت فایل raw نمونه از داده ۲۰ مهر ۱۴۰۵ برای آزمون کل زنجیره بدون دسترسی به فیپیران.
اجرا: python -m tests.make_raw raw.json.gz"""
import sys
from tests.smoke import Fake
from monitor import main

main.run(dry=True, fixture=Fake("tests/sample_detail.json", "tests/sample_list.txt"), stage="fetch", raw_path=sys.argv[1] if len(sys.argv) > 1 else "raw.json.gz")
