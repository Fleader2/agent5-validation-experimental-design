"""Agent 5's own output contract: validation/generalization/experimental-design types.

Every type here is a plain, frozen, JSON-friendly dataclass -- consistent with every other
package in this project's own family. Numeric simulation/scoring data is kept as ``float``, not
``Decimal``, mirroring ``app.agent3.types``/``app.agent4.types``'s own identical, deliberate
divergence: this data is produced by, and only ever consumed by, real numerical ODE integration
and finite-difference sensitivity analysis (both IEEE double precision throughout).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FindingSeverity(StrEnum):
    """How seriously a finding should be treated by a downstream consumer -- identical
    vocabulary to ``app.agent3.types.DiagnosticSeverity``/``app.agent4.types
    .IdentifiabilitySeverity``, reimplemented independently per this project's own decoupling
    convention."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationStatus(StrEnum):
    """The overall outcome of one Agent 5 run.

    A small, closed, mutually-exclusive vocabulary, mirroring every earlier agent's own
    precedent of never conflating qualitatively different situations:

    * ``INVALID_REQUEST`` -- the ``ValidationRequest`` itself is malformed (an observation
      references a species id absent from the handoff, or similar) -- no simulation is ever
      attempted.
    * ``VALIDATION_FAILED`` -- the calibrated model (Agent 2's structure with Agent 4's fitted
      values applied) could not even be simulated once against the held-out observations'
      own time horizon.
    * ``INSUFFICIENT_VALIDATION_DATA`` -- the request is valid and the model simulates, but
      there are too few held-out observation points to say anything meaningful about
      generalization.
    * ``OVERFIT_WARNING`` -- validation ran, but held-out performance is materially worse than
      training performance (see ``docs/03_validation_semantics.md`` for the exact ratio rule).
    * ``EXPERIMENT_DESIGN_LIMITED`` -- validation itself succeeded (or was at least not worse
      than the above), but the experimental-design half of this run could not connect any
      candidate experiment meaningfully to a prediction (e.g. because the model's own baseline
      trajectory is trivial) -- reported explicitly rather than silently ranking meaningless
      candidates as if they were informative.
    * ``SUCCESS`` -- validation ran, generalization looked acceptable, and at least one
      candidate experiment was meaningfully scored.
    """

    SUCCESS = "SUCCESS"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INSUFFICIENT_VALIDATION_DATA = "INSUFFICIENT_VALIDATION_DATA"
    OVERFIT_WARNING = "OVERFIT_WARNING"
    EXPERIMENT_DESIGN_LIMITED = "EXPERIMENT_DESIGN_LIMITED"
    INVALID_REQUEST = "INVALID_REQUEST"


class ValidationObservationKind(StrEnum):
    TIME_SERIES = "TIME_SERIES"
    STEADY_STATE = "STEADY_STATE"


@dataclass(frozen=True, slots=True)
class ValidationObservation:
    """One held-out data series -- never used for recalibration, only for evaluating the
    already-fitted (frozen) calibrated model. Never fabricated by Agent 5."""

    observation_id: str
    target_species_id: str
    kind: ValidationObservationKind
    time_points: tuple[float, ...]
    values: tuple[float, ...]
    sigma: tuple[float, ...] | float | None = None


@dataclass(frozen=True, slots=True)
class ValidationObservationSet:
    observation_set_id: str
    observations: tuple[ValidationObservation, ...]


@dataclass(frozen=True, slots=True)
class ValidationMetric:
    """One scalar summary statistic over one partition's residuals (e.g. RMSE, weighted SSE,
    max absolute residual, R^2)."""

    metric_name: str
    partition: str
    value: float
    description: str


@dataclass(frozen=True, slots=True)
class ValidationResidualSummary:
    """Per-observation residual statistics for the held-out validation partition, computed
    fresh by Agent 5 against the calibrated model -- never copied from Agent 4's own residuals
    (which only ever covered Agent 4's own train/validation split at calibration time)."""

    observation_id: str
    residuals: tuple[float, ...]
    sum_squared_residual: float
    weighted_sum_squared_residual: float
    n_points: int


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The full outcome of simulating the calibrated model against held-out observations."""

    validation_run_id: str
    simulated: bool
    message: str | None
    metrics: tuple[ValidationMetric, ...]
    validation_residuals: tuple[ValidationResidualSummary, ...]
    overfit_ratio: float | None


class GeneralizationCategory(StrEnum):
    OVERFIT_SUSPECTED = "OVERFIT_SUSPECTED"
    GENERALIZES_WELL = "GENERALIZES_WELL"
    INSUFFICIENT_VALIDATION_DATA = "INSUFFICIENT_VALIDATION_DATA"
    VALIDATION_SIMULATION_FAILED = "VALIDATION_SIMULATION_FAILED"
    DOMINANT_UNCERTAINTY_PARAMETER = "DOMINANT_UNCERTAINTY_PARAMETER"


@dataclass(frozen=True, slots=True)
class GeneralizationFinding:
    finding_id: str
    category: GeneralizationCategory
    severity: FindingSeverity
    summary: str
    explanation: str
    related_parameter_ids: tuple[str, ...] = ()
    related_observation_ids: tuple[str, ...] = ()


class ExperimentType(StrEnum):
    """Version 1's own deliberately practical, closed set of candidate-experiment kinds."""

    METABOLITE_CONCENTRATION_AT_TIME = "METABOLITE_CONCENTRATION_AT_TIME"
    REACTION_FLUX = "REACTION_FLUX"
    PROTEIN_ABUNDANCE = "PROTEIN_ABUNDANCE"
    ENZYME_KINETIC_PARAMETER = "ENZYME_KINETIC_PARAMETER"
    INITIAL_CONCENTRATION_PERTURBATION = "INITIAL_CONCENTRATION_PERTURBATION"
    PARAMETER_PERTURBATION = "PARAMETER_PERTURBATION"
    ADDITIONAL_TIME_POINT = "ADDITIONAL_TIME_POINT"
    TIME_SERIES = "TIME_SERIES"


