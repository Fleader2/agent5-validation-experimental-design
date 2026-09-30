"""Tests for ``app.agent5.experiment_design``: candidate generation and Fisher-information-
proxy scoring."""

from __future__ import annotations

import numpy as np

from app.agent5.experiment_design import (
    DEFAULT_CANDIDATE_TIME,
    default_candidate_experiments,
    experimental_design_findings,
    reference_information,
    score_candidates,
    sensitivity_vector,
    uncertain_target_bounds,
)
from app.agent5.types import (
    CandidateExperiment,
    ExperimentalDesignCategory,
    ExperimentType,
    ValidationObservation,
    ValidationObservationKind,
    ValidationObservationSet,
)
from tests.agent5.fixtures import (
    ONE_PARAMETER_ANTIMONY,
    ONE_PARAMETER_TRUE_K,
    TWO_PARAMETER_ANTIMONY,
    TWO_PARAMETER_TRUE_K1,
    TWO_PARAMETER_TRUE_K2,
    minimal_agent2_model_dict,
    minimal_agent4_report_dict,
    parsed_handoff,
)


def _two_parameter_handoff(only_measure_s1: bool):
    model = minimal_agent2_model_dict(
        TWO_PARAMETER_ANTIMONY,
        species=[
            {
                "species_id": "S1",
                "name": "S1",
                "compartment_id": "C",
                "initial_concentration": "10",
            },
            {"species_id": "S2", "name": "S2", "compartment_id": "C", "initial_concentration": "0"},
            {"species_id": "S3", "name": "S3", "compartment_id": "C", "initial_concentration": "0"},
        ],
        reactions=[
            {
                "reaction_id": "reaction-1",
                "name": "r1",
                "reversible": False,
                "participants": [
                    {"species_id": "S1", "role": "REACTANT", "stoichiometry": "1"},
                    {"species_id": "S2", "role": "PRODUCT", "stoichiometry": "1"},
                ],
            },
            {
                "reaction_id": "reaction-2",
                "name": "r2",
                "reversible": False,
                "participants": [
                    {"species_id": "S2", "role": "REACTANT", "stoichiometry": "1"},
                    {"species_id": "S3", "role": "PRODUCT", "stoichiometry": "1"},
                ],
            },
        ],
        parameters=[
            {
                "parameter_id": "k1",
                "name": "k1",
                "source": "HEURISTIC_INITIALIZATION",
                "value": "0.1",
            },
            {
                "parameter_id": "k2",
                "name": "k2",
                "source": "HEURISTIC_INITIALIZATION",
                "value": "0.1",
            },
        ],
    )
    report = minimal_agent4_report_dict(
        agent2_model_id="test-model-1",
        calibration={
            "calibration_run_id": "run-1",
            "status": "SUCCESS",
            "objective_before": 1.0,
            "objective_after": 1e-9,
            "parameter_estimates": [
                {
                    "target_kind": "PARAMETER",
                    "target_id": "k1",
                    "original_value": 0.1,
                    "original_source": "HEURISTIC_INITIALIZATION",
                    "fitted_value": TWO_PARAMETER_TRUE_K1,
                    "lower_bound": 0.01,
                    "upper_bound": 2.0,
                    "at_lower_bound": False,
                    "at_upper_bound": False,
                    "new_source": "CALIBRATED",
                    "provenance_refs": [],
                },
                {
                    "target_kind": "PARAMETER",
                    "target_id": "k2",
                    "original_value": 0.1,
                    "original_source": "HEURISTIC_INITIALIZATION",
                    "fitted_value": TWO_PARAMETER_TRUE_K2,
                    "lower_bound": 0.01,
                    "upper_bound": 2.0,
                    "at_lower_bound": False,
                    "at_upper_bound": False,
                    "new_source": "CALIBRATED",
                    "provenance_refs": [],
                },
            ],
            "residuals": [],
            "identifiability_findings": [
                {
                    "finding_id": "low-sensitivity:k2",
                    "category": "LOW_SENSITIVITY",
                    "severity": "WARNING",
                    "summary": "k2 barely moves the objective given only S1 data",
                    "explanation": "detail",
                    "related_target_ids": ["k2"],
                }
            ]
            if only_measure_s1
            else [],
            "n_multistarts": 1,
            "best_start_index": 0,
            "all_start_objectives": [1e-9],
        },
    )
    return parsed_handoff(model, report)


def test_sensitivity_vector_matches_analytic_decay_derivative():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    bounds = uncertain_target_bounds(handoff.agent4_report)
    from app.agent5.antimony_ids import build_species_antimony_id_map

    species_id_map = build_species_antimony_id_map(["S1"])
    vec = sensitivity_vector(
        handoff.agent2_model,
        {"k1": ONE_PARAMETER_TRUE_K},
        ["k1"],
        bounds,
        observable_kind="SPECIES",
        observable_id="S1",
        time_point=5.0,
        species_id_map=species_id_map,
        reaction_id_map={},
    )
    assert vec is not None
    # d/dk1 [10*exp(-k1*t)] = -10*t*exp(-k1*t); at t=5, k1=0.7: -10*5*exp(-3.5).
    # The finite-difference step here is 1% of the target's own (0.01-5.0) bound range --
    # large relative to k1 itself, so a forward difference against the true (curved,
    # exponential) analytic derivative is only expected to agree loosely, not tightly.
    expected = -10 * 5 * np.exp(-ONE_PARAMETER_TRUE_K * 5)
    assert vec[0] == pytest_approx(expected, rel=0.15)


