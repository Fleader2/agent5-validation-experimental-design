# Validation Semantics (`validation-v1`)

Implemented in `app.agent5.validation` and `app.agent5.generalization`. Formalizes every
metric, threshold, and status-precedence decision.

## The calibrated model, and only the calibrated model

`app.agent5.validation.calibrated_overrides(agent4_report)` returns exactly
`{target_id: fitted_value}` for every `ParameterEstimate` Agent 4 declared — nothing more,
nothing re-derived. This is the **only** vector of values ever applied to the Agent 2 model
before simulating it. Held-out data is never used to adjust this vector.

## Simulation

`app.agent5.simulation.simulate_calibrated_model` loads a **fresh** RoadRunner instance from the
handoff's own unmodified `antimony_text`, applies the calibrated overrides, and simulates on a
dense 500-point grid from `0` to the maximum requested time point, linearly interpolating onto
the exact observation time points — identical mechanism and rationale to
`app.agent4.simulation.evaluate_candidate`'s own dense-grid-plus-interpolation approach on the
sibling repository. Reaction fluxes are requested as extra `timeCourseSelections` columns
alongside floating species (confirmed empirically this session that RoadRunner's `simulate`
accepts a mixed species+reaction selection list directly).

## Validation metrics

Computed once, pooled across every held-out observation's every point:

* **RMSE** — `sqrt(mean(residuals**2))`.
* **WEIGHTED_SSE** — `sum(weights * residuals**2)`, `weights = 1/sigma**2` per point (or `1.0`
  if no `sigma` was supplied).
* **MAX_ABS_RESIDUAL** — `max(abs(residuals))`.

The same three metrics are also computed for the `TRAIN` partition, but **read directly from
Agent 4's own already-reported residuals** (`app.agent5.validation
.train_metrics_from_agent4`) — never re-simulated, since Agent 5 has no access to Agent 4's own
raw training observation values, only the residuals Agent 4 already computed, which is exactly
what this comparison needs.

## Overfit detection

```
overfit_ratio = validation_RMSE / train_RMSE   (None if train_RMSE is 0 or unavailable)
```

If `overfit_ratio > request.overfit_ratio_threshold` (default `3.0`), an `OVERFIT_SUSPECTED`
finding is raised (severity `ERROR`) and the overall run status becomes `OVERFIT_WARNING`.
Otherwise, a `GENERALIZES_WELL` finding (severity `INFO`) is raised instead — the absence of a
concern is itself disclosed, not silently omitted. If `overfit_ratio` cannot be computed (e.g.
the fixture's own training residuals are all exactly `0.0`, an all-too-common synthetic-test
degenerate case), no generalization/overfit finding is raised for this reason at all — reported
as `None`, never guessed at.

**This is a single, ratio-based heuristic, not a formal statistical generalization test** (no
confidence interval, no hypothesis test, no cross-validation). It is sufficient to catch the
qualitative signature Version 1 targets (dramatically worse held-out than training performance)
without claiming more rigor than is actually implemented.

## Insufficient validation data

`app.agent5.generalization.MIN_VALIDATION_POINTS = 2`. Fewer than two total held-out points
(summed across every `ValidationObservation.values`) makes any generalization conclusion
meaningless — one point cannot distinguish "generalizes well" from "got lucky." When triggered,
this short-circuits the entire run to `ValidationStatus.INSUFFICIENT_VALIDATION_DATA` before any
experimental-design scoring is attempted.

## Dominant-uncertainty aggregation

`app.agent5.generalization.dominant_uncertainty_parameter_ids` collects every `target_id`
appearing in any Agent 4 `identifiability_findings` entry whose `category` is one of
`BOUND_HIT`, `LOW_SENSITIVITY`, `HIGH_CORRELATION`, or `DEGENERATE_OBJECTIVE` — deduplicated,
sorted for determinism. This is a pure read of Agent 4's own already-declared findings; Agent 5
never recomputes Agent 4's own identifiability logic independently. If Agent 4 calibrated
nothing (as in the real current `sce00061` state), this list is correctly empty.

## Overall status precedence (`app.agent5.report.determine_overall_status`)

Most to least severe, first match wins:

1. The calibrated model could not be simulated at all → `VALIDATION_FAILED`.
2. Fewer than `MIN_VALIDATION_POINTS` held-out points → `INSUFFICIENT_VALIDATION_DATA`.
3. An `OVERFIT_SUSPECTED` finding was raised → `OVERFIT_WARNING`.
4. Every scored candidate experiment has an information score of exactly `0.0` → `EXPERIMENT_DESIGN_LIMITED`.
5. Otherwise → `SUCCESS`.

A request-level contract violation (an observation referencing a species id that does not
exist in the Agent 2 model, or similar) is checked first, before any of the above, and produces
`INVALID_REQUEST`.
