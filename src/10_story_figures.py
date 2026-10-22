"""Story figures for the EMNLP atlas, in the style of the NeurIPS atlas. Every title states what the chart
shows, and is filled in from the numbers, so the same code works with provisional or final topic names.

OUT/figures/:
- tracks_growth.png        papers per track, previous vs current year
- field_moved.png          the current map coloured by how much each topic's share changed
- agents_family.png        papers per agent topic, previous vs current year
- areas_slope.png          area shares, previous -> current year
- movers_x.png             topics that gained and lost the most share
- vocabulary_trends.png    change in the share of papers using some common terms
- countries.png, top_institutions.png
- findings_share_by_area.png   Findings as a share of each area's Main + Findings papers
- presentation_mix.png, oral_rate_by_area.png, papers_per_day.png   current year, only when the program is known

Run 05_stats.py first. "Ratio" always means share_cur / share_prev.
"""
import json, re, textwrap
import numpy as np
import pandas as pd
from config import CUR, PREV, P, OUT
from common import load_papers
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe
from scipy.ndimage import gaussian_filter

FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

INK, MUTED, ACC, COOL, GREY, BG = "#1f2a44", "#6b7489", "#d9480f", "#3b5bdb", "#b8bfcc", "#fbfaf7"
PRES_COL = {"oral": "#c92a2a", "poster": "#f08c00", "virtual": "#7048e8", "demo": "#2b8a3e", "not presenting": "#adb5bd"}
PRES_LAB = {"oral": "Oral", "poster": "Poster", "virtual": "Virtual", "demo": "Demo", "not presenting": "Not presented"}
plt.rcParams.update({"font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#c9ced8",
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
                     "legend.labelcolor": INK, "figure.facecolor": BG, "axes.facecolor": BG,
                     "savefig.facecolor": BG, "savefig.bbox": "tight", "savefig.dpi": 200})
SOURCE = f"Data: ACL Anthology, EMNLP {CUR} · Analysis: Hadi Mohammadi · github.com/mohammadi-hadi/emnlp"

df = load_papers()
L = json.load(open(P / "labels.json"))
S = json.load(open(OUT / "stats.json"))
fine_name = {int(k): v["name"] for k, v in L["fine"].items()}
broad_name = {int(k): v["name"] for k, v in L["broad"].items()}
dc, dp = df[df.year == CUR], df[df.year == PREV]
c, p = str(CUR), str(PREV)
growth_conf = len(dc) / len(dp)
fine = pd.read_csv(OUT / "topics_fine.csv", index_col=0)
sc, sp, nc, np_ = f"share_{c}", f"share_{p}", f"n_{c}", f"n_{p}"


def short(name, n=34):
    """Display name: drops the 'Area 3: ' prefix of provisional labels and cuts long names."""
    s = re.sub(r"^Area \d+:\s*", "", str(name)).strip()
    return s if len(s) <= n else s[:n - 1].rstrip(" ·,") + "…"


def country(cn):
    return {"USA": "the US", "UK": "the UK", "UAE": "the UAE", "Netherlands": "the Netherlands"}.get(cn, cn)


def frame(fig, title, subtitle, y=0.995):
    fig.text(0.01, y, title, fontsize=19, fontweight="bold", color=INK, va="top")
    fig.text(0.01, y - 0.42 / fig.get_figheight(), subtitle, fontsize=11.5, color=MUTED, va="top")  # same gap at any height
    fig.text(0.01, 0.005, SOURCE, fontsize=8, color=MUTED, va="bottom")


def outline(t, w=3):
    t.set_path_effects([pe.withStroke(linewidth=w, foreground=BG)])


def grid_x(ax):
    ax.grid(axis="x", color="#e6e8ee", lw=0.8)
    ax.set_axisbelow(True)


