"""End-to-end pipeline tests against the synthetic fixtures the task requires:

1. a well-calibrated model that validates successfully
2. a deliberately overfit model with poor held-out performance
3. insufficient validation data
4. one poorly identifiable parameter where Agent 5 correctly recommends a discriminating
   measurement
5. two competing candidate experiments with deterministic ranking
6. a candidate perturbation that improves information over passive observation
7. provenance traceability
8. proof that Agent 5 never changes fitted parameters
9. deterministic repeatability
"""

from __future__ import annotations

import pytest

from app.agent5.pipeline import run_agent5_pipeline
from app.agent5.types import (
    CandidateExperiment,
    ExperimentType,
    ValidationObservation,
    ValidationObservationKind,
    ValidationObservationSet,
    ValidationRequest,
    ValidationStatus,
)
from tests.agent5.fixtures import (
    MISSING_IC_ANTIMONY,
    MISSING_IC_KNOWN_K,
    ONE_PARAMETER_ANTIMONY,
    minimal_agent2_model_dict,
    minimal_agent4_report_dict,
    parsed_handoff,
    simulate_truth,
)


def _held_out_from_truth(antimony_text, species_id, idx=(2, 6, 12, 18), end_time=10, num_points=21):
    time_points, values = simulate_truth(
        antimony_text, species_id, end_time=end_time, num_points=num_points
    )
    return tuple(time_points[i] for i in idx), tuple(values[i] for i in idx)


# --- 1. well-calibrated model validates successfully -----------------------------------------


def test_well_calibrated_model_validates_successfully():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    time_points, values = _held_out_from_truth(ONE_PARAMETER_ANTIMONY, "s_S1")
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    request = ValidationRequest(
        request_id="req-1",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-1", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert report.overall_status in (
        ValidationStatus.SUCCESS,
        ValidationStatus.EXPERIMENT_DESIGN_LIMITED,
    )
    rmse = next(
        m.value
        for m in report.validation.metrics
        if m.metric_name == "RMSE" and m.partition == "VALIDATION"
    )
    assert rmse < 1e-3


# --- 2. deliberately overfit model with poor held-out performance -----------------------------


def test_overfit_model_flagged_with_poor_held_out_performance():
    # The "calibrated" value (0.02) fits a small, nonzero TRAIN residual set well, but
    # genuinely disagrees with held-out data generated from the real dynamics (0.7).
    report_dict = minimal_agent4_report_dict()
    report_dict["calibration"]["parameter_estimates"][0]["fitted_value"] = 0.02
    report_dict["calibration"]["residuals"][0]["residuals"] = [0.01] * 11
    report_dict["calibration"]["residuals"][0]["sum_squared_residual"] = 11 * 0.01**2
    report_dict["calibration"]["residuals"][0]["weighted_sum_squared_residual"] = 11 * 0.01**2
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY), report_dict)

    time_points, values = _held_out_from_truth(ONE_PARAMETER_ANTIMONY, "s_S1")
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    request = ValidationRequest(
        request_id="req-2",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-2", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert report.overall_status is ValidationStatus.OVERFIT_WARNING
    assert any(f.category.value == "OVERFIT_SUSPECTED" for f in report.generalization_findings)


# --- 3. insufficient validation data -----------------------------------------------------------


def test_insufficient_validation_data_status():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=(1.0,),
        values=(4.9,),
    )
    request = ValidationRequest(
        request_id="req-3",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-3", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert report.overall_status is ValidationStatus.INSUFFICIENT_VALIDATION_DATA
    assert report.sufficient_for_full_workflow is True


# --- 4. poorly identifiable parameter -> discriminating measurement recommended ---------------


def test_poorly_identifiable_parameter_gets_discriminating_recommendation():
    from tests.agent5.test_experiment_design import _two_parameter_handoff

    handoff = _two_parameter_handoff(only_measure_s1=True)
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=(1.0, 2.0, 3.0),
        values=(6.0, 3.6, 2.2),
    )
    request = ValidationRequest(
        request_id="req-4",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-4", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert "k2" in report.dominant_uncertainty_parameter_ids
    discriminating = [
        s for s in report.experiment_scores if "k2" in s.discriminates_between_target_ids
    ]
    assert discriminating
    top_discriminating = discriminating[0]
    assert (
        "k2" in top_discriminating.rationale or top_discriminating.discriminates_between_target_ids
    )


# --- 5. two competing candidate experiments, deterministic ranking -----------------------------


def test_two_competing_candidates_ranked_deterministically():
    from tests.agent5.test_experiment_design import _two_parameter_handoff

    handoff = _two_parameter_handoff(only_measure_s1=False)
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=(1.0, 2.0),
        values=(6.0, 3.6),
    )
    candidates = (
        CandidateExperiment(
            experiment_id="measure-concentration:S1",
            experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
            target_id="S1",
            time_point=10.0,
        ),
        CandidateExperiment(
            experiment_id="measure-concentration:S3",
            experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
            target_id="S3",
            time_point=10.0,
        ),
    )
    request = ValidationRequest(
        request_id="req-5",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-5", observations=(obs,)
        ),
        candidate_experiments=candidates,
    )
    report1 = run_agent5_pipeline(handoff, request)
    report2 = run_agent5_pipeline(handoff, request)
    ranks1 = {s.experiment_id: s.rank for s in report1.experiment_scores}
    ranks2 = {s.experiment_id: s.rank for s in report2.experiment_scores}
    assert ranks1 == ranks2
    assert len(report1.experiment_scores) == 2
    assert ranks1["measure-concentration:S1"] != ranks1["measure-concentration:S3"]


