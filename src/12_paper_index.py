"""papers.html: a searchable list of every EMNLP paper of the current edition, with its ACL Anthology page,
PDF, track, area, topic and, for 2026, room, day and time in Budapest. Also writes papers_index.csv."""
import json
import pandas as pd
from config import CUR, P, OUT, DOCS
from common import load_papers, anthology_pages_live
from site_template import page as site_page, atlas_nav

L = json.load(open(P / "labels.json"))
fine_name = {int(k): v["name"] for k, v in L["fine"].items()}
broad_name = {int(k): v["name"] for k, v in L["broad"].items()}


def short_authors(a, n=180):
    """Cuts a long author list at a name, not in the middle of one."""
    names = [x.strip() for x in str(a).replace(";", ",").split(",") if x.strip()]
    out = []
    for x in names:
        if len(", ".join(out + [x])) > n and len(names) - len(out) > 1: return ", ".join(out) + f" and {len(names) - len(out)} more"
        out.append(x)
    return ", ".join(out)

d = load_papers()
d = d[d.year == CUR].copy()
date = pd.to_datetime(d["date"], errors="coerce")
d["when"] = [f"{x.strftime('%a %-d %b')} {s}".strip() if not pd.isna(x) else "" for x, s in zip(date, d["start"])]
PRES = {"oral": "Oral", "poster": "Poster", "virtual": "Virtual", "demo": "Demo", "not presenting": "Not presented in person"}
d["pres"] = d["pres_type"].str.lower().map(PRES).fillna("")
d.loc[d["mode"].eq("virtual") & d["pres"].isin(["Oral", "Poster"]), "pres"] = "Virtual"
d["area"] = d["broad"].map(broad_name)
d["topic"] = d["fine"].map(fine_name)
cols = ["title_display", "authors", "track", "area", "topic", "pres", "room", "when", "anthology", "pdf"]
idx = d[cols].rename(columns={"title_display": "title"}).fillna("")
idx = idx.iloc[idx["title"].str.replace(r"^[^0-9A-Za-z]+", "", regex=True).str.lower().argsort(kind="stable")]  # "(How)..." sorts under H
idx.to_csv(OUT / "papers_index.csv", index=False)

full = lambda a: ", ".join(x.strip() for x in str(a).replace(";", ",").split(",") if x.strip())
rows = [[r.title, short_authors(r.authors), r.track, r.area, r.topic, r.pres, r.room, r.when, r.anthology.rstrip("/").rsplit("/", 1)[-1],
         full(r.authors) if short_authors(r.authors) != full(r.authors) else ""]
        for r in idx.itertuples()]
opts = lambda col: "".join(f"<option>{a}</option>" for a in sorted((x for x in idx[col].unique() if x), key=str.casefold))