@dataclass(frozen=True, slots=True)
class CandidateExperiment:
    """One candidate next measurement/perturbation.

    ``feasibility_note`` is set (never left implicit) whenever Agent 5 cannot meaningfully
    connect this candidate to a model prediction (e.g. the model's own baseline trajectory is
    trivial, or the entity type -- protein abundance, an enzyme kinetic parameter -- is not
    itself a simulated quantity) -- see ``docs/04_experimental_design_scoring_policy.md``.
    """

    experiment_id: str
    experiment_type: ExperimentType
    target_id: str
    time_point: float | None = None
    perturbation_fraction: float | None = None
    description: str = ""
    feasibility_note: str | None = None


@dataclass(frozen=True, slots=True)
class ExperimentScore:
    """The ranked information-value score for one ``CandidateExperiment``.

    ``rationale`` always explains *why* -- per the task's own explicit requirement that every
    recommendation explain its usefulness, never just a bare number.
    """

    experiment_id: str
    information_score: float
    rank: int
    related_parameter_ids: tuple[str, ...]
    discriminates_between_target_ids: tuple[str, ...]
    rationale: str


class ExperimentalDesignCategory(StrEnum):
    NO_MEANINGFUL_CONNECTION = "NO_MEANINGFUL_CONNECTION"
    STRUCTURALLY_INDISTINGUISHABLE = "STRUCTURALLY_INDISTINGUISHABLE"
    CANDIDATE_SET_LIMITED = "CANDIDATE_SET_LIMITED"


@dataclass(frozen=True, slots=True)
class ExperimentalDesignFinding:
    finding_id: str
    category: ExperimentalDesignCategory
    severity: FindingSeverity
    summary: str
    explanation: str
    related_experiment_ids: tuple[str, ...] = ()
    related_parameter_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    """One complete, explicit request to validate the calibrated model and (optionally) score a
    caller-supplied candidate-experiment list -- when ``candidate_experiments`` is ``None``,
    Agent 5's own default generation policy is used (see ``app.agent5.experiment_design``).
    """

    request_id: str
    validation_observations: ValidationObservationSet
    candidate_experiments: tuple[CandidateExperiment, ...] | None = None
    overfit_ratio_threshold: float = 3.0
    max_default_candidates: int = 10


@dataclass(frozen=True, slots=True)
class Agent5Report:
    """The single, top-level structured output Agent 5 produces -- the final report of the
    first complete five-agent workflow."""

    report_id: str
    agent5_contract_version: str
    agent2_model_id: str
    agent4_report_id: str
    request_id: str
    overall_status: ValidationStatus
    validation: ValidationResult | None
    generalization_findings: tuple[GeneralizationFinding, ...]
    dominant_uncertainty_parameter_ids: tuple[str, ...]
    candidate_experiments: tuple[CandidateExperiment, ...]
    experiment_scores: tuple[ExperimentScore, ...]
    experimental_design_findings: tuple[ExperimentalDesignFinding, ...]
    calibrated_parameters_verified_unchanged: bool
    calibrated_parameter_ids_checked: tuple[str, ...]
    sufficient_for_full_workflow: bool
    sufficiency_note: str


__all__ = [
    "Agent5Report",
    "CandidateExperiment",
    "ExperimentScore",
    "ExperimentType",
    "ExperimentalDesignCategory",
    "ExperimentalDesignFinding",
    "FindingSeverity",
    "GeneralizationCategory",
    "GeneralizationFinding",
    "ValidationMetric",
    "ValidationObservation",
    "ValidationObservationKind",
    "ValidationObservationSet",
    "ValidationRequest",
    "ValidationResidualSummary",
    "ValidationResult",
    "ValidationStatus",
]
