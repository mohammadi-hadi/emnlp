"""LinkedIn carousel for the EMNLP atlas: six social cards, 1080x1350, large type, ported from the NeurIPS atlas.

Writes OUT/carousel/1_cover.png ... 6_explore.png and private/linkedin_carousel.pdf (private/ is gitignored).
Every number comes from stats.json or the paper table. The cards are drawn fresh at card size, not shrunk blog
figures, so the text stays readable on a phone. Run 05_stats.py (and 10_story_figures.py for the blog) first.
"""
import json
from datetime import date
import numpy as np
import pandas as pd
from PIL import Image
from config import CUR, PREV, P, OUT, ROOT
from common import load_papers
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe
from scipy.ndimage import gaussian_filter

CAR, PRIV = OUT / "carousel", ROOT / "private"
CAR.mkdir(parents=True, exist_ok=True)
PRIV.mkdir(parents=True, exist_ok=True)

INK, MUTED, ACC, COOL, GREY, BG = "#1f2a44", "#6b7489", "#d9480f", "#3b5bdb", "#b8bfcc", "#fbfaf7"
plt.rcParams.update({"font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#c9ced8",
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
                     "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG})
URL = f"mohammadi.cv/emnlp/{CUR}"
REPO = "github.com/mohammadi-hadi/emnlp"
CITY = "Budapest"
AUTHOR = "Hadi Mohammadi"

df = load_papers()
L = json.load(open(P / "labels.json"))
S = json.load(open(OUT / "stats.json"))
broad_name = {int(k): v["name"] for k, v in L["broad"].items()}
dc = df[df.year == CUR]
c, p = str(CUR), str(PREV)
n_cur, n_prev = S[f"n_{c}"], S[f"n_{p}"]


def outline(t, w=3):
    t.set_path_effects([pe.withStroke(linewidth=w, foreground=BG)])


def pct(x):
    return f"{x:.0f}%"


# ---------------- card frame, as in the NeurIPS atlas ----------------
W, H = 5.4, 6.75  # inches at 200 dpi = 1080 x 1350


def card(name, kicker, big, line, draw, box, footer=True, big_fs=26):
    fig = plt.figure(figsize=(W, H), dpi=200)
    fig.patch.set_facecolor(BG)
    fig.text(0.07, 0.945, kicker, fontsize=11, color=ACC, fontweight="bold", va="top")
    t = fig.text(0.07, 0.895, big, fontsize=big_fs, color=INK, fontweight="bold", va="top", linespacing=1.05)
    fig.canvas.draw()
    bottom = t.get_window_extent().transformed(fig.transFigure.inverted()).y0
    if line:
        t = fig.text(0.07, bottom - 0.025, line, fontsize=12.5, color=INK, va="top", linespacing=1.3)
        fig.canvas.draw()
        bottom = t.get_window_extent().transformed(fig.transFigure.inverted()).y0
    fig.text_bottom = bottom
    draw(fig, box)
    if footer:
        fig.text(0.07, 0.035, f"{AUTHOR} · {URL}", fontsize=9.5, color=MUTED)
    with plt.rc_context({"savefig.bbox": "standard"}):
        fig.savefig(CAR / name, dpi=200, facecolor=BG)
    plt.close(fig)
    written.append(CAR / name)


written = []

# ---------------- shared map geometry ----------------
xmin, xmax = dc.x.quantile([0.002, 0.998]); ymin, ymax = dc.y.quantile([0.002, 0.998])
pad = 0.06 * max(xmax - xmin, ymax - ymin)
ext = [xmin - pad, xmax + pad, ymin - pad, ymax + pad]
med = dc.groupby("broad")[["x", "y"]].median()


def map_axes(fig, box):
    """Axes whose data aspect matches the map, centred in box."""
    bw, bh = box[2] * W, box[3] * H
    aspect = (ext[3] - ext[2]) / (ext[1] - ext[0])
    w, h = (bw, bw * aspect) if bw * aspect <= bh else (bh / aspect, bh)
    ax = fig.add_axes([box[0] + (box[2] - w / W) / 2, box[1] + (box[3] - h / H) / 2, w / W, h / H])
    ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:]); ax.axis("off")
    return ax


