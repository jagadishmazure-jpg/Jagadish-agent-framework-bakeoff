"""The comparison matrix names a mechanism per framework. Check the adapter code really uses it."""

from pathlib import Path

import pytest

from bakeoff.cli import FEATURES, MARKERS
from bakeoff.eval import ADAPTERS
from bakeoff.runner import adapter_loc, code_lines

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", list(ADAPTERS))
def test_markers_present(name):
    src = (ROOT / "src" / "bakeoff" / "adapters" / (ADAPTERS[name].rsplit(".", 1)[1] + ".py")).read_text()
    for m in MARKERS[name]:
        assert m in src, f"{name}: {m}"


def test_every_adapter_has_a_feature_row():
    assert set(FEATURES) == set(ADAPTERS) == set(MARKERS)


def test_crewai_hitl_is_not_claimed_native():
    assert "no per-tool pause" in FEATURES["crewai"][2]


def test_loc_counter_skips_docstrings_and_comments(tmp_path):
    p = tmp_path / "m.py"
    p.write_text('"""doc\nmore"""\n\n# c\nx = 1\n\n\ndef f():\n    """d"""\n    return x\n')
    assert code_lines(p) == 3


def test_adapter_loc_positive():
    assert all(adapter_loc(n) > 10 for n in ADAPTERS)
