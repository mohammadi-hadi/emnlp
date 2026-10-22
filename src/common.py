"""Shared helpers for the EMNLP atlas: readable titles, title keys and the paper table."""
import html, json, re
from urllib.parse import quote_plus
import pandas as pd
from config import P, ROOT

GREEK = {name: chr(cp) for name, cp in [
    ("alpha", 0x3B1), ("beta", 0x3B2), ("gamma", 0x3B3), ("delta", 0x3B4), ("epsilon", 0x3B5), ("varepsilon", 0x3B5),
    ("zeta", 0x3B6), ("eta", 0x3B7), ("theta", 0x3B8), ("kappa", 0x3BA), ("lambda", 0x3BB), ("mu", 0x3BC),
    ("nu", 0x3BD), ("xi", 0x3BE), ("pi", 0x3C0), ("rho", 0x3C1), ("sigma", 0x3C3), ("tau", 0x3C4), ("phi", 0x3C6),
    ("varphi", 0x3C6), ("chi", 0x3C7), ("psi", 0x3C8), ("omega", 0x3C9), ("Gamma", 0x393), ("Delta", 0x394),
    ("Theta", 0x398), ("Lambda", 0x39B), ("Pi", 0x3A0), ("Sigma", 0x3A3), ("Phi", 0x3A6), ("Psi", 0x3A8), ("Omega", 0x3A9)]}
SYMBOLS = {"ell": "ℓ", "infty": "∞", "times": "×", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "to": "→",
           "rightarrow": "→", "sqrt": "√", "cdot": "·", "approx": "≈", "sim": "~", "pm": "±", "star": "*",
           "partial": "∂", "neq": "≠", "ne": "≠", "neg": "¬", "nabla": "∇", "log": "log", "mathcal": "", "mathbf": "", "mathrm": "", "boldsymbol": "",
           "text": "", "textbf": "", "textit": "", "mathbb": "", "emph": "", "operatorname": "", "texttt": ""}


def tex_to_text(s):
    """Turn inline LaTeX into readable text: '$\\gamma$-weakly' -> 'γ-weakly'."""
    s = html.unescape(s or "")

    def inner(m):
        t = m.group(1)
        t = re.sub(r"\\([A-Za-z]+)", lambda c: GREEK.get(c.group(1), SYMBOLS.get(c.group(1), c.group(1))), t)
        return re.sub(r"[{}$]|\\,|\\ |\\!", "", t).replace("^", "").replace("_", "")
    s = re.sub(r"\$([^$]*)\$", inner, s)
    s = re.sub(r"\\([A-Za-z]+)", lambda c: GREEK.get(c.group(1), SYMBOLS.get(c.group(1), c.group(1))), s)
    return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "")).strip()


def title_key(t):
    """Lower-case letters and digits only, for matching the same title across sources."""
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def arxiv_search(title):
    # keep apostrophes: arXiv finds "Don't" but not "Don t"
    q = re.sub(r"[^\w\s'-]", " ", re.sub(r"[’‘]", "'", title))
    return "https://arxiv.org/search/?query=" + quote_plus(q) + "&searchtype=title"


def load_papers(drop_duplicates=True):
    """Clustered paper table with labels applied. Keeps the row index, which lines up with the embeddings."""
    df = pd.read_parquet(P / "papers_clustered.parquet")
    lab = P / "labels.json"
    if lab.exists():
        labels = json.load(open(lab))
        moves = {int(k): int(v) for k, v in labels.get("broad_moves", {}).items()}
        df["broad"] = [moves.get(int(f), int(b)) for f, b in zip(df["fine"], df["broad"])]
    if drop_duplicates:
        df = df[~df["dup"].astype(bool)]
    # titles parsed before "neq" was in SYMBOLS still read "Adopt neq Adapt"
    df["title_display"] = df["title_display"].str.replace(r"(?<=\w) neq (?=\w)", " ≠ ", regex=True)
    if "room" in df:
        df["room"] = df["room"].replace({"zoom": "Zoom"})
    df["arxiv"] = df["title_display"].map(arxiv_search)
    return df


