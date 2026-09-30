# Experimental-Design Scoring Policy (`experimental-design-v1`)

Implemented in `app.agent5.experiment_design`. **This is a diagonal, per-parameter local-
sensitivity proxy — not full (joint, Bayesian, D-optimal) experimental design.** This document
states precisely what the method computes and what it does not claim.

## Candidate types (Version 1's own closed, practical set)

`METABOLITE_CONCENTRATION_AT_TIME`, `REACTION_FLUX`, `PROTEIN_ABUNDANCE`,
`ENZYME_KINETIC_PARAMETER`, `INITIAL_CONCENTRATION_PERTURBATION`, `PARAMETER_PERTURBATION`,
`ADDITIONAL_TIME_POINT`, `TIME_SERIES`.

## Default candidate generation (`default_candidate_experiments`)

When the caller does not supply an explicit candidate list, Agent 5 generates, deterministically:

1. A `METABOLITE_CONCENTRATION_AT_TIME` candidate for every species, at a fixed default time
   (`DEFAULT_CANDIDATE_TIME = 10.0` — a generic, unit-agnostic default, mirroring
   `app.agent3.pipeline.DEFAULT_SIMULATION_REQUEST`'s own identical rationale for not having a
   per-reaction characteristic timescale to derive a better one from).
2. A `REACTION_FLUX` candidate for every reaction, at the same default time.
3. An `ENZYME_KINETIC_PARAMETER` "measure this directly" candidate for every target already
   aggregated into `dominant_uncertainty_parameter_ids` (see `docs/03_validation_semantics.md`).
4. A `PARAMETER_PERTURBATION` (±10%, `PARAMETER_PERTURBATION_FRACTION`) candidate for every
   calibrated `PARAMETER` target, and an `INITIAL_CONCENTRATION_PERTURBATION` candidate for
   every calibrated `INITIAL_CONDITION` target.
5. An `INITIAL_CONCENTRATION_PERTURBATION` candidate for every species Agent 2 declares with no
   initial condition at all, that Agent 4 never calibrated either.

Truncated to `request.max_default_candidates` (default `10`) by a fixed type-priority order
(passive measurements, then perturbations, then direct-parameter-measurement) — never a random
or silently-changing order.

## The sensitivity/information proxy

For a candidate whose prediction can be simulated (every type except
`ENZYME_KINETIC_PARAMETER`/`PROTEIN_ABUNDANCE`):

```
sensitivity[T] = d(predicted_value) / d(T)     (central/forward finite difference, 1% of T's
                                                 own bound range, evaluated at the calibrated
                                                 operating point -- or a perturbed operating
                                                 point, for a *_PERTURBATION candidate)

information_score = sum_T  weight[T] * sensitivity[T]**2

weight[T] = base_weight[T] / (reference_information[T] + epsilon)
base_weight[T] = 1.0 if T in dominant_uncertainty_parameter_ids else 0.1
reference_information[T] = sum over every already-supplied validation observation's own
                            squared sensitivity to T (computed once per report)
epsilon = 1e-6
```

This is a **diagonal** proxy: it never forms or inverts a joint Fisher-information matrix
across the full parameter set, never computes a determinant/eigenvalue (D-optimality,
A-optimality), and never propagates a Bayesian posterior. It is a legitimate, standard
simplification of Fisher-information-based experimental design (the diagonal/greedy
approximation), not a claim of joint optimality.

`weight[T]` is the mechanism for "expected reduction in uncertainty": a target the existing
validation data barely touches (`reference_information[T]` near `0`) gets a very large weight
(via the `epsilon` floor), so any candidate informative about it is prioritized; a target the
existing data already constrains well gets a small weight, so further information about it is
deprioritized even if a candidate is nominally sensitive to it.

## Rule-based scoring for non-simulated candidate types

`ENZYME_KINETIC_PARAMETER` and `PROTEIN_ABUNDANCE` candidates recommend a direct biochemical
measurement of a quantity that is not itself a simulated model output — there is no sensitivity
to compute. These are scored instead from a fixed severity-to-score table over every Agent 4
identifiability finding naming that target (`CRITICAL`→10, `ERROR`→6, `WARNING`→3, `INFO`→1,
summed across every matching finding) — a deliberately simple, disclosed rule, never dressed up
as a sensitivity computation it is not.

## The "discriminates" determination

A candidate is recorded as discriminating target `T`
(`ExperimentScore.discriminates_between_target_ids`) when:

```
reference_information[T] < _POORLY_CONSTRAINED_REFERENCE_THRESHOLD (1e-6)     -- the existing
                                                                                  data barely
                                                                                  touches T
AND
sensitivity[T]**2 > _MEANINGFUL_SENSITIVITY_THRESHOLD (1e-9)                   -- this candidate
                                                                                  is meaningfully
                                                                                  informative
                                                                                  about T
```

This directly implements "whether a candidate discriminates between nearly equivalent parameter
sets": when a parameter is poorly identified by the data already collected (large "nearly
equivalent" range of plausible values), a candidate satisfying both conditions above reveals
information the existing measurements cannot — confirmed, in this repository's own tests,
against a two-step reaction chain where measuring only the first species leaves the second
rate constant essentially unconstrained, and measuring the third species (sensitive to both
rate constants) correctly discriminates it.

## Honest disclosure of an unconnectable candidate

If the calibrated model's own baseline trajectory is trivial (every species constant for the
entire simulated horizon — reimplemented independently in
`app.agent5.simulation.is_trivial_trajectory`, mirroring `app.agent3.diagnostics
.trivial_trajectory_finding`'s own judgment, since Agent 5 never imports Agent 3's code),
`app.agent5.experiment_design.experimental_design_findings` raises a dedicated
`NO_MEANINGFUL_CONNECTION` finding naming every candidate that scored `0.0` for this reason,
rather than letting a `0.0` score be silently misread as "checked and found uninformative" when
it actually means "could not be evaluated at all." If *every* scored candidate is `0.0`, a
second, more severe `CANDIDATE_SET_LIMITED` finding is raised and the overall run status
becomes `EXPERIMENT_DESIGN_LIMITED`.

## Ranking

Deterministic: sorted by `information_score` descending, ties broken by `experiment_id`
(lexicographic) — never by insertion order or any other unstated tiebreak. Re-running the same
request against the same handoff always produces identical ranks (confirmed by this
repository's own repeatability test).
