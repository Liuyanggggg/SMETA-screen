# Large language models for title and abstract screening in oncology systematic reviews

Code for the paper. One frozen recall-first prompt; five vendor APIs; humans read include or uncertain.

![Graphical abstract](ga.png)

![First-pass action](fig1.png)

Bibliographic records from the source reviews are not in this repository. Use your own records.

## Run

```bash
export SMETA_API_KEY=...
export SMETA_MODEL=deepseek-chat
export SMETA_BASE=https://api.deepseek.com/v1
python3 screen.py criteria.txt records.jsonl out.jsonl
```

`records.jsonl` lines are `{"id","title","abstract"}`. Temperature is 0. Uncertain is retained with include.

## Paper files

- Production prompt: `prompts/smeta_recall_first.txt`
- Catalogue prompts: `prompts/`
- Locked 800-record split: `data/locked_split.json`
- Catalogue metrics: `data/metrics.csv`

## Citation

Liu Y, Song Y, Li X, Deng J, Du Y, Qin C, Xu T. Large language models for title and abstract screening in oncology systematic reviews. *npj Digital Medicine* (in submission).

Code is MIT. Using the code does not replace citing the paper.
