"""Numbers for the story: size and tracks, topics this year vs last, agents, benchmarks and datasets,
vocabulary, team size, organisations and countries, and (current year only) how papers are presented.
Writes OUT/stats.json and CSV tables in OUT/.

Topics are fitted on the current edition; each paper of the previous edition is assigned to its nearest
topic, so both years are measured with the same ruler. "Ratio" is always share_cur / share_prev.

Agent papers, two ways:
- keyword: the title or abstract says agent, agents or agentic (AGENT_RX), in both years;
- topic family: topics where at least AGENT_TOPIC_MIN of the current year's papers match the keyword,
  plus, once real labels exist, topics whose name says "agent".
"""
import json, re
from collections import Counter
import numpy as np
import pandas as pd
from config import CUR, PREV, P, OUT
from common import load_papers, paper_orgs, paper_countries, affiliation_parts, orgs_of

MIN_CUR, MIN_PREV = 20, 15  # size guard for risers (papers this year) and fallers (papers last year)
AGENT_RX = r"\bagent(?:s|ic)?\b"
AGENT_TOPIC_MIN = 0.4
BENCH_RX = r"\bbenchmark|\bdatasets?\b|\bcorp(?:us|ora)\b"
# "we introduce / present / release ... a (new) benchmark / dataset / corpus": papers that contribute a resource
NEW_RESOURCE_RX = (r"\b(?:we|this (?:paper|work))\s+(?:\w+\s+){0,2}?(?:introduce|present|propose|release|construct|"
                   r"build|create|curate|collect|develop)\w*\s+(?:[\w-]+,?\s+){0,8}?(?:benchmark|dataset|corpus|test ?bed|suite)")

df = load_papers()
L = json.load(open(P / "labels.json"))
PROVISIONAL = bool(L.get("provisional"))
fine_name = {int(k): v["name"] for k, v in L["fine"].items()}
broad_name = {int(k): v["name"] for k, v in L["broad"].items()}
df["broad_name"] = df["broad"].map(broad_name)
df["fine_name"] = df["fine"].map(fine_name)
df["text"] = df["title_display"] + " " + df["abstract"].fillna("")
dc, dp = df[df.year == CUR], df[df.year == PREV]
c, p = str(CUR), str(PREV)
S = {"years": {"cur": CUR, "prev": PREV}, "provisional_labels": PROVISIONAL,
     f"n_{c}": len(dc), f"n_{p}": len(dp), "growth_pct": round(100 * (len(dc) / len(dp) - 1), 1)}


def pct(x):
    return round(100 * float(x), 2)


# ---------- size and tracks ----------
tr = pd.DataFrame({f"n_{c}": dc.track.value_counts(), f"n_{p}": dp.track.value_counts()}).fillna(0).astype(int)
tr = tr.reindex([t for t in ["Main", "Findings", "Industry", "Demo"] if t in tr.index] + [t for t in tr.index if t not in
                ("Main", "Findings", "Industry", "Demo")])
tr[f"share_{c}"] = 100 * tr[f"n_{c}"] / len(dc)
tr[f"share_{p}"] = 100 * tr[f"n_{p}"] / len(dp)
tr["growth_pct"] = 100 * (tr[f"n_{c}"] / tr[f"n_{p}"].replace(0, np.nan) - 1)
tr.index.name = "track"
tr.round(2).to_csv(OUT / "tracks.csv")
S["tracks"] = tr.round(2).reset_index().to_dict("records")
mf = lambda d: int(d.track.isin(["Main", "Findings"]).sum())
S["main_findings_growth_pct"] = round(100 * (mf(dc) / mf(dp) - 1), 1)


# ---------- topics: share this year vs last (grouped by id, so repeated names cannot merge) ----------
def shares(col, names):
    t = pd.DataFrame({f"n_{c}": dc[col].value_counts(), f"n_{p}": dp[col].value_counts()}).fillna(0).astype(int)
    t[f"share_{c}"] = 100 * t[f"n_{c}"] / len(dc)
    t[f"share_{p}"] = 100 * t[f"n_{p}"] / len(dp)
    t["delta_pp"] = t[f"share_{c}"] - t[f"share_{p}"]
    t["ratio"] = t[f"share_{c}"] / t[f"share_{p}"].replace(0, np.nan)
    t.insert(0, "topic", t.index.map(names))
    t.index.name = "id"
    return t.sort_values(f"share_{c}", ascending=False)