def pytest_approx(expected, rel=1e-6):
    import pytest

    return pytest.approx(expected, rel=rel)


def test_default_candidate_experiments_includes_species_and_reactions():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    candidates = default_candidate_experiments(
        handoff.agent2_model, handoff.agent4_report, (), max_candidates=10
    )
    types = {c.experiment_type for c in candidates}
    assert ExperimentType.METABOLITE_CONCENTRATION_AT_TIME in types
    assert ExperimentType.REACTION_FLUX in types
    assert ExperimentType.PARAMETER_PERTURBATION in types


def test_default_candidate_experiments_respects_max_cap():
    handoff = parsed_handoff(minimal_agent2_model_dict(ONE_PARAMETER_ANTIMONY))
    candidates = default_candidate_experiments(
        handoff.agent2_model, handoff.agent4_report, (), max_candidates=1
    )
    assert len(candidates) == 1


def test_reference_information_low_for_parameter_never_measured():
    handoff = _two_parameter_handoff(only_measure_s1=True)
    bounds = uncertain_target_bounds(handoff.agent4_report)
    obs_set = ValidationObservationSet(
        observation_set_id="vset",
        observations=(
            ValidationObservation(
                observation_id="v1",
                target_species_id="S1",
                kind=ValidationObservationKind.TIME_SERIES,
                time_points=(1.0, 2.0, 3.0),
                values=(6.0, 3.6, 2.2),
            ),
        ),
    )
    ref_info = reference_information(
        handoff.agent2_model, handoff.agent4_report, obs_set, ["k1", "k2"], bounds
    )
    # S1's own dynamics depend only on k1 -- k2's reference information should be ~0.
    assert ref_info["k2"] < 1e-9
    assert ref_info["k1"] > 1e-6


def test_candidate_measuring_s3_discriminates_poorly_identified_k2():
    handoff = _two_parameter_handoff(only_measure_s1=True)
    bounds = uncertain_target_bounds(handoff.agent4_report)
    dominant_ids = ("k2",)
    obs_set = ValidationObservationSet(
        observation_set_id="vset",
        observations=(
            ValidationObservation(
                observation_id="v1",
                target_species_id="S1",
                kind=ValidationObservationKind.TIME_SERIES,
                time_points=(1.0, 2.0, 3.0),
                values=(6.0, 3.6, 2.2),
            ),
        ),
    )
    ref_info = reference_information(
        handoff.agent2_model, handoff.agent4_report, obs_set, ["k1", "k2"], bounds
    )

    candidate_s3 = CandidateExperiment(
        experiment_id="measure-concentration:S3",
        experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
        target_id="S3",
        time_point=DEFAULT_CANDIDATE_TIME,
    )
    candidate_s1 = CandidateExperiment(
        experiment_id="measure-concentration:S1",
        experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
        target_id="S1",
        time_point=DEFAULT_CANDIDATE_TIME,
    )
    scores = score_candidates(
        handoff.agent2_model,
        handoff.agent4_report,
        (candidate_s3, candidate_s1),
        dominant_ids,
        ref_info,
        bounds,
    )
    s3_score = next(s for s in scores if s.experiment_id == "measure-concentration:S3")
    s1_score = next(s for s in scores if s.experiment_id == "measure-concentration:S1")
    assert "k2" in s3_score.discriminates_between_target_ids
    assert "k2" not in s1_score.discriminates_between_target_ids
    assert s3_score.information_score > s1_score.information_score


def test_score_candidates_ranking_is_deterministic():
    handoff = _two_parameter_handoff(only_measure_s1=False)
    bounds = uncertain_target_bounds(handoff.agent4_report)
    ref_info = {"k1": 0.0, "k2": 0.0}
    candidates = (
        CandidateExperiment(
            experiment_id="measure-concentration:S3",
            experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
            target_id="S3",
            time_point=10.0,
        ),
        CandidateExperiment(
            experiment_id="measure-concentration:S1",
            experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
            target_id="S1",
            time_point=10.0,
        ),
    )
    first = score_candidates(
        handoff.agent2_model, handoff.agent4_report, candidates, (), ref_info, bounds
    )
    second = score_candidates(
        handoff.agent2_model, handoff.agent4_report, candidates, (), ref_info, bounds
    )
    assert [s.experiment_id for s in first] == [s.experiment_id for s in second]
    assert [s.rank for s in first] == sorted(s.rank for s in first)


def test_experimental_design_findings_flags_empty_candidate_set():
    findings = experimental_design_findings((), (), baseline_trivial=False)
    assert len(findings) == 1
    assert findings[0].category is ExperimentalDesignCategory.CANDIDATE_SET_LIMITED
