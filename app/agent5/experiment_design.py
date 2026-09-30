"""Candidate-experiment generation and deterministic, Fisher-information-proxy ranking
(``experimental-design-v1``).

**This is a diagonal, per-parameter sensitivity proxy, not full (joint, Bayesian, D-optimal)
experimental design.** Every candidate's own "information score" is a weighted sum of its
squared local sensitivities to each currently-uncertain parameter/initial condition, never a
joint Fisher-information-matrix determinant/eigenvalue computed across the whole parameter set
at once, and never a Bayesian posterior-variance-reduction calculation. See ``docs/
04_experimental_design_scoring_policy.md`` for the full, precise method and its limits.
"""

from __future__ import annotations

import numpy as np

from app.agent5.antimony_ids import build_reaction_antimony_id_map, build_species_antimony_id_map
from app.agent5.handoff import Agent2Model, Agent4ReportView
from app.agent5.simulation import simulate_calibrated_model
from app.agent5.types import (
    CandidateExperiment,
    ExperimentalDesignCategory,
    ExperimentalDesignFinding,
    ExperimentScore,
    ExperimentType,
    FindingSeverity,
    ValidationObservationSet,
)
from app.agent5.validation import calibrated_overrides

#: Version 1's own default observation time for a passively-observed candidate, when the
#: caller's own request does not name one -- a generic, unit-agnostic default (there is no
#: per-reaction characteristic timescale in the handoff contract to derive a better one from,
#: mirroring ``app.agent3.pipeline.DEFAULT_SIMULATION_REQUEST``'s own identical rationale).
DEFAULT_CANDIDATE_TIME = 10.0

#: Version 1's own default perturbation fraction for a ``PARAMETER_PERTURBATION`` candidate.
PARAMETER_PERTURBATION_FRACTION = 0.10

#: Version 1's own default absolute nudge for an ``INITIAL_CONCENTRATION_PERTURBATION``
#: candidate when the species' own current (calibrated or Agent-2-declared) value is zero or
#: undeclared, where a *relative* perturbation is undefined.
INITIAL_CONDITION_PERTURBATION_ABSOLUTE_NUDGE = 1.0

#: Relative finite-difference step (of each uncertain target's own bound range) used for every
#: sensitivity computation in this module -- identical convention to
#: ``app.agent4.identifiability``'s own ``_SENSITIVITY_RELATIVE_STEP``.
_SENSITIVITY_RELATIVE_STEP = 0.01

#: Weight applied to a target Agent 4 already flagged as dominating the model's uncertainty
#: (see ``app.agent5.generalization.dominant_uncertainty_parameter_ids``) versus one it did not.
_DOMINANT_TARGET_WEIGHT = 1.0
_NON_DOMINANT_TARGET_WEIGHT = 0.1

#: Prevents division by zero when a target is completely unconstrained by the reference
#: (already-collected) observation set -- deliberately tiny so an unconstrained target's weight
#: is very large (correctly prioritized), never infinite.
_REFERENCE_INFORMATION_EPSILON = 1e-6

#: Below this squared-sensitivity magnitude, a target's reference information is treated as
#: "the existing data barely touches this" for the purpose of the ``discriminates_between_
#: target_ids`` determination below.
_POORLY_CONSTRAINED_REFERENCE_THRESHOLD = 1e-6

#: Above this squared-sensitivity magnitude, a candidate's own sensitivity to a target is
#: treated as "meaningfully informative" for that same determination.
_MEANINGFUL_SENSITIVITY_THRESHOLD = 1e-9


def uncertain_target_bounds(agent4_report: Agent4ReportView) -> dict[str, tuple[float, float]]:
    """``{target_id: (lower_bound, upper_bound)}`` for every calibrated target -- read directly
    from Agent 4's own already-declared ``ParameterEstimate.lower_bound``/``.upper_bound``,
    never re-derived from Agent 2's contract independently (Agent 4's own bounds are exactly
    what was actually used to fit the value being evaluated here)."""
    return {
        e.target_id: (e.lower_bound, e.upper_bound)
        for e in agent4_report.calibration.parameter_estimates
    }