def label_areas(ax, names, fs, w=4):
    """Large outlined labels at the median of each area, pushed apart vertically if they would collide."""
    ids = [b for b in med.index if b in names]
    pos = med.loc[ids].astype(float)
    bb = ax.get_position()
    ux = (ext[1] - ext[0]) / (bb.width * W * 72)   # data units per point
    uy = (ext[3] - ext[2]) / (bb.height * H * 72)
    wid = {b: 0.58 * fs * len(names[b]) * ux for b in ids}
    hgt = 1.4 * fs * uy
    for _ in range(400):
        moved = False
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                i, j = ids[a], ids[b]
                ddx, ddy = pos.at[j, "x"] - pos.at[i, "x"], pos.at[j, "y"] - pos.at[i, "y"]
                if abs(ddy) < hgt and abs(ddx) < (wid[i] + wid[j]) / 2:
                    s = 0.1 * hgt if ddy >= 0 else -0.1 * hgt
                    pos.at[j, "y"] += s; pos.at[i, "y"] -= s; moved = True
        if not moved:
            break
    for b, r in pos.iterrows():  # keep labels inside the map
        half = wid[b] / 2
        x = min(max(r.x, ext[0] + half), ext[1] - half)
        outline(ax.text(x, r.y, names[b], ha="center", va="center", fontsize=fs, color=INK, fontweight="bold"), w)


def area_id(word):
    return next(k for k, v in broad_name.items() if v == word)


# ================= 1. cover: the map =================
days = S["schedule"]["papers_per_day"]
d0, d1 = date.fromisoformat(days[0]["iso"]), date.fromisoformat(days[-1]["iso"])
when = (f"{d0.day} to {d1.day} {d1:%B %Y}" if (d0.month, d0.year) == (d1.month, d1.year)
        else f"{d0.day} {d0:%B} to {d1.day} {d1:%B %Y}")

COVER_NAMES = {area_id("LLM Agents"): "LLM Agents",
               area_id("Vision-Language Models"): "Vision-Language",
               area_id("Speech & Audio Models"): "Speech & Audio",
               area_id("Retrieval & Structured Knowledge"): "Retrieval",
               area_id("Linguistics, Multilinguality & Translation"): "Translation",
               area_id("Reasoning & Reinforcement Learning"): "Reasoning & RL",
               area_id("Efficient LLMs & Decoding"): "Efficient LLMs",
               area_id("Medical & Clinical NLP"): "Medical NLP"}


def draw_cover(fig, box):
    ax = map_axes(fig, box)
    pal = plt.get_cmap("tab20")
    ax.scatter(dc.x, dc.y, s=2.6, c=[pal(int(b) % 20) for b in dc.broad], alpha=0.85, linewidths=0)
    label_areas(ax, COVER_NAMES, 13)
    fig.text(0.07, 0.035, f"{AUTHOR} · {CITY} · {when}", fontsize=9.5, color=MUTED)


card("1_cover.png", "Paper atlas", f"EMNLP {CUR}\non one map",
     f"All {n_cur:,} papers, and what changed since {PREV}", draw_cover, (0.0, 0.065, 1.0, 0.65), footer=False)

# ================= 2. agents =================
A = S["agents"]
ks_p, ks_c = A["keyword_share"][p], A["keyword_share"][c]
frac = {2: "One in two", 3: "One in three", 4: "One in four", 5: "One in five"}
k = round(100 / ks_c)
assert k in frac and abs(100 / k - ks_c) < 1.5, f"agent share {ks_c} is not close to one in k"
AGENT_MIN = 75  # topics where at least this % of the current papers mention agents
fam = [f for f in A["family"] if f["keyword_share_cur"] >= AGENT_MIN][:8]
AGENT_SHORT = {
    "Agent Benchmarks and Failure Diagnosis": "Agent benchmarks", "Long-Term Memory for Agents": "Memory",
    "Long-Horizon Agents and World Models": "Long-horizon agents", "Deep Research and Search Agents": "Deep research",
    "Multi-Agent Collaboration and Communication": "Multi-agent teams", "Tool Use and Function Calling Agents": "Tool use",
    "Agent Skill Libraries and Skill Evolution": "Skill libraries", "Agent Safety and Tool-Use Risks": "Agent safety",
    "Coding Agents for Software Engineering": "Coding agents", "GUI Agent Benchmarks and Simulators": "GUI agents"}


