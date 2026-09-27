# SMETA-screen

Frozen recall-first title–abstract screening for the SMETA study.

45 oncology randomised-trial meta-analyses, 128,023 unique records, **597 unique final inclusions** (627 inclusions with abstracts). Not 611.

Include or uncertain is kept for a person. Temperature 0.

Bibliographic records from the source reviews are not in this repository.

## What is here

- `prompts/` — production prompt (`smeta_recall_first.txt`) and the 12 catalogue prompts
- `data/locked_split.json` — locked 800-record split
- `data/metrics.csv` — catalogue scores on that split
- `screen.py` — run the production prompt on your own JSONL

```bash
export SMETA_API_KEY=...
export SMETA_MODEL=deepseek-chat          # optional
export SMETA_BASE=https://api.deepseek.com/v1   # optional
python3 screen.py criteria.txt records.jsonl out.jsonl
python3 screen.py --check
```

`records.jsonl` lines: `{"id","title","abstract"}`.

## Citation

Liu Y, Song Y, Li X, Deng J, Du Y, Qin C, Xu T. Large language models for title and abstract screening in oncology systematic reviews.

Code is MIT. Citing the paper is separate.