# --- 6. perturbation candidate improves information over passive observation ------------------


def test_perturbation_candidate_beats_passive_observation_when_baseline_trivial():
    # k1 IS a genuinely calibrated (uncertain) target here -- the point of this scenario is
    # that S1's missing initial condition leaves the baseline trajectory stuck at 0 (so k1's
    # own effect on S1 is completely invisible to a passive measurement), while perturbing S1
    # away from 0 unlocks real dynamics whose sensitivity to k1 becomes visible.
    model = minimal_agent2_model_dict(
        MISSING_IC_ANTIMONY,
        species=[
            {
                "species_id": "S1",
                "name": "S1",
                "compartment_id": "C",
                "initial_amount": None,
                "initial_concentration": None,
            }
        ],
        parameters=[
            {
                "parameter_id": "k1",
                "name": "k1",
                "source": "HEURISTIC_INITIALIZATION",
                "value": str(MISSING_IC_KNOWN_K),
            }
        ],
    )
    report_dict = minimal_agent4_report_dict(
        calibration={
            "calibration_run_id": "run-1",
            "status": "SUCCESS",
            "objective_before": 0.0,
            "objective_after": 0.0,
            "parameter_estimates": [
                {
                    "target_kind": "PARAMETER",
                    "target_id": "k1",
                    "original_value": MISSING_IC_KNOWN_K,
                    "original_source": "HEURISTIC_INITIALIZATION",
                    "fitted_value": MISSING_IC_KNOWN_K,
                    "lower_bound": 0.01,
                    "upper_bound": 2.0,
                    "at_lower_bound": False,
                    "at_upper_bound": False,
                    "new_source": "CALIBRATED",
                    "provenance_refs": [],
                }
            ],
            "residuals": [],
            "identifiability_findings": [],
            "n_multistarts": 0,
            "best_start_index": None,
            "all_start_objectives": [],
        }
    )
    handoff = parsed_handoff(model, report_dict)
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=(1.0, 2.0),
        values=(0.0, 0.0),
    )
    request = ValidationRequest(
        request_id="req-6",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-6", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    passive = next(
        s for s in report.experiment_scores if s.experiment_id == "measure-concentration:S1"
    )
    perturbation = next(
        s
        for s in report.experiment_scores
        if s.experiment_id == "perturb-missing-initial-condition:S1"
    )
    assert passive.information_score == 0.0
    assert perturbation.information_score > passive.information_score
    assert any(
        f.finding_id == "baseline-trajectory-trivial" for f in report.experimental_design_findings
    )


# --- 7. provenance traceability -----------------------------------------------------------------


def test_provenance_traceability():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    time_points, values = _held_out_from_truth(ONE_PARAMETER_ANTIMONY, "s_S1")
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    request = ValidationRequest(
        request_id="req-7",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-7", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert report.agent2_model_id == handoff.agent2_model.model_id
    assert report.agent4_report_id == handoff.agent4_report.report_id
    for candidate in report.candidate_experiments:
        if candidate.experiment_type.value in (
            "METABOLITE_CONCENTRATION_AT_TIME",
            "PARAMETER_PERTURBATION",
        ):
            known_ids = {s.species_id for s in handoff.agent2_model.species} | {
                p.parameter_id for p in handoff.agent2_model.parameters
            }
            assert candidate.target_id in known_ids


# --- 8. Agent 5 never changes fitted parameters ---------------------------------------------------


def test_agent5_never_changes_fitted_parameters():
    report_dict = minimal_agent4_report_dict()
    original_fitted_value = report_dict["calibration"]["parameter_estimates"][0]["fitted_value"]
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY), report_dict)
    time_points, values = _held_out_from_truth(ONE_PARAMETER_ANTIMONY, "s_S1")
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    request = ValidationRequest(
        request_id="req-8",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-8", observations=(obs,)
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert report.calibrated_parameters_verified_unchanged is True
    # The original dict passed to parse_agent5_handoff is untouched.
    assert (
        report_dict["calibration"]["parameter_estimates"][0]["fitted_value"]
        == original_fitted_value
    )
    # The parsed, frozen handoff's own estimate is untouched too.
    assert handoff.agent4_report.calibration.parameter_estimates[0].fitted_value == pytest.approx(
        original_fitted_value
    )


# --- 9. deterministic repeatability -------------------------------------------------------------


def test_deterministic_repeatability():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    time_points, values = _held_out_from_truth(ONE_PARAMETER_ANTIMONY, "s_S1")
    obs = ValidationObservation(
        observation_id="v1",
        target_species_id="S1",
        kind=ValidationObservationKind.TIME_SERIES,
        time_points=time_points,
        values=values,
    )
    request = ValidationRequest(
        request_id="req-9",
        validation_observations=ValidationObservationSet(
            observation_set_id="vset-9", observations=(obs,)
        ),
    )
    report1 = run_agent5_pipeline(handoff, request)
    report2 = run_agent5_pipeline(handoff, request)
    assert report1.overall_status == report2.overall_status
    assert [s.information_score for s in report1.experiment_scores] == [
        s.information_score for s in report2.experiment_scores
    ]
    assert [s.rank for s in report1.experiment_scores] == [
        s.rank for s in report2.experiment_scores
    ]
