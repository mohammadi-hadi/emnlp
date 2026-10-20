"""Embed title + abstract with the same open model as the NeurIPS atlas (Qwen3-Embedding-0.6B), so EMNLP
and NeurIPS papers share one space. Vectors are cached per paper, so a re-run only embeds new papers."""
import hashlib, time
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from config import P, ROOT

MODEL = ROOT / "models/Qwen3-Embedding-0.6B"
CACHE = ROOT / "data/embed_cache"
CACHE.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(P / "papers.parquet")
texts = (df["title_display"] + ". " + df["abstract"]).tolist()
keys = [hashlib.sha1(f"{u}\n{t}".encode()).hexdigest() for u, t in zip(df["uid"], texts)]

cache_file = CACHE / "vectors.npz"
cached = dict(np.load(cache_file)) if cache_file.exists() else {}
todo = [i for i, k in enumerate(keys) if k not in cached]
print(f"{len(df)} papers, {len(df) - len(todo)} cached, {len(todo)} to embed")

if todo:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer(str(MODEL), device=device)
    model.max_seq_length = 384
    order = sorted(todo, key=lambda i: -len(texts[i]))  # longest first keeps padding small
    t0 = time.time()
    emb = model.encode([texts[i] for i in order], batch_size=32, normalize_embeddings=True,
                       show_progress_bar=True, convert_to_numpy=True)
    for i, v in zip(order, emb):
        cached[keys[i]] = v.astype(np.float32)
    np.savez(cache_file, **cached)
    print(f"embedded {len(todo)} in {time.time() - t0:.0f}s on {device}")

np.save(P / "embeddings.npy", np.stack([cached[k] for k in keys]))
(P / "embeddings_model.txt").write_text(MODEL.name)
