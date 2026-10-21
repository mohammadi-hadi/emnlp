"""Two-level topics fitted on the current edition only; the previous edition is assigned to the nearest
topic, so both years are measured with the same ruler. Same method as the NeurIPS atlas."""
import json
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
import umap
from config import CUR, PREV, P

N_FINE, N_BROAD, SEED = 100, 16, 42

df = pd.read_parquet(P / "papers.parquet")
X = np.load(P / "embeddings.npy")
cur = (df["year"] == CUR).to_numpy() & ~df["dup"].to_numpy()

km = KMeans(N_FINE, n_init=10, random_state=SEED).fit(X[cur])
C = km.cluster_centers_ / np.linalg.norm(km.cluster_centers_, axis=1, keepdims=True)
fine = np.argmax(X @ C.T, axis=1)
df["fine"] = fine
df["sim_to_centroid"] = (X * C[fine]).sum(1)

sizes = np.bincount(fine[cur], minlength=N_FINE)
kb = KMeans(N_BROAD, n_init=20, random_state=SEED).fit(C, sample_weight=sizes)
df["broad"] = kb.labels_[df["fine"]]

red = umap.UMAP(n_neighbors=30, min_dist=0.05, metric="cosine", random_state=SEED).fit(X[cur])
xy = np.zeros((len(df), 2), dtype=np.float32)
xy[cur] = red.embedding_
xy[~cur] = red.transform(X[~cur])
df["x"], df["y"] = xy[:, 0], xy[:, 1]
np.save(P / "centroids.npy", C)

stop = list(ENGLISH_STOP_WORDS | {"model", "models", "method", "methods", "propose", "proposed", "results",
                                   "paper", "approach", "show", "based", "learning", "data", "existing",
                                   "performance", "new", "novel", "task", "tasks", "using", "achieves",
                                   "framework", "state", "art", "experiments", "demonstrate", "work",
                                   "language", "llms", "llm", "large"})
dc = df[cur]
docs = dc.groupby("fine").apply(lambda g: " ".join(g["title_display"] + " " + g["abstract"])).reindex(range(N_FINE), fill_value="")
tf = TfidfVectorizer(stop_words=stop, ngram_range=(1, 2), min_df=2, max_df=0.5, sublinear_tf=True,
                     token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b")
M = tf.fit_transform(docs)
vocab = np.array(tf.get_feature_names_out())

clusters = []
for c in range(N_FINE):
    g = dc[dc["fine"] == c].sort_values("sim_to_centroid", ascending=False)
    # official EMNLP area names, from the oral sessions in the program (2026 only)
    official = g.loc[g["pres_type"].eq("oral"), "subsession"].str.replace(r"\s+\d+$", "", regex=True)
    official = official[official != ""].value_counts().head(3).to_dict()
    clusters.append({
        "fine_id": c, "broad_id": int(kb.labels_[c]), f"n_{CUR}": int(len(g)),
        f"n_{PREV}": int(((df["year"] == PREV) & (df["fine"] == c) & ~df["dup"]).sum()),
        "top_terms": vocab[np.argsort(-M[c].toarray().ravel())[:15]].tolist(),
        "official_areas_sample": official,
        "representative_titles": g["title_display"].head(20).tolist(),
        "representative_abstracts": [a[:600] for a in g["abstract"].head(3)],
        "random_titles": g["title_display"].sample(min(10, len(g)), random_state=SEED).tolist(),
    })
json.dump(clusters, open(P / "clusters_fine.json", "w"), indent=1)
broad = [{"broad_id": b, f"n_{CUR}": sum(c[f"n_{CUR}"] for c in clusters if c["broad_id"] == b),
          "fine_ids": [c["fine_id"] for c in clusters if c["broad_id"] == b]} for b in range(N_BROAD)]
json.dump(broad, open(P / "clusters_broad.json", "w"), indent=1)
df.to_parquet(P / "papers_clustered.parquet", index=False)
print("fine sizes:", sizes.min(), int(np.median(sizes)), sizes.max(), "| broad:", sorted((b[f"n_{CUR}"] for b in broad), reverse=True))