broad = shares("broad", broad_name)
fine = shares("fine", fine_name)
f2b = dc.groupby("fine")["broad"].agg(lambda s: s.mode().iloc[0])
fine.insert(1, "broad", fine.index.map(f2b))
fine.insert(2, "area", fine["broad"].map(broad_name))
broad.round(3).to_csv(OUT / "topics_broad.csv")
fine.round(3).to_csv(OUT / "topics_fine.csv")
rec = lambda t: t.round(2).reset_index().to_dict("records")
S["broad"] = rec(broad)
S["fine_largest"] = rec(fine.head(15))
S["fine_growers"] = rec(fine[fine[f"n_{c}"] >= MIN_CUR].sort_values("delta_pp", ascending=False).head(12))
S["fine_shrinkers"] = rec(fine[fine[f"n_{p}"] >= MIN_PREV].sort_values("delta_pp").head(12))
S["fine_fastest_ratio"] = rec(fine[(fine[f"n_{c}"] >= MIN_CUR) & (fine[f"n_{p}"] >= 10)].sort_values("ratio", ascending=False).head(12))
S["mover_guard"] = {"min_papers_cur": MIN_CUR, "min_papers_prev": MIN_PREV}

# ---------- agents ----------
df["agent_kw"] = df["text"].str.contains(AGENT_RX, case=False, regex=True)
df["agent_title"] = df["title_display"].str.contains(AGENT_RX, case=False, regex=True)
dc, dp = df[df.year == CUR], df[df.year == PREV]
kw_topic = dc.groupby("fine")["agent_kw"].mean()
fam = set(kw_topic[kw_topic >= AGENT_TOPIC_MIN].index)
if not PROVISIONAL:
    fam |= {f for f, n in fine_name.items() if re.search(r"\bagent", n, re.I)}
fam = sorted(fam, key=lambda f: -int((dc.fine == f).sum()))
fine["agent_keyword_share"] = (100 * kw_topic).reindex(fine.index).round(1)
fine.round(3).to_csv(OUT / "topics_fine.csv")
S["agents"] = {
    "method": (f"Keyword: title or abstract matches {AGENT_RX} (case-insensitive). Topic family: topics where at least "
               f"{AGENT_TOPIC_MIN:.0%} of the {CUR} papers match the keyword"
               + ("." if PROVISIONAL else ", plus topics whose name mentions agents.")),
    "topic_min_pct": round(100 * AGENT_TOPIC_MIN),
    "keyword_share": {c: pct(dc.agent_kw.mean()), p: pct(dp.agent_kw.mean())},
    "keyword_n": {c: int(dc.agent_kw.sum()), p: int(dp.agent_kw.sum())},
    "title_share": {c: pct(dc.agent_title.mean()), p: pct(dp.agent_title.mean())},
    "family": [{"id": int(f), "topic": fine_name[f], f"n_{c}": int((dc.fine == f).sum()), f"n_{p}": int((dp.fine == f).sum()),
                "keyword_share_cur": pct(kw_topic[f])} for f in fam],
    "family_n": {c: int(dc.fine.isin(fam).sum()), p: int(dp.fine.isin(fam).sum())},
    "family_share": {c: pct(dc.fine.isin(fam).mean()), p: pct(dp.fine.isin(fam).mean())},
    "keyword_share_by_area": {broad_name[b]: {c: pct(dc[dc.broad == b].agent_kw.mean()),
                                              p: pct(dp[dp.broad == b].agent_kw.mean()) if (dp.broad == b).any() else None}
                              for b in broad.index},
}

# ---------- benchmarks and datasets ----------
S["benchmark_or_dataset"] = {
    "method": f"Mention: title or abstract matches {BENCH_RX}. New resource: the abstract says the paper "
              "introduces, presents, releases or builds a benchmark, dataset or corpus (a rough pattern, a lower bound).",
    "mention_share": {y: pct(d.text.str.contains(BENCH_RX, case=False, regex=True).mean()) for y, d in ((c, dc), (p, dp))},
    "new_resource_share": {y: pct(d.text.str.contains(NEW_RESOURCE_RX, case=False, regex=True).mean()) for y, d in ((c, dc), (p, dp))},
    "benchmark_word_share": {y: pct(d.text.str.contains(r"\bbenchmark", case=False, regex=True).mean()) for y, d in ((c, dc), (p, dp))},
}