def _predict(
    agent2_model: Agent2Model,
    overrides: dict[str, float],
    *,
    observable_kind: str,
    observable_id: str,
    time_point: float,
    species_id_map: dict[str, str],
    reaction_id_map: dict[str, str],
) -> float | None:
    outcome = simulate_calibrated_model(
        agent2_model.antimony_text,
        overrides,
        (time_point,),
        species_id_map=species_id_map,
        reaction_id_map=reaction_id_map,
        include_reaction_fluxes=(observable_kind == "REACTION"),
    )
    if not outcome.succeeded:
        return None
    if observable_kind == "SPECIES":
        trajectory = (outcome.species_trajectories or {}).get(observable_id)
    else:
        trajectory = (outcome.reaction_flux_trajectories or {}).get(observable_id)
    if trajectory is None:
        return None
    return trajectory[0]


def sensitivity_vector(
    agent2_model: Agent2Model,
    base_overrides: dict[str, float],
    target_ids: list[str],
    bounds: dict[str, tuple[float, float]],
    *,
    observable_kind: str,
    observable_id: str,
    time_point: float,
    species_id_map: dict[str, str],
    reaction_id_map: dict[str, str],
) -> np.ndarray | None:
    """The local finite-difference sensitivity of one observable (a species concentration or
    reaction flux at ``time_point``, evaluated starting from ``base_overrides``) with respect
    to every id in ``target_ids``, in that order. ``None`` if the observable cannot be evaluated
    at all (e.g. the base simulation itself fails)."""
    base_value = _predict(
        agent2_model,
        base_overrides,
        observable_kind=observable_kind,
        observable_id=observable_id,
        time_point=time_point,
        species_id_map=species_id_map,
        reaction_id_map=reaction_id_map,
    )
    if base_value is None:
        return None

    components = []
    for target_id in target_ids:
        lower, upper = bounds.get(target_id, (0.0, 0.0))
        span = upper - lower
        current = base_overrides.get(target_id, 0.0)
        step = span * _SENSITIVITY_RELATIVE_STEP if span > 0 else max(abs(current) * 0.01, 1e-6)
        nudged_overrides = dict(base_overrides)
        nudged_overrides[target_id] = current + step
        nudged_value = _predict(
            agent2_model,
            nudged_overrides,
            observable_kind=observable_kind,
            observable_id=observable_id,
            time_point=time_point,
            species_id_map=species_id_map,
            reaction_id_map=reaction_id_map,
        )
        if nudged_value is None:
            return None
        components.append((nudged_value - base_value) / step)
    return np.asarray(components)


