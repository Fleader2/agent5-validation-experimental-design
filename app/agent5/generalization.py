"""Generalization/overfitting analysis, and surfacing Agent 4's own dominant-uncertainty
parameters (``validation-v1``).

Every finding here is either a pure read of Agent 4's own already-declared
``identifiability_findings`` (never a new judgment about calibration quality) or a comparison
of validation performance against Agent 4's own already-reported training performance (never a
re-fit).
"""

from __future__ import annotations

from app.agent5.handoff import Agent4ReportView
from app.agent5.types import (
    FindingSeverity,
    GeneralizationCategory,
    GeneralizationFinding,
    ValidationObservationSet,
    ValidationResult,
)

#: Below this many total held-out data points, Agent 5 refuses to draw any generalization
#: conclusion -- one or even zero points cannot distinguish "generalizes well" from "got lucky."
MIN_VALIDATION_POINTS = 2


def n_validation_points(validation_observations: ValidationObservationSet) -> int:
    return sum(len(o.values) for o in validation_observations.observations)


def insufficient_validation_data_finding(n_points: int) -> GeneralizationFinding | None:
    if n_points >= MIN_VALIDATION_POINTS:
        return None
    return GeneralizationFinding(
        finding_id="insufficient-validation-data",
        category=GeneralizationCategory.INSUFFICIENT_VALIDATION_DATA,
        severity=FindingSeverity.CRITICAL,
        summary=f"Only {n_points} held-out validation point(s) supplied.",
        explanation=(
            f"At least {MIN_VALIDATION_POINTS} held-out points are required to say anything "
            "meaningful about generalization -- reporting this honestly rather than declaring "
            "success or failure from too little data."
        ),
    )


def validation_simulation_failed_finding(
    validation_result: ValidationResult,
) -> GeneralizationFinding | None:
    if validation_result.simulated:
        return None
    return GeneralizationFinding(
        finding_id="validation-simulation-failed",
        category=GeneralizationCategory.VALIDATION_SIMULATION_FAILED,
        severity=FindingSeverity.CRITICAL,
        summary="The calibrated model could not be simulated against the held-out observations.",
        explanation=validation_result.message or "No further detail was reported.",
    )


def overfit_finding(
    validation_result: ValidationResult, threshold: float
) -> GeneralizationFinding | None:
    if validation_result.overfit_ratio is None:
        return None
    ratio = validation_result.overfit_ratio
    if ratio > threshold:
        return GeneralizationFinding(
            finding_id="overfit-suspected",
            category=GeneralizationCategory.OVERFIT_SUSPECTED,
            severity=FindingSeverity.ERROR,
            summary=(
                f"Validation RMSE is {ratio:.2f}x training RMSE, exceeding the "
                f"{threshold:g}x threshold."
            ),
            explanation=(
                "The calibrated model fits its own training data substantially better than "
                "held-out data it never saw -- a classic overfitting signature. The fitted "
                "values themselves are not altered by this finding; it is a disclosure, not a "
                "correction."
            ),
        )
    return GeneralizationFinding(
        finding_id="generalizes-well",
        category=GeneralizationCategory.GENERALIZES_WELL,
        severity=FindingSeverity.INFO,
        summary=(
            f"Validation RMSE is {ratio:.2f}x training RMSE, within the {threshold:g}x threshold."
        ),
        explanation=(
            "Held-out performance is comparable to training performance -- no overfitting "
            "signature detected by this modest ratio-based check."
        ),
    )


#: Every Agent 4 identifiability category Agent 5 treats as evidence a parameter dominates the
#: model's remaining uncertainty.
_UNCERTAINTY_CATEGORIES = frozenset(
    {"BOUND_HIT", "LOW_SENSITIVITY", "HIGH_CORRELATION", "DEGENERATE_OBJECTIVE"}
)


def dominant_uncertainty_parameter_ids(agent4_report: Agent4ReportView) -> tuple[str, ...]:
    """Every target id appearing in any Agent 4 identifiability finding whose category is one
    of ``_UNCERTAINTY_CATEGORIES`` -- deduplicated, sorted for determinism. A pure read of
    Agent 4's own already-declared findings, never a new judgment."""
    ids: set[str] = set()
    for finding in agent4_report.calibration.identifiability_findings:
        if finding.category in _UNCERTAINTY_CATEGORIES:
            ids.update(finding.related_target_ids)
    return tuple(sorted(ids))


def dominant_uncertainty_finding(agent4_report: Agent4ReportView) -> GeneralizationFinding | None:
    ids = dominant_uncertainty_parameter_ids(agent4_report)
    if not ids:
        return None
    return GeneralizationFinding(
        finding_id="dominant-uncertainty-parameters",
        category=GeneralizationCategory.DOMINANT_UNCERTAINTY_PARAMETER,
        severity=FindingSeverity.WARNING,
        summary=(
            f"{len(ids)} calibrated target(s) dominate the model's remaining uncertainty, per "
            "Agent 4's own identifiability findings."
        ),
        explanation=(
            "Carried through unchanged from Agent 4's own already-declared BOUND_HIT/"
            "LOW_SENSITIVITY/HIGH_CORRELATION/DEGENERATE_OBJECTIVE findings -- Agent 5 never "
            "recomputes Agent 4's own identifiability logic, only aggregates which targets it "
            "already flagged, to inform which measurements would be most valuable next."
        ),
        related_parameter_ids=ids,
    )


def run_generalization_analysis(
    validation_result: ValidationResult,
    validation_observations: ValidationObservationSet,
    agent4_report: Agent4ReportView,
    *,
    overfit_ratio_threshold: float,
) -> tuple[GeneralizationFinding, ...]:
    """The full Version 1 generalization sweep, in a fixed, deterministic order."""
    findings: list[GeneralizationFinding] = []

    n_points = n_validation_points(validation_observations)
    insufficient = insufficient_validation_data_finding(n_points)
    if insufficient is not None:
        findings.append(insufficient)
        return tuple(findings)

    sim_failed = validation_simulation_failed_finding(validation_result)
    if sim_failed is not None:
        findings.append(sim_failed)
        return tuple(findings)

    overfit = overfit_finding(validation_result, overfit_ratio_threshold)
    if overfit is not None:
        findings.append(overfit)

    dominant = dominant_uncertainty_finding(agent4_report)
    if dominant is not None:
        findings.append(dominant)

    return tuple(findings)


__all__ = [
    "MIN_VALIDATION_POINTS",
    "dominant_uncertainty_finding",
    "dominant_uncertainty_parameter_ids",
    "insufficient_validation_data_finding",
    "n_validation_points",
    "overfit_finding",
    "run_generalization_analysis",
    "validation_simulation_failed_finding",
]