# ---------- affiliations -> organisations, countries, sectors ----------
# Same approach as the NeurIPS atlas: an exact lookup of the raw string (institutions_map.json, copied
# from the NeurIPS project), then of each part of strings that join several organisations. The Anthology
# spells affiliations differently, so institutions_extra.json adds the common EMNLP spellings.
_ORGS = None
COUNTRY_HINTS = [  # used only for the country of an affiliation that names no known organisation
    ("Hong Kong", r"Hong Kong|\bHKU"), ("Taiwan", r"Taiwan|Taipei|Hsinchu"), ("Macau", r"Maca[uo]"),
    ("China", r"\bChina\b|Chinese|Beijing|Shanghai|Shenzhen|Guangzhou|Hangzhou|Nanjing|Wuhan|Harbin|Tianjin|"
              r"Chengdu|Xi'?an\b|Zhejiang|Jiangsu|Sichuan|Shandong|Fujian|Hunan|Hubei|Guangdong|Yunnan|Kunming|Dalian"),
    ("India", r"\bIndia\b|\bIIT\b|\bIIIT|Indian Institute|Delhi|Bombay|Mumbai|Bangalore|Bengaluru|Hyderabad|Kharagpur|Kanpur|Madras"),
    ("Japan", r"Japan|Tokyo|Kyoto|Osaka|Tohoku|Nagoya|NAIST|\bRIKEN\b"),
    ("South Korea", r"Korea|Seoul|KAIST|Daejeon|Busan|POSTECH"),
    ("Singapore", r"Singapore|A\*STAR"), ("UAE", r"\bUAE\b|Abu Dhabi|Dubai|MBZUAI|Emirates"),
    ("Qatar", r"Qatar|Doha"), ("Saudi Arabia", r"Saudi|KAUST|Riyadh"), ("Israel", r"Israel|Tel Aviv|Technion|Jerusalem"),
    ("Austria", r"Austria|Vienna|Wien|Innsbruck|Graz|Linz"),
    ("Switzerland", r"Switzerland|Swiss|Zurich|Z[üu]rich|Lausanne|Geneva|EPFL|ETH\b"),
    ("Germany", r"German|Universität|Technische|M[üu]nchen|Munich|Berlin|Hamburg|Stuttgart|Darmstadt|Heidelberg|"
                r"T[üu]bingen|Saarland|Mannheim|Bielefeld|W[üu]rzburg|Max Planck|Fraunhofer|Leibniz"),
    ("UK", r"\bUK\b|United Kingdom|London|Oxford|Cambridge, UK|Edinburgh|Manchester|Sheffield|Leeds|Glasgow|"
           r"Aberdeen|Durham|Warwick|Bristol|Sussex|Imperial College"),
    ("France", r"France|Paris|INRIA|CNRS|Sorbonne|Grenoble|Lyon|Toulouse"), ("Italy", r"\bItal|Roma|Rome|Milan|Turin|Torino|Bologna|Pisa|Trento"),
    ("Spain", r"Spain|Madrid|Barcelona|Valencia|Coru[ñn]a|Basque"), ("Portugal", r"Portugal|Lisbon|Lisboa|T[ée]cnico|Porto"),
    ("Netherlands", r"Netherlands|Amsterdam|Utrecht|Leiden|Groningen|Delft|Tilburg|Eindhoven|Nijmegen"),
    ("Belgium", r"Belgium|Leuven|Ghent|Antwerp|Brussels"),
    ("Denmark", r"Denmark|Copenhagen|Aarhus"), ("Sweden", r"Sweden|Stockholm|Uppsala|Gothenburg|G[öo]teborg|Link[öo]ping|KTH"),
    ("Norway", r"Norway|Oslo|Bergen|NTNU"), ("Finland", r"Finland|Helsinki|Aalto|Turku|Tampere"),
    ("Czechia", r"Czech|Prague|Charles University|Brno"), ("Poland", r"Poland|Warsaw|Krak[oó]w|Wroc"),
    ("Greece", r"Greece|Athens|Thessaloniki|Crete"), ("Ireland", r"Ireland|Dublin"), ("Slovakia", r"Slovak|Bratislava|Kempelen"),
    ("Romania", r"Romania|Bucharest"), ("Hungary", r"Hungary|Budapest"), ("Croatia", r"Croatia|Zagreb"),
    ("Estonia", r"Estonia|Tartu"), ("Turkey", r"Turkey|T[üu]rkiye|Istanbul|Ankara|Bo[gğ]azi[cç]i|Ko[cç] University"),
    ("Russia", r"Russia|Moscow|Skoltech|St\.? Petersburg|HSE University"),
    ("Canada", r"Canada|Toronto|Montr[ée]al|McGill|Waterloo|Alberta|British Columbia|Vector Institute|Mila\b|Ottawa|Qu[ée]bec"),
    ("Australia", r"Australia|Sydney|Melbourne|Monash|Queensland|Adelaide|Canberra|\bANU\b|\bCSIRO"),
    ("New Zealand", r"New Zealand|Auckland|Otago|Wellington"), ("Brazil", r"Brazil|S[ãa]o Paulo|Rio de Janeiro"),
    ("Vietnam", r"Viet ?nam|Hanoi|Ho Chi Minh"), ("Thailand", r"Thailand|Bangkok|Chulalongkorn|VISTEC|Mahidol"),
    ("Indonesia", r"Indonesia|Jakarta"), ("Malaysia", r"Malaysia|Kuala Lumpur"), ("Pakistan", r"Pakistan|Lahore|Islamabad"),
    ("Bangladesh", r"Bangladesh|Dhaka"), ("Iran", r"\bIran|Tehran|Sharif"), ("Egypt", r"Egypt|Cairo"),
    ("South Africa", r"South Africa|Cape Town|Johannesburg|Pretoria"), ("Nigeria", r"Nigeria|Lagos"),
    ("Mexico", r"Mexico|M[ée]xico"), ("Chile", r"Chile|Santiago"), ("Argentina", r"Argentin"),
    ("USA", r"\bUSA\b|United States|California|Stanford|\bMIT\b|Harvard|Carnegie|Princeton|Yale|Columbia|Cornell|"
            r"Illinois|Michigan|Washington|Texas|Georgia|Massachusetts|Maryland|Pennsylvania|Virginia|Arizona|Utah|"
            r"Ohio|Oregon|Colorado|Florida|Minnesota|Wisconsin|Indiana|Iowa|Purdue|Rutgers|Duke|Brown|Emory|Notre Dame|"
            r"Johns Hopkins|New York|Northwestern|Allen Institute"),
]
_HINTS = [(c, re.compile(p)) for c, p in COUNTRY_HINTS]
MERGE = {"New York University": "NYU", "Technical University of Munich": "TU Munich"}  # one name per organisation


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')).strip(" ,;")


