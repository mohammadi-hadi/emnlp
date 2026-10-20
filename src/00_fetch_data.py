"""Download the public data: ACL Anthology XML for both editions and the EMNLP 2026 program sheet.
Usage: python 00_fetch_data.py"""
import time
import requests
from config import ANTHOLOGY_RAW, REFS, RAW, YEARS, PROGRAM_SHEET

UA = {"User-Agent": "EMNLP atlas (https://mohammadi.cv); a handful of requests"}


def fetch(name):
    """Try master first, then the ingestion branch. Returns the ref it came from, or None."""
    for ref in REFS:
        r = requests.get(ANTHOLOGY_RAW.format(ref=ref, name=name), headers=UA, timeout=60)
        if r.status_code == 200:
            (RAW / name).write_bytes(r.content)
            return ref
        time.sleep(1)
    return None


for year in YEARS:
    for name in (f"{year}.emnlp.xml", f"{year}.findings.xml"):
        ref = fetch(name)
        print(f"{name}: {'from ' + ref if ref else 'NOT FOUND'}")

r = requests.get(PROGRAM_SHEET, headers=UA, timeout=60)
r.raise_for_status()
(RAW / "emnlp2026_program.csv").write_bytes(r.content)
print("program sheet:", len(r.content) // 1024, "KB")