def spread(vals, gap):
    """Spread label positions symmetrically so neighbours are at least `gap` apart."""
    vals = np.asarray(vals, float)
    order = np.argsort(vals)
    pos = vals[order].copy()
    for _ in range(500):
        moved = False
        for k in range(1, len(pos)):
            d = pos[k] - pos[k - 1]
            if d < gap:
                push = (gap - d) / 2
                pos[k - 1] -= push; pos[k] += push; moved = True
        if not moved:
            break
    out = np.empty_like(pos); out[order] = pos
    return out


def save(fig, name):
    fig.savefig(FIG / name); plt.close(fig)
    written.append(name)


written = []

# ================= 1. size and tracks =================
tr = pd.DataFrame(S["tracks"]).set_index("track")
fig, ax = plt.subplots(figsize=(10, 5.2))
fig.subplots_adjust(top=0.8, bottom=0.14, left=0.12, right=0.95)
yy = np.arange(len(tr))[::-1]
ax.barh(yy - 0.2, tr[np_], 0.38, color=GREY, label=p)
ax.barh(yy + 0.2, tr[nc], 0.38, color=ACC, label=c)
for y_, (_, r) in zip(yy, tr.iterrows()):
    ax.text(r[nc] + tr[nc].max() * 0.01, y_ + 0.2, f"{r[nc]:,.0f}" + (f"  ({r.growth_pct:+.0f}%)" if pd.notna(r.growth_pct) else ""),
            va="center", fontsize=9.5, color=INK)
ax.set_yticks(yy, tr.index)
ax.set_xlim(0, tr[nc].max() * 1.2)
ax.set_xlabel("papers")
ax.legend(frameon=False, loc="lower right")
grid_x(ax)
frame(fig, f"EMNLP {CUR} has {len(dc):,} papers, {S['growth_pct']:.0f}% more than in {PREV}",
      f"Papers per track in the ACL Anthology. Main and Findings together grew {S['main_findings_growth_pct']:.0f}%.")
save(fig, "tracks_growth.png")

# ================= 2. where the field moved =================
# Colour = growth of the topic each current-year paper belongs to (shares come from the embedding-space
# assignment, not from map positions), smoothed over the map and shown only where papers are.
shc = dc.fine.value_counts(normalize=True)
shp = dp.fine.value_counts(normalize=True).reindex(shc.index, fill_value=0)
grow = np.log2((shc + 0.0005) / (shp + 0.0005)).clip(-1.5, 1.5)
xmin, xmax = dc.x.quantile([0.002, 0.998]); ymin, ymax = dc.y.quantile([0.002, 0.998])
pad = 0.06 * max(xmax - xmin, ymax - ymin)
ext = [xmin - pad, xmax + pad, ymin - pad, ymax + pad]
rng, bins, sig = [ext[:2], ext[2:]], 300, 3.5
cnt = gaussian_filter(np.histogram2d(dc.x, dc.y, bins=bins, range=rng)[0], sig)
wsum = gaussian_filter(np.histogram2d(dc.x, dc.y, bins=bins, range=rng, weights=dc.fine.map(grow))[0], sig)
field = np.ma.masked_where(cnt < 0.08, wsum / np.maximum(cnt, 1e-9))
med = dc.groupby("broad")[["x", "y"]].median()


def soft_field(x, y, w, ext):
    """The same colour field on a finer grid, fading out at the edges instead of stepping in square pixels."""
    rng, bins, sig = [ext[:2], ext[2:]], 600, 7
    cnt = gaussian_filter(np.histogram2d(x, y, bins=bins, range=rng)[0], sig)
    wsum = gaussian_filter(np.histogram2d(x, y, bins=bins, range=rng, weights=w)[0], sig)
    rgba = plt.cm.RdBu_r(plt.Normalize(-1.2, 1.2)(wsum / np.maximum(cnt, 1e-9)))
    rgba[..., 3] = np.clip((cnt - 0.012) / 0.016, 0, 1)
    return rgba.transpose(1, 0, 2)

