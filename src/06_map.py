"""Interactive map of all EMNLP papers of the current edition (DataMapPlot), in the same style as the
NeurIPS atlas: recolour by area, change since last year, track, presentation and team size, filter by day."""
import json
import numpy as np
import pandas as pd
import datamapplot
from config import CUR, PREV, P, OUT, DOCS
from common import load_papers, anthology_pages_live

ANTH_PAGES = anthology_pages_live(CUR)
print('ACL Anthology paper pages live:', ANTH_PAGES)

df = load_papers()
labels = json.load(open(P / "labels.json"))
fine_name = {int(k): v["name"] for k, v in labels["fine"].items()}
broad_name = {int(k): v["name"] for k, v in labels["broad"].items()}

dc, dp = df[df.year == CUR], df[df.year == PREV]
shc = dc.fine.value_counts(normalize=True)
shp = dp.fine.value_counts(normalize=True).reindex(shc.index, fill_value=0)
growth = np.log2((shc + 0.0005) / (shp + 0.0005))

d = dc.reset_index(drop=True)
coords = d[["x", "y"]].to_numpy()
fine_lab = d["fine"].map(fine_name).to_numpy()
broad_lab = d["broad"].map(broad_name).to_numpy()

PRES = {"oral": "Oral", "poster": "Poster", "virtual": "Virtual", "demo": "Demo",
        "not presenting": "Not presented in person"}
pres = d["pres_type"].str.lower().map(PRES).fillna("Not in the program")
pres = np.where(d["mode"].eq("virtual") & pres.isin(["Oral", "Poster"]), "Virtual", pres)
date = pd.to_datetime(d["date"], errors="coerce")
# one word per label ("25-Sun"): the histogram shows only the first word and turned "Mon 26" into a date
day = np.where(date.notna(), date.dt.strftime("%d-%a"), "no-slot")
where = np.where(d["room"].ne(""), d["room"] + ", " + d["date"] + " " + d["start"], "")

g = d["fine"].map(growth).clip(-1.5, 1.5).to_numpy()
change_txt = [f"{fine_name[f]}: {100 * shp[f]:.2f}% → {100 * shc[f]:.2f}% of papers since {PREV}" for f in d["fine"]]
title = d["title_display"]
safe = title.str.replace(r"[`$\\]", "", regex=True)
extra = pd.DataFrame({
    "title": title, "safe_title": safe, "anthology": d["anthology"], "pdf": d["pdf"], "arxiv": d["arxiv"],
    "authors": d["authors"].str.slice(0, 160), "track": d["track"], "pres": pres, "where": where,
    "area": d["broad"].map(broad_name), "change": change_txt, "abstract": d["abstract"].str.slice(0, 420) + "…",
})
marker = np.where(pres == "Oral", 7, 2.5)
hover = (title + " — " + d["track"] + " · " + pres).to_numpy()

cmap_raw = [g, d["track"].to_numpy(), np.asarray(pres), np.log2(d["n_authors"].clip(1, 40)).to_numpy()]
cmap_meta = [
    {"field": "growth", "description": f"Change since {PREV} (red grew, blue shrank)", "cmap": "RdBu_r", "kind": "continuous"},
    {"field": "track", "description": "Main, Findings, industry or demo", "kind": "categorical",
     "color_mapping": {"Main": "#1e3a5f", "Findings": "#4dabf7", "Industry": "#e8590c", "Demo": "#2b8a3e"}},
    {"field": "pres", "description": "How it is presented", "kind": "categorical",
     "color_mapping": {"Oral": "#c92a2a", "Poster": "#f08c00", "Virtual": "#7048e8", "Demo": "#2b8a3e",
                       "Not presented in person": "#adb5bd", "Not in the program": "#e9ecef"}},
    {"field": "team", "description": "Number of authors", "cmap": "viridis", "kind": "continuous"},
]