CSS = """<style>
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}
.controls input,.controls select{font:inherit;font-size:var(--step--1);padding:8px 10px;border:1px solid var(--rule);border-radius:8px;background:var(--surface);color:var(--ink)}
.controls input{flex:1;min-width:220px}
@media (max-width:560px){.controls input,.controls select{flex:1 1 100%;min-width:0}}
.p .a{display:flex;flex-wrap:wrap;gap:4px 0;align-items:center}
.p .when{display:block;flex-basis:100%}
.p{border-bottom:1px solid var(--rule);padding:12px 0}.p .t{font-weight:600;line-height:1.4}
.p .m,.meta{color:var(--ink-3);font-size:var(--step--1)}.p .a{font-size:var(--step--1);margin-top:4px}
.p .a a{margin-right:14px;font-weight:500}
.tag{display:inline-block;font-family:var(--mono);font-size:.7rem;padding:1px 7px;border-radius:10px;background:var(--paper-deep);margin-right:6px}
.tag.o{background:var(--accent);color:#fff}
#more{margin-top:16px}
</style>"""
BODY = """__NAV__<main id="main"><article class="post"><header class="post-head"><div class="post-wrap wide">
<p class="post-crumbs"><a href="/blog/">Blog</a><span class="sep">/</span><a href="../">EMNLP Atlas</a><span class="sep">/</span><a href="index.html">__Y__</a></p>
<h1>All __N__ EMNLP __Y__ papers</h1>
<p>Search by title or author, or filter by track, area and how the paper is presented. Each paper links to its ACL Anthology page, its PDF and an arXiv search. Times are Budapest time.</p>
<div class="controls"><input id="q" type="search" placeholder="Search title or author…" aria-label="search">
<select id="track" aria-label="track"><option value="">All tracks</option>__TRACKS__</select>
<select id="area" aria-label="area"><option value="">All areas</option>__AREAS__</select>
<select id="pres" aria-label="presentation"><option value="">Any presentation</option>__PRES__</select></div>
<div id="count" class="meta"></div><div id="list"></div><button id="more" class="btn" type="button">Show more</button>
</div></header></article></main>
<script>
const D = __DATA__;
const norm = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/[’‘`]/g, "'").toLowerCase();
// search text: title, all authors (also the ones the card hides behind "and N more"), without accents
const KEY = D.map(r => norm(r[0] + ' ' + r[1] + ' ' + (r[9] || '')).replace(/\\s+/g, ' '));
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let shown = 0, hits = [];
function filter() {
  const q = document.getElementById('q').value, t = document.getElementById('track').value,
        a = document.getElementById('area').value, p = document.getElementById('pres').value;
  // the exact phrase first (so a shared link for a name shows only that person); if nothing has it, every word in any order
  const nq = norm(q).trim().replace(/\\s+/g, ' '), words = nq.split(' ').filter(Boolean);
  const phrase = nq && KEY.some(k => k.includes(nq));
  const match = i => !nq || (phrase ? KEY[i].includes(nq) : words.every(w => KEY[i].includes(w)));
  hits = D.filter((r, i) => match(i) && (!t || r[2] === t) && (!a || r[3] === a) && (!p || r[5] === p));
  shown = 0; document.getElementById('list').innerHTML = ''; more();
}
function more() {
  const html = hits.slice(shown, shown + 100).map(r => {
    const tag = r[5] === 'Oral' ? '<span class="tag o">Oral</span>' : '';
    // orals show their room as 'Room F8'; posters already say 'Poster · Hall H'
    const room = r[5] === 'Oral' && r[6] ? 'Room ' + r[6] : r[6];
    const where = [r[5] !== 'Oral' ? r[5] : '', room, r[7]].filter(Boolean).join(' · ') || 'Time not published';
    const ax = 'https://arxiv.org/search/?query=' + encodeURIComponent(r[0].replace(/[’‘]/g, "'").replace(/[^\\w\\s'-]/g, ' ')).replace(/%20/g, '+') + '&searchtype=title';
    const links = `<a href="https://aclanthology.org/${r[8]}.pdf" target="_blank" rel="noopener">PDF</a>` +
      (__ANTH_PAGES__ ? `<a href="https://aclanthology.org/${r[8]}/" target="_blank" rel="noopener">ACL Anthology</a>` : '') +
      `<a href="${ax}" target="_blank" rel="noopener">Search arXiv</a>`;
    return `<div class="p"><div class="t">${tag}${esc(r[0])}</div><div class="m">${esc(r[1])}</div>` +
      `<div class="a"><span class="tag">${esc(r[2])}</span><span class="tag">${esc(r[3])}</span><span class="when">${esc(where)}</span></div><div class="a">${links}</div></div>`;
  }).join('');
  document.getElementById('list').insertAdjacentHTML('beforeend', html);
  shown += 100;
  const n = hits.length;
  document.getElementById('count').textContent = n === 0 ? 'No papers match. Try fewer words or clear the filters.' :
    `${n.toLocaleString()} ${n === 1 ? 'paper' : 'papers'}` + (n > shown ? ` · showing the first ${shown.toLocaleString()}` : '');
  const btn = document.getElementById('more');
  btn.textContent = `Show ${Math.min(100, n - shown)} more`;
  btn.style.display = shown < n ? 'inline-block' : 'none';
}
['q', 'track', 'area', 'pres'].forEach(id => document.getElementById(id).addEventListener('input', filter));
document.getElementById('more').addEventListener('click', more);
const params = new URLSearchParams(location.search); if (params.get('q')) document.getElementById('q').value = params.get('q');
filter();
</script>"""
body = (BODY.replace("__NAV__", atlas_nav("", "papers.html")).replace("__ANTH_PAGES__", "true" if anthology_pages_live(CUR) else "false").replace("__N__", f"{len(rows):,}").replace("__Y__", str(CUR))
        .replace("__TRACKS__", opts("track")).replace("__AREAS__", opts("area")).replace("__PRES__", opts("pres"))
        .replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":"))))
(DOCS / "papers.html").write_text(site_page(
    f"All EMNLP {CUR} papers", f"Search all {len(rows):,} EMNLP {CUR} papers and find their links.",
    f"https://mohammadi.cv/emnlp/{CUR}/papers.html", body, extra_head=CSS))
print("wrote papers.html,", len(rows), "papers")
