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
           "partial": "∂", "nabla": "∇", "log": "log", "mathcal": "", "mathbf": "", "mathrm": "", "boldsymbol": "",
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
    return "https://arxiv.org/search/?query=" + quote_plus(re.sub(r"[^\w\s-]", " ", title)) + "&searchtype=title"


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
    df["arxiv"] = df["title_display"].map(arxiv_search)
    return df
