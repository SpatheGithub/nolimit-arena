"""Cross-validation against pokerkit (see arena/engine/xval.py).

The quick test runs on every ``pytest -q``. The full test replays 100,000
random hands across NLHE, fixed-limit, pot-limit Omaha, short deck and royal
on all cores; set NOLIMIT_XVAL_HANDS to change the count.
"""

import os

import pytest

pytest.importorskip("pokerkit")

from arena.engine import xval  # noqa: E402


def test_crossval_quick():
    tally, failures = xval.run_cases(seed=12345, count=1500)
    assert not failures, "\n".join(failures)
    assert tally["hands"] + tally["diverged_hands"] == 1500


@pytest.mark.slow
def test_crossval_full():
    n = int(os.environ.get("NOLIMIT_XVAL_HANDS", "100000"))
    tally, failures = xval.run(n, seed=1)
    assert not failures, "\n".join(failures[:10])
    assert tally["hands"] + tally["diverged_hands"] == n
    assert tally["showdowns"] > n // 2
