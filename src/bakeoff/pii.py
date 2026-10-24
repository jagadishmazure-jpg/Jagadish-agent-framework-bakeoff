"""PII masking for traces, logs and error messages.

Covers payment cards (Luhn-checked so order numbers are not masked), emails, phone numbers and US SSNs.
Anything that leaves the process as a log line or exception text goes through `mask` first.
"""

from __future__ import annotations

import logging
import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
PHONE = re.compile(r"(?<!\w)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _card(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    return "[CARD]" if 13 <= len(digits) <= 19 and luhn_ok(digits) else m.group(0)


def mask(text: str) -> str:
    text = EMAIL.sub("[EMAIL]", text)
    text = CARD.sub(_card, text)
    text = SSN.sub("[SSN]", text)
    return PHONE.sub("[PHONE]", text)


class MaskingFilter(logging.Filter):
    """Attach to any handler: masks the rendered message, args included, before it is written."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask(record.getMessage())
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = mask(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def get_logger(name: str = "cuagents") -> logging.Logger:
    log = logging.getLogger(name)
    if not any(isinstance(f, MaskingFilter) for f in log.filters):
        log.addFilter(MaskingFilter())
    return log
