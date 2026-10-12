"""Virtual patients: synthetic health records joined with twins fitted on real patients.

Each virtual patient (docs/techstack.md, Section 5.8) has:
- a synthetic Indian health record from the record generator;
- a donor twin, chosen from the real patients in the right group (training or test).
  Donors with a fasting glucose close to the record's fasting glucose are more likely,
  so that the twin parameters agree with the record;
- a "true" parameter set, drawn around the donor's fitted parameters with the donor's
  uncertainty. The true parameters generate the synthetic data;
- an "estimated" parameter set, which is the donor's fitted mean. The prediction models
  use the estimated parameters, because a real twin is only an estimate of the patient.

The sulfonylurea effect (decision of 12 October 2026): the real data identified this
effect poorly (model card, Section 5.5). Clinical studies show that sulfonylureas cause
low blood sugar during fasting. Virtual patients and demo patients therefore use the
population value γ_su = 3 as the estimate, and their true value is drawn around it with
a log-scale standard deviation of 0.5. The evaluation will repeat the analysis with the
weaker fitted values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from rozmarra.ehr.records import PatientRecord
from rozmarra.synth.split import is_test
from rozmarra.twin.model import CENTRES, FITTED, FITTED_NAMES
from rozmarra.twin.profiles import counter_regulation_factor
from rozmarra.twin.simulate import TwinProfile

GAMMA_SU_LOG_SD = 0.5
DONOR_GLUCOSE_SD = 15.0  # mg/dL, how closely the donor's fasting level should match
TRUE_LOG_SD_CAP = 0.3
_PRIOR_SD = {p.name: p.log_sd for p in FITTED}
_BOUNDS = {p.name: (np.log(p.low), np.log(p.high)) for p in FITTED}


@dataclass
class VirtualTwin:
    record: PatientRecord
    donor_id: str
    profile: TwinProfile  # The estimate: the donor's fitted mean and covariance
    true_values: dict[str, float]  # The parameters that generate the synthetic data

    @property
    def estimated_values(self) -> dict[str, float]:
        return {
            n: float(np.exp(v))
            for n, v in zip(self.profile.names, self.profile.log_mean, strict=True)
        }


def training_twins(twins: list[dict]) -> list[dict]:
    return [t for t in twins if not is_test(t["patient_id"])]


def held_out_twins(twins: list[dict]) -> list[dict]:
    return [t for t in twins if is_test(t["patient_id"])]


def choose_donor(
    fasting_glucose: float, twins: list[dict], rng: np.random.Generator | None = None
) -> dict:
    """Choose a donor twin. Without a random generator, the closest donor is chosen."""
    levels = np.array([t["G_b"] for t in twins])
    if rng is None:
        return twins[int(np.argmin(np.abs(levels - fasting_glucose)))]
    weights = np.exp(-0.5 * ((levels - fasting_glucose) / DONOR_GLUCOSE_SD) ** 2) + 1e-6
    return twins[int(rng.choice(len(twins), p=weights / weights.sum()))]


def donor_profile(record: PatientRecord, donor: dict, day: date) -> TwinProfile:
    """The estimated twin of a synthetic patient: the donor's fitted parameters and uncertainty."""
    names = FITTED_NAMES
    mean = np.log([CENTRES[n] for n in names])
    cov = np.diag([_PRIOR_SD[n] ** 2 for n in names])
    donor_names = donor["fitted_names"]
    donor_cov = np.asarray(donor["log_cov"])
    for i, name in enumerate(names):
        if name in donor_names and name != "gamma_su":
            a = donor_names.index(name)
            mean[i] = donor["log_mean"][a]
            for j, other in enumerate(names):
                if other in donor_names and other != "gamma_su":
                    cov[i, j] = donor_cov[a, donor_names.index(other)]
    g = names.index("gamma_su")
    mean[g] = np.log(CENTRES["gamma_su"])
    cov[g, :] = cov[:, g] = 0.0
    cov[g, g] = GAMMA_SU_LOG_SD**2
    return TwinProfile(
        G_b=record.fasting_glucose_mg_dl,
        I_b=float(np.clip(record.fasting_insulin_uu_ml, 5, 25)),
        body_weight=record.weight_kg,
        egfr=record.egfr,
        cr_factor=counter_regulation_factor(record, day),
        cyp_factor=record.cyp2c9_clearance_factor,
        names=names,
        log_mean=mean,
        log_cov=cov,
        source=f"donor twin {donor['patient_id']}",
    )


def true_parameters(profile: TwinProfile, rng: np.random.Generator) -> dict[str, float]:
    """Draw the true parameters around the estimate.

    Poorly identified parameters have an uncertainty as wide as the prior, which would push
    many virtual patients to the limits of the ranges. The draw therefore keeps the
    correlation of the donor's uncertainty but caps each standard deviation at
    TRUE_LOG_SD_CAP on the log scale.
    """
    cov = np.asarray(profile.log_cov)
    sd = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    corr = cov / np.outer(sd, sd)
    capped = np.minimum(sd, TRUE_LOG_SD_CAP)
    draw = rng.multivariate_normal(
        profile.log_mean, corr * np.outer(capped, capped), check_valid="ignore", method="eigh"
    )
    values = {}
    for i, name in enumerate(profile.names):
        low, high = _BOUNDS[name]
        values[name] = float(np.exp(np.clip(draw[i], low, high)))
    return values


def virtual_twin(
    record: PatientRecord, twins: list[dict], day: date, rng: np.random.Generator
) -> VirtualTwin:
    donor = choose_donor(record.fasting_glucose_mg_dl, twins, rng)
    profile = donor_profile(record, donor, day)
    return VirtualTwin(record, donor["patient_id"], profile, true_parameters(profile, rng))


def demo_twin(record: PatientRecord, twins: list[dict], day: date) -> VirtualTwin:
    """The twin of a demo patient: the closest training donor, with no random draw."""
    donor = choose_donor(record.fasting_glucose_mg_dl, training_twins(twins))
    profile = donor_profile(record, donor, day)
    return VirtualTwin(
        record,
        donor["patient_id"],
        profile,
        {n: float(np.exp(v)) for n, v in zip(profile.names, profile.log_mean, strict=True)},
    )
