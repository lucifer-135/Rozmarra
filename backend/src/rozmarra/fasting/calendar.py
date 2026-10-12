"""Festival dates and the times of dawn, sunrise and sunset in Indian cities.

The sun times use the solar position equations of the United States National
Oceanic and Atmospheric Administration (NOAA). They are accurate to about two
minutes, which is enough for a fasting plan. All times are in Indian Standard Time.

Moonrise is harder to calculate. For Karva Chauth, Rozmarra uses a published
moonrise time for Delhi, and the doctor can change it to the local time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

IST_OFFSET_MIN = 330

# Latitude and longitude in degrees for the cities that the synthetic records use.
CITIES: dict[str, tuple[float, float]] = {
    "Delhi": (28.61, 77.21),
    "Mumbai": (19.08, 72.88),
    "Kolkata": (22.57, 88.36),
    "Chennai": (13.08, 80.27),
    "Bengaluru": (12.97, 77.59),
    "Hyderabad": (17.39, 78.49),
    "Ahmedabad": (23.02, 72.57),
    "Pune": (18.52, 73.86),
    "Jaipur": (26.91, 75.79),
    "Lucknow": (26.85, 80.95),
    "Varanasi": (25.32, 82.97),
    "Patna": (25.59, 85.14),
    "Bhopal": (23.26, 77.41),
    "Indore": (22.72, 75.86),
    "Surat": (21.17, 72.83),
    "Kochi": (9.93, 76.27),
    "Dhanbad": (23.80, 86.43),
}

# Festival dates in 2026 and 2027 (docs/prd.md, Section 4).
SHARAD_NAVRATRI_2026 = (date(2026, 10, 11), date(2026, 10, 20))
KARVA_CHAUTH_2026 = date(2026, 10, 28)
# The exact dates of Ramadan depend on the sighting of the moon.
RAMADAN_2027_EXPECTED = (date(2027, 2, 9), date(2027, 3, 9))

# The published moonrise time in Delhi on Karva Chauth 2026 (docs/prd.md, Section 4).
KARVA_CHAUTH_2026_MOONRISE_DELHI = time(20, 14)

# Zenith angles in degrees. Fajr (dawn) uses the sun at 18 degrees below the horizon,
# which is the convention that many timetables in India use.
ZENITH_SUNRISE_SUNSET = 90.833
ZENITH_DAWN = 108.0


@dataclass(frozen=True)
class SunTimes:
    dawn: datetime
    sunrise: datetime
    sunset: datetime


def _solar_terms(day: date) -> tuple[float, float]:
    """Return the equation of time (minutes) and the solar declination (radians) at noon."""
    n = day.timetuple().tm_yday
    days_in_year = 366 if day.year % 4 == 0 else 365
    gamma = 2 * math.pi / days_in_year * (n - 1)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    return eqtime, decl


def _event(day: date, latitude: float, longitude: float, zenith: float, rising: bool) -> datetime:
    eqtime, decl = _solar_terms(day)
    lat = math.radians(latitude)
    cos_ha = math.cos(math.radians(zenith)) / (math.cos(lat) * math.cos(decl)) - math.tan(
        lat
    ) * math.tan(decl)
    hour_angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
    sign = 1 if rising else -1
    utc_minutes = 720 - 4 * (longitude + sign * hour_angle) - eqtime
    local = datetime.combine(day, time()) + timedelta(minutes=utc_minutes + IST_OFFSET_MIN)
    return local.replace(second=0, microsecond=0)


def sun_times(day: date, city: str) -> SunTimes:
    """Return the times of dawn, sunrise and sunset in a city, in Indian Standard Time."""
    if city not in CITIES:
        raise KeyError(f"The city '{city}' is not known. Known cities: {', '.join(CITIES)}.")
    latitude, longitude = CITIES[city]
    return SunTimes(
        dawn=_event(day, latitude, longitude, ZENITH_DAWN, rising=True),
        sunrise=_event(day, latitude, longitude, ZENITH_SUNRISE_SUNSET, rising=True),
        sunset=_event(day, latitude, longitude, ZENITH_SUNRISE_SUNSET, rising=False),
    )


def moonrise(day: date, city: str) -> tuple[datetime, str]:
    """Return a moonrise time for Karva Chauth and a note about its source."""
    moon = datetime.combine(day, KARVA_CHAUTH_2026_MOONRISE_DELHI)
    if day == KARVA_CHAUTH_2026 and city == "Delhi":
        return moon, "The moonrise time is the published time for Delhi."
    return moon, (
        "The moonrise time is the published time for Delhi on Karva Chauth 2026. "
        "Please change it to the local moonrise time."
    )
