"""Contract tests for ``app.agent5.handoff``."""

from __future__ import annotations

import pytest

from app.agent5.errors import HandoffContractError
from app.agent5.handoff import parse_agent5_handoff
from tests.agent5.fixtures import (
    ONE_PARAMETER_ANTIMONY,
    build_handoff_dict,
    minimal_agent2_model_dict,
    minimal_agent4_report_dict,
)


def test_valid_handoff_parses():
    handoff = parse_agent5_handoff(
        build_handoff_dict(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    )
    assert handoff.agent2_model.model_id == "test-model-1"
    assert len(handoff.agent2_model.parameters) == 1
    assert handoff.agent4_report.report_id == "agent4-report-test"
    assert len(handoff.agent4_report.calibration.parameter_estimates) == 1


def test_missing_required_field_raises():
    data = build_handoff_dict(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    del data["agent2_model"]["antimony_text"]
    with pytest.raises(HandoffContractError):
        parse_agent5_handoff(data)


def test_not_a_dict_raises():
    with pytest.raises(HandoffContractError):
        parse_agent5_handoff("not a dict")


def test_missing_agent2_model_key_raises():
    with pytest.raises(HandoffContractError):
        parse_agent5_handoff({"agent4_report": minimal_agent4_report_dict()})


def test_missing_agent4_report_key_raises():
    with pytest.raises(HandoffContractError):
        parse_agent5_handoff({"agent2_model": minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY)})


def test_parameter_bounds_and_fixed_round_trip():
    model = minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY)
    model["parameters"][0]["lower_bound"] = "0.01"
    model["parameters"][0]["upper_bound"] = "5.0"
    model["parameters"][0]["fixed"] = True
    handoff = parse_agent5_handoff(build_handoff_dict(model))
    param = handoff.agent2_model.parameters[0]
    assert float(param.lower_bound) == pytest.approx(0.01)
    assert float(param.upper_bound) == pytest.approx(5.0)
    assert param.fixed is True


def test_parameter_estimate_view_round_trip():
    handoff = parse_agent5_handoff(
        build_handoff_dict(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    )
    estimate = handoff.agent4_report.calibration.parameter_estimates[0]
    assert estimate.target_id == "k1"
    assert estimate.fitted_value == pytest.approx(0.7)
    assert estimate.original_source == "HEURISTIC_INITIALIZATION"
    assert estimate.new_source == "CALIBRATED"


def test_identifiability_finding_view_round_trip():
    report = minimal_agent4_report_dict()
    report["calibration"]["identifiability_findings"] = [
        {
            "finding_id": "low-sensitivity:k1",
            "category": "LOW_SENSITIVITY",
            "severity": "WARNING",
            "summary": "barely moves",
            "explanation": "detail",
            "related_target_ids": ["k1"],
        }
    ]
    handoff = parse_agent5_handoff(
        build_handoff_dict(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY), report)
    )
    finding = handoff.agent4_report.calibration.identifiability_findings[0]
    assert finding.category == "LOW_SENSITIVITY"
    assert finding.related_target_ids == ("k1",)
