# Agent 5 — Responsibility Boundary

Agent 5 is the **Validation and Experimental Design Agent** in the five-agent biochemical-
modeling pipeline (Agent 1 curation → Agent 2 model assembly → Agent 3 simulation/diagnostics →
Agent 4 calibration → **Agent 5 validation/experimental design**). Agent 5 completes the first
full pass of the five-agent workflow.

## Central rule

> Agent 5 validates and prioritizes experiments; it does not recalibrate the model, invent
> data, or silently change biology.

## What Agent 5 does

1. **Consumes** a plain, JSON-serializable handoff dict combining Agent 2's own model/parameter
   metadata and a lightweight mirror of Agent 4's calibration report — see `docs/
   02_agent4_to_agent5_contract.md`.
2. **Applies Agent 4's own already-declared fitted values** (never a different value) to the
   Agent 2 model and simulates it once, fresh, against caller-supplied held-out observations.
3. **Computes validation metrics** (RMSE, weighted SSE, max absolute residual) and compares
   them against Agent 4's own already-reported training performance to detect overfitting.
4. **Aggregates Agent 4's own identifiability findings** into a dominant-uncertainty parameter
   list — never recomputing Agent 4's own identifiability logic independently.
5. **Generates and scores candidate experiments** — measurements and perturbations — by a
   deterministic, local, diagonal Fisher-information-style sensitivity proxy, explicitly
   labeled as such (never presented as full Bayesian optimal experimental design).
6. **Explains every recommendation**: every `ExperimentScore` carries a `rationale` naming which
   uncertain parameters it informs and, where applicable, which poorly-constrained parameter it
   discriminates that the existing data does not.
7. **Verifies** that Agent 4's own calibrated values were never touched during this process, as
   a defensive, literal invariant check.

## What Agent 5 explicitly does NOT do

- **Does not recalibrate anything.** Held-out observations are used only to *evaluate* the
  already-fitted model; Agent 5 never runs an optimizer, never adjusts a parameter or initial
  condition, and never feeds validation data back into a fitting process.
- **Does not invent observations.** Every `ValidationObservation` is supplied by the caller. The
  only "synthetic" data anywhere in this repository is in its own clearly-labeled test
  fixtures, built from known-ground-truth toy models, never presented as real biological data.
- **Does not silently change biology.** No kinetic law, parameter value, or initial condition in
  the Agent 2 model is ever altered — Agent 5 only reads the model and Agent 4's own fitted
  values, simulates, and reports.
- **Does not claim full Bayesian optimal experimental design.** The candidate-scoring method is
  a modest, local, per-parameter (diagonal) sensitivity proxy — see `docs/
  04_experimental_design_scoring_policy.md` for exactly what it does and does not establish.
- **Does not recommend a measurement the model cannot meaningfully connect to a prediction
  without disclosing that limitation explicitly.** A candidate whose sensitivity cannot be
  computed (e.g. because the calibrated model's own baseline trajectory is trivial) is still
  reported, with its `feasibility_note` and a dedicated `ExperimentalDesignFinding` disclosing
  exactly why, rather than silently ranked alongside genuinely-uninformative candidates.
- **Does not modify Agent 1, 2, 3, or 4 code or output.** Agent 5 never imports any sibling
  package's Python code — it consumes only the plain-dict contract documented in `docs/
  02_agent4_to_agent5_contract.md`.
- **Does not decide whether the underlying biology is correct.** `ValidationStatus` and
  `sufficient_for_full_workflow` are completeness/traceability judgments, never a claim that the
  calibrated model, or the recommendations built on it, are scientifically validated.
- **Does not pretend to validate yeast biology without real data.** The real `sce00061`
  integration in this repository deliberately reports `INSUFFICIENT_VALIDATION_DATA` (there are
  no real held-out observations for this model) and labels every measurement-class observation
  explicitly as a workflow-test recommendation, never a validated experimental priority.

## Relationship to neighboring agents

| Agent | Relationship to Agent 5 |
|---|---|
| Agent 1 (curation) | Four hops upstream; never read directly. |
| Agent 2 (model assembly) | Indirectly upstream via the handoff's `agent2_model` section. |
| Agent 3 (simulation/diagnostics) | Not part of Agent 5's own handoff contract directly — Agent 3's findings reach Agent 5 only insofar as Agent 4 already carried them through its own report. |
| Agent 4 (calibration) | Indirectly upstream via the handoff's `agent4_report` section — Agent 5 never imports Agent 4's Python package, and never recomputes Agent 4's own calibration or identifiability logic. |
| Agent 5 (this repository) | Validates and ranks; never edits the model or its fitted values. |

Agent 5 completes the first full pass of the intended five-agent workflow: curate → assemble →
simulate/diagnose → calibrate → validate/design. There is no Agent 6 in Version 1 — the output
of this repository is the workflow's own final structured artifact for this pass.
