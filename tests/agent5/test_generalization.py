"""Tests for ``app.agent5.generalization``: overfit detection and dominant-uncertainty
aggregation."""

from __future__ import annotations

from app.agent5.generalization import (
    dominant_uncertainty_finding,
    dominant_uncertainty_parameter_ids,
    insufficient_validation_data_finding,
    n_validation_points,
    overfit_finding,
    validation_simulation_failed_finding,
)
from app.agent5.types import (
    GeneralizationCategory,
    ValidationObservation,
    ValidationObservationKind,
    ValidationObservationSet,
    ValidationResult,
)
from tests.agent5.fixtures import (
    ONE_PARAMETER_ANTIMONY,
    minimal_agent2_model_dict,
    minimal_agent4_report_dict,
    parsed_handoff,
)


def test_insufficient_validation_data_below_threshold():
    obs_set = ValidationObservationSet(
        observation_set_id="vset",
        observations=(
            ValidationObservation(
                observation_id="v1",
                target_species_id="S1",
                kind=ValidationObservationKind.TIME_SERIES,
                time_points=(0.0,),
                values=(10.0,),
            ),
        ),
    )
    assert n_validation_points(obs_set) == 1
    finding = insufficient_validation_data_finding(1)
    assert finding is not None
    assert finding.category is GeneralizationCategory.INSUFFICIENT_VALIDATION_DATA


def test_insufficient_validation_data_none_when_enough_points():
    assert insufficient_validation_data_finding(5) is None


def test_validation_simulation_failed_finding():
    result = ValidationResult(
        validation_run_id="r1",
        simulated=False,
        message="boom",
        metrics=(),
        validation_residuals=(),
        overfit_ratio=None,
    )
    finding = validation_simulation_failed_finding(result)
    assert finding is not None
    assert "boom" in finding.explanation


def test_overfit_finding_flags_ratio_above_threshold():
    result = ValidationResult(
        validation_run_id="r1",
        simulated=True,
        message=None,
        metrics=(),
        validation_residuals=(),
        overfit_ratio=10.0,
    )
    finding = overfit_finding(result, threshold=3.0)
    assert finding is not None
    assert finding.category is GeneralizationCategory.OVERFIT_SUSPECTED


def test_overfit_finding_reports_generalizes_well_below_threshold():
    result = ValidationResult(
        validation_run_id="r1",
        simulated=True,
        message=None,
        metrics=(),
        validation_residuals=(),
        overfit_ratio=1.2,
    )
    finding = overfit_finding(result, threshold=3.0)
    assert finding is not None
    assert finding.category is GeneralizationCategory.GENERALIZES_WELL


def test_overfit_finding_none_when_ratio_unavailable():
    result = ValidationResult(
        validation_run_id="r1",
        simulated=True,
        message=None,
        metrics=(),
        validation_residuals=(),
        overfit_ratio=None,
    )
    assert overfit_finding(result, threshold=3.0) is None


def test_dominant_uncertainty_parameter_ids_reads_agent4_findings_verbatim():
    report_dict = minimal_agent4_report_dict()
    report_dict["calibration"]["identifiability_findings"] = [
        {
            "finding_id": "bound-hit:k1",
            "category": "BOUND_HIT",
            "severity": "WARNING",
            "summary": "at bound",
            "explanation": "detail",
            "related_target_ids": ["k1"],
        },
        {
            "finding_id": "steady-state",
            "category": "INSUFFICIENT_OBSERVATIONS",
            "severity": "CRITICAL",
            "summary": "irrelevant category",
            "explanation": "detail",
            "related_target_ids": ["k1"],
        },
    ]
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY), report_dict)
    ids = dominant_uncertainty_parameter_ids(handoff.agent4_report)
    assert ids == ("k1",)


def test_dominant_uncertainty_finding_none_when_no_findings():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    assert dominant_uncertainty_finding(handoff.agent4_report) is None
