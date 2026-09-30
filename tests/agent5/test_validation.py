"""Tests for ``app.agent5.validation``: held-out simulation and metric computation."""

from __future__ import annotations

import pytest

from app.agent5.types import (
    ValidationObservation,
    ValidationObservationKind,
    ValidationObservationSet,
)
from app.agent5.validation import calibrated_overrides, run_validation, train_metrics_from_agent4
from tests.agent5.fixtures import (
    ONE_PARAMETER_ANTIMONY,
    ONE_PARAMETER_TRUE_K,
    minimal_agent2_model_dict,
    parsed_handoff,
    simulate_truth,
)


def test_calibrated_overrides_uses_agent4_fitted_values():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    overrides = calibrated_overrides(handoff.agent4_report)
    assert overrides == {"k1": pytest.approx(ONE_PARAMETER_TRUE_K)}


def test_validation_against_correct_model_gives_near_zero_residuals():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    time_points, values = simulate_truth(ONE_PARAMETER_ANTIMONY, "s_S1", end_time=10, num_points=11)
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    obs_set = ValidationObservationSet(observation_set_id="vset", observations=(obs,))
    result = run_validation(handoff.agent2_model, handoff.agent4_report, obs_set)
    assert result.simulated
    rmse = next(
        m.value for m in result.metrics if m.metric_name == "RMSE" and m.partition == "VALIDATION"
    )
    assert rmse < 1e-4


def test_validation_against_wrong_model_gives_large_residuals():
    model = minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY)
    handoff = parsed_handoff(model)
    # Held-out data generated from a very different true decay rate than the "calibrated" 0.7.
    wrong_truth_antimony = ONE_PARAMETER_ANTIMONY.replace(
        f"p_k1 = {ONE_PARAMETER_TRUE_K}", "p_k1 = 0.02"
    )
    time_points, values = simulate_truth(wrong_truth_antimony, "s_S1", end_time=10, num_points=11)
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    obs_set = ValidationObservationSet(observation_set_id="vset", observations=(obs,))
    result = run_validation(handoff.agent2_model, handoff.agent4_report, obs_set)
    assert result.simulated
    rmse = next(
        m.value for m in result.metrics if m.metric_name == "RMSE" and m.partition == "VALIDATION"
    )
    assert rmse > 1.0


def test_validation_simulation_failure_reported_not_raised():
    handoff = parsed_handoff(minimal_agent2_model_dict("this is not $$$ valid antimony"))
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=(0.0, 1.0),
        values=(10.0, 5.0),
    )
    obs_set = ValidationObservationSet(observation_set_id="vset", observations=(obs,))
    result = run_validation(handoff.agent2_model, handoff.agent4_report, obs_set)
    assert not result.simulated
    assert result.message is not None


def test_train_metrics_from_agent4_reads_residuals_verbatim():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    metrics = train_metrics_from_agent4(handoff.agent4_report)
    rmse = next(m.value for m in metrics if m.metric_name == "RMSE")
    assert rmse == pytest.approx(0.0, abs=1e-6)


def test_overfit_ratio_is_none_when_train_rmse_is_zero():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    time_points, values = simulate_truth(ONE_PARAMETER_ANTIMONY, "s_S1", end_time=10, num_points=11)
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    obs_set = ValidationObservationSet(observation_set_id="vset", observations=(obs,))
    result = run_validation(handoff.agent2_model, handoff.agent4_report, obs_set)
    # Fixture's own train residuals are all exactly 0.0 -> train RMSE is 0 -> ratio undefined.
    assert result.overfit_ratio is None
