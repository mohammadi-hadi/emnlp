# EMNLP Atlas

What EMNLP papers are about, and how that changes each year. Every paper of an edition goes on one map,
placed by what its title and abstract say, and is compared with the year before.

This is the sister project of the [NeurIPS Atlas](https://github.com/mohammadi-hadi/neurips)
([live site](https://mohammadi.cv/neurips/)), built with the same method.

## Data

All data is public:

- Paper titles, authors, affiliations and abstracts come from the [ACL Anthology](https://aclanthology.org/)
  (CC BY 4.0): the main, Findings, industry and demo volumes of each EMNLP edition.
- Rooms, days and times for EMNLP 2026 come from the public program sheet linked on
  [2026.emnlp.org/program](https://2026.emnlp.org/program/), matched to the papers by title.

## Reproduce

```bash
cd src
python 00_fetch_data.py      # Anthology XML and the program sheet
python 01_prepare.py         # one table for both editions
python 02_embed.py           # Qwen3-Embedding-0.6B, cached per paper
python 03_cluster.py         # 100 topics in 16 areas, fitted on the current year
python 04_provisional_labels.py
python 06_map.py             # interactive map
python 12_paper_index.py     # searchable list
python 09_build_site.py      # story and landing pages (needs pandoc)
```

The years are a setting: `ATLAS_CUR=2025 ATLAS_PREV=2024 python 01_prepare.py` runs the same pipeline
on earlier editions.

Made by [Hadi Mohammadi](https://mohammadi.cv).
