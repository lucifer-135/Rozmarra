"""The split of real patients into folds, so that the same person never appears in two groups.

Rozmarra assigns each real person to one of five folds with a fixed hash of the person's
identifier. Two ShanghaiT2DM recording periods of the same person, such as "SH-2001-0"
and "SH-2001-1", always share a fold. Fold 0 is the test group for the synthetic fasting
test: virtual test patients come only from real patients in fold 0 (docs/prd.md,
Section 15.1). The real-data evaluation uses all five folds for cross-validation.
"""

from __future__ import annotations

import zlib

FOLDS = 5
TEST_FOLD = 0


def person_of(patient_id: str) -> str:
    """The person behind a patient identifier, for example "SH-2001" for "SH-2001-1"."""
    parts = patient_id.split("-")
    return "-".join(parts[:2]) if patient_id.startswith("SH-") else patient_id


def fold_of(patient_id: str) -> int:
    return zlib.crc32(person_of(patient_id).encode("utf-8")) % FOLDS


def is_test(patient_id: str) -> bool:
    return fold_of(patient_id) == TEST_FOLD
