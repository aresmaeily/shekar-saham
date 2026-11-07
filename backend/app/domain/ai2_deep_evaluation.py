"""ai2_deep_evaluation.py — AI-2 deep-evaluation record contracts (WAVE-B, WP-B).

Work package B (AI-2/MVRL research loop) work item 1: the typed record
family for the bounded deterministic deep-evaluation block composed by the
governed generation pipeline (``app/services/ai2_generation.py``, added
AFTER the existing backtest + paper-replay stages; the pipeline stages
themselves are unchanged). MVRL stage mapping of the composition:

- stage 9  walk-forward : ``app/engines/walk_forward.py`` (pinned fold math,
            OOS-confirmed-once) over the SAME seeded synthetic series the
            pipeline already evaluates on;
- stage 10 holdout      : ``app/engines/holdout.py`` attestation for the
            declared evaluation-window split (holdout = tail, minority
            segment, selection declared closed strictly before the boundary);
- stage 11 robustness   : ``app/engines/regime_slices.py`` slices over the
            synthetic window with CALLER-DECLARED (pinned) regime labels —
            the pipeline never infers a regime from data;
- stage 12 comparison   : the candidate's backtest metrics vs the pipeline's
            DECLARED baseline program evaluated on the SAME seeded path and
            window (float deltas with an explicit ``delta_basis`` note).

LOCATION CHOICE (engineering authority, documented per the WP-B spec which
allows either home): a NEW domain module, NOT ``ai2_governance.py``. The
AI2-F run-governance contracts (budget/evidence/ledger/duplicate/acceptance)
are a separate, heavily test-pinned record family; deep evaluation is
EVALUATION EVIDENCE attached to a generation candidate, not run governance.
No import exists between the two modules; both stay deterministic and
clock-free.

Contract discipline (mirrors ai2_governance.py):
- frozen pydantic records, ``extra="forbid"``, deterministic, no I/O, no
  network, no LLM, no scheduler, NO CLOCK READS anywhere;
- fail-honest: an engine refusal is recorded as an ``AI2DeepRefusal`` row —
  it never raises out of the composition and never silently skips a stage;
- ``AI2HoldoutSummary.isolated`` is typed ``Literal[True]`` exactly like
  ``HoldoutAttestation.isolated``: the summary exists ONLY on the
  all-checks-passed path; every failing path yields a refusal row instead;
- the record is never vacuous: a ``AI2DeepEvaluation`` always carries at
  least one stage summary, one comparison row, or one refusal row
  (validated at the type level).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEEP_EVALUATION_VERSION = "AI2-DEEP-EVAL-1.0.0"

#: The evaluation stages of the composition (plus ``composition`` for
#: refusals of the composition itself, e.g. the seeded series refusing).
DeepEvaluationStage = Literal[
    "walk_forward",
    "holdout",
    "regime_slices",
    "comparison",
    "composition",
]


class AI2WalkForwardSummary(BaseModel):
    """Folds summary of the pinned small walk-forward over the seeded series.

    Field set mirrors the task's required summary (``n_folds``,
    ``confirmed_folds``, ``positive_folds``, ``oos_mean``,
    ``engine_version``) plus the pinned fold spec echo and the engine's own
    deterministic discipline fields (objective / selection basis /
    reproducibility digest) so the summary is auditable without re-running.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    n_folds: int = Field(ge=0)
    train_bars: int = Field(ge=1)
    test_bars: int = Field(ge=1)
    confirmed_folds: int = Field(ge=0)
    positive_folds: int = Field(ge=0)
    oos_mean: float | None = None
    engine_version: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    selection_basis: str = Field(min_length=1)
    reproducibility_digest: str = Field(min_length=64, max_length=64)
    declared_inputs: tuple[str, ...] = ()
    no_grid_note: str = ""

    @model_validator(mode="after")
    def _fold_counts_consistent(self) -> "AI2WalkForwardSummary":
        if self.confirmed_folds > self.n_folds or self.positive_folds > self.n_folds:
            raise ValueError("walk_forward_fold_counts_exceed_n_folds")
        return self