def draw_agents(fig, box):
    t = fig.text(0.07, fig.text_bottom - 0.03, f"{pct(ks_p)} → {pct(ks_c)}", fontsize=34, color=ACC,
                 fontweight="bold", va="top")
    fig.canvas.draw()
    y0 = t.get_window_extent().transformed(fig.transFigure.inverted()).y0
    fig.text(0.07, y0 - 0.012, f"of all papers mention agents ({PREV} → {CUR})", fontsize=12, color=MUTED, va="top")
    ax = fig.add_axes([box[0] + 0.33, box[1], box[2] - 0.5, box[3]])
    a_p = np.array([f[f"n_{p}"] for f in fam]); a_c = np.array([f[f"n_{c}"] for f in fam])
    yy = np.arange(len(fam))[::-1]
    ax.hlines(yy, a_p, a_c, color=ACC, lw=3, alpha=0.5)
    ax.scatter(a_p, yy, s=60, color=GREY, zorder=3)
    ax.scatter(a_c, yy, s=80, color=ACC, zorder=4)
    for y_, a_, b_ in zip(yy, a_p, a_c):
        ax.annotate(f"{a_} → {b_}", (b_, y_), xytext=(7, 0), textcoords="offset points", va="center",
                    fontsize=11.5, color=INK, annotation_clip=False)
    ax.set_yticks(yy, [AGENT_SHORT.get(f["topic"], f["topic"]) for f in fam], fontsize=12.5)
    ax.set_xlim(0, a_c.max() * 1.05)
    ax.tick_params(axis="x", labelsize=10.5)
    ax.set_xlabel(f"papers per agent topic (grey {PREV}, orange {CUR})", fontsize=10.5, x=0.4)
    ax.grid(axis="x", color="#e6e8ee", lw=0.8); ax.set_axisbelow(True)


card("2_agents.png", "Biggest shift", f"{frac[k]} papers now\nmentions agents", "", draw_agents,
     (0.05, 0.135, 0.9, 0.39))

# ================= 3. where the field moved =================
shc = dc.fine.value_counts(normalize=True)
shp = df[df.year == PREV].fine.value_counts(normalize=True).reindex(shc.index, fill_value=0)
grow = np.log2((shc + 0.0005) / (shp + 0.0005)).clip(-1.5, 1.5)
bins, sig = 600, 7.0  # finer grid than the blog figure, same smoothing radius in map units
rng = [ext[:2], ext[2:]]
cnt = gaussian_filter(np.histogram2d(dc.x, dc.y, bins=bins, range=rng)[0], sig)
wsum = gaussian_filter(np.histogram2d(dc.x, dc.y, bins=bins, range=rng, weights=dc.fine.map(grow))[0], sig)
val = wsum / np.maximum(cnt, 1e-9)
rgba = plt.get_cmap("RdBu_r")(plt.Normalize(-1.2, 1.2)(val))
thr = 0.02  # same density cut-off as the blog figure (0.08 at 300 bins), with a soft edge instead of a hard one
rgba[..., 3] = np.clip((cnt - thr * 0.5) / (thr * 1.5), 0, 1)

FIELD_NAMES = {area_id("LLM Agents"): "Agents",
               area_id("Long-Term Agent Memory"): "Agent memory",
               area_id("Reasoning & Reinforcement Learning"): "Reasoning & RL",
               area_id("Linguistics, Multilinguality & Translation"): "Translation",
               area_id("Fine-Tuning & Preference Alignment"): "Fine-tuning",
               area_id("Retrieval & Structured Knowledge"): "Retrieval"}


def draw_field(fig, box):
    ax = map_axes(fig, box)
    ax.imshow(np.transpose(rgba, (1, 0, 2)), origin="lower", extent=ext, interpolation="bilinear", aspect="auto")
    label_areas(ax, FIELD_NAMES, 13)
    cax = fig.add_axes([0.2, 0.125, 0.6, 0.014])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap="RdBu_r", norm=plt.Normalize(-1.2, 1.2)), cax=cax, orientation="horizontal")
    cb.set_ticks([-1, 0, 1]); cb.set_ticklabels(["half the share", "same", "double the share"])
    cb.outline.set_visible(False); cax.tick_params(labelsize=10.5, colors=MUTED, length=0)


card("3_moved.png", "Where the field moved", "Red grew,\nblue shrank",
     f"The {CUR} map, coloured by how each\ntopic's share of papers changed since {PREV}.",
     draw_field, (0.0, 0.16, 1.0, 0.5))

# ================= 4. four numbers =================
grow_by_name = {g["topic"]: g for g in S["fine_growers"]}
mem = next(g for t, g in grow_by_name.items() if "Memory" in t and "Agent" in t)
rlvr = next(g for t, g in grow_by_name.items() if "RLVR" in t)
bench = next(v for v in S["vocabulary"] if v["term"] == "benchmark")


