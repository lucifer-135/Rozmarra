"""The fasting plan that the doctor tests, compares and approves.

The API and the dashboard exchange plans in this format. It follows the example in
docs/techstack.md, Section 4.3, with one change: every time is a full date and time,
so that fasts that last more than one day, such as a Jain upvas, are clear.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

from rozmarra.fasting.meals import FoodCategory


class PlanStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class PlannedMeal(BaseModel):
    time: datetime
    label: str
    label_hi: str = ""
    food_category: FoodCategory
    carbs_g: float = Field(ge=0)
    breaks_fast: bool = False


class PlannedMedicine(BaseModel):
    """One dose of a medicine. The dose unit (mg or units) comes from the medicine catalogue."""

    name: str
    dose: float = Field(ge=0)
    time: datetime
    usual_dose: float | None = None
    usual_time: datetime | None = None

    @property
    def is_changed(self) -> bool:
        return (self.usual_dose is not None and self.dose != self.usual_dose) or (
            self.usual_time is not None and self.time != self.usual_time
        )


class PlannedActivity(BaseModel):
    start: datetime
    end: datetime
    label: str
    mets: float = Field(ge=1)


class FastingPlan(BaseModel):
    patient_id: str
    plan_name: str
    template_id: str
    fast_type: str
    date: date
    city: str
    fast_start: datetime
    fast_end: datetime
    water_allowed: bool
    meals: list[PlannedMeal]
    medicines: list[PlannedMedicine] = []
    activities: list[PlannedActivity] = []
    status: PlanStatus = PlanStatus.DRAFT
    approved_by: str | None = None
    approved_on: date | None = None
    # The contact details that the doctor gives for the patient plan, for example a clinic.
    approved_contact: str | None = None
    notes: list[str] = []

    @property
    def fast_hours(self) -> float:
        """The length of the fasting window, in hours."""
        return (self.fast_end - self.fast_start) / timedelta(hours=1)

    @property
    def breaking_meal(self) -> PlannedMeal | None:
        return next((meal for meal in self.meals if meal.breaks_fast), None)

    @property
    def longest_gap_without_food_hours(self) -> float:
        """The longest time between two meals, in hours.

        Rozmarra uses this value for the "fasting hours" item of the IDF-DAR score,
        because it works for every type of fast, including fasts with fruit and milk.
        """
        times = sorted(meal.time for meal in self.meals)
        gaps = [(b - a) / timedelta(hours=1) for a, b in zip(times, times[1:], strict=False)]
        return max(gaps, default=0.0)

    @property
    def window_start(self) -> datetime:
        """The start of the period that the twin simulates."""
        first_meal = min((meal.time for meal in self.meals), default=self.fast_start)
        return min(self.fast_start, first_meal) - timedelta(hours=2)

    @property
    def window_end(self) -> datetime:
        """The end of the period that the twin simulates: 4 hours after the fast ends."""
        breaking = self.breaking_meal
        end = max(self.fast_end, breaking.time if breaking else self.fast_end)
        return end + timedelta(hours=4)
