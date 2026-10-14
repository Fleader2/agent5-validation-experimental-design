"""Shared, hand-crafted fixtures for Agent 5's own test suite.

Every synthetic model here is small and clearly labeled as synthetic -- per the task's own
explicit instruction, Version 1's validation/experimental-design tests are proven against
known-ground-truth synthetic models first, never against fabricated yeast biology. The real
sce00061 fixture (``load_real_sce00061_handoff``) is used only to prove Agent 5 can *parse* the
real Agent 2/Agent 4 context and correctly identify workflow-test-only recommendations -- never
to pretend real biological validation happened without real held-out data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.agent5.handoff import parse_agent5_handoff
from app.agent5.loader import load_antimony_model

_INVALID_CHAR = re.compile(r"[^A-Za-z0-9_]")


def _sanitize(raw: str) -> str:
    return _INVALID_CHAR.sub("_", raw)


ONE_PARAMETER_TRUE_K = 0.7

#: A single first-order decay: dS1/dt = -k1*S1. Reaction id sanitized to match Agent 2's own
#: Antimony naming convention (``J_<reaction_id>``), exactly as Agent 3/Agent 4's own fixtures
#: do -- ``minimal_agent2_model_dict``'s own ``antimony_symbol_map`` below resolves these
#: fixtures' targets exactly as the real sce00061 integration does, never bypassing it.
ONE_PARAMETER_ANTIMONY = f"""
model decay
  compartment C = 1
  species s_S1 in C
  s_S1 = 10
  J_reaction_1: s_S1 -> ;
  J_reaction_1 = p_k1 * s_S1
  p_k1 = {ONE_PARAMETER_TRUE_K}
end
"""

TWO_PARAMETER_TRUE_K1 = 0.5
TWO_PARAMETER_TRUE_K2 = 0.2

#: A two-step irreversible chain S1 -> S2 -> S3. S1(t) depends only on k1; S3(t) depends on
#: both -- used to test that a candidate measuring S3 discriminates k2 when only S1 was ever
#: measured (making k2 poorly identifiable from that limited data alone).
TWO_PARAMETER_ANTIMONY = f"""
model chain
  compartment C = 1
  species s_S1 in C
  species s_S2 in C
  species s_S3 in C
  s_S1 = 10
  s_S2 = 0
  s_S3 = 0
  J_reaction_1: s_S1 -> s_S2;
  J_reaction_1 = p_k1 * s_S1
  J_reaction_2: s_S2 -> s_S3;
  J_reaction_2 = p_k2 * s_S2
  p_k1 = {TWO_PARAMETER_TRUE_K1}
  p_k2 = {TWO_PARAMETER_TRUE_K2}
end
"""

#: Simple decay with an undeclared initial concentration (None/None in the Agent 2 contract) --
#: the baseline trajectory is trivial (everything stays at 0) until that initial concentration
#: is established, exactly mirroring the real sce00061 model's own honest limitation.
MISSING_IC_KNOWN_K = 0.3
MISSING_IC_ANTIMONY = f"""
model missing_ic
  compartment C = 1
  species s_S1 in C
  s_S1 = 0
  J_reaction_1: s_S1 -> ;
  J_reaction_1 = p_k1 * s_S1
  p_k1 = {MISSING_IC_KNOWN_K}
