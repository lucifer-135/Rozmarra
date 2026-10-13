"""The times at which the patient plan asks the patient to check their blood sugar.

The times follow fixed rules, so that every plan is predictable and the doctor can check it:

1. During the fast, the first check is 2 hours after the fast starts, and then one check
   follows every 3 hours.
2. One check is 1 hour before the fast ends, before the meal that breaks the fast.
3. One check is 30 minutes before the time at which the twin predicts the lowest blood sugar,
   when that time falls inside the fast.
4. One check is 2 hours after the meal that breaks the fast.

Checks from rules 1 to 3 are only planned between 6:00 am and 10:00 pm, so that the plan does
not wake the patient at night. Each time is rounded to the nearest half hour. When two checks
are less than 75 minutes apart, only one stays, in this order of priority: rule 4, rule 2,
rule 3 and then rule 1. The IDF-DAR 2021
guidelines recommend several checks during each day of Ramadan. These rules apply the same
idea to every fast. A clinical expert should review them.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from rozmarra.fasting.plan import FastingPlan

FIRST_CHECK = timedelta(hours=2)
EVERY = timedelta(hours=3)
BEFORE_END = timedelta(hours=1)
BEFORE_LOWEST = timedelta(minutes=30)
AFTER_BREAKING_MEAL = timedelta(hours=2)
MIN_GAP = timedelta(minutes=75)
AWAKE_FROM = time(6, 0)
AWAKE_UNTIL = time(22, 0)


def _round_half_hour(moment: datetime) -> datetime:
    start = moment.replace(minute=0, second=0, microsecond=0)
    minutes = round((moment - start) / timedelta(minutes=30)) * 30
    return start + timedelta(minutes=minutes)


def _awake(moment: datetime) -> bool:
    return AWAKE_FROM <= moment.time() <= AWAKE_UNTIL


def check_times(plan: FastingPlan, lowest_time: datetime | None = None) -> list[datetime]:
    """The check times for a plan, in order. The lowest time comes from the twin's simulation."""
    # The candidates are listed in order of priority. A candidate is kept only when it is at
    # least 75 minutes from every check that is already kept.
    candidates: list[datetime] = []
    breaking = plan.breaking_meal
    if breaking is not None:
        candidates.append(_round_half_hour(breaking.time + AFTER_BREAKING_MEAL))
    before_end = _round_half_hour(plan.fast_end - BEFORE_END)
    if before_end > plan.fast_start and _awake(before_end):
        candidates.append(before_end)
    if lowest_time is not None and plan.fast_start <= lowest_time <= plan.fast_end:
        before_lowest = _round_half_hour(lowest_time - BEFORE_LOWEST)
        if _awake(before_lowest):
            candidates.append(before_lowest)
    moment = plan.fast_start + FIRST_CHECK
    while moment <= plan.fast_end - BEFORE_END:
        candidate = _round_half_hour(moment)
        if _awake(candidate):
            candidates.append(candidate)
        moment += EVERY

    kept: list[datetime] = []
    for candidate in candidates:
        if all(abs(candidate - other) >= MIN_GAP for other in kept):
            kept.append(candidate)
    return sorted(kept)
