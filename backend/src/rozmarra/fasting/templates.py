"""Starting templates for the fasting patterns in docs/prd.md, Section 9.

Practices vary between families, communities and regions. These templates are only
starting points. The doctor can change every time, meal and water setting to match
how the patient actually fasts. The meal sizes are starting values, and the data
card records them.

Each time in a template is set relative to the clock, dawn, sunrise, sunset or
moonrise, so the same template works in every city and on every date.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from rozmarra.fasting.calendar import moonrise, sun_times
from rozmarra.fasting.meals import FoodCategory
from rozmarra.fasting.plan import FastingPlan, PlannedActivity, PlannedMeal, PlannedMedicine


class FastType(StrEnum):
    NAVRATRI = "navratri"
    KARVA_CHAUTH = "karva_chauth"
    EKADASHI = "ekadashi"
    RAMADAN = "ramadan"
    JAIN = "jain"
    CHHATH = "chhath"
    CUSTOM = "custom"


class Anchor(StrEnum):
    CLOCK = "clock"
    DAWN = "dawn"
    SUNRISE = "sunrise"
    SUNSET = "sunset"
    MOONRISE = "moonrise"


@dataclass(frozen=True)
class When:
    """A time in a template: a clock time, or an offset from a sun or moon event."""

    anchor: Anchor
    clock: time | None = None
    offset_min: int = 0
    day: int = 0  # The number of days after the date of the fast. The day before is -1.


def at(hour: int, minute: int = 0, day: int = 0) -> When:
    return When(Anchor.CLOCK, time(hour, minute), 0, day)


def after(anchor: Anchor, minutes: int = 0, day: int = 0) -> When:
    return When(anchor, None, minutes, day)


@dataclass(frozen=True)
class MealTemplate:
    when: When
    label: str
    label_hi: str
    food_category: FoodCategory
    carbs_g: float
    breaks_fast: bool = False


@dataclass(frozen=True)
class ActivityTemplate:
    start: When
    end: When
    label: str
    mets: float


@dataclass(frozen=True)
class FastTemplate:
    id: str
    fast_type: FastType
    name: str
    name_hi: str
    word_hi: str
    description: str
    water_allowed: bool
    fast_start: When
    fast_end: When
    meals: tuple[MealTemplate, ...]
    activities: tuple[ActivityTemplate, ...] = ()
    glucose_notes: str = ""
    water_note: str = ""
    # True when the patient eats nothing between the start and the end of the fast.
    no_food_during_fast: bool = True


@dataclass(frozen=True)
class UsualDose:
    """One dose in the patient's usual daily routine."""

    name: str
    dose: float
    time: time


F = FoodCategory

