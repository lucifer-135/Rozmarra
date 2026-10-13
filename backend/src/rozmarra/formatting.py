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


# --- Times and dates for the patient plan ---------------------------------------------------

HINDI_MONTHS = (
    "जनवरी",
    "फ़रवरी",
    "मार्च",
    "अप्रैल",
    "मई",
    "जून",
    "जुलाई",
    "अगस्त",
    "सितंबर",
    "अक्टूबर",
    "नवंबर",
    "दिसंबर",
)


def patient_time(moment: time) -> str:
    """A time for patients, for example "8 am", "4:30 pm" or "12 noon"."""
    if moment.minute == 0 and moment.hour == 12:
        return "12 noon"
    if moment.minute == 0 and moment.hour == 0:
        return "12 midnight"
    hour = moment.hour % 12 or 12
    suffix = "am" if moment.hour < 12 else "pm"
    return f"{hour} {suffix}" if moment.minute == 0 else f"{hour}:{moment.minute:02d} {suffix}"


def hindi_time(moment: time) -> str:
    """A time in Hindi with the part of the day, for example "सुबह 8 बजे" or "शाम 5:30 बजे"."""
    if 4 <= moment.hour < 12:
        part = "सुबह"
    elif 12 <= moment.hour < 16:
        part = "दोपहर"
    elif 16 <= moment.hour < 20:
        part = "शाम"
    else:
        part = "रात"
    hour = moment.hour % 12 or 12
    clock = f"{hour}" if moment.minute == 0 else f"{hour}:{moment.minute:02d}"
    return f"{part} {clock} बजे"


def hindi_date(day: date) -> str:
    return f"{day.day} {HINDI_MONTHS[day.month - 1]} {day.year}"
