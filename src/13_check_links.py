"""Check every link in the README, report and web pages of the current run (DOCS, REPORT).

- relative links: the target file must exist
- external links: fetched (polite, 2 workers) and must end in HTTP 200
- paper links: all links written in the appendix, plus a random sample of 40 papers from the index
- ACL Anthology pages of an edition that is not in the Anthology yet (its event page answers 404) are
  reported as "not public yet": they are the official links and open on release
- the repository and the live site (mohammadi.cv/emnlp) are reported as "pending" while they are private
  or not launched; every other mohammadi.cv link is fetched like any other link
Writes OUT/link_check.csv and prints a summary.
"""
import re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urldefrag, quote
import pandas as pd
import requests
from config import CUR, ROOT, OUT, DOCS, REPORT
from common import arxiv_search

SITE = f"https://mohammadi.cv/emnlp/{CUR}/"
REPO = "https://github.com/mohammadi-hadi/emnlp"
UA = {"User-Agent": "Mozilla/5.0 (link check; EMNLP paper overview)"}
ANTH = "https://aclanthology.org/"

links = []  # (source file, link)
for f in [ROOT / "README.md", *sorted(REPORT.glob("*.md"))]:
    if f.exists():
        for m in re.finditer(r"\]\(([^)\s]+)\)|<(https?://[^>]+)>", f.read_text()):
            links.append((f, m.group(1) or m.group(2)))
pages = sorted(DOCS.glob("*.html")) + sorted((DOCS / "charts").glob("*.html")) + sorted(DOCS.parent.glob("*.html"))
for f in pages:
    txt = f.read_text()
    if f.name == "atlas.html":  # only the hand-written parts; the rest is the map library
        txt = "\n".join(re.findall(r'<a class="atlas-back"[^>]*>|<script src="[^"]+"|<link [^>]*href="[^"]+"[^>]*>', txt))
    for m in re.finditer(r'<(?:a|img|script|iframe|link)\b[^>]*?(?:href|src)="([^"]+)"[^>]*>', txt):
        tag = m.group(0)
        if 'rel="preconnect"' in tag or "${" in m.group(1):  # font preconnect host / JS template, not links
            continue
        links.append((f, m.group(1)))

idx = pd.read_csv(OUT / "papers_index.csv").fillna("")
sample = idx.sample(min(40, len(idx)), random_state=1)
for r in sample.itertuples():
    for u in (r.anthology, r.pdf):
        if u:
            links.append((Path("papers_index.csv (sample)"), u))
if (DOCS / "papers.html").exists() and len(idx):  # templates of the JS-built links on papers.html
    r = idx.iloc[0]
    links += [(DOCS / "papers.html", r.anthology), (DOCS / "papers.html", arxiv_search(r.title))]


def status(url):
    try:
        return requests.get(url, headers=UA, timeout=40, allow_redirects=True).status_code
    except requests.RequestException:
        return None


ANTH_LIVE = status(f"{ANTH}events/emnlp-{CUR}/") == 200
rows, seen = [], {}


def check_external(url):
    if url in seen:
        return seen[url]
    if url.rstrip("/") == REPO or url.startswith(REPO + "/"):
        res = ("ok", "HTTP 200") if status(url) == 200 else ("pending", "repository is private; the link works once it is public")
    elif url.startswith(ANTH) and f"/{CUR}." in url and not ANTH_LIVE:
        res = ("not public yet", f"EMNLP {CUR} is not in the ACL Anthology yet (its event page answers 404)")
    else:
        slow = "arxiv.org" in url or url.startswith(ANTH)
        res = ("broken", "no response")
        for attempt in range(4):
            time.sleep(3.0 if slow else 0.3)
            try:
                r = requests.get(url, headers=UA, timeout=40, allow_redirects=True)
            except requests.RequestException as e:
                res = ("broken", str(e)[:80]); continue
            if r.status_code == 429:  # rate limited: wait and retry
                time.sleep(10 * (attempt + 1)); res = ("broken", "HTTP 429 after retries"); continue
            res = ("ok", f"HTTP {r.status_code}") if r.status_code == 200 else ("broken", f"HTTP {r.status_code}")
            break
        if res[0] == "broken" and url.startswith("https://mohammadi.cv/emnlp"):
            res = ("pending", "the EMNLP site is not live yet; the built page is checked as a relative link")
    seen[url] = res
    return res


def check(item):
    src, link = item
    link = link.strip()
    if link.startswith(("mailto:", "javascript:", "#")) or link == "":
        return src, link, "skip", ""
    if link.startswith(SITE):  # absolute links to this edition: check the built file instead
        link = urldefrag(link[len(SITE):])[0] or "index.html"
        src = DOCS / "index.html"
    elif link.startswith("/"):  # site-root links (header menu, stylesheet) live on mohammadi.cv itself
        link = "https://mohammadi.cv" + link
    if link.startswith("http"):
        st, note = check_external(quote(link, safe=":/?&=%#+@,;~"))
        return src, link, st, note
    if not urldefrag(link)[0]:
        return src, link, "skip", "fragment only"
    base = src.parent if src.suffix else ROOT
    if src.suffix == ".md" and src.parent == REPORT:  # the report becomes DOCS/*.html; 09 rewrites figure paths
        base, link = DOCS, link.replace("../outputs/figures/", "figures/")
    target = (base / urldefrag(link)[0]).resolve()
    if target.is_dir():
        target = target / "index.html"
    return src, link, "ok" if target.exists() else "broken", "relative file"


with ThreadPoolExecutor(2) as ex:
    for src, link, st, note in ex.map(check, links):
        rows.append({"source": str(src).replace(str(ROOT) + "/", ""), "link": link, "status": st, "note": note})

res = pd.DataFrame(rows).drop_duplicates()
res.to_csv(OUT / "link_check.csv", index=False)
print(f"EMNLP {CUR} in the ACL Anthology: {'yes' if ANTH_LIVE else 'not yet'}")
print(res.status.value_counts().to_string())
bad = res[res.status == "broken"]
if len(bad):
    print("\nBROKEN:\n" + bad.to_string(index=False))
sys.exit(1 if len(bad) else 0)
