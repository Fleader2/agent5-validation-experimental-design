"""Simulating the calibrated model (Agent 2's structure + Agent 4's fitted values).

Every simulation here loads a **fresh** ``roadrunner.RoadRunner`` instance from the handoff's
own unmodified ``antimony_text`` -- never reuses or mutates a shared instance. This module never
optimizes or fits anything; it only applies an already-decided vector of values (Agent 4's own
fitted values, or a small finite-difference nudge of one of them for sensitivity analysis) and
reports what the model predicts.

Reaction fluxes are requested as extra ``timeCourseSelections`` columns alongside floating
species -- confirmed empirically this session that RoadRunner's ``simulate`` accepts a mixed
species+reaction selection list directly, so a ``REACTION_FLUX`` candidate experiment is scored
using exactly the same dense-grid-plus-interpolation mechanism as a species concentration,
never a second, bespoke code path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.agent5.antimony_ids import candidate_parameter_antimony_id, candidate_species_antimony_id
from app.agent5.loader import load_antimony_model

#: Dense, fixed-resolution simulation grid used for every evaluation -- identical rationale to
#: ``app.agent4.simulation``'s own identically-named constant.
_DENSE_GRID_POINTS = 500

#: Identical threshold and rationale to ``app.agent3.simulation.DIVERGENCE_MAGNITUDE_THRESHOLD``/
#: ``app.agent4.simulation.DIVERGENCE_MAGNITUDE_THRESHOLD``.
DIVERGENCE_MAGNITUDE_THRESHOLD = 1e12


@dataclass(frozen=True, slots=True)
class CalibratedSimulationOutcome:
    """The outcome of simulating the model at one (possibly nudged) parameter/IC vector.

    ``species_trajectories``/``reaction_flux_trajectories`` are keyed by the **original** Agent
    2 entity id (never the sanitized Antimony identifier).
    """

    succeeded: bool
    message: str | None
    time_grid: tuple[float, ...] | None = None
    species_trajectories: dict[str, tuple[float, ...]] | None = None
    reaction_flux_trajectories: dict[str, tuple[float, ...]] | None = None
    final_state: dict[str, float] | None = None


def _resolve_and_apply(rr, overrides: dict[str, float]) -> str | None:
    real_parameter_ids = set(rr.model.getGlobalParameterIds())
    real_species_ids = set(rr.model.getFloatingSpeciesIds())
    for entity_id, value in overrides.items():
        param_candidate = candidate_parameter_antimony_id(entity_id)
        species_candidate = candidate_species_antimony_id(entity_id)
        if param_candidate in real_parameter_ids:
            rr[param_candidate] = value
        elif species_candidate in real_species_ids:
            rr[species_candidate] = value
        else:
            return (
                f"Could not resolve override target {entity_id!r} against the loaded model "
                f"(tried parameter id {param_candidate!r} and species id "
                f"{species_candidate!r})."
            )
    return None


def simulate_calibrated_model(
    antimony_text: str,
    overrides: dict[str, float],
    time_points_needed: tuple[float, ...],
    *,
    species_id_map: dict[str, str] | None = None,
    reaction_id_map: dict[str, str] | None = None,
    include_reaction_fluxes: bool = False,
) -> CalibratedSimulationOutcome:
    """Load a fresh model, apply ``overrides`` (typically every ``ParameterEstimate.fitted_
    value`` from Agent 4, possibly with one target nudged for a sensitivity finite-difference
    step), and simulate it, reporting trajectories at exactly ``time_points_needed``."""
    load_result = load_antimony_model(antimony_text)
    if not load_result.succeeded or load_result.roadrunner_instance is None:
        return CalibratedSimulationOutcome(succeeded=False, message=load_result.message)

    rr = load_result.roadrunner_instance
    species_id_map = species_id_map or {}
    reaction_id_map = reaction_id_map or {}

    resolution_error = _resolve_and_apply(rr, overrides)
    if resolution_error is not None:
        return CalibratedSimulationOutcome(succeeded=False, message=resolution_error)

    real_species_ids = list(rr.model.getFloatingSpeciesIds())
    real_reaction_ids = list(rr.model.getReactionIds()) if include_reaction_fluxes else []
    rr.timeCourseSelections = ["time", *real_species_ids, *real_reaction_ids]

    end_time = max(time_points_needed) if time_points_needed else 1.0
    if end_time <= 0:
        end_time = 1.0

    try:
        raw = rr.simulate(0.0, end_time, _DENSE_GRID_POINTS)
    except Exception as exc:  # pragma: no cover - roadrunner raises plain Exception/RuntimeError
        return CalibratedSimulationOutcome(
            succeeded=False, message=f"Integration failed for the calibrated model: {exc}"
        )

    array = np.asarray(raw)
    colnames = list(raw.colnames)
    grid_times = array[:, 0].astype(float)

    flat_values = array[:, 1:].astype(float).ravel()
    if np.isnan(flat_values).any() or np.isinf(flat_values).any():
        return CalibratedSimulationOutcome(
            succeeded=False, message="Calibrated-model simulation produced a NaN or Inf value."
        )
    finite_values = flat_values[np.isfinite(flat_values)]
    if finite_values.size and np.abs(finite_values).max() > DIVERGENCE_MAGNITUDE_THRESHOLD:
        return CalibratedSimulationOutcome(
            succeeded=False,
            message=(
                f"Calibrated-model simulation exceeded the divergence threshold "
                f"({DIVERGENCE_MAGNITUDE_THRESHOLD:g})."
            ),
        )

    requested = np.asarray(time_points_needed, dtype=float) if time_points_needed else grid_times

    species_trajectories: dict[str, tuple[float, ...]] = {}
    reaction_trajectories: dict[str, tuple[float, ...]] = {}
    final_state: dict[str, float] = {}
    n_species = len(real_species_ids)
    for col_index, col_name in enumerate(colnames[1:], start=1):
        raw_id = col_name.strip("[]")
        series = array[:, col_index].astype(float)
        interpolated = np.interp(requested, grid_times, series)
        if col_index - 1 < n_species:
            original_id = species_id_map.get(raw_id, raw_id)
            species_trajectories[original_id] = tuple(float(v) for v in interpolated)
            final_state[original_id] = float(series[-1])
        else:
            original_id = reaction_id_map.get(raw_id, raw_id)
            reaction_trajectories[original_id] = tuple(float(v) for v in interpolated)

    return CalibratedSimulationOutcome(
        succeeded=True,
        message=None,
        time_grid=tuple(float(v) for v in requested),
        species_trajectories=species_trajectories,
        reaction_flux_trajectories=reaction_trajectories or None,
        final_state=final_state,
    )


def is_trivial_trajectory(
    outcome: CalibratedSimulationOutcome, *, tolerance: float = 1e-12
) -> bool:
    """``True`` if every species' trajectory in ``outcome`` stays within ``tolerance`` of its
    own starting value for the entire simulated horizon -- reimplements, independently, the
    same judgment ``app.agent3.diagnostics.trivial_trajectory_finding`` makes on the sibling
    Agent 3 repository, since Agent 5 never imports Agent 3's code but needs the same concept to
    honestly label an experimental-design candidate it cannot meaningfully connect to a
    prediction."""
    if not outcome.succeeded or outcome.species_trajectories is None:
        return False
    for values in outcome.species_trajectories.values():
        arr = np.asarray(values, dtype=float)
        if not np.isfinite(arr).all():
            return False
        if arr.max() - arr.min() >= tolerance:
            return False
    return True


__all__ = [
    "DIVERGENCE_MAGNITUDE_THRESHOLD",
    "CalibratedSimulationOutcome",
    "is_trivial_trajectory",
    "simulate_calibrated_model",
]
