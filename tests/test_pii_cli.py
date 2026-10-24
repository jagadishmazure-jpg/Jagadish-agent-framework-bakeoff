import logging

import pytest

from bakeoff.pii import get_logger, mask


@pytest.mark.parametrize(
    "raw,token",
    [
        ("4111 1111 1111 1111", "[CARD]"),
        ("refunds@example.test", "[EMAIL]"),
        ("(555) 010-2233", "[PHONE]"),
        ("123-45-6789", "[SSN]"),
    ],
)
def test_mask(raw, token):
    assert token in mask(f"x {raw} y")


def test_order_number_not_masked():
    assert "[CARD]" not in mask("INV-1234567890123")


def test_logger_masks(caplog):
    log = get_logger("bakeoff.t")
    with caplog.at_level(logging.INFO, logger="bakeoff.t"):
        log.info("customer %s", "a.b@example.test")
        try:
            raise RuntimeError("card 4111111111111111")
        except RuntimeError:
            log.exception("boom")
    assert "a.b@example.test" not in caplog.text
    assert "4111111111111111" not in "".join(r.exc_text or "" for r in caplog.records)


def test_trace_masks_user_pii():
    from bakeoff.adapters import plain
    from bakeoff.eval import approve_all

    o = plain.run("Where is BW-1001? mail a.b@example.test", approve_all)
    assert "a.b@example.test" not in str(o.trace.spans) and "[EMAIL]" in str(o.trace.spans)


def test_readme_excerpt_is_real():
    from pathlib import Path

    from bakeoff.adapters import plain
    from bakeoff.eval import approve_all

    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    o = plain.run("Please refund 20.00 on BW-1002", approve_all)
    assert o.final in readme and str(o.agents) in readme and str(o.trace.kinds()) in readme
