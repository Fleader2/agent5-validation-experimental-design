"""Agent 5's own exception hierarchy.

Mirrors the sibling repositories' own per-package error convention: a narrow, typed hierarchy
raised only for genuine structural/contract problems Agent 5 itself detects before ever
attempting validation or experimental-design scoring -- never used to represent a *validation
outcome* (a failed simulation, poor generalization, insufficient data are all reported as data
-- ``ValidationStatus``/``Agent5Report`` -- never raised as Python exceptions, since they are
expected, first-class outcomes this package exists to describe, not programming errors).
"""

from __future__ import annotations


class Agent5Error(Exception):
    """Base class for every exception this package raises."""


class HandoffContractError(Agent5Error):
    """The supplied Agent 2/Agent 4 -> Agent 5 handoff dict is missing a required field, has a
    field of the wrong type, or otherwise fails to satisfy ``app.agent5.handoff``'s own
    contract. Raised only when the data cannot be parsed into the contract's own required shape
    at all.
    """


class ValidationRequestError(Agent5Error):
    """Raised only when a ``ValidationRequest`` cannot even be validated against the handoff it
    targets (e.g. an observation references a species id absent from the handoff entirely). A
    request-level policy violation short of that (insufficient data, an unconnectable candidate)
    is never raised as this exception -- it is reported as a ``ValidationStatus``/finding in the
    resulting ``Agent5Report``.
    """


__all__ = ["Agent5Error", "HandoffContractError", "ValidationRequestError"]
