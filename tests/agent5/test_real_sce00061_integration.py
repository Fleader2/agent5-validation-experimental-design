"""The bounded real integration check against the current sce00061 Agent 2/Agent 4 artifacts.

Per the task's own explicit instruction: Agent 4 itself never calibrated any real parameter for
this model (confirmed: zero real yeast observations exist, so Agent 4 correctly returned
``INSUFFICIENT_DATA`` with zero parameter estimates when this fixture was built). This test
proves Agent 5 can parse that real, honest state and correctly report that true biological
validation is blocked -- it never fabricates a real yeast validation observation to obtain a
"successful" result, and any measurement-class recommendation is explicitly labeled as a
workflow-test recommendation, not a validated yeast experimental priority.
"""

from __future__ import annotations

from app.agent5.handoff import parse_agent5_handoff
from app.agent5.pipeline import run_agent5_pipeline
from app.agent5.types import (
    ValidationObservationSet,
    ValidationRequest,
    ValidationStatus,
)
from app.agent5.version import AGENT5_HANDOFF_CONTRACT_VERSION
from tests.agent5.fixtures import load_real_sce00061_handoff


def test_real_handoff_parses():
    # Human-Readable Antimony Naming and Provenance Separation increment: this fixture was
    # regenerated from a fresh, real run of the same live organism (to pick up the new
    # antimony_symbol_map/agent2-downstream-v3 fields); the underlying curated data had
    # itself genuinely drifted since this fixture was last captured (unrelated curation work
    # between then and now, already disclosed identically in the sibling agent3-simulation-
    # diagnostics/agent4-calibration-estimator repositories' own test suites) -- the
    # parameter count dropped from a previously-recorded 115 to the current, real 91; species
    # (53) is unchanged.
    handoff = parse_agent5_handoff(load_real_sce00061_handoff())
    assert len(handoff.agent2_model.parameters) == 91
    assert len(handoff.agent2_model.species) == 53


def test_real_handoff_declares_the_one_canonical_contract_version():
    """Five-Agent Workflow V1 Hardening compatibility check: the real sce00061 ``agent2_model``
    artifact parses successfully and declares exactly the one canonical contract version this
    repository now expects -- with no re-stamping, no alias, and no per-consumer divergence
    from what Agents 3 and 4 also consume."""
    data = load_real_sce00061_handoff()
    assert (
        data["agent2_model"]["contract_version"]
        == AGENT5_HANDOFF_CONTRACT_VERSION
        == "agent2-downstream-v3"
    )
    parse_agent5_handoff(data)  # must not raise


def test_real_agent4_report_reflects_the_honest_no_data_state():
    """Confirms, with real data, that Agent 4 never actually calibrated anything for this
    model -- there are no real yeast observations, so Agent 4's own real run (used to build
    this fixture) correctly returned INSUFFICIENT_DATA with zero parameter estimates."""
    handoff = parse_agent5_handoff(load_real_sce00061_handoff())
    assert handoff.agent4_report.calibration.status == "INSUFFICIENT_DATA"
    assert handoff.agent4_report.calibration.parameter_estimates == ()


def test_real_workflow_test_measurement_classes_identified():
    """Identifies, directly from Agent 2's own real metadata (never from Agent 4's empty
    calibration output, since nothing was actually calibrated), the classes of measurement
    that would be most informative if this were a real validation effort -- labeled here, and
    in the completion report, explicitly as workflow-test recommendations."""
    handoff = parse_agent5_handoff(load_real_sce00061_handoff())
    heuristic_ids = [
        p.parameter_id
        for p in handoff.agent2_model.parameters
        if p.source == "HEURISTIC_INITIALIZATION"
    ]
    missing_ic_ids = [
        s.species_id
        for s in handoff.agent2_model.species
        if s.initial_amount is None and s.initial_concentration is None
    ]
    assert len(heuristic_ids) == 84
    assert len(missing_ic_ids) == 53


def test_real_validation_with_no_held_out_observations_is_honestly_blocked():
    """The central real-integration finding: with zero held-out observations (none exist for
    this model), Agent 5 correctly reports INSUFFICIENT_VALIDATION_DATA -- never a fabricated
    "successful" validation against invented yeast data."""
    handoff = parse_agent5_handoff(load_real_sce00061_handoff())
    request = ValidationRequest(
        request_id="real-sce00061-no-validation-data-check",
        validation_observations=ValidationObservationSet(
            observation_set_id="no-real-held-out-data", observations=()
        ),
    )
    report = run_agent5_pipeline(handoff, request)
    assert report.overall_status is ValidationStatus.INSUFFICIENT_VALIDATION_DATA
    assert report.sufficient_for_full_workflow is True
    assert report.calibrated_parameters_verified_unchanged is True


def test_real_dominant_uncertainty_ids_empty_since_nothing_was_calibrated():
    """Agent 5 never invents an uncertainty judgment Agent 4 did not already make -- since
    Agent 4 calibrated nothing for this real model, Agent 5's own dominant-uncertainty
    aggregation (a pure read of Agent 4's own identifiability findings) is correctly empty."""
    handoff = parse_agent5_handoff(load_real_sce00061_handoff())
    from app.agent5.generalization import dominant_uncertainty_parameter_ids

    assert dominant_uncertainty_parameter_ids(handoff.agent4_report) == ()