def default_candidate_experiments(
    agent2_model: Agent2Model,
    agent4_report: Agent4ReportView,
    dominant_ids: tuple[str, ...],
    *,
    max_candidates: int,
) -> tuple[CandidateExperiment, ...]:
    """Version 1's own deterministic default candidate set: a passive concentration/flux
    measurement for every species/reaction, a direct-measurement candidate for every
    dominant-uncertainty parameter, a ``PARAMETER_PERTURBATION`` for every calibrated parameter
    target, and an ``INITIAL_CONCENTRATION_PERTURBATION`` for every calibrated or missing
    initial condition. Truncated to ``max_candidates`` by a fixed type-priority order (passive
    measurements first, then perturbations, then direct parameter measurement) -- never a
    random or unstated ordering.
    """
    candidates: list[CandidateExperiment] = []

    for species in sorted(agent2_model.species, key=lambda s: s.species_id):
        candidates.append(
            CandidateExperiment(
                experiment_id=f"measure-concentration:{species.species_id}",
                experiment_type=ExperimentType.METABOLITE_CONCENTRATION_AT_TIME,
                target_id=species.species_id,
                time_point=DEFAULT_CANDIDATE_TIME,
                description=(
                    f"Measure the concentration of species {species.species_id!r} at "
                    f"t={DEFAULT_CANDIDATE_TIME:g}."
                ),
            )
        )

    for reaction in sorted(agent2_model.reactions, key=lambda r: r.reaction_id):
        candidates.append(
            CandidateExperiment(
                experiment_id=f"measure-flux:{reaction.reaction_id}",
                experiment_type=ExperimentType.REACTION_FLUX,
                target_id=reaction.reaction_id,
                time_point=DEFAULT_CANDIDATE_TIME,
                description=(
                    f"Measure the flux of reaction {reaction.reaction_id!r} at "
                    f"t={DEFAULT_CANDIDATE_TIME:g}."
                ),
            )
        )

    for target_id in dominant_ids:
        candidates.append(
            CandidateExperiment(
                experiment_id=f"measure-parameter-directly:{target_id}",
                experiment_type=ExperimentType.ENZYME_KINETIC_PARAMETER,
                target_id=target_id,
                description=(
                    f"Directly measure parameter {target_id!r} (e.g. an in-vitro kinetic "
                    "assay), bypassing the model's own limited sensitivity entirely."
                ),
            )
        )

    for estimate in agent4_report.calibration.parameter_estimates:
        if estimate.target_kind == "PARAMETER":
            candidates.append(
                CandidateExperiment(
                    experiment_id=f"perturb-parameter:{estimate.target_id}",
                    experiment_type=ExperimentType.PARAMETER_PERTURBATION,
                    target_id=estimate.target_id,
                    perturbation_fraction=PARAMETER_PERTURBATION_FRACTION,
                    description=(
                        f"Perturb parameter {estimate.target_id!r} by "
                        f"{PARAMETER_PERTURBATION_FRACTION:+.0%} and measure the default "
                        "observable set."
                    ),
                )
            )
        else:
            candidates.append(
                CandidateExperiment(
                    experiment_id=f"perturb-initial-condition:{estimate.target_id}",
                    experiment_type=ExperimentType.INITIAL_CONCENTRATION_PERTURBATION,
                    target_id=estimate.target_id,
                    perturbation_fraction=PARAMETER_PERTURBATION_FRACTION,
                    description=(
                        f"Perturb the initial concentration of {estimate.target_id!r} and "
                        "measure the default observable set."
                    ),
                )
            )

    calibrated_ic_ids = {
        e.target_id
        for e in agent4_report.calibration.parameter_estimates
        if e.target_kind == "INITIAL_CONCENTRATION"
    }
    for species in sorted(agent2_model.species, key=lambda s: s.species_id):
        if (
            species.initial_amount is None
            and species.initial_concentration is None
            and species.species_id not in calibrated_ic_ids
        ):
            candidates.append(
                CandidateExperiment(
                    experiment_id=f"perturb-missing-initial-condition:{species.species_id}",
                    experiment_type=ExperimentType.INITIAL_CONCENTRATION_PERTURBATION,
                    target_id=species.species_id,
                    description=(
                        f"Establish and perturb the currently-undeclared initial concentration "
                        f"of {species.species_id!r} and measure the default observable set."
                    ),
                )
            )

    type_priority = {
        ExperimentType.METABOLITE_CONCENTRATION_AT_TIME: 0,
        ExperimentType.REACTION_FLUX: 1,
        ExperimentType.PARAMETER_PERTURBATION: 2,
        ExperimentType.INITIAL_CONCENTRATION_PERTURBATION: 3,
        ExperimentType.ENZYME_KINETIC_PARAMETER: 4,
        ExperimentType.PROTEIN_ABUNDANCE: 5,
        ExperimentType.ADDITIONAL_TIME_POINT: 6,
        ExperimentType.TIME_SERIES: 7,
    }
    candidates.sort(key=lambda c: (type_priority[c.experiment_type], c.target_id))
    return tuple(candidates[:max_candidates])


def reference_information(
    agent2_model: Agent2Model,
    agent4_report: Agent4ReportView,
    validation_observations: ValidationObservationSet,
    target_ids: list[str],
    bounds: dict[str, tuple[float, float]],
) -> dict[str, float]:
    """``{target_id: squared sensitivity of the already-supplied validation observations to
    that target}`` -- an aggregate proxy for "how much does the data we already have constrain
    this target," computed once, used to weight every candidate's own score inversely (a target
    the existing data barely touches is weighted heavily; one it already constrains well is
    weighted lightly)."""
    overrides = calibrated_overrides(agent4_report)
    species_id_map = build_species_antimony_id_map([s.species_id for s in agent2_model.species])
    totals = dict.fromkeys(target_ids, 0.0)
    for obs in validation_observations.observations:
        for time_point in obs.time_points or (0.0,):
            vec = sensitivity_vector(
                agent2_model,
                overrides,
                target_ids,
                bounds,
                observable_kind="SPECIES",
                observable_id=obs.target_species_id,
                time_point=time_point,
                species_id_map=species_id_map,
                reaction_id_map={},
            )
            if vec is None:
                continue
            for target_id, component in zip(target_ids, vec, strict=True):
                totals[target_id] += float(component) ** 2
    return totals


