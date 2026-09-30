"""Deterministically re-deriving an Antimony identifier from an Agent 2 entity id.

Identical rule, and identical rationale, to ``app.agent3.antimony_ids``/``app.agent4
.antimony_ids`` on the sibling repositories -- re-implemented independently here rather than
imported, per this project's own decoupling convention. Agent 2's own Antimony generator maps
every compartment/species/parameter/reaction id to a stable, documented Antimony identifier:
strip every character outside ``[A-Za-z0-9_]`` (replacing it with ``_``), prefix by structural
category (``c_``/``s_``/``p_``/``J_``).

Every candidate this module produces is checked against the loaded model's own real identifier
list before being used -- never guessed, never silently assumed correct.
"""

from __future__ import annotations

import re
import unicodedata

_INVALID_CHAR = re.compile(r"[^A-Za-z0-9_]")


def sanitize_base(raw: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    cleaned = _INVALID_CHAR.sub("_", ascii_text)
    if not cleaned or cleaned.strip("_") == "":
        cleaned = "id"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def candidate_parameter_antimony_id(parameter_id: str) -> str:
    return f"p_{sanitize_base(parameter_id)}"


def candidate_species_antimony_id(species_id: str) -> str:
    return f"s_{sanitize_base(species_id)}"


def candidate_reaction_antimony_id(reaction_id: str) -> str:
    return f"J_{sanitize_base(reaction_id)}"


def build_species_antimony_id_map(species_ids: list[str]) -> dict[str, str]:
    return {candidate_species_antimony_id(sid): sid for sid in species_ids}


def build_reaction_antimony_id_map(reaction_ids: list[str]) -> dict[str, str]:
    return {candidate_reaction_antimony_id(rid): rid for rid in reaction_ids}


__all__ = [
    "build_reaction_antimony_id_map",
    "build_species_antimony_id_map",
    "candidate_parameter_antimony_id",
    "candidate_reaction_antimony_id",
    "candidate_species_antimony_id",
    "sanitize_base",
]
