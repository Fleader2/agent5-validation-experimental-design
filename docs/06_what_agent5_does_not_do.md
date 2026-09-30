# What Agent 5 Explicitly Does Not Do

A standalone, exhaustive list (the same commitments are stated in context throughout `docs/
01_agent5_responsibility_boundary.md`, gathered here as a single reference).

1. **Does not recalibrate the model.** No optimizer runs anywhere in this repository. Held-out
   observations are used exclusively to *evaluate* Agent 4's already-fitted values; they are
   never fed into a fitting process, and no parameter or initial-condition value in the Agent 2
   model is ever adjusted.
2. **Does not invent observations.** Every `ValidationObservation` comes from the caller. This
   repository's own synthetic test fixtures are clearly labeled as synthetic and are never
   presented as, or mixed with, real biological data.
3. **Does not silently change biology.** No kinetic law, stoichiometry, compartment, or
   parameter/initial-condition value in the Agent 2 model is ever mutated.
4. **Does not claim formal or full Bayesian optimal experimental design.** The scoring method
   is a disclosed, modest, diagonal local-sensitivity/Fisher-information proxy — see `docs/
   04_experimental_design_scoring_policy.md`.
5. **Does not present an unconnectable candidate as "checked and uninformative."** A candidate
   that cannot be meaningfully simulated (e.g. a trivial baseline trajectory) is scored `0.0`
   but flagged with a dedicated `feasibility_note` and `ExperimentalDesignFinding` naming the
   limitation explicitly.
6. **Does not recompute Agent 3's or Agent 4's own diagnostic/identifiability logic.** Every
   Agent-4-declared finding is read and aggregated, never independently re-derived from
   scratch (with the sole, disclosed exception of `is_trivial_trajectory`, which reimplements —
   never imports — the same judgment Agent 3 already makes, because Agent 5 needs it locally
   and does not have access to Agent 3's own report at all in its Version 1 contract).
7. **Does not import any sibling package's Python code.** Agent 2, Agent 3, and Agent 4 are
   consumed exclusively through the plain-dict contract in `docs/
   02_agent4_to_agent5_contract.md`.
8. **Does not modify Agent 1, 2, 3, or 4's code or output.** No change was made to any sibling
   repository while building Agent 5; every interface question was resolved entirely within
   this repository's own code.
9. **Does not decide whether the underlying biology is correct.** `ValidationStatus` and
   `sufficient_for_full_workflow` are completeness/traceability judgments, never a scientific
   verdict.
10. **Does not fabricate real yeast validation success.** The real `sce00061` integration in
    this repository reports `INSUFFICIENT_VALIDATION_DATA` because no real held-out
    observations exist for this model, and labels every measurement-class observation
    explicitly as a workflow-test recommendation.
11. **Does not implement or begin Version 2 work**, and does not implement an Agent 6 (none is
    specified) — Version 1 stops at a complete, traceable structured report.
