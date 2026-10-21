"""Generate APPENDIX.md (report/ for the real edition, OUT/ in a dry run): every area and topic with
counts, shares, the Main / Findings split and, once the program is known, the orals."""
import json
import pandas as pd
from config import CUR, PREV, P, REPORT
from common import load_papers, anthology_pages_live

ANTH_PAGES = anthology_pages_live(CUR)

REPORT.mkdir(parents=True, exist_ok=True)
df = load_papers()
L = json.load(open(P / "labels.json"))
fine = {int(k): v for k, v in L["fine"].items()}
broad = {int(k): v for k, v in L["broad"].items()}
dc, dp = df[df.year == CUR], df[df.year == PREV]
nc, np_ = dc.fine.value_counts(), dp.fine.value_counts()
bc, bp = dc.broad.value_counts(), dp.broad.value_counts()
f2b = dc.groupby("fine")["broad"].agg(lambda s: s.mode().iloc[0])
about = any(v.get("one_line") for v in fine.values())
oral = dc["pres_type"].fillna("").str.lower().eq("oral") & dc["mode"].fillna("").str.lower().ne("virtual")
sched = oral.any()


def cell(s):
    return str(s).replace("|", "/").replace("\n", " ").strip()


intro = (f"All {dc.broad.nunique()} areas and {dc.fine.nunique()} topics of EMNLP {CUR} ({len(dc):,} papers in the Main, "
         f"Findings, Industry and Demo tracks). For each topic you see "
         + ("what the papers do, " if about else "")
         + f"how many papers it has, its share of all papers in {PREV} and {CUR}, and how many of its papers are in Main and "
           f"in Findings." + (" Orals is the number of in-person orals." if sched else ""))
lines = ["# All areas and topics", "", intro, ""]
if L.get("provisional"):
    lines += ["Topic names here are provisional: each is the topic's three most typical terms, not a written name.", ""]
head = ["Topic"] + (["What the papers do"] if about else []) + [str(CUR), f"share {PREV} → {CUR}", "Main / Findings"] + \
       (["Orals"] if sched else [])
for b in sorted(broad, key=lambda b: -bc.get(b, 0)):
    if not bc.get(b, 0):
        continue
    sc, sp = 100 * bc.get(b, 0) / len(dc), 100 * bp.get(b, 0) / len(dp)
    lines += [f"## {cell(broad[b]['name'])}: {bc.get(b, 0):,} papers ({sc:.1f}% of all, {PREV}: {sp:.1f}%)", ""]
    if broad[b].get("one_line"):
        lines += [broad[b]["one_line"], ""]
    lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for f in sorted([f for f in fine if nc.get(f, 0) and f2b[f] == b], key=lambda f: -nc.get(f, 0)):
        g = dc[dc.fine == f]
        row = [cell(fine[f]["name"])] + ([cell(fine[f].get("one_line", ""))] if about else []) + [
            str(len(g)), f"{100 * np_.get(f, 0) / len(dp):.2f}% → {100 * len(g) / len(dc):.2f}%",
            f"{int((g.track == 'Main').sum())} / {int((g.track == 'Findings').sum())}"]
        row += [str(int(oral[g.index].sum()))] if sched else []
        lines.append("| " + " | ".join(row) + " |")
    orals = dc[(dc.broad == b) & oral].fillna({"anthology": "", "pdf": ""}).sort_values("title_display")
    if len(orals):
        lines += ["", "**Orals**", ""]
        for o in orals.itertuples():
            links = " · ".join(x for x in (f"[Anthology]({o.anthology})" if o.anthology and ANTH_PAGES else "",
                                           f"[PDF]({o.pdf})" if o.pdf else "") if x)
            lines.append(f"- {cell(o.title_display)}" + (f": {links}" if links else ""))
    lines.append("")
(REPORT / "APPENDIX.md").write_text("\n".join(lines))
print("wrote", REPORT / "APPENDIX.md")
