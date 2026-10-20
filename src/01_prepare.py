"""Turn the Anthology XML into one paper table for both editions, and attach the EMNLP 2026
program (session, room, day and time) by matching titles. Writes data/processed*/papers.parquet."""
import csv, json, re
import xml.etree.ElementTree as ET
import pandas as pd
from config import CUR, P, RAW, TRACKS, YEARS
from common import tex_to_text, title_key

VOLUMES = {"emnlp": ["main", "industry", "demos", "demo"], "findings": ["emnlp"]}  # 2024 calls it "demo"


def text_of(el):
    """Readable text of a title or abstract element: drops <fixed-case>, keeps maths as $...$."""
    if el is None:
        return ""
    parts = [el.text or ""]
    for ch in el:
        if ch.tag == "tex-math":
            parts.append("$" + "".join(ch.itertext()) + "$")
        else:
            parts.append(text_of(ch))
        parts.append(ch.tail or "")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


rows = []
for year in YEARS:
    for coll, vols in VOLUMES.items():
        path = RAW / f"{year}.{coll}.xml"
        if not path.exists():
            print("missing", path.name)
            continue
        root = ET.parse(path).getroot()
        for vol in root.findall("volume"):
            vid = vol.get("id")
            if vid not in vols:
                continue
            track = "findings" if coll == "findings" else ("demos" if vid == "demo" else vid)
            for p in vol.findall("paper"):
                url = (p.findtext("url") or "").strip()
                authors = p.findall("author")
                affs = []
                for a in authors:
                    aff = (a.findtext("affiliation") or "").strip()
                    if aff and aff not in affs:
                        affs.append(aff)
                title = text_of(p.find("title"))
                rows.append({
                    "uid": url or f"{year}.{coll}-{vid}.{p.get('id')}", "year": year, "track": TRACKS[track],
                    "title": title, "title_display": tex_to_text(title),
                    "abstract": tex_to_text(text_of(p.find("abstract"))),
                    "authors": ", ".join(f"{a.findtext('first') or ''} {a.findtext('last') or ''}".strip() for a in authors),
                    "n_authors": len(authors),
                    "affiliations": " | ".join(affs),
                    "n_authors_with_aff": sum(bool((a.findtext("affiliation") or "").strip()) for a in authors),
                    "doi": p.findtext("doi") or "",
                })

df = pd.DataFrame(rows)
df["anthology"] = "https://aclanthology.org/" + df["uid"] + "/"
df["pdf"] = "https://aclanthology.org/" + df["uid"] + ".pdf"
df["k"] = df["title_display"].map(title_key)
df["dup"] = df.duplicated(["year", "k"])
df["has_abstract"] = df["abstract"].str.len() > 50

# EMNLP 2026 program: join by title (the sheet has no Anthology ids)
sched_cols = ["pres_type", "mode", "room", "session", "subsession", "date", "start", "end"]
for c in sched_cols:
    df[c] = ""
report = {}
sheet = RAW / "emnlp2026_program.csv"
if CUR == 2026 and sheet.exists():
    rd = list(csv.reader(open(sheet, encoding="utf-8")))
    hdr = [h.replace("\n", " ").strip() for h in rd[0]]
    prog = pd.DataFrame(rd[1:], columns=hdr)
    prog.columns = ["pid", "title", "pres_type", "mode", "presenter", "room", "session", "subsession",
                    "date", "start", "end"][:len(prog.columns)]
    for c in prog.columns:
        prog[c] = prog[c].astype(str).str.strip()
    prog["prog_track"] = prog["pid"].str.split("-").str[-1].str.upper()
    prog = prog[~prog["prog_track"].isin(["TACL", "CL"])]
    prog["k"] = prog["title"].map(lambda t: title_key(tex_to_text(t)))
    # virtual rows put the whole range in "start", e.g. "12:30-14:00 CET"
    rng = prog["start"].str.extract(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
    has = rng[0].notna()
    prog.loc[has, "end"] = rng.loc[has, 1]
    prog.loc[has, "start"] = rng.loc[has, 0]
    prog["pres_type"] = prog["pres_type"].str.lower().str.replace(r"\s+pres$", "", regex=True).str.strip()
    prog["mode"] = prog["mode"].str.lower()
    prog = prog.replace({"#N/A": "", "TBD": "", "nan": ""})
    prog = prog.drop_duplicates("k")
    m = df["year"].eq(2026)
    joined = df.loc[m, ["k"]].merge(prog[["k"] + sched_cols], on="k", how="left")
    for c in sched_cols:
        df.loc[m, c] = joined[c].fillna("").to_numpy()
    report = {"program_rows": int(len(prog)), "papers_2026": int(m.sum()),
              "matched": int((df.loc[m, "pres_type"] != "").sum()),
              "unmatched_program_rows": int((~prog["k"].isin(df.loc[m, "k"])).sum())}

counts = df[~df["dup"]].groupby(["year", "track"]).size().unstack(fill_value=0)
report.update({"counts": {int(y): {t: int(n) for t, n in r.items()} for y, r in counts.iterrows()},
               "duplicates_flagged": int(df["dup"].sum()),
               "abstract_coverage": {int(y): round(float(g["has_abstract"].mean()), 4) for y, g in df.groupby("year")},
               "papers_with_affiliation": {int(y): round(float((g["affiliations"] != "").mean()), 4) for y, g in df.groupby("year")}})
df.to_parquet(P / "papers.parquet", index=False)
json.dump(report, open(P / "prepare_report.json", "w"), indent=1)
print(json.dumps(report, indent=1))
