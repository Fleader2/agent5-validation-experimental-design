# Agent 4 → Agent 5 Contract

This is the smallest stable input shape Agent 5 Version 1 requires, expressed as a plain,
JSON-serializable dict with two top-level keys: `agent2_model` and `agent4_report`.
`app.agent5.handoff.parse_agent5_handoff` parses and validates it into the frozen
`Agent5Handoff` dataclass family in `app.agent5.handoff`. Agent 5 never imports Agent 2's,
Agent 3's, or Agent 4's Python package.

**Five-Agent Workflow V1 Hardening increment:** `agent2_model.contract_version` was previously
expected to be `"agent2-agent4-to-agent5-v1"` — a name this repository invented independently of
Agent 3's `"agent2-to-agent3-v1"` and Agent 4's `"agent2-agent3-to-agent4-v1"`, even though all
three described the identical real artifact shape. It became `"agent2-downstream-v1"`
(`AGENT5_HANDOFF_CONTRACT_VERSION`), the one canonical name Agent 2's own
`AGENT2_DOWNSTREAM_CONTRACT_VERSION` emits and Agents 3, 4, and 5 all consume unchanged. The
`agent2_model` shape itself was unchanged by that rename; `agent4_report`'s own shape and the
overall two-key wrapping were also unchanged.

**Human-Readable Antimony Naming and Provenance Separation increment:** bumped again,
`"agent2-downstream-v1"` → `"agent2-downstream-v2"`, adding `agent2_model.antimony_symbol_map`
(see the sibling Agent 3 repository's own contract doc for the full field description —
`agent2_model` stays field-for-field identical to Agents 3 and 4's own shape). Agent 2's
generated Antimony symbols now prefer a curated biological name over a bare id, which this
repository's own former `app.agent5.antimony_ids` module — an independent re-implementation of
Agent 2's *old* id-only naming rule, the only one of the three sibling re-implementations that
also covered *reactions* (`candidate_reaction_antimony_id`, for `REACTION_FLUX` candidate
experiments) — could no longer resolve correctly. That module is removed entirely:
`app.agent5.simulation.simulate_calibrated_model` now takes `parameter_symbol_map`/
`species_symbol_map` arguments (`agent2_model.antimony_symbol_map.parameters`/`.species`
directly) instead of locally re-deriving a candidate identifier, and
`app.agent5.handoff.species_antimony_id_map`/`reaction_antimony_id_map` replace
`app.agent5.antimony_ids.build_species_antimony_id_map`/`build_reaction_antimony_id_map` for
building the reverse (symbol → id) maps trajectories/fluxes are relabeled with.

## `agent2_model`

Identical shape to the sibling Agent 4 repository's own `agent2_model` (see `agent4-
calibration-estimator/docs/02_agent2_agent3_to_agent4_contract.md` for the full field table):
`contract_version`, `model_id`, `network_id`, `antimony_text`, `antimony_generator_version`,
`antimony_symbol_map`, `readiness`, `unresolved_reaction_ids`/`unresolved_kinetic_law_ids`,
`compartments[]`, `species[]` (including `initialization_source`), `reactions[]`,
`kinetic_laws[]`, `parameters[]` (including `lower_bound`/`upper_bound`/`fixed`),
`model_assumptions[]`.

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

`tests/fixtures/sce00061_agent5_handoff.json` was assembled by:

1. Reusing the sibling Agent 4 repository's own real `agent2_model` section verbatim — itself
   produced by Agent 2's own canonical `run_agent2_pipeline` entrypoint (Five-Agent Workflow V1
   Hardening increment): 53 species, 38 reactions, 115 parameters, with `lower_bound`/
   `upper_bound`/`fixed`/`initialization_source` all confirmed `null` for every entry.
2. Actually running Agent 4's own committed pipeline (`run_agent4_pipeline`) against that model
   with one nominally-eligible heuristic parameter as a target and **zero real observations**
   supplied — because no real yeast observation data exists for this model. Agent 4 itself
   correctly returned `CalibrationStatus.INSUFFICIENT_DATA` with **zero parameter estimates**.
3. Serializing that real `Agent4Report` (not a fabricated one) into the shape above.

This is the honest, real state of the workflow today: nothing has actually been calibrated for
`sce00061`, so Agent 5's own real-integration test operates on a report with no fitted values
at all — exactly what a genuine "no data yet" state looks like, never disguised as a successful
calibration.
