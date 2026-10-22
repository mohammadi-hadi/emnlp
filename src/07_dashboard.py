"""Interactive charts (Plotly) for the web version, written as standalone pages into DOCS/charts/:
treemap.html (topic treemap coloured by growth since last year), areas_dumbbell.html (area shares),
findings_mix.html (Main vs Findings per area), vocabulary.html, countries.html and, when the program is
known, presentation_mix.html (oral, poster, virtual... per area). Run 05_stats.py first."""
import json, re
import numpy as np
import pandas as pd
from config import CUR, PREV, P, OUT, DOCS
from common import load_papers
from site_template import treemap_page, treemap_figure, area_list
import plotly.graph_objects as go
import plotly.express as px

(DOCS / "charts").mkdir(parents=True, exist_ok=True)
INK, ACUR, APREV = "#1f2a44", "#d9480f", "#8aa1b1"
FONT = dict(family="Inter, system-ui, sans-serif", size=13, color=INK)
PRES_COL = {"oral": "#c92a2a", "poster": "#f08c00", "virtual": "#7048e8", "demo": "#2b8a3e", "not presenting": "#adb5bd"}
PRES_LAB = {"oral": "Oral", "poster": "Poster", "virtual": "Virtual", "demo": "Demo", "not presenting": "Not presented"}

df = load_papers()
L = json.load(open(P / "labels.json"))
S = json.load(open(OUT / "stats.json"))
c, p = str(CUR), str(PREV)


def short(name, n=44):
    """Drops the 'Area 3: ' prefix of provisional labels and cuts long names."""
    s = re.sub(r"^Area \d+:\s*", "", str(name)).strip()
    return s if len(s) <= n else s[:n - 1].rstrip(" ·,") + "…"


fine_name = {int(k): v["name"] for k, v in L["fine"].items()}
fine_line = {int(k): v.get("one_line", "") for k, v in L["fine"].items()}
broad_name = {int(k): short(v["name"]) for k, v in L["broad"].items()}
dc, dp = df[df.year == CUR], df[df.year == PREV]
sched = S["schedule"].get("schedule_available", False)


def save(fig, name, height=600):
    fig.update_layout(font=FONT, height=height, margin=dict(l=10, r=10, t=60, b=10),
                      paper_bgcolor="white", plot_bgcolor="white")
    # working charts, not part of the site: only the topics page (treemap.html) is published
    (OUT / "charts").mkdir(exist_ok=True)
    fig.write_html(OUT / "charts" / f"{name}.html", include_plotlyjs="cdn", full_html=True,
                   config={"displaylogo": False, "responsive": True})


# 1. treemap: area -> topic, size = papers this year, colour = change in share since last year
fine = pd.read_csv(OUT / "topics_fine.csv", index_col=0)
fine = fine[fine[f"n_{c}"] > 0]
t = pd.DataFrame({"fine": fine.index, "papers": fine[f"n_{c}"].values,
                  "share_cur": fine[f"share_{c}"].values, "share_prev": fine[f"share_{p}"].values})
t["growth"] = np.log2((t.share_cur + 0.05) / (t.share_prev + 0.05))
t["area"] = fine["broad"].map(broad_name).values
t["topic"] = t.fine.map(fine_name)
t["about"] = t.fine.map(fine_line).fillna("")
tracks = pd.crosstab(dc.fine, dc.track)
t["tracks"] = t.fine.map(lambda f: " · ".join(f"{k} {int(tracks.loc[f, k])}" for k in ["Main", "Findings", "Industry", "Demo"]
                                              if k in tracks and tracks.loc[f, k] > 0))
oral = dc["pres_type"].fillna("").str.lower().eq("oral") & dc["mode"].fillna("").str.lower().ne("virtual")
t["orals"] = t.fine.map(dc[oral].groupby("fine").size()).fillna(0).astype(int)
t["label"] = t.topic
TRK = ["Main", "Findings", "Industry", "Demo"]
fmt_tracks = lambda row: " · ".join(f"{k} {int(row[k])}" for k in TRK if k in row and row[k] > 0)
t["info"] = [x + (f"<br>orals: {o}" if sched else "") + (f"<br><i>{a}</i>" if a else "")
             for x, o, a in zip(t.tracks, t.orals, t.about)]
by_area = pd.crosstab(dc.fine.map(dict(zip(t.fine, t.area))), dc.track)
area_orals = t.groupby("area").orals.sum()
fig = treemap_figure(t, f"EMNLP {CUR}", c, p, {a: fmt_tracks(by_area.loc[a]) + (f"<br>orals: {area_orals[a]}" if sched else "")
                                                for a in t.area.unique()})
fig.update_layout(font=FONT, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="white")
LEDE = (f"All {len(dc):,} papers in {t.area.nunique()} areas and {len(t)} topics. Each box is an area, sized by its "
        f"number of papers. The colour shows how its share of the papers changed since {PREV}: red grew, blue shrank. "
        "Select an area to see its topics, and select the bar at the top to go back. Hover over or tap a topic for its numbers.")
(DOCS / "charts" / "treemap.html").write_text(treemap_page(fig, "EMNLP", LEDE, "https://mohammadi.cv/emnlp/2026/charts/treemap.html",
                                                                  area_list(t, p, c)))