def _target_weight(
    target_id: str, dominant_ids: tuple[str, ...], reference_info: dict[str, float]
) -> float:
    base = _DOMINANT_TARGET_WEIGHT if target_id in dominant_ids else _NON_DOMINANT_TARGET_WEIGHT
    return base / (reference_info.get(target_id, 0.0) + _REFERENCE_INFORMATION_EPSILON)


def _rule_based_score(target_id: str, agent4_report: Agent4ReportView) -> tuple[float, str]:
    """Scores an ``ENZYME_KINETIC_PARAMETER``/``PROTEIN_ABUNDANCE`` direct-measurement
    candidate -- these are never simulated (protein abundance and the parameter's own true
    value are not themselves model outputs), so scoring falls back to a fixed rule over Agent
    4's own already-declared identifiability-finding severities for that target."""
    severity_score = {"CRITICAL": 10.0, "ERROR": 6.0, "WARNING": 3.0, "INFO": 1.0}
    total = 0.0
    categories: list[str] = []
    for finding in agent4_report.calibration.identifiability_findings:
        if target_id in finding.related_target_ids:
            total += severity_score.get(finding.severity, 1.0)
            categories.append(finding.category)
    rationale = (
        f"Directly resolves {len(categories)} Agent-4-declared identifiability concern(s) "
        f"({', '.join(sorted(set(categories))) or 'none'}) for this target via direct "
        "biochemical measurement, bypassing the model's own limited sensitivity entirely."
    )
    return total, rationale


def score_candidates(
    agent2_model: Agent2Model,
    agent4_report: Agent4ReportView,
    candidates: tuple[CandidateExperiment, ...],
    dominant_ids: tuple[str, ...],
    reference_info: dict[str, float],
    bounds: dict[str, tuple[float, float]],
) -> tuple[ExperimentScore, ...]:
    """Score and deterministically rank every candidate (highest information score first, tied
    scores broken by ``experiment_id``)."""
    target_ids = list(bounds.keys())
    overrides = calibrated_overrides(agent4_report)
    species_id_map = build_species_antimony_id_map([s.species_id for s in agent2_model.species])
    reaction_id_map = build_reaction_antimony_id_map(
        [r.reaction_id for r in agent2_model.reactions]
    )
    weights = {tid: _target_weight(tid, dominant_ids, reference_info) for tid in target_ids}

    scored: list[tuple[float, ExperimentScore]] = []
    for candidate in candidates:
        if candidate.experiment_type in (
            ExperimentType.ENZYME_KINETIC_PARAMETER,
            ExperimentType.PROTEIN_ABUNDANCE,
        ):
            score, rationale = _rule_based_score(candidate.target_id, agent4_report)
            related = (candidate.target_id,)
            discriminates: tuple[str, ...] = ()
        else:
            base_overrides = dict(overrides)
            if candidate.experiment_type in (
                ExperimentType.PARAMETER_PERTURBATION,
                ExperimentType.INITIAL_CONCENTRATION_PERTURBATION,
            ):
                current = base_overrides.get(candidate.target_id, 0.0)
                nudge = current * (candidate.perturbation_fraction or 0.0)
                if nudge == 0.0:
                    nudge = INITIAL_CONDITION_PERTURBATION_ABSOLUTE_NUDGE
                base_overrides[candidate.target_id] = current + nudge

            observable_kind = (
                "REACTION"
                if candidate.experiment_type is ExperimentType.REACTION_FLUX
                else "SPECIES"
            )
            observable_id = candidate.target_id
            if candidate.experiment_type in (
                ExperimentType.PARAMETER_PERTURBATION,
                ExperimentType.INITIAL_CONCENTRATION_PERTURBATION,
            ):
                # A deterministic default "what we'd measure after perturbing" -- the first
                # species by id, never an Antimony-internal identifier.
                observable_id = min(agent2_model.species, key=lambda s: s.species_id).species_id
                observable_kind = "SPECIES"

            vec = sensitivity_vector(
                agent2_model,
                base_overrides,
                target_ids,
                bounds,
                observable_kind=observable_kind,
                observable_id=observable_id,
                time_point=candidate.time_point or DEFAULT_CANDIDATE_TIME,
                species_id_map=species_id_map,
                reaction_id_map=reaction_id_map,
            )
            if vec is None:
                score = 0.0
                rationale = (
                    "Could not be scored: the calibrated model failed to simulate for this "
                    "candidate's own operating point."
                )
                related = ()
                discriminates = ()
            else:
                per_target = {
                    tid: weights[tid] * float(c) ** 2
                    for tid, c in zip(target_ids, vec, strict=True)
                }
                score = sum(per_target.values())
                related = tuple(
                    tid
                    for tid, c in zip(target_ids, vec, strict=True)
                    if abs(c) > 1e-12 and per_target[tid] > 1e-12
                )
                discriminates = tuple(
                    tid
                    for tid, c in zip(target_ids, vec, strict=True)
                    if reference_info.get(tid, 0.0) < _POORLY_CONSTRAINED_REFERENCE_THRESHOLD
                    and float(c) ** 2 > _MEANINGFUL_SENSITIVITY_THRESHOLD
                )
                rationale = (
                    f"Weighted local sensitivity score {score:.3g}, informing "
                    f"{len(related)} currently-uncertain target(s)"
                    + (
                        f"; discriminates {len(discriminates)} target(s) the existing "
                        "validation observations barely constrain"
                        if discriminates
                        else ""
                    )
                    + "."
                )

        scored.append(
            (
                score,
                ExperimentScore(
                    experiment_id=candidate.experiment_id,
                    information_score=score,
                    rank=0,
                    related_parameter_ids=related,
                    discriminates_between_target_ids=discriminates,
                    rationale=rationale,
                ),
            )
        )

    scored.sort(key=lambda pair: (-pair[0], pair[1].experiment_id))
    ranked = [
        ExperimentScore(
            experiment_id=s.experiment_id,
            information_score=s.information_score,
            rank=rank,
            related_parameter_ids=s.related_parameter_ids,
            discriminates_between_target_ids=s.discriminates_between_target_ids,
            rationale=s.rationale,
        )
        for rank, (_, s) in enumerate(scored)
    ]
    return tuple(ranked)