def _org_lookup():
    global _ORGS
    if _ORGS is None:
        rows = json.load(open(ROOT / "data/labels/institutions_map.json"))
        extra = ROOT / "data/labels/institutions_extra.json"
        rows += json.load(open(extra)) if extra.exists() else []
        by_raw = {_norm(r["raw"]).lower(): (MERGE.get(r["canonical"], r["canonical"]), r["country"], r["sector"])
                  for r in rows if r["canonical"].strip().lower() not in ("", "unknown")}
        by_name = {}
        for c, ct, se in by_raw.values():
            by_name.setdefault(c.lower(), (c, ct, se))
        _ORGS = {**by_name, **by_raw}
    return _ORGS


def _spans(text, look):
    """Organisations in a string that may join several: the longest run of parts that matches wins, so
    'X University of Science and Technology and Y' keeps 'Science and Technology' together. A whole-string
    entry in the map counts too, plus whatever its parts name ('MIT/Google' -> MIT and Google)."""
    tok = re.split(r"(\s*(?:/|;|&|\band\b|\+)\s*)", text)
    parts, found, i = tok[0::2], set(), 0
    whole = look.get(_norm(text).lower())
    if whole:
        found.add(whole)
    while i < len(parts):
        for j in range(len(parts), i, -1):
            if whole and i == 0 and j == len(parts):
                continue
            cand = _norm("".join(tok[2 * i:2 * j - 1]))
            h = look.get(cand.lower()) or look.get(cand.strip(" ()").lower())
            if h:
                found.add(h); i = j - 1
                break
        i += 1
    return found


def orgs_of(raw):
    """All organisations named in one affiliation string, e.g. 'MIT and Google' -> {MIT, Google}."""
    look = _org_lookup()
    raw = _norm(raw)
    m = re.fullmatch(r"(.+), \1", raw)  # the Anthology often repeats the same name twice
    raw = m.group(1) if m else raw
    found = _spans(raw, look)
    if not found:  # 'Department of X, Some University': try each comma part
        for part in raw.split(","):
            found |= _spans(part.strip(), look)
    return found


def country_hint(raw):
    """Country named or implied by an affiliation string that matched no known organisation."""
    for c, rx in _HINTS:
        if rx.search(_norm(raw)):
            return c
    return ""


def affiliation_parts(affiliations):
    return [a for a in (_norm(x) for x in str(affiliations or "").split(" | ")) if a and a.upper() not in ("NA", "N/A", "NONE")]


def paper_orgs(affiliations):
    """Organisations on a paper (affiliations = ' | '-joined strings)."""
    out = set()
    for raw in affiliation_parts(affiliations):
        out |= orgs_of(raw)
    return out


def paper_countries(affiliations):
    """Countries on a paper: from the matched organisations, plus a name hint for strings that matched none."""
    out = set()
    for raw in affiliation_parts(affiliations):
        os_ = orgs_of(raw)
        cs = {o[1] for o in os_ if o[1] not in ("", "unknown")}
        out |= cs if cs else ({country_hint(raw)} - {""})
    return out


def anthology_pages_live(year):
    """True once the ACL Anthology has published the edition (its event page answers 200). Before that it
    already serves the PDFs but every paper page is a 404, so the site links the PDF only."""
    import requests
    try:
        r = requests.get(f"https://aclanthology.org/events/emnlp-{year}/", timeout=30,
                         headers={"User-Agent": "Mozilla/5.0 (EMNLP paper overview)"})
        return r.status_code == 200
    except requests.RequestException:
        return False