def spread_labels(pos, names, fs, ax_in):
    """Push apart area labels that would overlap, using their size in data units."""
    pos = pos.copy()
    ux = (ext[1] - ext[0]) / ax_in[0] / 72  # data units per point
    uy = (ext[3] - ext[2]) / ax_in[1] / 72
    w = {b: 0.55 * fs * max(len(x) for x in names[b].split("\n")) * ux for b in pos.index}
    h = 1.3 * fs * uy * max(names[b].count("\n") + 1 for b in pos.index)
    for _ in range(400):
        moved = False
        idx = list(pos.index)
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                ddx, ddy = pos.at[j, "x"] - pos.at[i, "x"], pos.at[j, "y"] - pos.at[i, "y"]
                if abs(ddy) < h and abs(ddx) < (w[i] + w[j]) / 2:
                    step = 0.1 * h if ddy >= 0 else -0.1 * h
                    pos.at[j, "y"] += step; pos.at[i, "y"] -= step; moved = True
        if not moved:
            break
    return pos


fig = plt.figure(figsize=(12, 12.6))
ax = fig.add_axes([0.0, 0.03, 1.0, 0.9])
ax.imshow(soft_field(dc.x, dc.y, dc.fine.map(grow), ext), origin="lower", extent=ext, interpolation="bilinear", aspect="auto")
ax.scatter(dc.x, dc.y, s=0.8, c=INK, alpha=0.18, linewidths=0)
# whole names on two or three lines, big enough to read at the size the story shows the figure
lab = {b: textwrap.fill(short(broad_name[b], 60), 18) for b in med.index}
for b, r in spread_labels(med, lab, 14, (12, 12.6 * 0.9)).iterrows():
    outline(ax.text(r.x, r.y, lab[b], ha="center", va="center", fontsize=14, color=INK, fontweight="bold", linespacing=1.0), 4)
ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.axis("off")
cax = fig.add_axes([0.62, 0.07, 0.34, 0.016])
cb = fig.colorbar(plt.cm.ScalarMappable(cmap="RdBu_r", norm=plt.Normalize(-1.2, 1.2)), cax=cax, orientation="horizontal")
cb.set_ticks([-1, 0, 1]); cb.set_ticklabels(["half the share", "same", "double the share"])
cb.outline.set_visible(False); cax.tick_params(labelsize=12, colors=MUTED, length=0)
frame(fig, f"Where EMNLP moved between {PREV} and {CUR}", "Red topics grew their share of papers. Blue ones shrank.")
save(fig, "field_moved.png")