def draw_numbers(fig, box):
    cells = [
        (f"{n_prev:,} → {n_cur:,}", f"papers in total\n({S['growth_pct']:+.0f}% on {PREV})", ACC),
        (f"{mem[f'n_{p}']} → {mem[f'n_{c}']}", "papers on memory\nfor agents", ACC),
        (f"{rlvr[f'n_{p}']} → {rlvr[f'n_{c}']}", "papers on RL with\nverifiable rewards (RLVR)", INK),
        (pct(bench[f"pct_{c}"]), f"of papers say 'benchmark'\n(was {pct(bench[f'pct_{p}'])} in {PREV})", INK),
    ]
    for i, (big, small, col) in enumerate(cells):
        x = 0.07 + (i % 2) * 0.46
        y = box[1] + box[3] - (i // 2) * 0.27
        fig.text(x, y, big, fontsize=22, fontweight="bold", color=col, va="top")
        fig.text(x, y - 0.07, small, fontsize=11.5, color=MUTED, va="top", linespacing=1.3)


card("4_numbers.png", "What else changed", "Memory and RLVR\ntook off",
     f"Four more numbers from the comparison\nwith EMNLP {PREV}.", draw_numbers, (0.05, 0.1, 0.9, 0.5))

# ================= 5. countries =================
cc = {k_: x for k_, _, x in S[f"countries_{c}"]}; cp = {k_: x for k_, _, x in S[f"countries_{p}"]}
assert cc["China"] > cc["USA"] and cp["USA"] > cp["China"], "the China / US order did not flip"
cov = S["affiliation_coverage"][c]["papers_with_country_pct"]


def draw_countries(fig, box):
    ax = fig.add_axes(box)
    for k_, col, lab in [("China", ACC, "China"), ("USA", COOL, "US")]:
        ax.plot([0, 1], [cp[k_], cc[k_]], color=col, lw=4, solid_capstyle="round")
        ax.scatter([0, 1], [cp[k_], cc[k_]], color=col, s=110, zorder=3)
        ax.text(-0.06, cp[k_], f"{lab} {pct(cp[k_])}", ha="right", va="center", fontsize=15, color=col, fontweight="bold")
        ax.text(1.06, cc[k_], f"{pct(cc[k_])} {lab}", ha="left", va="center", fontsize=15, color=col, fontweight="bold")
    lo = min(cp["China"], cp["USA"], cc["China"], cc["USA"]); hi = max(cp["China"], cp["USA"], cc["China"], cc["USA"])
    ax.set_ylim(lo - 4, hi + 5)
    ax.set_xlim(-0.75, 1.75); ax.axis("off")
    for x_, yr in [(0, p), (1, c)]:
        ax.text(x_, hi + 3.2, yr, ha="center", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.07, box[1] - 0.04, f"Share of papers with at least one author from the country.\n"
             f"Affiliations matched for {pct(cov)} of {CUR} papers.", fontsize=10.5, color=MUTED, va="top",
             linespacing=1.3)


card("5_countries.png", "Who writes the papers", "China overtook\nthe US",
     f"More papers have an author in China ({pct(cc['China'])})\nthan in the US ({pct(cc['USA'])}). "
     "Last year it was\nthe other way round.", draw_countries, (0.07, 0.17, 0.86, 0.38))

# ================= 6. explore =================


def draw_explore(fig, box):
    img = np.asarray(Image.open(OUT / "figures" / "atlas_clusters.png").convert("RGB")).astype(int)
    inner = img[30:-30, 30:-30]  # skip the thin frame drawn around the figure
    bg = inner[5, 5]
    ys, xs = np.where(np.abs(inner - bg).sum(axis=2) > 24)
    m = 20
    crop = inner[max(ys.min() - m, 0):ys.max() + m, max(xs.min() - m, 0):xs.max() + m]
    bw, bh = box[2] * W, box[3] * H
    asp = crop.shape[0] / crop.shape[1]
    w, h = (bw, bw * asp) if bw * asp <= bh else (bh / asp, bh)
    ax = fig.add_axes([box[0] + (box[2] - w / W) / 2, box[1] + (box[3] - h / H) / 2, w / W, h / H])
    ax.imshow(crop.astype(np.uint8), interpolation="lanczos"); ax.axis("off")
    fig.text(0.5, 0.135, URL, fontsize=21, fontweight="bold", color=ACC, ha="center")
    fig.text(0.5, 0.085, f"Code and data: {REPO}", fontsize=11, color=INK, ha="center")
    fig.text(0.5, 0.05, f"Same method as the NeurIPS {CUR} map", fontsize=11, color=MUTED, ha="center")


card("6_explore.png", "Explore it yourself", "Find any paper's\nroom and time",
     f"Search all {n_cur:,} papers by title or author,\nor click a dot on the map.", draw_explore,
     (0.04, 0.19, 0.92, 0.46), footer=False)

# ================= PDF for LinkedIn, as for the NeurIPS carousel =================
for f in written:
    assert Image.open(f).size == (1080, 1350), f"{f.name} is not 1080x1350"
pages = [Image.open(f).convert("RGB") for f in written]
pdf = PRIV / "linkedin_carousel.pdf"
pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=200, quality=95)
print("wrote", len(written), "cards to", CAR, "and", pdf)
