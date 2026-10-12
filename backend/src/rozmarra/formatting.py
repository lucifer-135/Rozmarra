"""Formats for text that people read (docs/prd.md, Section 17.4).

Dates are written in full, for example "28 October 2026". Times use the 12-hour
clock, for example "4:40 pm". Chances show a percentage and a word.
"""

from __future__ import annotations

from datetime import date, time


def long_date(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


def clock_12h(moment: time) -> str:
    return moment.strftime("%I:%M %p").lstrip("0").lower()


def capitalised(word: str) -> str:
    return word[:1].upper() + word[1:]