def experimental_design_findings(
    candidates: tuple[CandidateExperiment, ...],
    scores: tuple[ExperimentScore, ...],
    baseline_trivial: bool,
) -> tuple[ExperimentalDesignFinding, ...]:
    findings: list[ExperimentalDesignFinding] = []
    if not candidates:
        findings.append(
            ExperimentalDesignFinding(
                finding_id="candidate-set-empty",
                category=ExperimentalDesignCategory.CANDIDATE_SET_LIMITED,
                severity=FindingSeverity.WARNING,
                summary="No candidate experiments were generated or supplied.",
                explanation="Nothing to rank or recommend.",
            )
        )
        return tuple(findings)

    if baseline_trivial:
        findings.append(
            ExperimentalDesignFinding(
                finding_id="baseline-trajectory-trivial",
                category=ExperimentalDesignCategory.NO_MEANINGFUL_CONNECTION,
                severity=FindingSeverity.WARNING,
                summary=(
                    "The calibrated model's own baseline trajectory is trivial (every species "
                    "stays at a constant value) -- passive-observation candidates cannot be "
                    "meaningfully connected to a prediction until this is resolved."
                ),
                explanation=(
                    "Every candidate scored 0.0 for this reason is still reported (never "
                    "silently dropped), with this limitation labeled explicitly rather than "
                    "presented as 'not informative.'"
                ),
                related_experiment_ids=tuple(
                    s.experiment_id for s in scores if s.information_score == 0.0
                ),
            )
        )

    if scores and all(s.information_score == 0.0 for s in scores):
        findings.append(
            ExperimentalDesignFinding(
                finding_id="all-candidates-uninformative",
                category=ExperimentalDesignCategory.CANDIDATE_SET_LIMITED,
                severity=FindingSeverity.ERROR,
                summary="Every scored candidate has an information score of exactly 0.0.",
                explanation=(
                    "No candidate in this set could be meaningfully connected to a prediction "
                    "given the current calibrated model -- see the other findings for why."
                ),
            )
        )

    return tuple(findings)


__all__ = [
    "DEFAULT_CANDIDATE_TIME",
    "INITIAL_CONDITION_PERTURBATION_ABSOLUTE_NUDGE",
    "PARAMETER_PERTURBATION_FRACTION",
    "default_candidate_experiments",
    "experimental_design_findings",
    "reference_information",
    "score_candidates",
    "sensitivity_vector",
    "uncertain_target_bounds",
]
