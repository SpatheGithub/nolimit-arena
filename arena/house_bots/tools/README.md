# Regenerating the zoo's preflop data

`_common.json` (percentiles and equity vs random hands per deck) and `_strategy.json` (equity vs ranges and push/fold charts, used only by the bots kept out of builders' kits) come from these two offline scripts. Run them from the repo root with the repo venv:

```bash
.venv/bin/python arena/house_bots/tools/gen_equity.py OUT_DIR standard shortdeck royal
.venv/bin/python arena/house_bots/tools/gen_charts.py OUT_DIR
cp OUT_DIR/_common.json OUT_DIR/_strategy.json arena/house_bots/
.venv/bin/python -m arena.house_bots.sync
```

Milestone 6 needs this for new decks.
