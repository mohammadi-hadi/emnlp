"""Download the public data: ACL Anthology XML for both editions and the EMNLP 2026 program sheet.
Usage: python 00_fetch_data.py"""
import time
import requests
from config import ANTHOLOGY_RAW, REFS, RAW, YEARS, PROGRAM_SHEET

UA = {"User-Agent": "EMNLP atlas (https://mohammadi.cv); a handful of requests"}


def fetch(name, volume):
    """Try master first, then the ingestion branch, and keep the first copy that has the EMNLP volume
    (2026.findings.xml is on master early, with ACL and NAACL Findings but not yet EMNLP's).
    Returns the ref it came from, or None."""
    for ref in REFS:
        r = requests.get(ANTHOLOGY_RAW.format(ref=ref, name=name), headers=UA, timeout=60)
        if r.status_code == 200 and f'<volume id="{volume}"'.encode() in r.content:
            (RAW / name).write_bytes(r.content)
            return ref
        time.sleep(1)
    return None


for year in YEARS:
    for name, volume in ((f"{year}.emnlp.xml", "main"), (f"{year}.findings.xml", "emnlp")):
        ref = fetch(name, volume)
        print(f"{name}: {'from ' + ref if ref else 'NOT FOUND'}")

r = requests.get(PROGRAM_SHEET, headers=UA, timeout=60)
r.raise_for_status()
(RAW / "emnlp2026_program.csv").write_bytes(r.content)
print("program sheet:", len(r.content) // 1024, "KB")