end
"""


def minimal_agent2_model_dict(antimony_text: str, **overrides) -> dict:
    base = {
        "contract_version": "agent2-downstream-v3",
        "model_id": "test-model-1",
        "network_id": "test-network-1",
        "antimony_text": antimony_text,
        "antimony_generator_version": "test-generator-v0",
        "readiness": "EXECUTABLE",
        "unresolved_reaction_ids": [],
        "unresolved_kinetic_law_ids": [],
        "compartments": [
            {
                "compartment_id": "C",
                "name": "C",
                "initial_volume": "1",
                "volume_unit": "L",
                "constant": True,
            }
        ],
        "species": [
            {
                "species_id": "S1",
                "name": "S1",
                "compartment_id": "C",
                "source_compound_id": None,
                "source_enzyme_state_id": None,
                "initial_amount": None,
                "initial_concentration": "10",
                "constant": False,
                "boundary_condition": False,
                "initialization_source": None,
            }
        ],
        "reactions": [
            {
                "reaction_id": "reaction-1",
                "name": "decay",
                "reversible": False,
                "participants": [{"species_id": "S1", "role": "REACTANT", "stoichiometry": "1"}],
            }
        ],
        "kinetic_laws": [
            {
                "kinetic_law_id": "reaction-1::kinetic-law::none",
                "reaction_id": "reaction-1",
                "law_type": "MASS_ACTION",
                "expression": "k1 * S1",
                "parameter_ids": ["k1"],
                "species_ids": ["S1"],
                "enzyme_state_id": None,
                "protein_id": None,
                "complex_id": None,
                "assumptions": [],
            }
        ],
        "parameters": [
            {
                "parameter_id": "k1",
                "name": "k1",
                "source": "HEURISTIC_INITIALIZATION",
                "value": "0.1",
                "unit": "per_sec",
                "reaction_id": "reaction-1",
                "kinetic_law_assignment_id": "reaction-1::kinetic-law::none",
                "uncertainty_text": "Heuristic default; requires calibration.",
                "provenance_refs": [],
                "lower_bound": None,
                "upper_bound": None,
                "fixed": None,
            }
        ],
        "model_assumptions": [],
    }
    base.update(overrides)
    base.setdefault(
        "antimony_symbol_map",
        {
            "species": {s["species_id"]: f"s_{s['species_id']}" for s in base["species"]},
            "reactions": {
                r["reaction_id"]: f"J_{_sanitize(r['reaction_id'])}" for r in base["reactions"]
            },
            "parameters": {
                p["parameter_id"]: f"p_{p['parameter_id']}" for p in base["parameters"]
            },
        },
    )
    return base


def minimal_agent4_report_dict(**overrides) -> dict:
    base = {
        "report_id": "agent4-report-test",
        "agent4_contract_version": "0.1",
        "agent2_model_id": "test-model-1",
        "agent3_report_id": "agent3-report-test",
        "request_id": "agent4-req-test",
        "calibration": {
            "calibration_run_id": "run-1",
            "status": "SUCCESS",
            "objective_before": 260.0,
            "objective_after": 1e-9,
            "parameter_estimates": [
                {
                    "target_kind": "PARAMETER",
                    "target_id": "k1",
                    "original_value": 0.1,
                    "original_source": "HEURISTIC_INITIALIZATION",
                    "fitted_value": ONE_PARAMETER_TRUE_K,
                    "lower_bound": 0.01,
                    "upper_bound": 5.0,
                    "at_lower_bound": False,
                    "at_upper_bound": False,
                    "new_source": "CALIBRATED",
                    "provenance_refs": ["obs-set-1", "run-1"],
                }
            ],
            "residuals": [
                {
                    "observation_id": "o1",
                    "partition": "TRAIN",
                    "residuals": [0.0] * 11,
                    "sum_squared_residual": 1e-9,
                    "weighted_sum_squared_residual": 1e-9,
                    "n_points": 11,
                }
            ],
            "identifiability_findings": [],
            "n_multistarts": 3,
            "best_start_index": 0,
            "all_start_objectives": [1e-9, 0.5, 0.3],
        },
        "fixed_parameters_verified_unchanged": True,
        "fixed_parameter_ids_checked": [],
        "sufficient_for_agent5": True,
        "sufficiency_note": "ok",
    }
    base.update(overrides)
    return base


def build_handoff_dict(agent2_model: dict, agent4_report: dict | None = None) -> dict:
    return {
        "agent2_model": agent2_model,
        "agent4_report": agent4_report or minimal_agent4_report_dict(),
    }


def parsed_handoff(agent2_model: dict, agent4_report: dict | None = None):
    return parse_agent5_handoff(build_handoff_dict(agent2_model, agent4_report))


def simulate_truth(antimony_text: str, species_id: str, end_time: float, num_points: int):
    """Simulate ``antimony_text`` as-is (its own declared "true" parameter values) and return
    ``(time_points, values)`` for ``species_id``."""
    load_result = load_antimony_model(antimony_text)
    assert load_result.succeeded, load_result.message
    rr = load_result.roadrunner_instance
    sim = rr.simulate(0.0, end_time, num_points)
    colnames = [c.strip("[]") for c in sim.colnames]
    col_index = colnames.index(species_id)
    time_points = tuple(float(t) for t in sim[:, 0])
    values = tuple(float(v) for v in sim[:, col_index])
    return time_points, values


def load_real_sce00061_handoff() -> dict:
    """The real, saved Agent 2/Agent 4 handoff for the current ``sce00061`` model -- built once,
    in this session, by combining the sibling Agent 4 repository's own real
    ``sce00061_agent4_handoff.json`` (whose ``agent2_model`` section is already the exact shape
    this module needs) with a fresh, real ``Agent4Report`` produced by actually running Agent
    4's own committed pipeline against it, with zero real observations supplied (so Agent 4
    itself correctly reports ``INSUFFICIENT_DATA`` and no parameter is actually calibrated --
    the honest, real state of this workflow today)."""
    fixture_path = (
        Path(__file__).resolve().parent.parent / "fixtures" / "sce00061_agent5_handoff.json"
    )
    with open(fixture_path) as f:
        return json.load(f)


__all__ = [
    "MISSING_IC_ANTIMONY",
    "MISSING_IC_KNOWN_K",
    "ONE_PARAMETER_ANTIMONY",
    "ONE_PARAMETER_TRUE_K",
    "TWO_PARAMETER_ANTIMONY",
    "TWO_PARAMETER_TRUE_K1",
    "TWO_PARAMETER_TRUE_K2",
    "build_handoff_dict",
    "load_real_sce00061_handoff",
    "minimal_agent2_model_dict",
    "minimal_agent4_report_dict",
    "parsed_handoff",
    "simulate_truth",
]
