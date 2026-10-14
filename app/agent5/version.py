"""Agent 5 version/policy markers.

These are architecture/contract-shape version markers, not claims of validation maturity or
experimental-design optimality. Bump a constant only when the shape or policy it names actually
changes -- mirrors ``app.agent2.version``/``app.agent3.version``/``app.agent4.version``'s own
identical convention on the sibling repositories.

* ``AGENT5_CONTRACT_VERSION`` -- the version of Agent 5's own output contract
  (``app.agent5.types``: ``Agent5Report`` and the rest).
* ``AGENT5_HANDOFF_CONTRACT_VERSION`` -- the version of the Agent 2 model metadata embedded in
  this repository's own two-key handoff contract (``app.agent5.handoff``, ``docs/
  02_agent4_to_agent5_contract.md``). Five-Agent Workflow V1 Hardening increment: this is now
  ``"agent2-downstream-v1"``, the one canonical name Agent 2's own
  ``AGENT2_DOWNSTREAM_CONTRACT_VERSION`` emits and Agents 3, 4, and 5 all consume unchanged --
  replacing this repository's own previously-divergent ``"agent2-agent4-to-agent5-v1"`` name
  for what was already the identical real ``agent2_model`` artifact shape Agents 3 and 4 both
  consume. Not a guarantee that every upstream contract version is compatible -- version
  reconciliation is deferred, exactly as every earlier boundary's own precedent.

  **Human-Readable Antimony Naming and Provenance Separation increment (Agent 2):** bumped
  ``"agent2-downstream-v1"`` -> ``"agent2-downstream-v2"``. Agent 2's generated Antimony
  symbols now prefer a curated biological name over a bare id, which this repository's own
  former ``app.agent5.antimony_ids`` module -- an independent re-implementation of Agent 2's
  *old* id-only naming rule -- could no longer resolve correctly. That module is removed
  entirely: Agent 2's own ``antimony_symbol_map`` field (new in v2) is the one source of truth
  for resolving a handoff entity id to its real, compiled Antimony identifier. See
  ``app.agent5.handoff.Agent2Model.antimony_symbol_map``.
* ``VALIDATION_POLICY_VERSION`` -- the version of the validation-simulation/metric/
  generalization policy (metrics computed, overfit threshold, status precedence).
* ``EXPERIMENTAL_DESIGN_POLICY_VERSION`` -- the version of the candidate-experiment generation
  and scoring policy (default candidate types, sensitivity/Fisher-information proxy, ranking
  rule).
"""

from __future__ import annotations

AGENT5_CONTRACT_VERSION = "0.1"
AGENT5_HANDOFF_CONTRACT_VERSION = "agent2-downstream-v2"
VALIDATION_POLICY_VERSION = "validation-v1"
EXPERIMENTAL_DESIGN_POLICY_VERSION = "experimental-design-v1"

__all__ = [
    "AGENT5_CONTRACT_VERSION",
    "AGENT5_HANDOFF_CONTRACT_VERSION",
    "EXPERIMENTAL_DESIGN_POLICY_VERSION",
    "VALIDATION_POLICY_VERSION",
]
