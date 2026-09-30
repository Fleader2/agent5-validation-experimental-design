# Recommendation Provenance

How Agent 5 traces every recommendation back to a real model entity, a real Agent 4 finding, or
a real held-out observation — never an invented one.

## Every id is a real entity id

`CandidateExperiment.target_id` is always one of: a `species_id` from `agent2_model.species`
(for `METABOLITE_CONCENTRATION_AT_TIME`/`INITIAL_CONCENTRATION_PERTURBATION`), a `reaction_id`
from `agent2_model.reactions` (for `REACTION_FLUX`), or a `parameter_id` from
`agent2_model.parameters`/a target id already appearing in
`agent4_report.calibration.parameter_estimates` (for `PARAMETER_PERTURBATION`/
`ENZYME_KINETIC_PARAMETER`). None of these ids is ever invented, renamed, or abbreviated — a
downstream reader can always look the id up directly in the Agent 2 model or Agent 4 report
this Agent 5 report was built from.

## `ExperimentScore.related_parameter_ids`

Every target id whose sensitivity component actually contributed to the candidate's own
`information_score` (a non-negligible `weight[T] * sensitivity[T]**2` term) — never every
uncertain target unconditionally, only the ones this specific candidate actually informs.

## `ExperimentScore.discriminates_between_target_ids`

Every target id this candidate specifically reveals information about that the *already-
supplied validation observations* do not (see `docs/04_experimental_design_scoring_policy.md`
for the exact criterion) — traceable to a concrete comparison: this candidate's own computed
sensitivity versus `reference_information[T]`, itself computed from the caller's own supplied
`ValidationObservationSet`, never an assumption about what "should" already be known.

## `ExperimentScore.rationale`

Always a plain-English sentence naming the score, how many targets it informs, and (when
applicable) which targets it discriminates — per the task's own explicit requirement that every
recommendation explain why it is useful, never a bare ranked number.

## `GeneralizationFinding.related_parameter_ids`

For the `DOMINANT_UNCERTAINTY_PARAMETER` finding: exactly the target ids
`dominant_uncertainty_parameter_ids` collected from Agent 4's own `identifiability_findings` —
traceable, one hop, back to the specific Agent 4 finding(s) that named each one (Agent 4's own
`finding_id`s are not currently re-exposed on this aggregate finding, since Version 1 treats
the aggregation itself, not a finding-by-finding replay, as the useful unit here — a caller
wanting the original Agent 4 finding detail can read `agent4_report.calibration
.identifiability_findings` directly, which Agent 5 carries through unmodified in its own parsed
handoff).

## `ParameterEstimate` -- carried through, not recomputed

Agent 5 never constructs its own `ParameterEstimate`-like object. Every fitted value, original
value, original source, and `provenance_refs` a recommendation might reference by id is read
directly from `agent4_report.calibration.parameter_estimates`, exactly as Agent 4 declared it.

## `Agent5Report`'s own top-level traceability

`agent2_model_id` and `agent4_report_id` are always copied verbatim from the parsed handoff —
never regenerated, so a reader can always confirm which exact upstream Agent 2 model and Agent
4 report this Agent 5 report was built from.

## What this does NOT mean

Provenance-preserving does not mean every recommendation is correct or will remain the top
recommendation after more data arrives — it means every recommendation's own reasoning is fully
reconstructable from ids already present in the upstream contract, never a number with no
traceable origin.
