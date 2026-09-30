"""The Version 1 validation/experimental-design workflow, end to end.

``Agent 4 calibrated model/report + held-out observations -> validation simulation ->
residual/generalization analysis -> uncertainty/sensitivity analysis -> candidate-experiment
scoring -> ranked recommendations -> structured Agent 5 report``

Every early-exit branch (``INVALID_REQUEST``, ``VALIDATION_FAILED``,
``INSUFFICIENT_VALIDATION_DATA``) still returns a fully-formed ``Agent5Report`` -- never raises
for a genuine outcome, only for a structural contract problem (see ``app.agent5.errors``).
"""

from __future__ import annotations

import uuid

from app.agent5.antimony_ids import build_species_antimony_id_map
from app.agent5.experiment_design import (
    DEFAULT_CANDIDATE_TIME,
    default_candidate_experiments,
    experimental_design_findings,
    reference_information,
    score_candidates,
    uncertain_target_bounds,
)
from app.agent5.generalization import (
    dominant_uncertainty_parameter_ids,
    run_generalization_analysis,
)
from app.agent5.handoff import Agent5Handoff
from app.agent5.report import determine_full_workflow_sufficiency, determine_overall_status
from app.agent5.simulation import is_trivial_trajectory, simulate_calibrated_model
from app.agent5.types import Agent5Report, ValidationRequest, ValidationResult, ValidationStatus
from app.agent5.validation import calibrated_overrides, run_validation
from app.agent5.version import AGENT5_CONTRACT_VERSION


def _validate_request(handoff: Agent5Handoff, request: ValidationRequest) -> tuple[str, ...]:
    """Every request-level contract violation -- empty if the request is well-formed. Unlike
    Agent 4's eligibility policy (which governs what may be *fitted*), there is no protected-
    provenance concept here: Agent 5 never fits anything, so the only thing to validate is that
    every referenced entity actually exists."""
    violations = []
    species_ids = {s.species_id for s in handoff.agent2_model.species}
    for obs in request.validation_observations.observations:
        if obs.target_species_id not in species_ids:
            violations.append(
                f"Observation {obs.observation_id!r} references species "
                f"{obs.target_species_id!r}, which does not exist in the Agent 2 model."
            )
    if request.candidate_experiments is not None:
        for candidate in request.candidate_experiments:
            if not candidate.experiment_id:
                violations.append("A supplied candidate experiment has an empty experiment_id.")
    return tuple(violations)


def _empty_report(
    report_id: str,
    handoff: Agent5Handoff,
    request: ValidationRequest,
    status: ValidationStatus,
    *,
    validation: ValidationResult | None = None,
    generalization_findings: tuple = (),
) -> Agent5Report:
    sufficient, note = determine_full_workflow_sufficiency(status)
    return Agent5Report(
        report_id=report_id,
        agent5_contract_version=AGENT5_CONTRACT_VERSION,
        agent2_model_id=handoff.agent2_model.model_id,
        agent4_report_id=handoff.agent4_report.report_id,
        request_id=request.request_id,
        overall_status=status,
        validation=validation,
        generalization_findings=generalization_findings,
        dominant_uncertainty_parameter_ids=(),
        candidate_experiments=(),
        experiment_scores=(),
        experimental_design_findings=(),
        calibrated_parameters_verified_unchanged=True,
        calibrated_parameter_ids_checked=(),
        sufficient_for_full_workflow=sufficient,
        sufficiency_note=note,
    )


def run_agent5_pipeline(handoff: Agent5Handoff, request: ValidationRequest) -> Agent5Report:
    """Run the full Version 1 workflow against ``handoff`` and ``request`` and return one
    ``Agent5Report``. Never raises for a genuine validation/design outcome -- every such
    outcome is captured in the returned report's own ``ValidationStatus``."""
    report_id = f"agent5-report-{uuid.uuid4()}"

    violations = _validate_request(handoff, request)
    if violations:
        return _empty_report(
            report_id,
            handoff,
            request,
            ValidationStatus.INVALID_REQUEST,
            generalization_findings=(),
        )

    original_overrides = calibrated_overrides(handoff.agent4_report)

    validation_result = run_validation(
        handoff.agent2_model, handoff.agent4_report, request.validation_observations
    )
    generalization = run_generalization_analysis(
        validation_result,
        request.validation_observations,
        handoff.agent4_report,
        overfit_ratio_threshold=request.overfit_ratio_threshold,
    )

    if not validation_result.simulated:
        return _empty_report(
            report_id,
            handoff,
            request,
            ValidationStatus.VALIDATION_FAILED,
            validation=validation_result,
            generalization_findings=generalization,
        )

    if any(f.finding_id == "insufficient-validation-data" for f in generalization):
        report = _empty_report(
            report_id,
            handoff,
            request,
            ValidationStatus.INSUFFICIENT_VALIDATION_DATA,
            validation=validation_result,
            generalization_findings=generalization,
        )
        return report

    dominant_ids = dominant_uncertainty_parameter_ids(handoff.agent4_report)
    bounds = uncertain_target_bounds(handoff.agent4_report)
    target_ids = list(bounds.keys())

    baseline_probe = simulate_calibrated_model(
        handoff.agent2_model.antimony_text,
        original_overrides,
        (DEFAULT_CANDIDATE_TIME,),
        species_id_map=build_species_antimony_id_map(
            [s.species_id for s in handoff.agent2_model.species]
        ),
    )
    baseline_trivial = is_trivial_trajectory(baseline_probe)

    candidates = request.candidate_experiments
    if candidates is None:
        candidates = default_candidate_experiments(
            handoff.agent2_model,
            handoff.agent4_report,
            dominant_ids,
            max_candidates=request.max_default_candidates,
        )

    ref_info = (
        reference_information(
            handoff.agent2_model,
            handoff.agent4_report,
            request.validation_observations,
            target_ids,
            bounds,
        )
        if target_ids
        else {}
    )
    scores = score_candidates(
        handoff.agent2_model, handoff.agent4_report, candidates, dominant_ids, ref_info, bounds
    )
    design_findings = experimental_design_findings(candidates, scores, baseline_trivial)

    overall_status = determine_overall_status(validation_result, generalization, design_findings)
    sufficient, note = determine_full_workflow_sufficiency(overall_status)

    verified_overrides = calibrated_overrides(handoff.agent4_report)
    calibrated_unchanged = verified_overrides == original_overrides

    return Agent5Report(
        report_id=report_id,
        agent5_contract_version=AGENT5_CONTRACT_VERSION,
        agent2_model_id=handoff.agent2_model.model_id,
        agent4_report_id=handoff.agent4_report.report_id,
        request_id=request.request_id,
        overall_status=overall_status,
        validation=validation_result,
        generalization_findings=generalization,
        dominant_uncertainty_parameter_ids=dominant_ids,
        candidate_experiments=candidates,
        experiment_scores=scores,
        experimental_design_findings=design_findings,
        calibrated_parameters_verified_unchanged=calibrated_unchanged,
        calibrated_parameter_ids_checked=tuple(sorted(original_overrides.keys())),
        sufficient_for_full_workflow=sufficient,
        sufficiency_note=note,
    )


__all__ = ["run_agent5_pipeline"]