TEMPLATES: tuple[FastTemplate, ...] = (
    FastTemplate(
        id="navratri_one_meal",
        fast_type=FastType.NAVRATRI,
        name="Navratri: one meal a day in the evening",
        name_hi="नवरात्रि: शाम को एक समय भोजन",
        word_hi="व्रत",
        description=(
            "The patient eats one vrat meal each evening and avoids grains. "
            "Water is allowed during the day."
        ),
        water_allowed=True,
        fast_start=at(20, 0, day=-1),
        fast_end=at(19, 30),
        meals=(
            MealTemplate(
                at(19, 30, day=-1),
                "Vrat meal on the previous evening",
                "पिछली शाम का व्रत का भोजन",
                F.FAST_ABSORBING,
                90,
            ),
            MealTemplate(
                at(19, 30),
                "Evening vrat meal that breaks the fast: sabudana khichdi, potato and kuttu puri",
                "व्रत खोलने का शाम का भोजन: साबूदाना खिचड़ी, आलू और कुट्टू की पूरी",
                F.FAST_ABSORBING,
                100,
                breaks_fast=True,
            ),
        ),
        activities=(ActivityTemplate(at(21, 0), at(22, 30), "Garba or dandiya dancing", 5.0),),
        glucose_notes=(
            "Sabudana and potatoes can raise blood sugar quickly. Sweets and fried foods are "
            "common. Evening garba or dandiya dancing increases physical activity."
        ),
    ),
    FastTemplate(
        id="navratri_phalahar",
        fast_type=FastType.NAVRATRI,
        name="Navratri: fruit and milk during the day, with a vrat meal in the evening",
        name_hi="नवरात्रि: दिन में फल और दूध, शाम को व्रत का भोजन",
        word_hi="व्रत",
        description=(
            "The patient eats fruit, milk and vrat foods three times a day and avoids grains. "
            "Water is allowed."
        ),
        water_allowed=True,
        fast_start=after(Anchor.SUNRISE),
        fast_end=at(19, 30),
        meals=(
            MealTemplate(at(8, 0), "Fruit and milk", "फल और दूध", F.FAST_ABSORBING, 25),
            MealTemplate(at(13, 0), "Sabudana khichdi", "साबूदाना खिचड़ी", F.FAST_ABSORBING, 60),
            MealTemplate(
                at(19, 30),
                "Evening vrat meal: kuttu puri, potato and curd",
                "शाम का व्रत का भोजन: कुट्टू की पूरी, आलू और दही",
                F.FAST_ABSORBING,
                80,
                breaks_fast=True,
            ),
        ),
        glucose_notes=(
            "Sabudana and potatoes can raise blood sugar quickly. Sweets and fried foods are "
            "common."
        ),
        no_food_during_fast=False,
    ),
    FastTemplate(
        id="karva_chauth",
        fast_type=FastType.KARVA_CHAUTH,
        name="Karva Chauth: no food or water from sunrise to moonrise",
        name_hi="करवा चौथ: सूर्योदय से चंद्रोदय तक बिना भोजन और पानी के",
        word_hi="व्रत",
        description=(
            "The patient eats sargi before sunrise and then takes no food or water until "
            "moonrise. The patient breaks the fast with water and a meal that often includes "
            "sweets."
        ),
        water_allowed=False,
        fast_start=at(5, 0),
        fast_end=after(Anchor.MOONRISE),
        meals=(
            MealTemplate(at(4, 30), "Sargi before sunrise", "सूर्योदय से पहले सरगी", F.MIXED, 60),
            MealTemplate(
                after(Anchor.MOONRISE, 10),
                "Meal that breaks the fast, with water and sweets",
                "व्रत खोलने का भोजन, पानी और मिठाई के साथ",
                F.FAST_ABSORBING,
                110,
                breaks_fast=True,
            ),
        ),
        activities=(
            ActivityTemplate(at(17, 0), at(18, 30), "Evening puja and household work", 2.5),
        ),
        glucose_notes=(
            "The fast without water lasts about 15 to 16 hours. The meal that breaks the fast "
            "is often large and sweet."
        ),
    ),
    FastTemplate(
        id="ekadashi_phalahar",
        fast_type=FastType.EKADASHI,
        name="Ekadashi: fruit and milk, without grains or beans",
        name_hi="एकादशी: फल और दूध, बिना अनाज और दाल के",
        word_hi="व्रत",
        description=(
            "The patient eats fruit, milk and phalahar foods during the day and avoids grains "
            "and beans. The patient breaks the fast with a parana meal the next morning."
        ),
        water_allowed=True,
        fast_start=after(Anchor.SUNRISE),
        fast_end=at(7, 30, day=1),
        meals=(
            MealTemplate(
                at(8, 0), "Tea with milk and fruit", "दूध वाली चाय और फल", F.FAST_ABSORBING, 20
            ),
            MealTemplate(
                at(13, 0), "Fruit, milk and makhana", "फल, दूध और मखाना", F.FAST_ABSORBING, 30
            ),
            MealTemplate(
                at(19, 30),
                "Evening phalahar: potato or singhara",
                "शाम का फलाहार: आलू या सिंघाड़ा",
                F.FAST_ABSORBING,
                50,
            ),
            MealTemplate(
                at(7, 30, day=1),
                "Parana meal that breaks the fast the next morning",
                "अगली सुबह व्रत खोलने का पारण भोजन",
                F.MIXED,
                60,
                breaks_fast=True,
            ),
        ),
        glucose_notes=(
            "Ekadashi repeats twice a month, so Rozmarra can learn a personal pattern over time."
        ),
        no_food_during_fast=False,
    ),
    FastTemplate(
        id="nirjala_ekadashi",
        fast_type=FastType.EKADASHI,
        name="Nirjala Ekadashi: no food or water from sunrise to the next sunrise",
        name_hi="निर्जला एकादशी: सूर्योदय से अगले सूर्योदय तक बिना भोजन और पानी के",
        word_hi="व्रत",
        description=(
            "The patient takes no food or water from sunrise until after sunrise on the next "
            "day, and then breaks the fast with a parana meal."
        ),
        water_allowed=False,
        fast_start=after(Anchor.SUNRISE),
        fast_end=after(Anchor.SUNRISE, 30, day=1),
        meals=(
            MealTemplate(
                at(20, 0, day=-1), "Meal on the previous evening", "पिछली शाम का भोजन", F.MIXED, 70
            ),
            MealTemplate(
                after(Anchor.SUNRISE, 45, day=1),
                "Parana meal that breaks the fast",
                "व्रत खोलने का पारण भोजन",
                F.MIXED,
                60,
                breaks_fast=True,
            ),
        ),
        glucose_notes="This fast lasts more than 24 hours without water.",
    ),
    FastTemplate(
        id="ramadan",
        fast_type=FastType.RAMADAN,
        name="Ramadan: no food or water from dawn to sunset",
        name_hi="रमज़ान: सुबह होने से सूर्यास्त तक बिना भोजन और पानी के",
        word_hi="रोज़ा",
        description=(
            "The patient eats suhoor before dawn and takes no food or water until sunset. "
            "The patient breaks the fast at sunset with iftar, which often begins with dates "
            "and water."
        ),
        water_allowed=False,
        fast_start=after(Anchor.DAWN),
        fast_end=after(Anchor.SUNSET),
        meals=(
            MealTemplate(
                after(Anchor.DAWN, -30),
                "Suhoor before dawn",
                "सुबह होने से पहले सहरी",
                F.SLOW_ABSORBING,
                70,
            ),
            MealTemplate(
                after(Anchor.SUNSET),
                "Iftar at sunset, starting with dates and water",
                "सूर्यास्त पर इफ़्तार, खजूर और पानी से शुरुआत",
                F.FAST_ABSORBING,
                80,
                breaks_fast=True,
            ),
            MealTemplate(after(Anchor.SUNSET, 75), "Dinner", "रात का खाना", F.MIXED, 60),
        ),
        activities=(
            ActivityTemplate(
                after(Anchor.SUNSET, 105), after(Anchor.SUNSET, 195), "Taraweeh night prayers", 2.5
            ),
        ),
        glucose_notes=(
            "In February and March, the daily fast in India lasts about 12 to 14 hours. Sleep "
            "patterns change because of the meal before dawn and night prayers."
        ),
    ),
    FastTemplate(
        id="jain_upvas",
        fast_type=FastType.JAIN,
        name="Jain upvas: no food for the whole day, with boiled water during daylight",
        name_hi="जैन उपवास: पूरे दिन बिना भोजन के, दिन में केवल उबला पानी",
        word_hi="उपवास",
        description=(
            "The patient eats before sunset on the previous day, takes no food for the whole "
            "day, and breaks the fast after sunrise on the next day."
        ),
        water_allowed=True,
        water_note=(
            "Many people take only boiled water during daylight hours, and some people take "
            "no water at all. If the patient takes no water, please set water to not allowed."
        ),
        fast_start=after(Anchor.SUNSET, -15, day=-1),
        fast_end=after(Anchor.SUNRISE, 48, day=1),
        meals=(
            MealTemplate(
                after(Anchor.SUNSET, -45, day=-1),
                "Meal before sunset on the previous day",
                "पिछले दिन सूर्यास्त से पहले का भोजन",
                F.MIXED,
                70,
            ),
            MealTemplate(
                after(Anchor.SUNRISE, 60, day=1),
                "Parana meal that breaks the fast",
                "उपवास खोलने का पारणा भोजन",
                F.MIXED,
                50,
                breaks_fast=True,
            ),
        ),
        glucose_notes="The fast lasts more than 36 hours. Some fasts last several days.",
    ),
    FastTemplate(
        id="jain_ekasana",
        fast_type=FastType.JAIN,
        name="Jain ekasana: one meal a day, before sunset",
        name_hi="जैन एकासना: सूर्यास्त से पहले दिन में एक बार भोजन",
        word_hi="उपवास",
        description=(
            "The patient eats one meal in the daytime and takes only boiled water at other "
            "times during daylight."
        ),
        water_allowed=True,
        water_note="Many people take only boiled water during daylight hours.",
        fast_start=after(Anchor.SUNSET, -15, day=-1),
        fast_end=at(11, 30),
        meals=(
            MealTemplate(
                after(Anchor.SUNSET, -45, day=-1),
                "Meal before sunset on the previous day",
                "पिछले दिन सूर्यास्त से पहले का भोजन",
                F.MIXED,
                70,
            ),
            MealTemplate(
                at(11, 30),
                "The single meal of the day",
                "दिन का एकमात्र भोजन",
                F.MIXED,
                90,
                breaks_fast=True,
            ),
        ),
    ),
    FastTemplate(
        id="chhath",
        fast_type=FastType.CHHATH,
        name="Chhath Puja: about 36 hours without food or water",
        name_hi="छठ पूजा: लगभग 36 घंटे बिना भोजन और पानी के",
        word_hi="व्रत",
        description=(
            "The patient eats the kharna prasad in the evening and then takes no food or water "
            "for about 36 hours, until after the morning arghya."
        ),
        water_allowed=False,
        fast_start=at(19, 30, day=-1),
        fast_end=after(Anchor.SUNRISE, 30, day=1),
        meals=(
            MealTemplate(
                at(19, 0, day=-1),
                "Kharna prasad: kheer and roti",
                "खरना प्रसाद: खीर और रोटी",
                F.FAST_ABSORBING,
                90,
            ),
            MealTemplate(
                after(Anchor.SUNRISE, 45, day=1),
                "Prasad that breaks the fast, such as thekua",
                "व्रत खोलने का प्रसाद, जैसे ठेकुआ",
                F.FAST_ABSORBING,
                70,
                breaks_fast=True,
            ),
        ),
        activities=(
            ActivityTemplate(
                after(Anchor.SUNSET, -90),
                after(Anchor.SUNSET),
                "Evening arghya at the riverside",
                2.5,
            ),
        ),
        glucose_notes=(
            "This is one of the longest fasts without water, so the dehydration caution is "
            "especially important."
        ),
    ),
    FastTemplate(
        id="custom",
        fast_type=FastType.CUSTOM,
        name="Custom fast: the doctor sets every time",
        name_hi="अपनी पसंद का उपवास: डॉक्टर हर समय तय करते हैं",
        word_hi="उपवास",
        description="The doctor sets the start and end times, the meals and the water setting.",
        water_allowed=True,
        fast_start=at(6, 0),
        fast_end=at(18, 0),
        meals=(
            MealTemplate(at(5, 30), "Meal before the fast", "उपवास से पहले का भोजन", F.MIXED, 60),
            MealTemplate(
                at(18, 0),
                "Meal that breaks the fast",
                "उपवास खोलने का भोजन",
                F.MIXED,
                70,
                breaks_fast=True,
            ),
        ),
    ),
)