class AI2HoldoutSummary(BaseModel):
    """Attestation summary of the declared evaluation-window split.

    ``isolated`` is typed ``Literal[True]`` — the summary is constructed ONLY
    from a real ``HoldoutAttestation`` (the engine's all-checks-passed path);
    every holdout refusal produces a refusal row instead of a summary.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    holdout_fraction: float = Field(gt=0.0, lt=0.5)
    isolated: Literal[True] = True
    insample_bar_count: int = Field(ge=1)
    holdout_bar_count: int = Field(ge=1)
    selection_end_bar_index: int | None = None
    basis_note: str = ""

    @model_validator(mode="after")
    def _segment_counts_consistent(self) -> "AI2HoldoutSummary":
        if self.insample_bar_count + self.holdout_bar_count < 2:
            raise ValueError("holdout_summary_degenerate_segments")
        return self


class AI2RegimeSliceSummary(BaseModel):
    """Regime-slices summary over the synthetic window (declared labels).

    The labels are CALLER DECLARATIONS (positional/structural), never
    data-inferred regimes; ``declaration_note`` carries that statement so the
    summary can never be read as a data-driven regime discovery.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    labels: tuple[str, ...] = Field(min_length=1)
    bar_counts: tuple[int, ...]
    metric_names: tuple[str, ...] = Field(min_length=1)
    metrics: tuple[tuple[float, ...], ...]
    gap_labels: tuple[str, ...] = ()
    uncovered_bar_count: int = Field(ge=0)
    declaration_note: str = ""

    @model_validator(mode="after")
    def _aligned(self) -> "AI2RegimeSliceSummary":
        if not (len(self.labels) == len(self.bar_counts) == len(self.metrics)):
            raise ValueError("regime_summary_misaligned_rows")
        if any(len(row) != len(self.metric_names) for row in self.metrics):
            raise ValueError("regime_summary_metric_width_mismatch")
        return self


class AI2ComparisonRow(BaseModel):
    """One metric comparison: candidate vs the DECLARED baseline.

    ``delta`` is a plain IEEE-754 subtraction of two floats produced by the
    SAME engine on the SAME seeded path and window; ``delta_basis`` states
    that explicitly (the task allows float deltas with a basis note; no
    exact-rational claim is made). Unavailable metrics (e.g. sharpe with no
    trades) are recorded as ``None`` — never silently dropped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: str = Field(min_length=1)
    candidate: float | None = None
    baseline: float | None = None
    delta: float | None = None
    delta_basis: str = Field(min_length=1)
    baseline_spec: str = Field(min_length=1)


class AI2DeepRefusal(BaseModel):
    """One honest refusal row: an engine refused inside the deep evaluation.

    Recorded, never silent, never raised. ``reason`` is a stable machine
    code (engine reason code or ``engine_exception:<Type>``); ``detail``
    carries the bounded human-readable detail.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: DeepEvaluationStage
    reason: str = Field(min_length=1, max_length=200)
    detail: str = Field(default="", max_length=500)


class AI2DeepEvaluation(BaseModel):
    """The complete deep-evaluation record attached to one candidate.

    ``None`` summaries mean THAT STAGE REFUSED (with a matching refusal row)
    — never that it was silently skipped. All content is derived from the
    deterministic seeded synthetic path (``SYNTHETIC_OR_PAPER`` label is part
    of the record); identical inputs produce byte-identical records.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    deep_evaluation_version: str = DEEP_EVALUATION_VERSION
    data_label: Literal["SYNTHETIC_OR_PAPER"] = "SYNTHETIC_OR_PAPER"
    walk_forward: AI2WalkForwardSummary | None = None
    holdout: AI2HoldoutSummary | None = None
    robustness: AI2RegimeSliceSummary | None = None
    comparison: tuple[AI2ComparisonRow, ...] = ()
    refusals: tuple[AI2DeepRefusal, ...] = ()

    @model_validator(mode="after")
    def _never_vacuous(self) -> "AI2DeepEvaluation":
        if (
            self.walk_forward is None
            and self.holdout is None
            and self.robustness is None
            and not self.comparison
            and not self.refusals
        ):
            raise ValueError("deep_evaluation_vacuous")
        return self
