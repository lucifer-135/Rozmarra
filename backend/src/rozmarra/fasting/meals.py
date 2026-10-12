"""Food categories for meals.

Rozmarra uses three food categories (docs/techstack.md, Section 4.3). Each category
sets the starting meal absorption speed of the twin (docs/techstack.md, Section 5.3).
"""

from __future__ import annotations

from enum import StrEnum


class FoodCategory(StrEnum):
    # Sweets, sabudana, potatoes, fruit juice and dates.
    FAST_ABSORBING = "fast_absorbing"
    # Ordinary mixed meals.
    MIXED = "mixed"
    # Meals that are high in fibre, fat or protein.
    SLOW_ABSORBING = "slow_absorbing"


# The meal absorption speed k_abs for each category, in units per minute.
ABSORPTION_RATE_PER_MIN = {
    FoodCategory.FAST_ABSORBING: 0.03,
    FoodCategory.MIXED: 0.02,
    FoodCategory.SLOW_ABSORBING: 0.012,
}

FOOD_CATEGORY_LABELS = {
    FoodCategory.FAST_ABSORBING: "Fast-absorbing food, such as sweets, sabudana or dates",
    FoodCategory.MIXED: "An ordinary mixed meal",
    FoodCategory.SLOW_ABSORBING: "A meal that is high in fibre, fat or protein",
}
