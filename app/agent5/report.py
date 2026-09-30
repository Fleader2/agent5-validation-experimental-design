"""Determining Agent 5's own overall status and full-workflow sufficiency.

``determine_overall_status`` is the one place the whole run's own single, most-informative
status is decided -- deliberately centralized so no two call sites can ever disagree, mirroring
``app.agent3.report.determine_overall_status``/``app.agent4.report.determine_agent5_sufficiency``'s
own identical precedent on the sibling repositories.
"""

from __future__ import annotations

from app.agent5.types import (
    ExperimentalDesignFinding,
    GeneralizationCategory,
    GeneralizationFinding,
    ValidationResult,
    ValidationStatus,
)


def determine_overall_status(
    validation_result: ValidationResult | None,
    generalization_findings: tuple[GeneralizationFinding, ...],
    experimental_design_findings: tuple[ExperimentalDesignFinding, ...],
) -> ValidationStatus:
    """Precedence (most to least severe): a load/simulation failure always wins; then
    insufficient validation data; then an overfit warning; then a fully-limited experimental-
    design outcome; otherwise ``SUCCESS``."""
    if validation_result is None or not validation_result.simulated:
        return ValidationStatus.VALIDATION_FAILED
    if any(
        f.category is GeneralizationCategory.INSUFFICIENT_VALIDATION_DATA
        for f in generalization_findings
    ):
        return ValidationStatus.INSUFFICIENT_VALIDATION_DATA
    if any(f.category is GeneralizationCategory.OVERFIT_SUSPECTED for f in generalization_findings):
        return ValidationStatus.OVERFIT_WARNING
    if any(f.finding_id == "all-candidates-uninformative" for f in experimental_design_findings):
        return ValidationStatus.EXPERIMENT_DESIGN_LIMITED
    return ValidationStatus.SUCCESS


def determine_full_workflow_sufficiency(status: ValidationStatus) -> tuple[bool, str]:
    """Whether this report completes a usable first pass of the full five-agent workflow --
    never a claim that the underlying biology is correct, only that the workflow chain
    (Agent 1 through Agent 5) produced a traceable, structured end-to-end result."""
    if status is ValidationStatus.INVALID_REQUEST:
        return (
            False,
            "The request itself was rejected before any validation was attempted -- there is "
            "no workflow-completing content beyond the rejection reason itself.",
        )
    if status is ValidationStatus.VALIDATION_FAILED:
        return (
            False,
            "The calibrated model could not even be simulated against the held-out "
            "observations -- there is no workflow-completing content beyond the failure "
            "message itself.",
        )
    if status is ValidationStatus.INSUFFICIENT_VALIDATION_DATA:
        return (
            True,
            "No generalization conclusion could be drawn from too few held-out points, but "
            "this is fully disclosed, and the experimental-design half of this report is still "
            "a complete, traceable first pass of the full workflow.",
        )
    if status is ValidationStatus.OVERFIT_WARNING:
        return (
            True,
            "Held-out performance is worse than training performance -- a genuine, disclosed "
            "generalization concern -- but the full five-agent chain still produced a complete, "
            "traceable end-to-end result, including ranked next-experiment recommendations.",
        )
    if status is ValidationStatus.EXPERIMENT_DESIGN_LIMITED:
        return (
            True,
            "Validation itself was not the limiting factor, but no candidate experiment could "
            "be meaningfully connected to a prediction given the current calibrated model -- "
            "fully disclosed rather than presented as a ranked, actionable recommendation set.",
        )
    return (
        True,
        "The calibrated model validated against held-out data, generalization and uncertainty "
        "were assessed, and candidate experiments were scored and ranked with full provenance "
        "-- a complete, traceable first pass of the full five-agent workflow.",
    )


__all__ = ["determine_full_workflow_sufficiency", "determine_overall_status"]