# ================= 3. the agent family =================
A = S["agents"]
fam = A["family"]
if fam:
    n_all = len(fam)
    fam = sorted(fam, key=lambda f: -f[nc])[:12]  # the 12 largest keep the chart readable on a phone
    names = [short(f["topic"], 52) for f in fam]
    a_p, a_c = np.array([f[np_] for f in fam]), np.array([f[nc] for f in fam])
    fg = A["family_n"][c] / max(A["family_n"][p], 1)
    fig, ax = plt.subplots(figsize=(11, 1.6 + 0.55 * len(fam)))
    fig.subplots_adjust(top=1 - 1.15 / (1.6 + 0.55 * len(fam)), bottom=0.6 / (1.6 + 0.55 * len(fam)), left=0.42, right=0.93)
    yy = np.arange(len(fam))[::-1]
    ax.hlines(yy, a_p, a_c, color=ACC, lw=3, alpha=0.5)
    ax.scatter(a_p, yy, s=60, color=GREY, zorder=3, label=p)
    ax.scatter(a_c, yy, s=80, color=ACC, zorder=4, label=c)
    for y_, a_, b_ in zip(yy, a_p, a_c):
        ax.annotate(f"{a_} → {b_}", (max(a_, b_), y_), xytext=(8, 0), textcoords="offset points", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(yy, names)
    ax.set_xlim(0, max(a_c.max(), a_p.max()) * 1.25)
    ax.set_xlabel("papers")
    grid_x(ax)
    ax.legend(frameon=False, loc="lower right")
    frame(fig, f"Papers that mention agents went from {A['keyword_share'][p]:.0f}% to {A['keyword_share'][c]:.0f}% of EMNLP",
          f"The {len(fam)} largest of the {n_all} agent topics (at least {A['topic_min_pct']}% of their {CUR} papers mention agents). "
          f"All {n_all} grew {fg:.1f}x, the conference {growth_conf:.1f}x.", y=0.995)
    save(fig, "agents_family.png")
else:
    print("no agent topic family, skipped agents_family.png")

# ================= 4. slope chart of areas =================
b = pd.DataFrame(S["broad"])
b["label"] = b.topic.map(lambda t: short(t, 38))
H = max(8, 0.55 * len(b) + 2.5)
fig, ax = plt.subplots(figsize=(10, H))
fig.subplots_adjust(top=1 - 1.4 / H, left=0.03, right=0.97, bottom=0.04)
span = max(b[sc].max(), b[sp].max()) - min(b[sc].min(), b[sp].min())
gap = span * 0.032  # about one line of 9.5 pt text at this height
yl, yr = spread(b[sp], gap), spread(b[sc], gap)
for (_, row), a, cc in zip(b.iterrows(), yl, yr):
    up, down = row.delta_pp > 0.5, row.delta_pp < -0.5
    col = ACC if up else (COOL if down else GREY)
    tcol = ACC if up else (COOL if down else MUTED)
    ax.plot([0, 1], [row[sp], row[sc]], color=col, lw=2.6 if (up or down) else 1.2, solid_capstyle="round",
            zorder=3 if (up or down) else 1)
    ax.scatter([0, 1], [row[sp], row[sc]], color=col, s=22, zorder=4)
    ax.plot([-0.06, -0.01], [a, row[sp]], color="#c9ced8", lw=0.7)  # leader lines
    ax.plot([1.01, 1.06], [row[sc], cc], color="#c9ced8", lw=0.7)
    ax.text(-0.07, a, f"{row.label}  {row[sp]:.1f}%", ha="right", va="center", fontsize=9.5, color=tcol)
    ax.text(1.07, cc, f"{row[sc]:.1f}%  {row.label}", ha="left", va="center", fontsize=9.5, color=tcol,
            fontweight="bold" if abs(row.delta_pp) > 1 else "normal")
ax.set_xlim(-1.05, 2.05); ax.axis("off")
top_y = max(yl.max(), yr.max()) + gap * 1.6
ax.text(0, top_y, p, ha="center", fontsize=12, fontweight="bold", color=INK)
ax.text(1, top_y, c, ha="center", fontsize=12, fontweight="bold", color=INK)
riser, faller = b.loc[b.delta_pp.idxmax()], b.loc[b.delta_pp.idxmin()]
if riser.delta_pp < 0.5 and faller.delta_pp > -0.5:
    t = "No research area moved by more than half a point"
else:
    t = f"{short(riser.topic, 28)} grew the most. {short(faller.topic, 28)} shrank the most."
frame(fig, t, "Share of all papers per area. Orange: up more than half a point. Blue: down more than half a point. "
      "Grey: smaller change.", y=0.995)
save(fig, "areas_slope.png")

# ================= 5. topics that gained and lost the most share =================
MIN_CUR, MIN_PREV = S["mover_guard"]["min_papers_cur"], S["mover_guard"]["min_papers_prev"]
up = fine[fine[nc] >= MIN_CUR].sort_values("delta_pp", ascending=False).head(10)
up = up[up.delta_pp > 0]
dn = fine[fine[np_] >= MIN_PREV].sort_values("delta_pp").head(8)
dn = dn[dn.delta_pp < 0]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14.5, 7.8), gridspec_kw={"wspace": 0.95})
fig.subplots_adjust(top=0.82, bottom=0.13, left=0.23, right=0.97)
for ax, t, col, ttl in [(a1, up.iloc[::-1], ACC, "Gained most share"), (a2, dn.iloc[::-1], COOL, "Lost most share")]:
    yy = np.arange(len(t))
    ax.hlines(yy, t[sp], t[sc], color=col, lw=2.5, alpha=0.6)
    ax.scatter(t[sp], yy, color=GREY, s=40, zorder=3, label=p)
    ax.scatter(t[sc], yy, color=col, s=55, zorder=4, label=c)
    ax.set_yticks(yy, [short(x, 36) for x in t.topic], fontsize=10)
    for y_, (_, row) in zip(yy, t.iterrows()):
        lab = (f"{row[np_]:.0f} → {row[nc]:.0f} papers" if row[np_] < 15
               else (f"×{row.ratio:.1f}" if row.ratio >= 1 else f"×{row.ratio:.2f}"))
        ax.annotate(lab, (max(row[sp], row[sc]), y_), xytext=(7, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=col, fontweight="bold", annotation_clip=False)
    if len(t):
        ax.set_xlim(0, max(t[sp].max(), t[sc].max()) * 1.32)
    ax.set_title(ttl, loc="left", fontsize=13, color=col, fontweight="bold")
    ax.set_xlabel("% of papers")
    grid_x(ax)
a1.legend(frameon=False, loc="lower right", fontsize=9)
frame(fig, f"{short(up.iloc[0].topic, 40)} gained the most ground" if len(up) else "Topic shares barely moved",
      f"Grey dot: {PREV}. Coloured dot: {CUR}. The label shows how many times bigger or smaller the share got "
      f"(paper counts for topics that were tiny in {PREV}).\nOnly topics with at least {MIN_CUR} papers in {CUR} "
      f"(gains) or {MIN_PREV} in {PREV} (losses).")
save(fig, "movers_x.png")

# ================= 6. vocabulary =================
v = pd.DataFrame(S["vocabulary"]).sort_values("delta_pp")
fig, ax = plt.subplots(figsize=(10, 9.5))
fig.subplots_adjust(top=0.87, bottom=0.1, left=0.33, right=0.95)
ax.barh(v.term, v.delta_pp, color=[ACC if x > 0 else COOL for x in v.delta_pp], height=0.65)
for i, (pc_, dlt) in enumerate(zip(v[f"pct_{c}"], v.delta_pp)):
    ax.text(dlt + 0.15 if dlt >= 0 else 0.15, i, f"{pc_:.0f}%", va="center", fontsize=8.5, color=MUTED)
ax.axvline(0, color="#9aa3b5", lw=1)
ax.set_xlabel(f"change since {PREV}, in points")
grid_x(ax)
WORDS = {"LLM / large language model": "LLMs", "agent / agentic": "agents", "benchmark": "benchmarks",
         "multimodal / vision-language": "multimodal models", "reinforcement learning / RL": "reinforcement learning",
         "retrieval-augmented / RAG": "RAG", "LoRA / parameter-efficient": "LoRA", "code": "code"}
word = lambda t: WORDS.get(t, t.split(" / ")[0])
top2 = v.sort_values("delta_pp", ascending=False).head(2).term.map(word).tolist()
low = v.iloc[0]
t = f"More papers talk about {top2[0]} and {top2[1]}"
t += f". Fewer say '{word(low.term)}'." if low.delta_pp <= -1 else "."
frame(fig, t, f"Change since {PREV} in the share of papers whose title or abstract uses each term. The label is the {CUR} share.")
save(fig, "vocabulary_trends.png")

# ================= 7. countries and organisations =================
cov = S["affiliation_coverage"]
ccur = {k: x for k, _, x in S[f"countries_{c}"]}; cprev = {k: x for k, _, x in S[f"countries_{p}"]}
cs = [k for k, _, _ in S[f"countries_{c}"][:12]][::-1]
fig, ax = plt.subplots(figsize=(9, 7))
fig.subplots_adjust(top=0.84, bottom=0.12, left=0.2, right=0.95)
yy = np.arange(len(cs))
ax.hlines(yy, [cprev.get(k, 0) for k in cs], [ccur.get(k, 0) for k in cs], color="#c9ced8", lw=2.5)
ax.scatter([cprev.get(k, 0) for k in cs], yy, s=50, color=GREY, label=p, zorder=3)
ax.scatter([ccur.get(k, 0) for k in cs], yy, s=70, color=ACC, label=c, zorder=4)
ax.set_yticks(yy, cs)
ax.set_xlabel("% of papers (with a matched affiliation) that have an author from the country")
ax.legend(frameon=False, loc="lower right")
grid_x(ax)
k1, k2 = cs[-1], cs[-2]
frame(fig, f"{country(k1)[0].upper() + country(k1)[1:]} is on {ccur[k1]:.0f}% of papers, {country(k2)} on {ccur[k2]:.0f}%",
      f"Share of papers with at least one author from each country. {country(k2)[0].upper() + country(k2)[1:]} was at "
      f"{cprev.get(k2, 0):.0f}% in {PREV}. Affiliations matched for {cov[c]['papers_with_country_pct']:.0f}% of papers.")
save(fig, "countries.png")

top = S[f"institutions_{c}"][:20][::-1]
fig, ax = plt.subplots(figsize=(9, 8))
fig.subplots_adjust(top=0.86, bottom=0.1, left=0.3, right=0.95)
ax.barh([t_[0] for t_ in top], [t_[1] for t_ in top], color=INK, height=0.65)
for i, t_ in enumerate(top):
    ax.text(t_[1] + top[-1][1] * 0.012, i, str(t_[1]), va="center", fontsize=9, color=MUTED)
ax.set_xlabel("papers with at least one author from the organisation")
grid_x(ax)
frame(fig, f"{top[-1][0]} is on the most papers: {top[-1][1]}",
      f"The 20 organisations with the most EMNLP {CUR} papers. Only {cov[c]['authors_with_affiliation_pct']:.0f}% of "
      "authors list an affiliation, so these are lower bounds.")
save(fig, "top_institutions.png")

# ================= 8. Findings share by area =================
fs = pd.DataFrame(S["findings_share_by_area"]).sort_values(f"findings_share_{c}")
ov = S["findings_share_overall"]
fig, ax = plt.subplots(figsize=(10, max(6, 0.45 * len(fs) + 2)))
fig.subplots_adjust(top=0.86, bottom=0.1, left=0.3, right=0.95)
yy = np.arange(len(fs))
ax.hlines(yy, fs[f"findings_share_{p}"], fs[f"findings_share_{c}"], color="#c9ced8", lw=2.5)
ax.scatter(fs[f"findings_share_{p}"], yy, s=50, color=GREY, label=p, zorder=3)
ax.scatter(fs[f"findings_share_{c}"], yy, s=70, color=ACC, label=c, zorder=4)
ax.axvline(ov[c], color=INK, ls="--", lw=1)
ax.text(ov[c] + 0.3, len(fs) - 0.4, f"all of EMNLP {CUR}: {ov[c]:.0f}%", fontsize=9, color=INK)
ax.set_yticks(yy, [short(x, 36) for x in fs.topic])
ax.set_xlabel("% of the area's Main and Findings papers that are in Findings")
ax.legend(frameon=False, loc="lower right")
grid_x(ax)
hi_ = fs.iloc[-1]
frame(fig, f"{short(hi_.topic, 36)} has the largest Findings share: {hi_[f'findings_share_{c}']:.0f}%",
      f"Findings papers as a share of each area's Main and Findings papers. Grey dot: {PREV}. Orange dot: {CUR}.")
save(fig, "findings_share_by_area.png")

# ================= 9. presentation (current year, from the program) =================
SCH = S.get("schedule") or {}
if SCH.get("schedule_available"):
    PRES = ["oral", "poster", "demo", "virtual", "not presenting"]
    m = pd.DataFrame(SCH["pres_mix_by_area"])
    m["in_person"] = m[["oral", "poster", "demo"]].sum(axis=1)
    m = m.sort_values("in_person")
    fig, ax = plt.subplots(figsize=(11, max(6, 0.45 * len(m) + 2.2)))
    fig.subplots_adjust(top=0.85, bottom=0.14, left=0.28, right=0.97)
    left = np.zeros(len(m))
    for k in PRES:
        ax.barh(np.arange(len(m)), m[k], left=left, color=PRES_COL[k], label=PRES_LAB[k], height=0.7)
        left += m[k].to_numpy()
    ax.set_yticks(np.arange(len(m)), [short(x, 36) for x in m.topic])
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of the area's papers in the program")
    ax.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.45, -0.07), fontsize=10)
    po = SCH["pres_overall_pct"]
    inp = po.get("oral", 0) + po.get("poster", 0) + po.get("demo", 0)
    frame(fig, f"{inp:.0f}% of the papers in the program are presented in person",
          f"How each area's papers are presented at EMNLP {CUR}, from the conference program. Findings papers may choose "
          "not to present.\nOrals and posters given online count as virtual.")
    save(fig, "presentation_mix.png")

    if SCH.get("oral_rate_by_area"):
        r = pd.DataFrame(SCH["oral_rate_by_area"]).sort_values("rate_pct")
        avg = SCH["oral_rate_overall_pct"]
        p0 = avg / 100
        band = 200 * np.sqrt(p0 * (1 - p0) / r.papers)  # 2 standard errors, in percent
        cols = [ACC if x - avg > s_ else (COOL if avg - x > s_ else GREY) for x, s_ in zip(r.rate_pct, band)]
        fig, ax = plt.subplots(figsize=(10, max(6, 0.45 * len(r) + 2)))
        fig.subplots_adjust(top=0.86, bottom=0.1, left=0.3, right=0.95)
        lbl = [short(x, 36) for x in r.topic]
        ax.hlines(lbl, 0, r.rate_pct, color="#d5d9e2", lw=2)
        ax.scatter(r.rate_pct, lbl, s=70, color=cols, zorder=3)
        ax.axvline(avg, color=INK, ls="--", lw=1)
        ax.text(avg + 0.15, len(r) - 0.6, f"conference average {avg:.1f}%", fontsize=9, color=INK)
        ax.set_xlabel("% of the area's Main and Industry papers given an in-person oral")
        grid_x(ax)
        frame(fig, f"{short(r.iloc[-1].topic, 36)} papers get the most orals",
              "Share of each area's Main and Industry papers in the program given an in-person oral. Grey means the gap could be chance.")
        save(fig, "oral_rate_by_area.png")

    if SCH.get("papers_per_day"):
        dd = pd.DataFrame(SCH["papers_per_day"])
        fig, ax = plt.subplots(figsize=(9, 5.5))
        fig.subplots_adjust(top=0.8, bottom=0.2, left=0.1, right=0.95)
        bottom = np.zeros(len(dd))
        for k in PRES:
            if k in dd and dd[k].sum():
                ax.bar(dd.day, dd[k], bottom=bottom, color=PRES_COL[k], label=PRES_LAB[k], width=0.6)
                bottom += dd[k].to_numpy()
        for i, n in enumerate(dd.papers):
            ax.text(i, n + dd.papers.max() * 0.015, f"{n:,}", ha="center", fontsize=9.5, color=INK)
        ax.set_ylabel("papers")
        ax.grid(axis="y", color="#e6e8ee", lw=0.8); ax.set_axisbelow(True)
        ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=10)
        busy = dd.loc[dd.papers.idxmax()]
        frame(fig, f"{busy.day} is the busiest day, with {busy.papers:,} papers",
              f"Papers with a slot on each day of EMNLP {CUR}, from the conference program.")
        save(fig, "papers_per_day.png")
else:
    print("no program data for", CUR, "- skipped presentation_mix, oral_rate_by_area, papers_per_day")

print("wrote", len(written), "figures to", FIG, ":", ", ".join(written))
