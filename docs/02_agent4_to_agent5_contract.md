# Agent 4 → Agent 5 Contract (`agent2-agent4-to-agent5-v1`)

This is the smallest stable input shape Agent 5 Version 1 requires, expressed as a plain,
JSON-serializable dict with two top-level keys: `agent2_model` and `agent4_report`.
`app.agent5.handoff.parse_agent5_handoff` parses and validates it into the frozen
`Agent5Handoff` dataclass family in `app.agent5.handoff`. Agent 5 never imports Agent 2's,
Agent 3's, or Agent 4's Python package.

## `agent2_model`

Identical shape to the sibling Agent 4 repository's own `agent2_model` (see `agent4-
calibration-estimator/docs/02_agent2_agent3_to_agent4_contract.md` for the full field table):
`contract_version`, `model_id`, `network_id`, `antimony_text`, `antimony_generator_version`,
`readiness`, `unresolved_reaction_ids`/`unresolved_kinetic_law_ids`, `compartments[]`,
`species[]` (including `initialization_source`), `reactions[]`, `kinetic_laws[]`,
`parameters[]` (including `lower_bound`/`upper_bound`/`fixed`), `model_assumptions[]`.

Agent 5 needs the full structural contract (not just Agent 4's fitted values) because it must:
simulate the model at all (needs `antimony_text`); identify species with a missing initial
condition as candidate measurement targets (needs `species[].initial_amount`/
`.initial_concentration`); generate `REACTION_FLUX` candidates (needs `reactions[]`).

## `agent4_report`

A lightweight mirror of Agent 4's own `Agent4Report`:

| Field | Type | Notes |
|---|---|---|
| `report_id` | str | Carried through onto `Agent5Report.agent4_report_id`. |
| `agent4_contract_version` | str | Informational. |
| `agent2_model_id` | str | Cross-check against `agent2_model.model_id`. |
| `agent3_report_id` | str | Carried through from Agent 4's own report (traces back to Agent 3). |
| `request_id` | str | Agent 4's own request id. |
| `calibration` | object | See below. |
| `fixed_parameters_verified_unchanged` | bool | Agent 4's own invariant check result. |
| `fixed_parameter_ids_checked` | list[str] | Agent 4's own declared fixed-parameter ids. |
| `sufficient_for_agent5` | bool | Agent 4's own verdict — informational only. |
| `sufficiency_note` | str | Agent 4's own explanation. |

`calibration` mirrors Agent 4's own `CalibrationResult`:

| Field | Type | Notes |
|---|---|---|
| `calibration_run_id` | str | Traced into every `ParameterEstimate.provenance_refs`. |
| `status` | str | Agent 4's own `CalibrationStatus` value. |
| `objective_before`/`objective_after` | float or null | Informational. |
| `parameter_estimates[]` | list of estimate views | The **only** values Agent 5 ever applies to the model — see below. |
| `residuals[]` | list of residual-summary views | Used to compute `TRAIN`-partition metrics for overfit comparison — see `docs/03_validation_semantics.md`. |
| `identifiability_findings[]` | list of finding views | Aggregated into `dominant_uncertainty_parameter_ids` — never recomputed. |
| `n_multistarts`, `best_start_index`, `all_start_objectives` | — | Carried through, not currently used by Agent 5's own logic. |

Each `parameter_estimates[]` entry: `target_kind` (`"PARAMETER"`\|`"INITIAL_CONCENTRATION"`),
`target_id`, `original_value`, `original_source`, `fitted_value`, `lower_bound`, `upper_bound`,
`at_lower_bound`, `at_upper_bound`, `new_source` (always `"CALIBRATED"`), `provenance_refs[]`.
`app.agent5.validation.calibrated_overrides` reads exactly these `target_id`/`fitted_value`
pairs and nothing else to build the vector of values applied before every simulation.

Each `residuals[]` entry: `observation_id`, `partition` (`"TRAIN"`\|`"VALIDATION"`),
`residuals[]`, `sum_squared_residual`, `weighted_sum_squared_residual`, `n_points`.

Each `identifiability_findings[]` entry: `finding_id`, `category` (e.g. `"LOW_SENSITIVITY"`,
`"HIGH_CORRELATION"`, `"BOUND_HIT"`, `"DEGENERATE_OBJECTIVE"`, `"INSUFFICIENT_OBSERVATIONS"`),
`severity`, `summary`, `explanation`, `related_target_ids[]`.

## How the real `sce00061` fixture for this repository was built

`tests/fixtures/sce00061_agent5_handoff.json` was assembled, in this session, by:

1. Reusing the sibling Agent 4 repository's own real `agent2_model` section verbatim (already
   validated: 53 species, 38 reactions, 109 parameters, with `lower_bound`/`upper_bound`/`fixed`/
   `initialization_source` all confirmed `null` for every entry).
2. Actually running Agent 4's own committed pipeline (`run_agent4_pipeline`) against that model
   with one nominally-eligible heuristic parameter as a target and **zero real observations**
   supplied — because no real yeast observation data exists for this model. Agent 4 itself
   correctly returned `CalibrationStatus.INSUFFICIENT_DATA` with **zero parameter estimates**.
3. Serializing that real `Agent4Report` (not a fabricated one) into the shape above.

This is the honest, real state of the workflow today: nothing has actually been calibrated for
`sce00061`, so Agent 5's own real-integration test operates on a report with no fitted values
at all — exactly what a genuine "no data yet" state looks like, never disguised as a successful
calibration.