# ---------- vocabulary trends (share of papers whose title or abstract uses a term) ----------
TERMS = {
    "LLM / large language model": r"\bLLMs?\b|large language model",
    "agent / agentic": AGENT_RX,
    "reasoning": r"\breasoning\b",
    "chain-of-thought": r"chain[- ]of[- ]thoughts?|\bCoT\b",
    "reinforcement learning / RL": r"reinforcement learning|\bRL\b",
    "GRPO / RLVR": r"\bGRPO\b|\bRLVR\b|verifiable rewards?",
    "preference / DPO / RLHF": r"\bDPO\b|\bRLHF\b|preference optimi[sz]ation",
    "retrieval-augmented / RAG": r"retrieval[- ]augmented|\bRAG\b",
    "benchmark": r"\bbenchmark",
    "hallucination": r"hallucinat",
    "multilingual / low-resource": r"multilingual|low[- ]resource|cross[- ]lingual",
    "translation": r"translat",
    "multimodal / vision-language": r"multi-?modal|\bVLMs?\b|\bMLLMs?\b|vision[- ]language",
    "speech / audio": r"\bspeech\b|\baudio\b|spoken",
    "safety / jailbreak": r"\bsafety\b|jailbreak|red[- ]teaming",
    "bias / fairness": r"\bbias(?:es|ed)?\b|fairness|stereotyp",
    "interpretability": r"interpretab|mechanistic|probing|sparse autoencoder",
    "LLM-as-a-judge": r"as[- ]an?[- ]judges?|LLM judges?|judge models?",
    "in-context learning": r"in[- ]context learning|\bICL\b|few[- ]shot",
    "LoRA / parameter-efficient": r"\bLoRA\b|parameter[- ]efficient|\bPEFT\b",
    "synthetic data": r"synthetic data|data synthesis|synthesi[sz]ed data",
    "long context": r"long[- ]context",
    "efficient / efficiency": r"\befficien(?:t|cy)\b",
    "dialogue": r"\bdialog(?:ue)?s?\b|conversation",
    "summarisation": r"summari[sz]",
    "code": r"\bcode\b|\bcoding\b|program synthesis",
    "BERT": r"\bBERT\b|RoBERTa",
}
rows = []
for name, pat in TERMS.items():
    rx = re.compile(pat, re.I)
    a, b = dc.text.map(lambda t: bool(rx.search(t))).mean(), dp.text.map(lambda t: bool(rx.search(t))).mean()
    rows.append({"term": name, f"pct_{c}": round(100 * a, 1), f"pct_{p}": round(100 * b, 1), "delta_pp": round(100 * (a - b), 1)})
vt = pd.DataFrame(rows).sort_values("delta_pp", ascending=False)
vt.to_csv(OUT / "vocabulary_trends.csv", index=False)
S["vocabulary"] = vt.to_dict("records")

# ---------- team size ----------
S["authors_median"] = {c: float(dc.n_authors.median()), p: float(dp.n_authors.median())}
S["authors_mean"] = {c: round(dc.n_authors.mean(), 2), p: round(dp.n_authors.mean(), 2)}
S["single_author_n"] = {c: int((dc.n_authors == 1).sum()), p: int((dp.n_authors == 1).sum())}
S["single_author_pct"] = {c: pct((dc.n_authors == 1).mean()), p: pct((dp.n_authors == 1).mean())}
S["10plus_author_pct"] = {c: pct((dc.n_authors >= 10).mean()), p: pct((dp.n_authors >= 10).mean())}

