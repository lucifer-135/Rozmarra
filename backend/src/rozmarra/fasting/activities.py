"""Activities that the doctor can add to a fasting plan in the dashboard.

The intensity of each activity is given in METs (metabolic equivalents of task). The values
are approximate values from the Compendium of Physical Activities (Ainsworth and colleagues,
2011). The twin uses them to estimate the extra use of glucose during the activity. The
garba value matches the Navratri template.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityPreset:
    id: str
    label: str
    mets: float
    minutes: int


ACTIVITY_PRESETS = (
    ActivityPreset("walking", "Walking at an ordinary pace", 3.5, 30),
    ActivityPreset("brisk_walking", "Brisk walking", 4.3, 30),
    ActivityPreset("household_work", "Household work", 2.5, 60),
    ActivityPreset("garba", "Garba or dandiya dancing", 5.0, 90),
)
