"""Robustness check: do the area-level shifts depend on fitting the topics on the current edition?

Refit the topics two other ways (on the previous edition only, and on both years pooled), map each new
topic to the research area most of its papers had in the main fit, and recompute the area shares.
Writes OUT/robustness_areas.csv.
"""
import json, re
import numpy as np
import pandas as pd
from config import CUR, PREV, P, OUT
from common import load_papers
from sklearn.cluster import KMeans

df = load_papers()
X = np.load(P / "embeddings.npy")[df.index.to_numpy()]  # rows of the papers kept by load_papers
N_FINE = len(json.load(open(P / "clusters_fine.json")))
broad_name = {int(k): re.sub(r"^Area \d+:\s*", "", v["name"]) for k, v in json.load(open(P / "labels.json"))["broad"].items()}
isp, isc = (df.year == PREV).to_numpy(), (df.year == CUR).to_numpy()
c, p = str(CUR), str(PREV)


def area_shares(area):
    return pd.DataFrame({yr: pd.Series(area[m]).map(broad_name).value_counts(normalize=True) * 100
                         for yr, m in ((p, isp), (c, isc))})


rows = {f"fit on {c} (main)": area_shares(df.broad.to_numpy())}
for name, mask in ((f"fit on {p}", isp), ("fit on both years", isp | isc)):
    km = KMeans(N_FINE, n_init=4, random_state=42).fit(X[mask])
    C = km.cluster_centers_ / np.linalg.norm(km.cluster_centers_, axis=1, keepdims=True)
    lab = np.argmax(X @ C.T, axis=1)
    to_area = pd.Series(df.broad.to_numpy()).groupby(lab).agg(lambda s: s.value_counts().idxmax())
    rows[name] = area_shares(to_area.reindex(lab).to_numpy())

out = pd.concat(rows, axis=1).fillna(0).round(2)
out.columns = [f"{fit} · {yr}" for fit, yr in out.columns]
for fit in rows:
    out[f"{fit} · change"] = (out[f"{fit} · {c}"] - out[f"{fit} · {p}"]).round(2)
main = f"fit on {c} (main) · change"
out = out.sort_values(main, ascending=False)
out.index.name = "area"
out.to_csv(OUT / "robustness_areas.csv")
ch = out[[k for k in out.columns if "change" in k]]
same = np.sign(ch).eq(np.sign(ch[main]), axis=0).all(axis=1) | ch[main].abs().lt(0.5)
print(ch.to_string())
print(f"\n{int(same.sum())} of {len(ch)} areas move the same way under all three fits (or change by under 0.5 points "
      f"in the main fit); correlation of changes with the main fit: "
      + ", ".join(f"{k.split(' · ')[0]} {ch[main].corr(ch[k]):.2f}" for k in ch.columns if k != main))
