"""Build the GitHub Pages site in the style of mohammadi.cv: docs/index.html (landing page),
docs/<year>/index.html (story, from report/BLOG.md) and docs/<year>/appendix.html. Needs pandoc on PATH."""
import html, re, shutil, subprocess
from config import CUR, OUT, DOCS, REPORT
from site_template import page, atlas_nav

SITE = f"https://mohammadi.cv/emnlp/{CUR}/"
(DOCS / "figures").mkdir(parents=True, exist_ok=True)
for f in (OUT / "figures").glob("*.png"):
    shutil.copy(f, DOCS / "figures" / f.name)


def trimmed_preview(src, dst, pad=30):
    """The static map has a wide empty margin; cut it off so the preview shows the map large."""
    from PIL import Image, ImageChops
    im = Image.open(src).convert("RGB")
    inner = im.crop((20, 20, im.width - 20, im.height - 20))  # skip the thin frame line
    bg = Image.new("RGB", inner.size, inner.getpixel((5, 5)))
    box = ImageChops.difference(inner, bg).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
    l, t, r, b = box
    inner.crop((max(0, l - pad), max(0, t - pad), min(inner.width, r + pad), min(inner.height, b + pad))).save(dst)


trimmed_preview(DOCS / "figures" / "atlas_clusters.png", DOCS / "figures" / "atlas_preview.png")

HEIGHTS = {"treemap": 820, "vocabulary": 740}
HERO = ('</div><section class="container atlas-hero" aria-label="map of all papers">'
        '<div class="map-frame"><img class="map-preview" src="figures/atlas_preview.png" '
        f'alt="Map of all EMNLP {CUR} papers, coloured by research area">'
        '<button class="map-cover" type="button" onclick="openMap(this)"><span>Click to explore the map</span></button></div>'
        '<div class="actions"><a class="btn" href="atlas.html">Open the map full screen</a>'
        '<a class="btn btn-ghost" href="papers.html">Search all papers</a></div></section>'
        # the live map only loads on click; on small screens it opens full screen instead
        '<script>function openMap(b){if(window.innerWidth<900){location.href="atlas.html";return;}'
        f'b.parentNode.innerHTML=\'<iframe src="atlas.html" title="Map of all EMNLP {CUR} papers"></iframe>\';}}</script>'
        '<div class="post-wrap">')


PHONE_LABELS = {"2026": "Papers", "★": "Orals and spotlights"}


def label_cells(body):
    """Gives each number cell of a table its column name, so on a phone a row can be shown as a card."""
    def table(m):
        heads = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", m.group(0), re.S)]
        def row(r):
            cells = iter(range(10**6))
            return re.sub(r"<td>", lambda _: (lambda i: f'<td data-label="{html.escape(PHONE_LABELS.get(heads[i], heads[i][:1].upper() + heads[i][1:]))}">'
                                                         if 2 <= i < len(heads) else "<td>")(next(cells)), r.group(0))
        return re.sub(r"<tr>.*?</tr>", row, m.group(0), flags=re.S)
    return re.sub(r"<table>.*?</table>", table, body, flags=re.S)

def md_to_html(md_path):
    body = subprocess.run(["pandoc", str(md_path), "-f", "gfm", "-t", "html5", "--wrap=none"], capture_output=True,
                          text=True, check=True).stdout
    body = body.replace("../outputs/figures/", "figures/").replace(SITE, "")
    title = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    body = re.sub(r"<h1[^>]*>.*?</h1>", "", body, count=1, flags=re.S)
    body = re.sub(r'<p>(<a href="[^"]*">)?<img\s+src="([^"]+)"\s+alt="([^"]*)"\s*/?>(</a>)?</p>',
                  lambda m: f'<figure>{m.group(1) or '<a href="' + m.group(2) + '">'}<img src="{m.group(2)}" alt="{m.group(3)}" loading="lazy">'
                            f'{m.group(4) or "</a>"}<figcaption>{m.group(3)}</figcaption></figure>', body)
    body = re.sub(r"<!--\s*atlas-hero\s*-->\s*<p><strong><a [^>]*>[^<]*</a></strong></p>", HERO, body)
    body = re.sub(r"<!--\s*interactive:\s*([a-z_]+)\s*-->",
                  lambda m: f'<iframe class="chart" style="height:{HEIGHTS.get(m.group(1), 680)}px" '
                            f'src="charts/{m.group(1)}.html" loading="lazy" title="interactive chart"></iframe>', body)
    return (html.unescape(re.sub(r"<[^>]+>", "", title.group(1))) if title else ""), body


