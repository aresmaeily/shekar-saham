"""MASTER-RADAR directive §C2 — DSL versioning and API contract.

Holds the language version string, the frozen API contract exposed to callers
(the dashboard/API layer can serialize ``CONTRACT`` verbatim), and the
migration policy used to decide whether a stored strategy source is still
accepted by this engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

DSL_VERSION = "RSL-1.0.0"


class StrategyApiContract(BaseModel):
    """Frozen description of the public strategy-DSL API surface."""

    model_config = ConfigDict(frozen=True)

    dsl_version: str
    api_version: str = "1"
    features: list[str] = Field(default_factory=list)
    deprecations: list[str] = Field(default_factory=list)


CONTRACT = StrategyApiContract(
    dsl_version=DSL_VERSION,
    api_version="1",
    features=[
        "entry-exit-alert-sections",
        "numeric-inputs",
        "risk-spec",
        "mtf-series-refs",
        "symbol-series-refs",
        "whitelisted-indicator-functions",
        "deterministic-no-lookahead-evaluation",
    ],
    deprecations=[],
)


@dataclass(frozen=True)
class MigrationPolicy:
    """Documentation dataclass describing accepted source versions."""

    accepted_versions: tuple[str, ...] = ("RSL-1.0.0",)
    migration_notes: tuple[str, ...] = (
        "RSL-1.0.0 is the initial language version; no migrations are defined yet.",
    )


MIGRATION_POLICY = MigrationPolicy()


def check_version_compat(version: str) -> bool:
    """Return True when ``version`` is an accepted RSL source version."""
    return version in MIGRATION_POLICY.accepted_versions