# ---------- organisations, countries, sectors ----------
# Shares are among papers with at least one matched affiliation (or country), so coverage differences cancel out.
# Only some authors carry an affiliation in the Anthology, so counts per organisation are lower bounds.
cov, inst_tab, ctry_tab, n_ctry = {}, {}, {}, {}
unmatched = Counter()
for y, d in ((c, dc), (p, dp)):
    orgs = d["affiliations"].map(paper_orgs)
    ctrs = d["affiliations"].map(paper_countries)
    inst = Counter(o for os_ in orgs for o in {x[0] for x in os_})
    ctry = Counter(x for cs in ctrs for x in cs)
    has_org, has_ctry = orgs.map(len) > 0, ctrs.map(len) > 0
    has_ind = orgs.map(lambda os_: any(o[2] == "industry" for o in os_))
    has_acad = orgs.map(lambda os_: any(o[2] == "academia" for o in os_))
    parts = [a for x in d["affiliations"] for a in affiliation_parts(x)]
    miss = [a for a in parts if not orgs_of(a)]
    unmatched.update(miss)
    cov[y] = {"papers_with_affiliation_pct": pct((d.affiliations.fillna("") != "").mean()),
              "authors_with_affiliation_pct": pct(d.n_authors_with_aff.sum() / max(d.n_authors.sum(), 1)),
              "affiliation_strings_matched_pct": pct(1 - len(miss) / max(len(parts), 1)),
              "papers_with_mapped_org_pct": pct(has_org.mean()),
              "papers_with_country_pct": pct(has_ctry.mean())}
    n_org, n_ct = max(int(has_org.sum()), 1), max(int(has_ctry.sum()), 1)
    sector = {o[0]: o[2] for os_ in orgs for o in os_}
    home = {o[0]: o[1] for os_ in orgs for o in os_}
    S[f"institutions_{y}"] = [(o, n, round(100 * n / n_org, 2), sector[o], home[o]) for o, n in inst.most_common(40)]
    S[f"countries_{y}"] = [(k, n, round(100 * n / n_ct, 2)) for k, n in ctry.most_common(25)]
    S[f"industry_share_{y}"] = round(100 * has_ind[has_org].mean(), 1)
    S[f"industry_only_share_{y}"] = round(100 * (has_ind & ~has_acad)[has_org].mean(), 1)
    inst_tab[y], ctry_tab[y], n_ctry[y] = inst, ctry, n_ct
S["affiliation_coverage"] = cov
S["affiliation_method"] = ("Each affiliation string is looked up in institutions_map.json (from the NeurIPS atlas) plus "
                           "institutions_extra.json (EMNLP spellings), whole and in parts. Countries also use a place-name "
                           "hint for strings that match no organisation. Shares are among papers with a match.")
it = pd.DataFrame({f"papers_{c}": pd.Series(inst_tab[c]), f"papers_{p}": pd.Series(inst_tab[p])}).fillna(0).astype(int)
it.index.name = "organisation"
it.sort_values(f"papers_{c}", ascending=False).head(300).to_csv(OUT / "institutions.csv")
ct = pd.DataFrame({f"papers_{c}": pd.Series(ctry_tab[c]), f"papers_{p}": pd.Series(ctry_tab[p])}).fillna(0).astype(int)
for y in (c, p):
    ct[f"pct_{y}"] = (100 * ct[f"papers_{y}"] / n_ctry[y]).round(2)
ct.index.name = "country"
ct.sort_values(f"papers_{c}", ascending=False).to_csv(OUT / "countries.csv")
pd.Series(unmatched).sort_values(ascending=False).head(300).rename("strings").rename_axis("affiliation").to_csv(
    OUT / "affiliations_unmatched.csv")  # what to add to institutions_extra.json next

# ---------- Main vs Findings by area (both years) ----------
def track_mix(d):
    t = pd.crosstab(d.broad, d.track)
    for k in ("Main", "Findings"):
        if k not in t:
            t[k] = 0
    return t


tm_c, tm_p = track_mix(dc), track_mix(dp)
fs = pd.DataFrame({"topic": broad_name, f"main_{c}": tm_c["Main"], f"findings_{c}": tm_c["Findings"],
                   f"main_{p}": tm_p["Main"], f"findings_{p}": tm_p["Findings"]}).dropna(subset=[f"main_{c}"]).fillna(0)
fs[f"findings_share_{c}"] = 100 * fs[f"findings_{c}"] / (fs[f"main_{c}"] + fs[f"findings_{c}"]).replace(0, np.nan)
fs[f"findings_share_{p}"] = 100 * fs[f"findings_{p}"] / (fs[f"main_{p}"] + fs[f"findings_{p}"]).replace(0, np.nan)
fs["delta_pp"] = fs[f"findings_share_{c}"] - fs[f"findings_share_{p}"]
fs.index.name = "id"
fs = fs.sort_values(f"findings_share_{c}", ascending=False)
fs.round(2).to_csv(OUT / "findings_share_by_area.csv")
S["findings_share_by_area"] = rec(fs)
S["findings_share_overall"] = {y: pct((d.track == "Findings").sum() / max(d.track.isin(["Main", "Findings"]).sum(), 1))
                               for y, d in ((c, dc), (p, dp))}


