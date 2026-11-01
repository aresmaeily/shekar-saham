"""Stable import surface for the AI-3 research-memory fixture kit.

The deterministic builders live canonically in
``backend/tests/fixtures/research_memory/``; this module re-exports them so
test modules can ``from helpers_research_memory_fixtures import ...``
independently of how pytest resolved the tests directory. Import is
defensive: the tests directory itself is ensured on ``sys.path`` so the
``fixtures.research_memory`` package resolves even under exotic invocations.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fixtures.research_memory import (  # noqa: E402  (path guard must run first)
    COMMIT_A,
    SHA_A,
    SHA_B,
    T0,
    T1,
    T2,
    T3,
    UTC,
    make_artifact_ref,
    make_episodic_entry,
    make_lesson,
    make_lesson_via_derive,
    make_seeded_lesson_store,
    make_store,
)

__all__ = [
    "COMMIT_A",
    "SHA_A",
    "SHA_B",
    "T0",
    "T1",
    "T2",
    "T3",
    "UTC",
    "make_artifact_ref",
    "make_episodic_entry",
    "make_lesson",
    "make_lesson_via_derive",
    "make_seeded_lesson_store",
    "make_store",
]