TEMPLATES_BY_ID: dict[str, FastTemplate] = {template.id: template for template in TEMPLATES}


def get_template(template_id: str) -> FastTemplate:
    try:
        return TEMPLATES_BY_ID[template_id]
    except KeyError:
        known = ", ".join(TEMPLATES_BY_ID)
        raise KeyError(f"The template '{template_id}' is not known. Known: {known}.") from None


class _Resolver:
    """Turns template times into dates and times for one city."""

    def __init__(self, fast_date: date, city: str):
        self.fast_date = fast_date
        self.city = city
        self.notes: list[str] = []

    def __call__(self, when: When) -> datetime:
        day = self.fast_date + timedelta(days=when.day)
        if when.anchor is Anchor.CLOCK:
            assert when.clock is not None
            return datetime.combine(day, when.clock)
        if when.anchor is Anchor.MOONRISE:
            base, note = moonrise(day, self.city)
            if note not in self.notes:
                self.notes.append(note)
        else:
            sun = sun_times(day, self.city)
            base = {Anchor.DAWN: sun.dawn, Anchor.SUNRISE: sun.sunrise, Anchor.SUNSET: sun.sunset}[
                when.anchor
            ]
        return base + timedelta(minutes=when.offset_min)


def build_plan(
    template_id: str,
    patient_id: str,
    fast_date: date,
    city: str,
    usual_doses: Iterable[UsualDose] = (),
    plan_name: str | None = None,
) -> FastingPlan:
    """Build a draft plan from a template, with the patient's usual medicines unchanged."""
    template = get_template(template_id)
    resolve = _Resolver(fast_date, city)
    meals = sorted(
        (
            PlannedMeal(
                time=resolve(meal.when),
                label=meal.label,
                label_hi=meal.label_hi,
                food_category=meal.food_category,
                carbs_g=meal.carbs_g,
                breaks_fast=meal.breaks_fast,
            )
            for meal in template.meals
        ),
        key=lambda meal: meal.time,
    )
    activities = [
        PlannedActivity(
            start=resolve(activity.start),
            end=resolve(activity.end),
            label=activity.label,
            mets=activity.mets,
        )
        for activity in template.activities
    ]
    notes = list(resolve.notes)
    if template.water_note:
        notes.append(template.water_note)
    plan = FastingPlan(
        patient_id=patient_id,
        plan_name=plan_name or "Plan A: usual medicines",
        template_id=template.id,
        fast_type=template.fast_type.value,
        date=fast_date,
        city=city,
        fast_start=resolve(template.fast_start),
        fast_end=resolve(template.fast_end),
        water_allowed=template.water_allowed,
        meals=meals,
        activities=activities,
        notes=notes,
    )
    plan.medicines = usual_medicines_in_window(plan, usual_doses)
    return plan


def usual_medicines_in_window(plan: FastingPlan, usual_doses: Iterable[UsualDose]):
    """List every usual dose that falls inside the period that the twin simulates."""
    doses: list[PlannedMedicine] = []
    first_day = plan.window_start.date()
    last_day = plan.window_end.date()
    for usual in usual_doses:
        day = first_day
        while day <= last_day:
            moment = datetime.combine(day, usual.time)
            if plan.window_start <= moment <= plan.window_end:
                doses.append(
                    PlannedMedicine(
                        name=usual.name,
                        dose=usual.dose,
                        time=moment,
                        usual_dose=usual.dose,
                        usual_time=moment,
                    )
                )
            day += timedelta(days=1)
    return sorted(doses, key=lambda dose: dose.time)
