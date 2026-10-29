# Regenerating the zoo's preflop data

`_common.json` (equity tables and push/fold charts per deck) comes from these two offline scripts. Run them from the repo root with the repo venv:

```bash
.venv/bin/python arena/house_bots/tools/gen_equity.py OUT_DIR standard shortdeck royal
.venv/bin/python arena/house_bots/tools/gen_charts.py OUT_DIR
cp OUT_DIR/_common.json arena/house_bots/_common.json
.venv/bin/python -m arena.house_bots.sync
```

Milestone 6 needs this for new decks.
