"""Validating the calibrated model against held-out observations (``validation-v1``).

Held-out data is used **only** to evaluate the already-fitted (frozen) calibrated model -- this
module never adjusts a parameter or initial-condition value; it only applies Agent 4's own
already-declared ``fitted_value`` for every target, simulates once, and reports how well the
result matches data Agent 4's own optimizer never saw.
"""

from __future__ import annotations

import uuid

import numpy as np

from app.agent5.antimony_ids import build_species_antimony_id_map
from app.agent5.handoff import Agent2Model, Agent4ReportView
from app.agent5.simulation import simulate_calibrated_model
from app.agent5.types import (
    ValidationMetric,
    ValidationObservation,
    ValidationObservationKind,
    ValidationObservationSet,
    ValidationResidualSummary,
    ValidationResult,
)


def calibrated_overrides(agent4_report: Agent4ReportView) -> dict[str, float]:
    """``{target_id: fitted_value}`` for every ``ParameterEstimate`` Agent 4 declared -- the
    exact, frozen vector this module applies to the Agent 2 model before simulating. Never a
    different value than what Agent 4 itself reported."""
    return {e.target_id: e.fitted_value for e in agent4_report.calibration.parameter_estimates}


def _weights_for(observation: ValidationObservation) -> np.ndarray:
    n = len(observation.values)
    if observation.sigma is None:
        return np.ones(n)
    if isinstance(observation.sigma, (int, float)):
        return np.full(n, 1.0 / (float(observation.sigma) ** 2))
    sigma_arr = np.asarray(observation.sigma, dtype=float)
    return 1.0 / (sigma_arr**2)


def _union_time_points(observations: tuple[ValidationObservation, ...]) -> tuple[float, ...]:
    points: set[float] = set()
    for obs in observations:
        if obs.kind is ValidationObservationKind.TIME_SERIES:
            points.update(obs.time_points)
    return tuple(sorted(points))


def _pooled_metrics(
    residuals: list[float], weights: list[float], partition: str
) -> tuple[ValidationMetric, ...]:
    if not residuals:
        return ()
    residuals_arr = np.asarray(residuals)
    weights_arr = np.asarray(weights)
    rmse = float(np.sqrt(np.mean(residuals_arr**2)))
    weighted_sse = float(np.sum(weights_arr * residuals_arr**2))
    max_abs = float(np.max(np.abs(residuals_arr)))
    return (
        ValidationMetric(
            metric_name="RMSE",
            partition=partition,
            value=rmse,
            description=(
                f"Root-mean-square residual across {len(residuals)} {partition} point(s)."
            ),
        ),
        ValidationMetric(
            metric_name="WEIGHTED_SSE",
            partition=partition,
            value=weighted_sse,
            description=(
                f"Weighted sum of squared residuals across {len(residuals)} {partition} point(s)."
            ),
        ),
        ValidationMetric(
            metric_name="MAX_ABS_RESIDUAL",
            partition=partition,
            value=max_abs,
            description=(
                f"Largest single absolute residual among {len(residuals)} {partition} point(s)."
            ),
        ),
    )


def train_metrics_from_agent4(agent4_report: Agent4ReportView) -> tuple[ValidationMetric, ...]:
    """Pooled RMSE/weighted-SSE/max-abs-residual over every Agent 4 ``TRAIN``-partition
    residual -- computed from Agent 4's own already-reported residuals, never re-simulated
    (Agent 5 has no access to Agent 4's own raw train observation values, only its residuals,
    which is exactly what this metric needs)."""
    train_residuals: list[float] = []
    for r in agent4_report.calibration.residuals:
        if r.partition == "TRAIN":
            train_residuals.extend(r.residuals)
    weights = [1.0] * len(train_residuals)
    return _pooled_metrics(train_residuals, weights, "TRAIN")


def run_validation(
    agent2_model: Agent2Model,
    agent4_report: Agent4ReportView,
    validation_observations: ValidationObservationSet,
) -> ValidationResult:
    """Simulate the calibrated model once and compute held-out validation metrics/residuals,
    compared against Agent 4's own already-reported training performance."""
    validation_run_id = f"agent5-validation-{uuid.uuid4()}"
    overrides = calibrated_overrides(agent4_report)
    species_id_map = build_species_antimony_id_map([s.species_id for s in agent2_model.species])

    observations = validation_observations.observations
    union_times = _union_time_points(observations)
    outcome = simulate_calibrated_model(
        agent2_model.antimony_text, overrides, union_times, species_id_map=species_id_map
    )
    if not outcome.succeeded:
        return ValidationResult(
            validation_run_id=validation_run_id,
            simulated=False,
            message=outcome.message,
            metrics=(),
            validation_residuals=(),
            overfit_ratio=None,
        )

    time_index = {t: i for i, t in enumerate(union_times)}
    residual_summaries: list[ValidationResidualSummary] = []
    all_residuals: list[float] = []
    all_weights: list[float] = []

    for obs in observations:
        weights = _weights_for(obs)
        if obs.kind is ValidationObservationKind.STEADY_STATE:
            trajectory = (outcome.species_trajectories or {}).get(obs.target_species_id)
            if trajectory is None:
                return ValidationResult(
                    validation_run_id=validation_run_id,
                    simulated=False,
                    message=f"Species {obs.target_species_id!r} not present in simulated output.",
                    metrics=(),
                    validation_residuals=(),
                    overfit_ratio=None,
                )
            residuals = np.array([trajectory[-1] - obs.values[0]])
        else:
            trajectory = (outcome.species_trajectories or {}).get(obs.target_species_id)
            if trajectory is None:
                return ValidationResult(
                    validation_run_id=validation_run_id,
                    simulated=False,
                    message=f"Species {obs.target_species_id!r} not present in simulated output.",
                    metrics=(),
                    validation_residuals=(),
                    overfit_ratio=None,
                )
            indices = [time_index[t] for t in obs.time_points]
            simulated_values = np.array([trajectory[i] for i in indices])
            residuals = simulated_values - np.asarray(obs.values, dtype=float)

        sum_sq = float(np.sum(residuals**2))
        weighted_sum_sq = float(np.sum(weights * residuals**2))
        residual_summaries.append(
            ValidationResidualSummary(
                observation_id=obs.observation_id,
                residuals=tuple(float(r) for r in residuals),
                sum_squared_residual=sum_sq,
                weighted_sum_squared_residual=weighted_sum_sq,
                n_points=len(residuals),
            )
        )
        all_residuals.extend(float(r) for r in residuals)
        all_weights.extend(float(w) for w in weights)

    validation_metrics = _pooled_metrics(all_residuals, all_weights, "VALIDATION")
    train_metrics = train_metrics_from_agent4(agent4_report)

    validation_rmse = next((m.value for m in validation_metrics if m.metric_name == "RMSE"), None)
    train_rmse = next((m.value for m in train_metrics if m.metric_name == "RMSE"), None)
    overfit_ratio = None
    if validation_rmse is not None and train_rmse is not None and train_rmse > 0:
        overfit_ratio = validation_rmse / train_rmse

    return ValidationResult(
        validation_run_id=validation_run_id,
        simulated=True,
        message=None,
        metrics=validation_metrics + train_metrics,
        validation_residuals=tuple(residual_summaries),
        overfit_ratio=overfit_ratio,
    )


__all__ = ["calibrated_overrides", "run_validation", "train_metrics_from_agent4"]
