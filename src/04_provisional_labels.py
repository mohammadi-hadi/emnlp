"""Stand-in topic names from each cluster's top terms, so the whole pipeline can run before the careful
naming pass. The real names (data/labels/labels_<year>.json) replace these when they exist."""
import json
from config import CUR, P, ROOT

real = ROOT / f"data/labels/labels_{CUR}.json"
if real.exists():
    json.dump(json.load(open(real)), open(P / "labels.json", "w"), indent=1)
    print("using", real.name)
else:
    fine = json.load(open(P / "clusters_fine.json"))
    broad = json.load(open(P / "clusters_broad.json"))
    names = {c["fine_id"]: " · ".join(c["top_terms"][:3]) for c in fine}
    out = {"fine": {str(k): {"name": v} for k, v in names.items()},
           "broad": {str(b["broad_id"]): {"name": f"Area {b['broad_id']}: " + names[max(
               b["fine_ids"], key=lambda f: fine[f][f"n_{CUR}"])]} for b in broad},
           "provisional": True}
    json.dump(out, open(P / "labels.json", "w"), indent=1)
    print("provisional labels for", len(names), "topics")