# ---------- presentation and schedule (current year only; empty in a dry run) ----------
PRES = ["oral", "poster", "virtual", "demo", "not presenting"]


def presentation(d):
    """oral / poster / virtual / demo / not presenting, or '' without a program entry. Orals and posters
    given in virtual mode count as virtual, as on the map."""
    t = d["pres_type"].fillna("").str.lower().str.strip().replace({"virtual pres-demo": "demo", "tbc": "", "nan": ""})
    t = t.where(t.isin(PRES), "")
    return t.mask(d["mode"].fillna("").str.lower().eq("virtual") & t.isin(["oral", "poster"]), "virtual")


def schedule_stats(d):
    d = d.assign(pres=presentation(d))
    prog = d[d.pres != ""]
    if prog.empty:
        return {"schedule_available": False}
    out = {"schedule_available": True, "papers_in_program": len(prog), "papers_without_slot": int((d.pres == "").sum()),
           "pres_counts": prog.pres.value_counts().reindex(PRES, fill_value=0).to_dict(),
           "pres_by_track": pd.crosstab(prog.track, prog.pres).to_dict("index")}
    mix = pd.crosstab(prog.broad, prog.pres, normalize="index").reindex(columns=PRES, fill_value=0) * 100
    mix.insert(0, "papers", prog.groupby("broad").size())
    mix.insert(0, "topic", mix.index.map(broad_name))
    mix.index.name = "id"
    mix = mix.sort_values("oral", ascending=False)
    mix.round(2).to_csv(OUT / "presentation_mix_by_area.csv")
    out["pres_mix_by_area"] = rec(mix)
    out["pres_overall_pct"] = (100 * prog.pres.value_counts(normalize=True)).reindex(PRES, fill_value=0).round(2).to_dict()
    # orals exist only in Main and Industry, so the oral rate is among those papers
    el = prog[prog.track.isin(["Main", "Industry"])]
    if len(el):
        r = el.assign(oral=el.pres.eq("oral")).groupby("broad").agg(papers=("oral", "size"), orals=("oral", "sum"))
        r["rate_pct"] = 100 * r.orals / r.papers
        r.insert(0, "topic", r.index.map(broad_name))
        r.index.name = "id"
        r = r.sort_values("rate_pct", ascending=False)
        r.round(2).to_csv(OUT / "oral_rate_by_area.csv")
        out["oral_rate_overall_pct"] = pct(el.pres.eq("oral").mean())
        out["oral_rate_by_area"] = rec(r)
    orals = prog[prog.pres.eq("oral") & prog["subsession"].fillna("").ne("")]
    if len(orals):  # official EMNLP area names of the oral sessions
        out["oral_sessions_by_official_area"] = orals.subsession.str.replace(r"\s+\d+$", "", regex=True).value_counts().head(30).to_dict()
    dt = pd.to_datetime(prog["date"], errors="coerce")
    days = prog[dt.notna()].assign(day=dt[dt.notna()].dt.strftime("%a %d %b"), iso=dt[dt.notna()].dt.strftime("%Y-%m-%d"))
    if len(days):
        pd_ = pd.crosstab([days.iso, days.day], days.pres).reindex(columns=PRES, fill_value=0)
        pd_["papers"] = pd_.sum(axis=1)
        pd_ = pd_.reset_index().sort_values("iso")
        pd_.to_csv(OUT / "papers_per_day.csv", index=False)
        out["papers_per_day"] = pd_.to_dict("records")
    return out


S["schedule"] = schedule_stats(dc)

json.dump(S, open(OUT / "stats.json", "w"), indent=1, default=str)
sch = S["schedule"]
print(f"{CUR}: {len(dc):,} papers ({S['growth_pct']:+.1f}% vs {PREV}) | areas {len(broad)} | agent keyword "
      f"{S['agents']['keyword_share'][p]}% → {S['agents']['keyword_share'][c]}% | family {len(fam)} topics | "
      f"orgs matched on {cov[c]['papers_with_mapped_org_pct']}% of papers | schedule: "
      + (f"{sch['papers_in_program']:,} papers in the program" if sch["schedule_available"] else "none"))