# 2. dumbbell: area share last year -> this year
b = pd.DataFrame(S["broad"]).assign(topic=lambda x: x.topic.map(short)).sort_values(f"share_{c}")
fig = go.Figure()
for _, r in b.iterrows():
    fig.add_trace(go.Scatter(x=[r[f"share_{p}"], r[f"share_{c}"]], y=[r.topic, r.topic], mode="lines",
                             line=dict(color="#ced4da", width=3), showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=b[f"share_{p}"], y=b.topic, mode="markers", name=p, marker=dict(size=11, color=APREV),
                         hovertemplate="%{y}: %{x:.1f}% in " + p + "<extra></extra>"))
fig.add_trace(go.Scatter(x=b[f"share_{c}"], y=b.topic, mode="markers", name=c, marker=dict(size=13, color=ACUR),
                         hovertemplate="%{y}: %{x:.1f}% in " + c + "<extra></extra>"))
fig.update_layout(title=f"Share of papers per research area, {p} → {c}", xaxis_title="% of papers",
                  legend=dict(orientation="h", y=1.05, x=0))
save(fig, "areas_dumbbell", 650)

# 3. Main vs Findings per area, both years
m = pd.DataFrame(S["findings_share_by_area"]).assign(topic=lambda x: x.topic.map(short)).sort_values(f"findings_share_{c}")
ov = S["findings_share_overall"]
fig = go.Figure([go.Bar(y=m.topic, x=m[f"findings_share_{p}"], name=p, orientation="h", marker_color=APREV,
                        customdata=m[[f"findings_{p}", f"main_{p}"]].values,
                        hovertemplate="%{y}<br>" + p + ": %{x:.1f}% Findings (%{customdata[0]:.0f} Findings, "
                                      "%{customdata[1]:.0f} Main)<extra></extra>"),
                 go.Bar(y=m.topic, x=m[f"findings_share_{c}"], name=c, orientation="h", marker_color=ACUR,
                        customdata=m[[f"findings_{c}", f"main_{c}"]].values,
                        hovertemplate="%{y}<br>" + c + ": %{x:.1f}% Findings (%{customdata[0]:.0f} Findings, "
                                      "%{customdata[1]:.0f} Main)<extra></extra>")])
fig.add_vline(x=ov[c], line=dict(color=INK, width=1, dash="dot"),
              annotation_text=f"all areas {c}: {ov[c]:.0f}%", annotation_position="top")
fig.update_layout(barmode="group", title="How much of each area appears in Findings rather than the main conference",
                  xaxis=dict(title="Findings papers as % of the area's Main + Findings papers",
                             range=[0, min(100, 10 + m[[f"findings_share_{p}", f"findings_share_{c}"]].max().max())]),
                  legend=dict(orientation="h", y=1.05, x=0))
save(fig, "findings_mix", 700)

# 4. presentation mix per area (only when the program is known)
if sched:
    x = pd.DataFrame(S["schedule"]["pres_mix_by_area"]).assign(topic=lambda x: x.topic.map(short)).sort_values("oral")
    fig = go.Figure()
    for k in PRES_COL:
        fig.add_trace(go.Bar(y=x.topic, x=x[k], name=PRES_LAB[k], orientation="h", marker_color=PRES_COL[k],
                             customdata=x[["papers"]].values,
                             hovertemplate="%{y}<br>" + PRES_LAB[k] + ": %{x:.1f}% of %{customdata[0]} papers<extra></extra>"))
    fig.update_layout(barmode="stack", title=f"How each area's papers are presented at EMNLP {CUR}",
                      xaxis=dict(title="% of the area's papers in the program", range=[0, 100]),
                      legend=dict(orientation="h", y=1.05, x=0, traceorder="normal"))
    save(fig, "presentation_mix", 680)
else:
    (DOCS / "charts" / "presentation_mix.html").unlink(missing_ok=True)

# 5. vocabulary
v = pd.DataFrame(S["vocabulary"]).sort_values("delta_pp")
fig = go.Figure(go.Bar(y=v.term, x=v.delta_pp, orientation="h",
                       marker_color=[ACUR if d > 0 else APREV for d in v.delta_pp],
                       customdata=np.stack([v[f"pct_{p}"], v[f"pct_{c}"]], axis=1),
                       hovertemplate="<b>%{y}</b><br>%{customdata[0]:.1f}% → %{customdata[1]:.1f}% of papers<extra></extra>"))
fig.update_layout(title=f"What titles and abstracts mention more (and less) than in {PREV}",
                  xaxis_title="change in % of papers (percentage points)")
save(fig, "vocabulary", 700)

# 6. countries
ccur = {k: s for k, _, s in S[f"countries_{c}"]}
cprev = {k: s for k, _, s in S[f"countries_{p}"]}
cs = [k for k, _, _ in S[f"countries_{c}"][:15]][::-1]
fig = go.Figure([go.Bar(y=cs, x=[cprev.get(k, 0) for k in cs], name=p, orientation="h", marker_color=APREV),
                 go.Bar(y=cs, x=[ccur.get(k, 0) for k in cs], name=c, orientation="h", marker_color=ACUR)])
fig.update_layout(barmode="group", title="Countries behind the papers",
                  xaxis_title="% of papers (with a known country) with an author there",
                  legend=dict(orientation="h", y=1.05, x=0))
save(fig, "countries", 650)

t.drop(columns=["label", "info"]).sort_values("papers", ascending=False).to_csv(OUT / "topics_treemap_data.csv", index=False)
print("charts written to", DOCS / "charts", "| presentation mix:", "yes" if sched else "no program data")
