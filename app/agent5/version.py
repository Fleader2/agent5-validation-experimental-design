"""Agent 5 version/policy markers.

These are architecture/contract-shape version markers, not claims of validation maturity or
experimental-design optimality. Bump a constant only when the shape or policy it names actually
changes -- mirrors ``app.agent2.version``/``app.agent3.version``/``app.agent4.version``'s own
identical convention on the sibling repositories.

* ``AGENT5_CONTRACT_VERSION`` -- the version of Agent 5's own output contract
  (``app.agent5.types``: ``Agent5Report`` and the rest).
* ``AGENT5_HANDOFF_CONTRACT_VERSION`` -- the version of the Agent 2/Agent 4 -> Agent 5 handoff
  contract this repository was built against (``app.agent5.handoff``, ``docs/
  02_agent4_to_agent5_contract.md``). Not a guarantee that every upstream contract version is
  compatible -- version reconciliation is deferred, exactly as every earlier boundary's own
  precedent.
* ``VALIDATION_POLICY_VERSION`` -- the version of the validation-simulation/metric/
  generalization policy (metrics computed, overfit threshold, status precedence).
* ``EXPERIMENTAL_DESIGN_POLICY_VERSION`` -- the version of the candidate-experiment generation
  and scoring policy (default candidate types, sensitivity/Fisher-information proxy, ranking
  rule).
"""

from __future__ import annotations

AGENT5_CONTRACT_VERSION = "0.1"
AGENT5_HANDOFF_CONTRACT_VERSION = "agent2-agent4-to-agent5-v1"
VALIDATION_POLICY_VERSION = "validation-v1"
EXPERIMENTAL_DESIGN_POLICY_VERSION = "experimental-design-v1"

__all__ = [
    "AGENT5_CONTRACT_VERSION",
    "AGENT5_HANDOFF_CONTRACT_VERSION",
    "EXPERIMENTAL_DESIGN_POLICY_VERSION",
    "VALIDATION_POLICY_VERSION",
]