CSS = """
#title-container{background:rgba(255,255,255,.94)!important;border-radius:10px;box-shadow:0 2px 12px rgba(31,42,68,.08);
  padding:14px 18px 13px!important;max-width:min(600px,calc(100vw - 48px));line-height:1.2!important}
#title-container br{display:none}
#main-title{display:block;font-family:"Source Serif 4",Georgia,serif!important;font-weight:600!important;font-size:30px!important;
  line-height:1.15!important;letter-spacing:-.01em;color:#1a1a1a!important;margin:0 0 6px;text-wrap:balance}
#title-container>span:not(#main-title){display:block;font-family:Inter,system-ui,sans-serif!important;font-size:14.5px!important;
  line-height:1.45!important;color:#444!important;text-wrap:pretty}
#paper-links{display:none;position:absolute;right:14px;bottom:60px;z-index:20;width:340px;background:#fff;
  border-radius:10px;box-shadow:0 6px 24px rgba(31,42,68,.18);padding:14px 16px;font:13px/1.4 Inter,system-ui,sans-serif;color:#1f2a44}
#paper-links .t{font-weight:700;margin:0 22px 10px 0}
#paper-links a{display:inline-block;margin:0 6px 6px 0;padding:6px 10px;border-radius:7px;background:#f1f3f5;color:#1f2a44;text-decoration:none;font-weight:600}
#paper-links a.main{background:#1e3a5f;color:#fff}
#paper-links .n{font-size:12px;color:#6b7489;margin:0 0 8px}
#paper-links .x{position:absolute;top:8px;right:10px;cursor:pointer;font-size:16px;color:#6b7489;border:0;background:none}
.embedded #topic-tree,.embedded #d3histogram-container,.embedded .atlas-back{display:none!important}
.embedded #title-container{display:none!important}
.atlas-back{position:absolute;bottom:14px;right:14px;z-index:10;font:600 13px Inter,system-ui,sans-serif;
  background:#1e3a5f;color:#fff;padding:8px 12px;border-radius:8px;text-decoration:none}
/* phones: placed last so these rules win over the ones above */
@media (max-width:768px){
  #main-title{font-size:21px!important;margin-bottom:4px}
  #title-container{padding:10px 12px!important}
  #title-container>span:not(#main-title){font-size:12.5px!important;line-height:1.4!important}
  .stack.top-left{max-height:44vh!important}
  #topic-tree{display:none!important}
  .stack.bottom-left{display:flex!important}  /* keep the colour menu on phones */
  #d3histogram-container{display:none!important}
  #colormap-selector-container{max-width:calc(100vw - 32px)!important;box-sizing:border-box}
  #colormap-selector-container .color-map-dropdown,#colormap-selector-container .color-map-selected{max-width:100%!important}
  .atlas-back{bottom:88px;right:12px;padding:7px 11px;font-size:12px}
  body:has(.color-map-options[style*="block"]) .atlas-back{visibility:hidden}  /* out of the way of the open menu */
  #paper-links{left:12px;right:12px;width:auto;bottom:132px}
}
"""
plot = datamapplot.create_interactive_plot(
    coords, fine_lab, broad_lab,  # finest layer first
    hover_text=hover,
    extra_point_data=extra,
    hover_text_html_template="""<div style="max-width:440px;font-family:Inter,system-ui,sans-serif">
<div style="font-weight:700;font-size:14px;line-height:1.3">{title}</div>
<div style="opacity:.7;font-size:12px;margin:2px 0 6px">{authors}</div>
<div style="font-size:12px"><b>{track}</b> · {pres} · <i>{area}</i></div>
<div style="font-size:12px;color:#d9480f;margin:2px 0 6px">{change}</div>
<div style="font-size:12px;opacity:.85">{abstract}</div>
<div style="font-size:11px;margin-top:6px;color:#1f2a44"><b>Click</b> for links to the paper.</div></div>""",
    on_click="showLinks(`{anthology}`, `{pdf}`, `{arxiv}`, `{safe_title}`, `{where}`)",
    marker_size_array=marker,
    title=f"EMNLP {CUR}: every paper on one map",
    sub_title=f"Each dot is one of the {len(d):,} papers. Similar papers sit close together. Big dots are orals. "
              f"Use the menu at the bottom left to colour by change since {PREV}, track or how a paper is presented.",
    enable_search=True,
    enable_topic_tree=True,
    colormap_rawdata=cmap_raw,
    colormap_metadata=cmap_meta,
    histogram_data=pd.Series(day),
    histogram_n_bins=10,
    histogram_settings={"histogram_title": "Day of the talk or poster. Click a bar to filter.",
                        "histogram_bin_unselected_fill_color": "#d0d7e2",
                        "histogram_bin_selected_fill_color": "#d9480f",
                        "histogram_width": 420, "histogram_height": 90},
    custom_css=CSS,
    custom_html='<a class="atlas-back" href="index.html">← Back to the story</a>'
                '<div id="paper-links"><button class="x" onclick="this.parentNode.style.display=\'none\'" '
                'aria-label="close">×</button><div class="t"></div><div class="n"></div><div class="l"></div></div>',
    custom_js="""
if (window.self !== window.top) {
  document.documentElement.classList.add('embedded');
}
function showLinks(page, pdf, arxiv, title, where) {
  const box = document.getElementById('paper-links');
  box.querySelector('.t').textContent = title;
  box.querySelector('.n').textContent = where ? 'In Budapest: ' + where : '';
  box.querySelector('.l').innerHTML =
    // PDF first: the Anthology serves the PDFs before its paper pages go live; the page link only once they are up
    '<a class="main" href="' + pdf + '" target="_blank" rel="noopener">PDF</a>' +
    (__ANTH_PAGES__ ? '<a href="' + page + '" target="_blank" rel="noopener">ACL Anthology</a>' : '') +
    '<a href="' + arxiv + '" target="_blank" rel="noopener">Find on arXiv</a>';
  box.style.display = 'block';
}
""".replace("__ANTH_PAGES__", "true" if ANTH_PAGES else "false"),
    darkmode=False,
    font_family="Inter",
    cluster_boundary_polygons=True,
    initial_zoom_fraction=0.95,
)
plot.save(str(DOCS / "atlas.html"))
page = (DOCS / "atlas.html").read_text().replace("apache-arrow@latest", "apache-arrow@21.2.0").replace("d3@latest", "d3@7")
FONT_LINK = '<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet" />'
anchor = '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />'
assert page.count(anchor) == 1
(DOCS / "atlas.html").write_text(page.replace(anchor, anchor + "\n" + FONT_LINK))
print("saved", DOCS / "atlas.html", len(d), "papers")

# still images: the story's hero preview (no title) and the share image (with title)
BG, INK, MUTED = "#fbfaf7", "#1f2a44", "#6b7489"
for name, title_txt in [("atlas_static.png", f"EMNLP {CUR} paper atlas"), ("atlas_clusters.png", None)]:
    kw = dict(title=title_txt, sub_title=f"{len(d):,} papers · {len(broad_name)} research areas · placed by what their abstracts say",
              title_keywords={"color": INK, "fontweight": "bold", "fontsize": 26},
              sub_title_keywords={"color": MUTED, "fontsize": 14}) if title_txt else {}
    fig, ax = datamapplot.create_plot(
        coords, broad_lab, label_font_size=12, label_wrap_width=14, use_medoids=True,
        font_family="Helvetica Neue", label_over_points=True, dynamic_label_size=True,
        figsize=(14, 14), dpi=150, darkmode=False, **kw)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    if title_txt:
        fig.text(0.01, 0.01, f"Data: ACL Anthology, EMNLP {CUR} · Analysis: Hadi Mohammadi · github.com/mohammadi-hadi/emnlp",
                 fontsize=10, color=MUTED)
    fig.savefig(OUT / "figures" / name, bbox_inches="tight", dpi=150, facecolor=BG)
