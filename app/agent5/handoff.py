"""The Agent 2/Agent 4 -> Agent 5 input contract (Version 1).

Mirrors this project's own established decoupling pattern at every earlier boundary: Agent 5
never imports Agent 2's, Agent 3's, or Agent 4's Python packages, and never constructs an Agent
2 ``ModelSpecification``, an Agent 3 ``Agent3Report``, or an Agent 4 ``Agent4Report`` object
directly. It consumes exactly two plain, JSON-serializable dict shapes, parsed here into this
module's own frozen, validated dataclasses.

**Why ``agent2_model`` + ``agent4_report``, not three or four separate dicts:** Agent 5's job is
to validate the *calibrated* model (Agent 2's structure + Agent 4's fitted values) against
held-out data, and to recommend what to measure next given the uncertainty Agent 4 (and, via
Agent 4's own carried-through fields, Agent 3) already disclosed. Concretely:

* ``agent2_model`` -- identical shape to the sibling Agent 4 repository's own ``agent2_model``
  (compartments/species/reactions/kinetic_laws/parameters/model_assumptions, plus
  ``lower_bound``/``upper_bound``/``fixed`` on parameters and ``initialization_source`` on
  species) -- the structural/provenance facts needed to simulate the calibrated model and trace
  a recommendation back to a reaction/species/assumption.
* ``agent4_report`` -- a lightweight mirror of Agent 4's own ``Agent4Report``: which parameters/
  initial conditions were fitted, to what value, from what original value/source, with what
  identifiability findings already disclosed. Agent 5 never recomputes Agent 4's own
  calibration or identifiability logic -- it reads Agent 4's already-declared findings and
  fitted values, and reapplies exactly those fitted values (never a different value) onto the
  Agent 2 model before simulating it for validation.

Nothing here is a validation result or an experimental-design recommendation -- this module
only parses and validates the shape of what Agent 2 and Agent 4 report about themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.agent5.errors import HandoffContractError


def _require_str(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HandoffContractError(f"{field} must be a non-empty string, got {value!r}")
    return value


def _optional_str(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HandoffContractError(f"{field} must be a string or null, got {value!r}")
    return value or None


def _optional_decimal(value: object, *, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise HandoffContractError(f"{field} must be numeric, got a bool ({value!r})")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise HandoffContractError(f"{field} is not a valid decimal: {value!r}") from exc
    raise HandoffContractError(f"{field} must be numeric or null, got {value!r}")


def _optional_bool(value: object, *, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise HandoffContractError(f"{field} must be a bool or null, got {value!r}")
    return value


def _require_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HandoffContractError(f"{field} must be numeric, got {value!r}")
    return float(value)


def _optional_float(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    return _require_float(value, field=field)


def _str_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or any(not isinstance(v, str) for v in value):
        raise HandoffContractError(f"{field} must be a list of strings, got {value!r}")
    return tuple(value)


def _float_tuple(value: object, *, field: str) -> tuple[float, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise HandoffContractError(f"{field} must be a list of numbers, got {value!r}")
    return tuple(_require_float(v, field=field) for v in value)


def _dict_list(value: object, *, field: str) -> tuple[dict, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or any(not isinstance(v, dict) for v in value):
        raise HandoffContractError(f"{field} must be a list of objects, got {value!r}")
    return tuple(value)


# --- agent2_model (identical shape to agent4-calibration-estimator's own contract) -----------


@dataclass(frozen=True, slots=True)
class Agent5Compartment:
    compartment_id: str
    name: str
    initial_volume: Decimal | None
    volume_unit: str | None
    constant: bool | None


@dataclass(frozen=True, slots=True)
class Agent5Species:
    species_id: str
    name: str
    compartment_id: str
    source_compound_id: str | None
    source_enzyme_state_id: str | None
    initial_amount: Decimal | None
    initial_concentration: Decimal | None
    constant: bool | None
    boundary_condition: bool | None
    initialization_source: str | None


@dataclass(frozen=True, slots=True)
class Agent5Participant:
    species_id: str
    role: str
    stoichiometry: Decimal


@dataclass(frozen=True, slots=True)
class Agent5Reaction:
    reaction_id: str
    name: str | None
    reversible: bool | None
    participants: tuple[Agent5Participant, ...]


@dataclass(frozen=True, slots=True)
class Agent5KineticLaw:
    kinetic_law_id: str
    reaction_id: str
    law_type: str
    expression: str | None
    parameter_ids: tuple[str, ...]
    species_ids: tuple[str, ...]
    enzyme_state_id: str | None
    protein_id: str | None
    complex_id: str | None
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Agent5Parameter:
    parameter_id: str
    name: str
    source: str
    value: Decimal | None
    unit: str | None
    reaction_id: str | None
    kinetic_law_assignment_id: str | None
    uncertainty_text: str | None
    provenance_refs: tuple[str, ...]
    lower_bound: Decimal | None
    upper_bound: Decimal | None
    fixed: bool | None


@dataclass(frozen=True, slots=True)
class Agent5ModelAssumption:
    assumption_id: str
    category: str
    statement: str
    related_entity_ids: tuple[str, ...]
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class AntimonySymbolMap:
    """Agent 2's own exact canonical-id -> real, compiled Antimony-symbol mapping (Human-
    Readable Antimony Naming and Provenance Separation increment, contract v2).

    Antimony symbol assignment is Agent 2-owned data: Agent 2's naming rule
    (``app.agent2.antimony.naming``) depends on curated biological names only Agent 2 has
    access to, so a symbol can never be correctly re-derived from a bare handoff entity id.
    This replaces this repository's former ``app.agent5.antimony_ids`` module, which
    independently re-implemented Agent 2's *old* id-only naming rule and silently broke the
    moment that rule changed -- Agent 5 now reads the real mapping directly instead.

    Missing from a v1 handoff: defaults to three empty dicts, never raises -- mirrors this
    contract's own established "version mismatch is disclosed, not raised" discipline.
    """

    species: dict[str, str]
    reactions: dict[str, str]
    parameters: dict[str, str]


def _parse_antimony_symbol_map(value: object, *, field: str) -> AntimonySymbolMap:
    if value is None:
        return AntimonySymbolMap(species={}, reactions={}, parameters={})
    if not isinstance(value, dict):
        raise HandoffContractError(f"{field} must be an object, got {value!r}")

    def _str_dict(sub: object, *, sub_field: str) -> dict[str, str]:
        if sub is None:
            return {}
        if not isinstance(sub, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in sub.items()
        ):
            raise HandoffContractError(
                f"{sub_field} must be an object of string -> string, got {sub!r}"
            )
        return dict(sub)

    return AntimonySymbolMap(
        species=_str_dict(value.get("species"), sub_field=f"{field}.species"),
        reactions=_str_dict(value.get("reactions"), sub_field=f"{field}.reactions"),
        parameters=_str_dict(value.get("parameters"), sub_field=f"{field}.parameters"),
    )


def species_antimony_id_map(agent2_model: Agent2Model) -> dict[str, str]:
    """``{antimony_species_symbol: original_agent2_species_id}`` -- the reverse of
    ``agent2_model.antimony_symbol_map.species``."""
    return {
        symbol: species_id
        for species_id, symbol in agent2_model.antimony_symbol_map.species.items()
    }


def reaction_antimony_id_map(agent2_model: Agent2Model) -> dict[str, str]:
    """``{antimony_reaction_symbol: original_agent2_reaction_id}`` -- the reverse of
    ``agent2_model.antimony_symbol_map.reactions``."""
    return {
        symbol: reaction_id
        for reaction_id, symbol in agent2_model.antimony_symbol_map.reactions.items()
    }


@dataclass(frozen=True, slots=True)
class Agent2Model:
    contract_version: str
    model_id: str
    network_id: str
    antimony_text: str
    antimony_generator_version: str
    antimony_symbol_map: AntimonySymbolMap
    readiness: str
    unresolved_reaction_ids: tuple[str, ...]
    unresolved_kinetic_law_ids: tuple[str, ...]
    compartments: tuple[Agent5Compartment, ...]
    species: tuple[Agent5Species, ...]
    reactions: tuple[Agent5Reaction, ...]
    kinetic_laws: tuple[Agent5KineticLaw, ...]
    parameters: tuple[Agent5Parameter, ...]
    model_assumptions: tuple[Agent5ModelAssumption, ...]


# --- agent4_report (lightweight mirror) -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Agent4ParameterEstimateView:
    target_kind: str
    target_id: str
    original_value: float | None
    original_source: str | None
    fitted_value: float
    lower_bound: float
    upper_bound: float
    at_lower_bound: bool
    at_upper_bound: bool
    new_source: str
    provenance_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Agent4ResidualSummaryView:
    observation_id: str
    partition: str
    residuals: tuple[float, ...]
    sum_squared_residual: float
    weighted_sum_squared_residual: float
    n_points: int


@dataclass(frozen=True, slots=True)
class Agent4IdentifiabilityFindingView:
    finding_id: str
    category: str
    severity: str
    summary: str
    explanation: str
    related_target_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Agent4CalibrationResultView:
    calibration_run_id: str
    status: str
    objective_before: float | None
    objective_after: float | None
    parameter_estimates: tuple[Agent4ParameterEstimateView, ...]
    residuals: tuple[Agent4ResidualSummaryView, ...]
    identifiability_findings: tuple[Agent4IdentifiabilityFindingView, ...]
    n_multistarts: int
    best_start_index: int | None
    all_start_objectives: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Agent4ReportView:
    report_id: str
    agent4_contract_version: str
    agent2_model_id: str
    agent3_report_id: str
    request_id: str
    calibration: Agent4CalibrationResultView
    fixed_parameters_verified_unchanged: bool
    fixed_parameter_ids_checked: tuple[str, ...]
    sufficient_for_agent5: bool
    sufficiency_note: str


@dataclass(frozen=True, slots=True)
class Agent5Handoff:
    """One complete, self-contained Agent 2/Agent 4 -> Agent 5 handoff."""

    agent2_model: Agent2Model
    agent4_report: Agent4ReportView


def _parse_agent2_model(data: dict) -> Agent2Model:
    compartments = tuple(
        Agent5Compartment(
            compartment_id=_require_str(
                c.get("compartment_id"), field="agent2_model.compartments[].compartment_id"
            ),
            name=_require_str(c.get("name"), field="agent2_model.compartments[].name"),
            initial_volume=_optional_decimal(
                c.get("initial_volume"), field="agent2_model.compartments[].initial_volume"
            ),
            volume_unit=_optional_str(
                c.get("volume_unit"), field="agent2_model.compartments[].volume_unit"
            ),
            constant=c.get("constant"),
        )
        for c in _dict_list(data.get("compartments"), field="agent2_model.compartments")
    )

    species = tuple(
        Agent5Species(
            species_id=_require_str(s.get("species_id"), field="agent2_model.species[].species_id"),
            name=_require_str(s.get("name"), field="agent2_model.species[].name"),
            compartment_id=_require_str(
                s.get("compartment_id"), field="agent2_model.species[].compartment_id"
            ),
            source_compound_id=_optional_str(
                s.get("source_compound_id"), field="agent2_model.species[].source_compound_id"
            ),
            source_enzyme_state_id=_optional_str(
                s.get("source_enzyme_state_id"),
                field="agent2_model.species[].source_enzyme_state_id",
            ),
            initial_amount=_optional_decimal(
                s.get("initial_amount"), field="agent2_model.species[].initial_amount"
            ),
            initial_concentration=_optional_decimal(
                s.get("initial_concentration"),
                field="agent2_model.species[].initial_concentration",
            ),
            constant=s.get("constant"),
            boundary_condition=s.get("boundary_condition"),
            initialization_source=_optional_str(
                s.get("initialization_source"),
                field="agent2_model.species[].initialization_source",
            ),
        )
        for s in _dict_list(data.get("species"), field="agent2_model.species")
    )

    reactions = tuple(
        Agent5Reaction(
            reaction_id=_require_str(
                r.get("reaction_id"), field="agent2_model.reactions[].reaction_id"
            ),
            name=_optional_str(r.get("name"), field="agent2_model.reactions[].name"),
            reversible=r.get("reversible"),
            participants=tuple(
                Agent5Participant(
                    species_id=_require_str(
                        p.get("species_id"),
                        field="agent2_model.reactions[].participants[].species_id",
                    ),
                    role=_require_str(
                        p.get("role"), field="agent2_model.reactions[].participants[].role"
                    ),
                    stoichiometry=_optional_decimal(
                        p.get("stoichiometry"),
                        field="agent2_model.reactions[].participants[].stoichiometry",
                    )
                    or Decimal(1),
                )
                for p in _dict_list(
                    r.get("participants"), field="agent2_model.reactions[].participants"
                )
            ),
        )
        for r in _dict_list(data.get("reactions"), field="agent2_model.reactions")
    )

    kinetic_laws = tuple(
        Agent5KineticLaw(
            kinetic_law_id=_require_str(
                k.get("kinetic_law_id"), field="agent2_model.kinetic_laws[].kinetic_law_id"
            ),
            reaction_id=_require_str(
                k.get("reaction_id"), field="agent2_model.kinetic_laws[].reaction_id"
            ),
            law_type=_require_str(k.get("law_type"), field="agent2_model.kinetic_laws[].law_type"),
            expression=_optional_str(
                k.get("expression"), field="agent2_model.kinetic_laws[].expression"
            ),
            parameter_ids=_str_tuple(
                k.get("parameter_ids"), field="agent2_model.kinetic_laws[].parameter_ids"
            ),
            species_ids=_str_tuple(
                k.get("species_ids"), field="agent2_model.kinetic_laws[].species_ids"
            ),
            enzyme_state_id=_optional_str(
                k.get("enzyme_state_id"), field="agent2_model.kinetic_laws[].enzyme_state_id"
            ),
            protein_id=_optional_str(
                k.get("protein_id"), field="agent2_model.kinetic_laws[].protein_id"
            ),
            complex_id=_optional_str(
                k.get("complex_id"), field="agent2_model.kinetic_laws[].complex_id"
            ),
            assumptions=_str_tuple(
                k.get("assumptions"), field="agent2_model.kinetic_laws[].assumptions"
            ),
        )
        for k in _dict_list(data.get("kinetic_laws"), field="agent2_model.kinetic_laws")
    )

    parameters = tuple(
        Agent5Parameter(
            parameter_id=_require_str(
                p.get("parameter_id"), field="agent2_model.parameters[].parameter_id"
            ),
            name=_require_str(p.get("name"), field="agent2_model.parameters[].name"),
            source=_require_str(p.get("source"), field="agent2_model.parameters[].source"),
            value=_optional_decimal(p.get("value"), field="agent2_model.parameters[].value"),
            unit=_optional_str(p.get("unit"), field="agent2_model.parameters[].unit"),
            reaction_id=_optional_str(
                p.get("reaction_id"), field="agent2_model.parameters[].reaction_id"
            ),
            kinetic_law_assignment_id=_optional_str(
                p.get("kinetic_law_assignment_id"),
                field="agent2_model.parameters[].kinetic_law_assignment_id",
            ),
            uncertainty_text=_optional_str(
                p.get("uncertainty_text"), field="agent2_model.parameters[].uncertainty_text"
            ),
            provenance_refs=_str_tuple(
                p.get("provenance_refs"), field="agent2_model.parameters[].provenance_refs"
            ),
            lower_bound=_optional_decimal(
                p.get("lower_bound"), field="agent2_model.parameters[].lower_bound"
            ),
            upper_bound=_optional_decimal(
                p.get("upper_bound"), field="agent2_model.parameters[].upper_bound"
            ),
            fixed=_optional_bool(p.get("fixed"), field="agent2_model.parameters[].fixed"),
        )
        for p in _dict_list(data.get("parameters"), field="agent2_model.parameters")
    )

    model_assumptions = tuple(
        Agent5ModelAssumption(
            assumption_id=_require_str(
                a.get("assumption_id"), field="agent2_model.model_assumptions[].assumption_id"
            ),
            category=_require_str(
                a.get("category"), field="agent2_model.model_assumptions[].category"
            ),
            statement=_require_str(
                a.get("statement"), field="agent2_model.model_assumptions[].statement"
            ),
            related_entity_ids=_str_tuple(
                a.get("related_entity_ids"),
                field="agent2_model.model_assumptions[].related_entity_ids",
            ),
            reason_code=_optional_str(
                a.get("reason_code"), field="agent2_model.model_assumptions[].reason_code"
            ),
        )
        for a in _dict_list(data.get("model_assumptions"), field="agent2_model.model_assumptions")
    )

    return Agent2Model(
        contract_version=_require_str(
            data.get("contract_version"), field="agent2_model.contract_version"
        ),
        model_id=_require_str(data.get("model_id"), field="agent2_model.model_id"),
        network_id=_require_str(data.get("network_id"), field="agent2_model.network_id"),
        antimony_text=_require_str(data.get("antimony_text"), field="agent2_model.antimony_text"),
        antimony_generator_version=_require_str(
            data.get("antimony_generator_version"),
            field="agent2_model.antimony_generator_version",
        ),
        antimony_symbol_map=_parse_antimony_symbol_map(
            data.get("antimony_symbol_map"), field="agent2_model.antimony_symbol_map"
        ),
        readiness=_require_str(data.get("readiness"), field="agent2_model.readiness"),
        unresolved_reaction_ids=_str_tuple(
            data.get("unresolved_reaction_ids"), field="agent2_model.unresolved_reaction_ids"
        ),
        unresolved_kinetic_law_ids=_str_tuple(
            data.get("unresolved_kinetic_law_ids"),
            field="agent2_model.unresolved_kinetic_law_ids",
        ),
        compartments=compartments,
        species=species,
        reactions=reactions,
        kinetic_laws=kinetic_laws,
        parameters=parameters,
        model_assumptions=model_assumptions,
    )


def _parse_agent4_report(data: dict) -> Agent4ReportView:
    calibration_data = data.get("calibration")
    if not isinstance(calibration_data, dict):
        raise HandoffContractError(
            f"agent4_report.calibration must be a dict, got {type(calibration_data)!r}"
        )

    parameter_estimates = tuple(
        Agent4ParameterEstimateView(
            target_kind=_require_str(
                e.get("target_kind"),
                field="agent4_report.calibration.parameter_estimates[].target_kind",
            ),
            target_id=_require_str(
                e.get("target_id"),
                field="agent4_report.calibration.parameter_estimates[].target_id",
            ),
            original_value=_optional_float(
                e.get("original_value"),
                field="agent4_report.calibration.parameter_estimates[].original_value",
            ),
            original_source=_optional_str(
                e.get("original_source"),
                field="agent4_report.calibration.parameter_estimates[].original_source",
            ),
            fitted_value=_require_float(
                e.get("fitted_value"),
                field="agent4_report.calibration.parameter_estimates[].fitted_value",
            ),
            lower_bound=_require_float(
                e.get("lower_bound"),
                field="agent4_report.calibration.parameter_estimates[].lower_bound",
            ),
            upper_bound=_require_float(
                e.get("upper_bound"),
                field="agent4_report.calibration.parameter_estimates[].upper_bound",
            ),
            at_lower_bound=bool(e.get("at_lower_bound", False)),
            at_upper_bound=bool(e.get("at_upper_bound", False)),
            new_source=_require_str(
                e.get("new_source"),
                field="agent4_report.calibration.parameter_estimates[].new_source",
            ),
            provenance_refs=_str_tuple(
                e.get("provenance_refs"),
                field="agent4_report.calibration.parameter_estimates[].provenance_refs",
            ),
        )
        for e in _dict_list(
            calibration_data.get("parameter_estimates"),
            field="agent4_report.calibration.parameter_estimates",
        )
    )

    residuals = tuple(
        Agent4ResidualSummaryView(
            observation_id=_require_str(
                r.get("observation_id"),
                field="agent4_report.calibration.residuals[].observation_id",
            ),
            partition=_require_str(
                r.get("partition"), field="agent4_report.calibration.residuals[].partition"
            ),
            residuals=_float_tuple(
                r.get("residuals"), field="agent4_report.calibration.residuals[].residuals"
            ),
            sum_squared_residual=_require_float(
                r.get("sum_squared_residual"),
                field="agent4_report.calibration.residuals[].sum_squared_residual",
            ),
            weighted_sum_squared_residual=_require_float(
                r.get("weighted_sum_squared_residual"),
                field="agent4_report.calibration.residuals[].weighted_sum_squared_residual",
            ),
            n_points=int(r.get("n_points", 0)),
        )
        for r in _dict_list(
            calibration_data.get("residuals"), field="agent4_report.calibration.residuals"
        )
    )

    identifiability_findings = tuple(
        Agent4IdentifiabilityFindingView(
            finding_id=_require_str(
                f.get("finding_id"),
                field="agent4_report.calibration.identifiability_findings[].finding_id",
            ),
            category=_require_str(
                f.get("category"),
                field="agent4_report.calibration.identifiability_findings[].category",
            ),
            severity=_require_str(
                f.get("severity"),
                field="agent4_report.calibration.identifiability_findings[].severity",
            ),
            summary=_require_str(
                f.get("summary"),
                field="agent4_report.calibration.identifiability_findings[].summary",
            ),
            explanation=_optional_str(
                f.get("explanation"),
                field="agent4_report.calibration.identifiability_findings[].explanation",
            )
            or "",
            related_target_ids=_str_tuple(
                f.get("related_target_ids"),
                field="agent4_report.calibration.identifiability_findings[].related_target_ids",
            ),
        )
        for f in _dict_list(
            calibration_data.get("identifiability_findings"),
            field="agent4_report.calibration.identifiability_findings",
        )
    )

    calibration = Agent4CalibrationResultView(
        calibration_run_id=_require_str(
            calibration_data.get("calibration_run_id"),
            field="agent4_report.calibration.calibration_run_id",
        ),
        status=_require_str(
            calibration_data.get("status"), field="agent4_report.calibration.status"
        ),
        objective_before=_optional_float(
            calibration_data.get("objective_before"),
            field="agent4_report.calibration.objective_before",
        ),
        objective_after=_optional_float(
            calibration_data.get("objective_after"),
            field="agent4_report.calibration.objective_after",
        ),
        parameter_estimates=parameter_estimates,
        residuals=residuals,
        identifiability_findings=identifiability_findings,
        n_multistarts=int(calibration_data.get("n_multistarts", 0)),
        best_start_index=calibration_data.get("best_start_index"),
        all_start_objectives=_float_tuple(
            calibration_data.get("all_start_objectives"),
            field="agent4_report.calibration.all_start_objectives",
        ),
    )

    return Agent4ReportView(
        report_id=_require_str(data.get("report_id"), field="agent4_report.report_id"),
        agent4_contract_version=_require_str(
            data.get("agent4_contract_version"), field="agent4_report.agent4_contract_version"
        ),
        agent2_model_id=_require_str(
            data.get("agent2_model_id"), field="agent4_report.agent2_model_id"
        ),
        agent3_report_id=_require_str(
            data.get("agent3_report_id"), field="agent4_report.agent3_report_id"
        ),
        request_id=_require_str(data.get("request_id"), field="agent4_report.request_id"),
        calibration=calibration,
        fixed_parameters_verified_unchanged=bool(
            data.get("fixed_parameters_verified_unchanged", False)
        ),
        fixed_parameter_ids_checked=_str_tuple(
            data.get("fixed_parameter_ids_checked"),
            field="agent4_report.fixed_parameter_ids_checked",
        ),
        sufficient_for_agent5=bool(data.get("sufficient_for_agent5", False)),
        sufficiency_note=_optional_str(
            data.get("sufficiency_note"), field="agent4_report.sufficiency_note"
        )
        or "",
    )


def parse_agent5_handoff(data: dict) -> Agent5Handoff:
    """Parse and validate one plain dict (with ``agent2_model`` and ``agent4_report`` keys)
    into an ``Agent5Handoff``. Raises ``HandoffContractError`` for any structurally malformed
    input. Never fills in a missing value with a guessed default."""
    if not isinstance(data, dict):
        raise HandoffContractError(f"Agent 5 handoff must be a dict, got {type(data)!r}")
    agent2_model_data = data.get("agent2_model")
    if not isinstance(agent2_model_data, dict):
        raise HandoffContractError(f"agent2_model must be a dict, got {type(agent2_model_data)!r}")
    agent4_report_data = data.get("agent4_report")
    if not isinstance(agent4_report_data, dict):
        raise HandoffContractError(
            f"agent4_report must be a dict, got {type(agent4_report_data)!r}"
        )
    return Agent5Handoff(
        agent2_model=_parse_agent2_model(agent2_model_data),
        agent4_report=_parse_agent4_report(agent4_report_data),
    )


def handoff_contract_version_note(handoff: Agent5Handoff) -> str | None:
    """``None`` in Version 1 -- placeholder for future version reconciliation, mirroring every
    earlier boundary's own identical precedent of deferring this."""
    del handoff
    return None


__all__ = [
    "Agent2Model",
    "Agent4CalibrationResultView",
    "Agent4IdentifiabilityFindingView",
    "Agent4ParameterEstimateView",
    "Agent4ReportView",
    "Agent4ResidualSummaryView",
    "Agent5Compartment",
    "Agent5Handoff",
    "Agent5KineticLaw",
    "Agent5ModelAssumption",
    "Agent5Parameter",
    "Agent5Participant",
    "Agent5Reaction",
    "Agent5Species",
    "AntimonySymbolMap",
    "handoff_contract_version_note",
    "parse_agent5_handoff",
    "reaction_antimony_id_map",
    "species_antimony_id_map",
]
