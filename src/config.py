"""Which EMNLP editions to compare. Defaults to 2026 vs 2025; set ATLAS_CUR / ATLAS_PREV to run the
same pipeline on other years (for example 2025 vs 2024 as a dry run while 2026 is not in the Anthology yet)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = int(os.environ.get("ATLAS_CUR", 2026))
PREV = int(os.environ.get("ATLAS_PREV", CUR - 1))
YEARS = (CUR, PREV)

RAW = ROOT / "data/raw"
# a dry run writes to its own folders, so it never mixes with the real edition
TAG = "" if (CUR, PREV) == (2026, 2025) else f"_{CUR}v{PREV}"
P = ROOT / f"data/processed{TAG}"
OUT = ROOT / f"outputs{TAG}"
DOCS = ROOT / "docs" / str(CUR) if not TAG else ROOT / f"docs_dryrun/{CUR}"
REPORT = ROOT / "report" if not TAG else OUT  # BLOG.md and APPENDIX.md; a dry run keeps report/ clean
for d in (RAW, P, OUT / "figures", DOCS):
    d.mkdir(parents=True, exist_ok=True)

# tracks that make up "EMNLP" in both years: Anthology volume -> label
TRACKS = {"main": "Main", "findings": "Findings", "industry": "Industry", "demos": "Demo"}
ANTHOLOGY_RAW = "https://raw.githubusercontent.com/acl-org/acl-anthology/{ref}/data/xml/{name}"
# until the 2026 volumes are merged, they live on the ingestion branch (acl-org/acl-anthology PR #10522)
REFS = ["master", "ingest-emnlp-2026"]
PROGRAM_SHEET = ("https://docs.google.com/spreadsheets/d/1aXGTy_7Xeh-OXIs3iJSbDpUsZ6YhbfA76b17kBZH0Yk/export"
                 "?format=csv&gid=943432490")
