"""The physiology twin: parameters, equations and starting state.

The model extends the Bergman minimal model (1979) with gut absorption in the style
of Dalla Man and colleagues (2007) and with medicine effects (docs/techstack.md,
Section 5.2). The meal, insulin and medicine inputs do not depend on glucose, so
Rozmarra calculates them in advance (twin.medicines). The solver integrates three
states for each parameter set: plasma glucose G, insulin action X and plasma insulin I.

Every array in this module has one value for each parameter set (the batch), so one
call can run many parameter sets or many forecast windows at the same time.

Changes to the starting design in docs/techstack.md:
- The term k_hgp × (I − I_b) adds the direct effect of insulin on glucose production
  by the liver. Section 5.4 of docs/techstack.md suggests this term, because the first
  check found that basal insulin had too weak an effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

# Starting values and fixed values from docs/techstack.md, Section 5.3.
P2 = 0.02  # Speed of insulin action, per minute
N_CLEARANCE = 0.14  # Insulin clearance, per minute
V_G = 1.6  # Glucose distribution volume, dL/kg
V_I = 120.0  # Insulin distribution volume, mL/kg
F_ABSORBED = 0.9  # Share of meal glucose that is absorbed
A_F = 0.15  # Fall in glucose production during a long fast
TAU_F = 720.0  # Time constant of that fall, minutes
E_MET = 0.2  # Effect of metformin on glucose production
E_DPP4 = 0.2  # Effect of a DPP-4 inhibitor on insulin release
K_R = 0.007  # Glucose loss in the urine, per minute
EC50_SU = 0.5  # Sulfonylurea activity at half of the full effect
E_A = 0.005  # Effect of activity on glucose uptake, per minute per unit of activity
C_CR = 0.05  # Counter-regulation response, per minute
G_CR = 65.0  # Glucose level below which counter-regulation starts, mg/dL
CR_REDUCED = 0.3  # Factor for unawareness of low blood sugar or diabetes for over 15 years
K_HGP = 0.02  # Direct effect of insulin on liver glucose production, mg/dL/min per µU/mL
I_B_DEFAULT = 10.0  # Fasting insulin when the record has none, µU/mL
I_B_RANGE = (5.0, 25.0)
X_MIN_FACTOR = -0.5  # The trend-matched start keeps X_0 at or above -0.5 × S_G
X_MAX = 0.05  # and at or below 0.05 per minute.
G_FLOOR = 10.0  # The solver keeps glucose at or above this value, mg/dL


@dataclass(frozen=True)
class FittedParameter:
    name: str
    centre: float
    low: float
    high: float

    @property
    def log_sd(self) -> float:
        """The prior standard deviation on the log scale: a quarter of the log range."""
        return float(np.log(self.high / self.low) / 4)


# The parameters that the fit estimates for each patient, with the starting value and
# the range from docs/techstack.md, Section 5.3.
FITTED = (
    FittedParameter("S_G", 0.015, 0.005, 0.035),
    FittedParameter("S_I", 2e-4, 0.3e-4, 8e-4),
    FittedParameter("beta", 0.04, 0.005, 0.15),
    FittedParameter("k_abs_factor", 1.0, 0.5, 2.0),
    FittedParameter("meal_factor", 1.0, 0.5, 2.0),
    FittedParameter("gamma_su", 8.0, 2.0, 15.0),
)
FITTED_NAMES = tuple(p.name for p in FITTED)


@dataclass
class Parameters:
    """The parameters of a batch of twins. Each field is an array of length B or a number."""

    G_b: np.ndarray
    I_b: np.ndarray
    body_weight: np.ndarray
    renal_factor: np.ndarray  # min(eGFR / 90, 1)
    S_G: np.ndarray = field(default_factory=lambda: np.array([0.015]))
    S_I: np.ndarray = field(default_factory=lambda: np.array([2e-4]))
    beta: np.ndarray = field(default_factory=lambda: np.array([0.04]))
    k_abs_factor: np.ndarray = field(default_factory=lambda: np.array([1.0]))
    meal_factor: np.ndarray = field(default_factory=lambda: np.array([1.0]))
    gamma_su: np.ndarray = field(default_factory=lambda: np.array([8.0]))
    cr_factor: np.ndarray = field(default_factory=lambda: np.array([1.0]))
    k_hgp: float = K_HGP
    a_f: float = A_F
    P0: np.ndarray | None = None

    def __post_init__(self):
        for name in (
            "G_b",
            "I_b",
            "body_weight",
            "renal_factor",
            "S_G",
            "S_I",
            "beta",
            "k_abs_factor",
            "meal_factor",
            "gamma_su",
            "cr_factor",
        ):
            setattr(self, name, np.atleast_1d(np.asarray(getattr(self, name), dtype=float)))

    @property
    def insulin_scale(self) -> np.ndarray:
        """Converts absorbed insulin in units per minute into µU/mL per minute."""
        return 1e6 / (V_I * self.body_weight)

    def with_fitted(self, values: dict[str, np.ndarray]) -> Parameters:
        return replace(self, **{k: np.atleast_1d(v) for k, v in values.items()}, P0=None)


@dataclass
class Forcing:
    """The inputs at each minute, as arrays of shape (B, L) or (L,).

    ra: meal glucose appearance, mg/dL per minute
    ri: absorbed injected insulin, units per minute
    secretagogue, metformin, dpp4, sglt2: summed activity of each group of medicines
    mets: physical activity in METs
    since_meal: minutes since the last meal
    """

    ra: np.ndarray
    ri: np.ndarray
    secretagogue: np.ndarray
    metformin: np.ndarray
    dpp4: np.ndarray
    sglt2: np.ndarray
    mets: np.ndarray
    since_meal: np.ndarray

    FIELDS = ("ra", "ri", "secretagogue", "metformin", "dpp4", "sglt2", "mets", "since_meal")

    def column(self, k: int) -> tuple[np.ndarray, ...]:
        return tuple(getattr(self, name)[..., k] for name in self.FIELDS)

    def windows(self, starts: np.ndarray, length: int) -> Forcing:
        """Cut windows of the same length from one timeline. The result has the shape (W, L)."""
        index = np.asarray(starts)[:, None] + np.arange(length)[None, :]
        return Forcing(*(getattr(self, name)[index] for name in self.FIELDS))

    def tiled(self, copies: int) -> Forcing:
        """Repeat every row, so that several parameter sets can share the same windows."""
        return Forcing(
            *(np.tile(np.atleast_2d(getattr(self, n)), (copies, 1)) for n in self.FIELDS)
        )

    @property
    def length(self) -> int:
        return self.ra.shape[-1]


def secretagogue_effect(activity: np.ndarray) -> np.ndarray:
    return activity / (EC50_SU + activity)


def urine_threshold(sglt2_activity: np.ndarray) -> np.ndarray:
    """The glucose level above which glucose passes into the urine, in mg/dL."""
    return 180.0 - 90.0 * np.minimum(sglt2_activity, 1.0)


def activity_level(mets: np.ndarray) -> np.ndarray:
    return np.clip((mets - 1.0) / 5.0, 0.0, 2.0)


def fasting_factor(since_meal: np.ndarray, a_f: float = A_F) -> np.ndarray:
    return 1.0 - a_f * (1.0 - np.exp(-since_meal / TAU_F))


def derivatives(G, X, I, p: Parameters, inputs: tuple[np.ndarray, ...]):
    """The rates of change of G, X and I (docs/techstack.md, Section 5.2)."""
    ra, ri, secretagogue, metformin, dpp4, sglt2, mets, since_meal = inputs
    production = p.P0 * fasting_factor(since_meal, p.a_f) * (1 - E_MET * np.minimum(metformin, 1))
    production = np.clip(production - p.k_hgp * (I - p.I_b), 0.0, 2.0 * p.P0)
    urine = K_R * p.renal_factor * np.maximum(G - urine_threshold(sglt2), 0.0)
    counter = C_CR * p.cr_factor * np.maximum(G_CR - G, 0.0)
    dG = production - (p.S_G + X) * G + ra - urine - E_A * activity_level(mets) * G + counter
    dX = -P2 * X + P2 * p.S_I * (I - p.I_b)
    boost = 1 + E_DPP4 * np.minimum(dpp4, 1) * (G > p.G_b)
    secretion = p.beta * (G - p.G_b) * boost + p.gamma_su * secretagogue_effect(secretagogue)
    dI = -N_CLEARANCE * (I - p.I_b) + secretion + p.insulin_scale * ri
    return dG, dX, dI


def steady_insulin(p: Parameters, ri: np.ndarray, secretagogue: np.ndarray) -> np.ndarray:
    """Plasma insulin at glucose G_b when the inputs change slowly."""
    extra = p.gamma_su * secretagogue_effect(secretagogue) + p.insulin_scale * ri
    return np.maximum(p.I_b + extra / N_CLEARANCE, 0.0)


def calibrate_production(p: Parameters, morning: tuple[np.ndarray, ...]) -> Parameters:
    """Choose P0 so that glucose does not change at G_b on a usual morning before breakfast.

    The morning inputs come from the usual plan: the medicine and insulin levels at the
    time of the fasting blood test, after an overnight fast and with no meal absorbing.
    """
    _, ri, secretagogue, metformin, _, sglt2, mets, since_meal = morning
    I_m = steady_insulin(p, ri, secretagogue)
    X_m = p.S_I * (I_m - p.I_b)
    G = p.G_b
    urine = K_R * p.renal_factor * np.maximum(G - urine_threshold(sglt2), 0.0)
    counter = C_CR * p.cr_factor * np.maximum(G_CR - G, 0.0)
    uptake = (p.S_G + X_m) * G + urine + E_A * activity_level(mets) * G - counter
    scale = fasting_factor(since_meal, p.a_f) * (1 - E_MET * np.minimum(metformin, 1))
    P0 = (uptake + p.k_hgp * (I_m - p.I_b)) / scale
    return replace(p, P0=np.maximum(P0, 1e-6))


def trend_matched_start(
    p: Parameters, glucose: np.ndarray, slope: np.ndarray, inputs: tuple[np.ndarray, ...]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The starting state of a forecast (docs/techstack.md, Section 5.7).

    G starts at the latest CGM value. Rozmarra chooses the insulin action X_0 so that the
    starting slope of glucose equals the CGM trend of the last 30 minutes, and then sets
    I_0 = I_b + X_0 / S_I, which agrees with X_0. The solution includes the liver term,
    because the liver term also depends on I_0.
    """
    ra, ri, secretagogue, metformin, dpp4, sglt2, mets, since_meal = inputs
    G = np.asarray(glucose, dtype=float)
    base = p.P0 * fasting_factor(since_meal, p.a_f) * (1 - E_MET * np.minimum(metformin, 1))
    urine = K_R * p.renal_factor * np.maximum(G - urine_threshold(sglt2), 0.0)
    counter = C_CR * p.cr_factor * np.maximum(G_CR - G, 0.0)
    rest = ra - urine - E_A * activity_level(mets) * G + counter
    X0 = (base - p.S_G * G + rest - slope) / (G + p.k_hgp / p.S_I)
    X0 = np.clip(X0, X_MIN_FACTOR * p.S_G, X_MAX)
    I0 = np.maximum(p.I_b + X0 / p.S_I, 0.0)
    return G, X0, I0


def steady_start(p: Parameters, inputs: tuple[np.ndarray, ...]):
    """A starting state at G_b with insulin at its slowly changing level."""
    _, ri, secretagogue, *_ = inputs
    I0 = steady_insulin(p, ri, secretagogue)
    return np.broadcast_to(p.G_b, I0.shape).astype(float), p.S_I * (I0 - p.I_b), I0
