"""An estimate of the carbohydrates in the ShanghaiT2DM meal records.

ShanghaiT2DM records each meal as text, for example "Rice 100 g" on one line and
"Vegetable 150 g" on the next. The dataset does not give carbohydrates. Rozmarra
estimates them from a small table of typical carbohydrate content per 100 g of each
food. The values are approximate food composition values for cooked foods, unless
the name says otherwise. The estimate is rough, and the data card says so. The twin
also fits a personal meal-size factor, which absorbs part of this error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NOT_RECORDED = "data not available"
# The carbohydrate content of a food that the table does not know, in grams per 100 g.
UNKNOWN_FOOD_CARBS_PER_100G = 8.0
# The amount assumed for a food line without an amount, in grams.
DEFAULT_AMOUNT_G = 100.0

# The table is searched in order, so more specific names come before general names.
CARBS_PER_100G: tuple[tuple[str, float], ...] = (
    ("rice in soup", 10),
    ("porridge", 9),
    ("congee", 9),
    ("rice cake", 45),
    ("rice wine", 4),
    ("glutinous rice", 30),
    ("fried rice", 30),
    ("rice noodle", 25),
    ("rice", 26),
    ("instant noodles", 60),
    ("noodle", 25),
    ("vermicelli", 25),
    ("steamed pork bun", 35),
    ("steamed vegetable bun", 40),
    ("bun", 45),
    ("steamed bread", 47),
    ("buckwheat bread", 45),
    ("bread", 50),
    ("toast", 50),
    ("dumpling", 25),
    ("wonton", 25),
    ("pancake", 40),
    ("cake", 50),
    ("biscuit", 70),
    ("cracker", 70),
    ("cereal", 65),
    ("oatmeal", 60),
    ("oats", 60),
    ("meal replacement powder", 50),
    ("coarse grain", 25),
    ("corn", 19),
    ("millet", 20),
    ("sweet potato", 20),
    ("purple potato", 20),
    ("potato", 17),
    ("taro", 26),
    ("yam", 25),
    ("pumpkin", 7),
    ("lotus root", 16),
    ("apple", 14),
    ("pear", 13),
    ("orange", 12),
    ("banana", 23),
    ("grapefruit", 8),
    ("kiwi", 15),
    ("peach", 10),
    ("grape", 17),
    ("watermelon", 8),
    ("dragon fruit", 13),
    ("strawberry", 8),
    ("red date", 60),
    ("fruit", 12),
    ("yogurt", 12),
    ("soybean milk", 3),
    ("soy milk", 3),
    ("milk", 5),
    ("beer", 4),
    ("juice", 11),
    ("coffee", 1),
    ("tea", 0),
    ("soup", 3),
    ("egg", 1),
    ("tofu", 2),
    ("bean curd", 3),
    ("meatball", 8),
    ("sausage", 5),
    ("fish", 0),
    ("hairtail", 0),
    ("shrimp", 0),
    ("sea cucumber", 0),
    ("beef", 0),
    ("pork", 0),
    ("chicken", 0),
    ("duck", 0),
    ("peanut", 16),
    ("walnut", 14),
    ("nut", 15),
    ("cucumber", 3),
    ("cabbage", 5),
    ("lettuce", 3),
    ("spinach", 4),
    ("tomato", 4),
    ("cauliflower", 5),
    ("radish", 4),
    ("celery", 3),
    ("eggplant", 6),
    ("gourd", 4),
    ("fungus", 5),
    ("mushroom", 4),
    ("bamboo shoot", 4),
    ("crown daisy", 3),
    ("carrot", 9),
    ("onion", 9),
    ("bean sprout", 4),
    ("green bean", 7),
    ("kelp", 3),
    ("seaweed", 3),
    ("vegetable", 4),
)

# Each name matches whole words only, with an optional plural ending. Without this
# rule, "steamed" would match "tea" and "eggplant" would match "egg".
_PATTERNS = tuple(
    (re.compile(rf"\b{re.escape(keyword)}(?:e?s)?\b"), carbs) for keyword, carbs in CARBS_PER_100G
)
_LINE = re.compile(r"^(?P<name>.*?)\s*(?P<amount>\d+(?:\.\d+)?)\s*(?:g|ml|mL)\s*$")


@dataclass(frozen=True)
class MealEstimate:
    carbs_g: float | None
    items: int
    unknown_items: int

    @property
    def source(self) -> str:
        if self.carbs_g is None:
            return "not recorded"
        return "estimated from the meal text"


def carbs_per_100g(name: str) -> float | None:
    lowered = name.lower()
    for pattern, carbs in _PATTERNS:
        if pattern.search(lowered):
            return carbs
    return None


def estimate_meal(text: str) -> MealEstimate:
    """Estimate the carbohydrates in a ShanghaiT2DM meal record, in grams."""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines or any(NOT_RECORDED in line.lower() for line in lines):
        return MealEstimate(None, 0, 0)
    total = 0.0
    unknown = 0
    for line in lines:
        match = _LINE.match(line)
        name, amount = (
            (match["name"], float(match["amount"])) if match else (line, DEFAULT_AMOUNT_G)
        )
        carbs = carbs_per_100g(name)
        if carbs is None:
            unknown += 1
            carbs = UNKNOWN_FOOD_CARBS_PER_100G
        total += carbs * amount / 100
    return MealEstimate(round(total, 1), len(lines), unknown)
