"""Prepare travel prose for Markdown without interpreting currency as math."""

import re


def format_itinerary(text: str) -> str:
    # Preserve already escaped dollars and handle even numbers of backslashes.
    return re.sub(r"(?<!\\)((?:\\\\)*)\$", r"\1\\$", text)