def article(md_path, crumbs, dek, byline):
    title, body = md_to_html(md_path)
    return title, f"""{atlas_nav()}<main id="main"><article class="post">
<header class="post-head"><div class="post-wrap">
<p class="post-crumbs">{crumbs}</p><h1>{title}</h1><p class="post-dek">{dek}</p>
<p class="post-byline"><span>{byline}</span></p></div></header>
<div class="post-body"><div class="post-wrap">{body}</div></div></article></main>"""


CRUMBS = '<a href="/blog/">Blog</a><span class="sep">/</span><a href="../">EMNLP Atlas</a>'
blog = REPORT / "BLOG.md"
if blog.exists():
    meta = dict(re.findall(r"<!--\s*(dek|date):\s*(.*?)\s*-->", blog.read_text()))
    words = len(re.sub(r"[#*\[\]()!<>-]", " ", blog.read_text()).split())
    title, body = article(blog, CRUMBS, meta.get("dek", ""), f"{round(words / 220)} min read · {meta.get('date', '')}")
    (DOCS / "index.html").write_text(page(title, meta.get("dek", ""), SITE, body,
                                          image=f"{SITE}figures/atlas_static.png"))
    print("wrote", DOCS / "index.html")
appx = REPORT / "APPENDIX.md"
if appx.exists():
    title, body = article(appx, CRUMBS + f'<span class="sep">/</span><a href="index.html">{CUR}</a>',
                          f"Every EMNLP {CUR} area and topic with its numbers.", "Reference")
    body = label_cells(body.replace('<div class="post-wrap">', '<div class="post-wrap wide">'))
    (DOCS / "appendix.html").write_text(page(title, f"Every EMNLP {CUR} topic with its numbers.", SITE + "appendix.html", body,
                                             image=f"{SITE}figures/atlas_static.png"))
    print("wrote", DOCS / "appendix.html")

root = DOCS.parent
(root / ".nojekyll").write_text("")
LANDING = f"""{atlas_nav(f"{CUR}/")}<main id="main"><section class="hero"><div class="container">
<span class="kicker">Project</span><h1>EMNLP Atlas</h1>
<p class="section-lede">What EMNLP papers are about, and how that changes each year. Made from the ACL Anthology.</p>
</div></section>
<section class="section"><div class="container">
<a href="{CUR}/atlas.html"><img src="{CUR}/figures/atlas_preview.png" alt="Map of all EMNLP {CUR} papers"
 style="width:100%;border:1px solid var(--rule);border-radius:10px;background:#fff"></a>
<p style="text-align:center;margin-top:16px"><a class="btn" href="{CUR}/atlas.html">Open the EMNLP {CUR} map</a>
<a class="btn btn-ghost" href="{CUR}/papers.html">Search all papers</a></p>
<div class="prose" style="margin-top:28px">
<h2>Editions</h2>
<p><a href="{CUR}/"><strong>EMNLP {CUR}: the story.</strong></a> Every paper on one map, and what changed since {CUR - 1}.</p>
<p>Also see the <a href="/neurips/"><strong>NeurIPS Atlas</strong></a>: all 9,110 NeurIPS 2026 papers on one map.</p>
</div></div></section></main>"""
(root / "index.html").write_text(page("EMNLP Atlas", "Maps and numbers on what EMNLP papers are about.",
                                      "https://mohammadi.cv/emnlp/", LANDING, image=f"{SITE}figures/atlas_static.png"))
print("wrote", root / "index.html")
