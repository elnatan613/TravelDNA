"""Small, conservative reader for common OpenStreetMap opening-hours strings."""
import re
from datetime import date


DAY_INDEX = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5, "Su": 6}
DAY_TOKEN = re.compile(r"(Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*-\s*(Mo|Tu|We|Th|Fr|Sa|Su))?")
TIME_RANGE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s*-\s*([01]?\d|2[0-3]):([0-5]\d)\b")


def _rule_days(prefix: str) -> set[int] | None:
    """Read simple weekday selectors; return None for syntax we cannot trust."""
    prefix = prefix.strip()
    if not prefix:
        return set(range(7))
    tokens = list(DAY_TOKEN.finditer(prefix))
    remainder = DAY_TOKEN.sub("", prefix).replace(",", "").strip()
    if not tokens or remainder:
        return None
    selected = set()
    for token in tokens:
        start, end = DAY_INDEX[token.group(1)], DAY_INDEX[token.group(2) or token.group(1)]
        selected.update(range(start, end + 1) if start <= end else [*range(start, 7), *range(0, end + 1)])
    return selected


def hours_for_date(value: str | None, when: date) -> tuple[str, str | None, str | None] | None:
    """Return open/closed and a simple local time range, otherwise no conclusion.

    This intentionally declines seasonal, holiday, split-shift and free-text rules.
    """
    if not value:
        return None
    value = value.strip()
    if value == "24/7":
        return "open", "00:00", "23:59"
    rules = [rule.strip() for rule in value.split(";") if rule.strip()]
    if not rules:
        return None
    understood = False
    for rule in rules:
        if "," in rule or "PH" in rule or "sunrise" in rule.lower() or "sunset" in rule.lower():
            return None
        time_range = TIME_RANGE.search(rule)
        prefix = rule[:time_range.start()] if time_range else rule
        days = _rule_days(prefix.replace("off", "").replace("closed", "").strip())
        if days is None:
            return None
        understood = True
        if when.weekday() not in days:
            continue
        if re.search(r"\b(off|closed)\b", rule, re.IGNORECASE):
            return "closed", None, None
        if not time_range:
            return None
        return "open", f"{int(time_range.group(1)):02}:{time_range.group(2)}", f"{int(time_range.group(3)):02}:{time_range.group(4)}"
    return ("closed", None, None) if understood else None
