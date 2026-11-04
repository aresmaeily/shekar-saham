"""MR2-A WAVE-2 tests — strategy_alerts on-demand evaluator.

Covers the pinned result contract of ``app.engines.strategy_alerts.evaluate_condition``:
trigger / no-trigger on the LAST closed bar, safe machine-readable compile
errors (strategy-DSL error shape, never raised), the documented staleness
refusal via the caller-injected ``as_of`` wall clock, determinism, and the
self-audit scans (no forbidden execution/egress primitives, no scheduler
plumbing) mirroring the ``test_strategy_dsl_sandbox`` audit style.  The file
reads happen here in the TEST only, never in domain code.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.engines.strategy_alerts import STALENESS_WINDOW_BARS, evaluate_condition

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "engines" / "strategy_alerts.py"

SOURCE = "INPUT p = 3\nENTRY close > sma(close, p)"


def rising_bars(n: int = 10, step: float = 1.0) -> list[dict]:
    """Shared-contract bars, closes strictly rising on a 60-second grid."""
    return [
        {
            "ts": 1_700_000_000 + i * 60,
            "o": 1.0 + i * step,
            "h": 2.0 + i * step,
            "l": 0.5 + i * step,
            "c": 1.5 + i * step,
            "v": 10.0,
        }
        for i in range(n)
    ]


def falling_bars(n: int = 10) -> list[dict]:
    """Shared-contract bars, closes strictly falling on a 60-second grid."""
    return [
        {
            "ts": 1_700_000_000 + i * 60,
            "o": 20.0 - i,
            "h": 20.5 - i,
            "l": 19.0 - i,
            "c": 19.75 - i,
            "v": 10.0,
        }
        for i in range(n)
    ]


class TestTriggerContract:
    def test_trigger_case_last_closed_bar(self) -> None:
        # closes 1.5..10.5; sma(3) at the last bar = (8.5+9.5+10.5)/3 = 9.5,
        # close 10.5 > 9.5 -> the LAST closed bar triggers.
        result = evaluate_condition(SOURCE, rising_bars())
        assert result["triggered"] is True
        assert result["last_value"] is True
        assert result["bar_ts"] == 1_700_000_000 + 9 * 60
        assert result["bars_evaluated"] == 10
        assert result["program_digest"] == hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
        assert result["errors"] == []
        assert "stale" not in result  # documented shape: no stale key on success

    def test_no_trigger_case(self) -> None:
        # closes 19.75 down to 10.75; sma(3) at the last bar = (12.75+11.75+10.75)/3
        # = 11.75, close 10.75 < 11.75 -> no trigger anywhere near the end.
        result = evaluate_condition(SOURCE, falling_bars())
        assert result["triggered"] is False
        assert result["last_value"] is False
        assert result["bars_evaluated"] == 10
        assert result["errors"] == []

    def test_condition_is_the_entry_section(self) -> None:
        # the documented semantics: triggered mirrors the program's ENTRY
        # decision on the last closed bar (ALERT/EXIT are not consulted).
        bars = rising_bars()
        assert evaluate_condition("ENTRY close > 100", bars)["triggered"] is False
        assert evaluate_condition("ENTRY close > 0", bars)["triggered"] is True

    def test_legacy_engine_shape_bars_accepted(self) -> None:
        bars = [
            {"time": 1_700_000_000 + i * 60, "open": 1.0 + i, "high": 2.0 + i,
             "low": 0.5 + i, "close": 1.5 + i, "volume": 10.0}
            for i in range(10)
        ]
        result = evaluate_condition("ENTRY close > 10", bars)
        assert result["triggered"] is True
        assert result["bar_ts"] == 1_700_000_000 + 9 * 60

    def test_volume_optional(self) -> None:
        bars = [{**b, **{}} for b in rising_bars(4)]
        for b in bars:
            del b["v"]
        result = evaluate_condition("ENTRY close > 0", bars)
        assert result["triggered"] is True and result["errors"] == []


class TestSafeErrorReporting:
    def test_compile_error_returned_not_raised(self) -> None:
        result = evaluate_condition("ENTRY close >", rising_bars())
        assert result["triggered"] is False
        assert result["bars_evaluated"] == 0
        assert result["program_digest"] is None
        assert len(result["errors"]) == 1
        err = result["errors"][0]
        assert set(err) == {"code", "message", "line", "col"}  # DSL error shape
        assert err["code"] == "PARSE_UNEXPECTED_TOKEN"
        assert err["message"]

    def test_budget_error_returned(self) -> None:
        result = evaluate_condition("ENTRY " + "0" * 5000, rising_bars())
        assert result["errors"][0]["code"] == "BUDGET_SOURCE_LEN"
        assert result["bars_evaluated"] == 0

    def test_hostile_source_never_executed(self) -> None:
        # from the sandbox table: a call-looking token is a type error and
        # nothing is ever evaluated
        result = evaluate_condition('ENTRY eval("1") > 0', rising_bars())
        assert result["triggered"] is False
        assert result["errors"][0]["code"] == "TYPE_REF_INVALID_BASE"

    def test_empty_series_error(self) -> None:
        result = evaluate_condition(SOURCE, [])
        assert result["errors"][0]["code"] == "ALERT_EMPTY_SERIES"
        assert result["bars_evaluated"] == 0 and result["bar_ts"] is None

    def test_malformed_bar_error(self) -> None:
        result = evaluate_condition(SOURCE, [{"ts": 1, "c": 1.0}])
        assert result["errors"][0]["code"] == "ALERT_BAD_SERIES"

    def test_non_string_source_error(self) -> None:
        result = evaluate_condition(42, rising_bars())  # type: ignore[arg-type]
        assert result["errors"][0]["code"] == "ALERT_BAD_SOURCE"


class TestStalenessRefusal:
    def test_refusal_beyond_documented_window(self) -> None:
        bars = rising_bars()  # median interval 60s -> window = 3*60 = 180s
        last_ts = bars[-1]["ts"]
        assert STALENESS_WINDOW_BARS == 3  # the documented constant
        fresh = evaluate_condition(SOURCE, bars, as_of=last_ts + 180)
        assert "stale" not in fresh and fresh["triggered"] is True  # age == window: accepted
        stale = evaluate_condition(SOURCE, bars, as_of=last_ts + 181)
        assert stale["stale"] is True
        assert stale["triggered"] is False
        assert stale["last_value"] is None
        assert stale["bar_ts"] == last_ts
        assert stale["bars_evaluated"] == 0  # refusal happens before evaluating
        assert stale["program_digest"] is None  # and before compiling
        assert stale["errors"] == []

    def test_as_of_before_last_bar_is_fresh(self) -> None:
        bars = rising_bars()
        result = evaluate_condition(SOURCE, bars, as_of=bars[-1]["ts"] - 10_000)
        assert "stale" not in result and result["triggered"] is True

    def test_single_bar_series_zero_window(self) -> None:
        # fewer than two bars -> no derivable interval -> zero window:
        # any positive age is refused (documented conservative default)
        bars = rising_bars(1)
        last_ts = bars[0]["ts"]
        assert evaluate_condition(SOURCE, bars, as_of=last_ts)["triggered"] is True
        refused = evaluate_condition(SOURCE, bars, as_of=last_ts + 1)
        assert refused["stale"] is True

    def test_irregular_intervals_use_median(self) -> None:
        # intervals 60,60,60,600,60,60,60 -> sorted positive deltas median 60
        bars = rising_bars(8)
        stamps = [b["ts"] for b in bars]
        bars[4]["ts"] = stamps[3] + 600  # one long gap
        for i in range(5, 8):
            bars[i]["ts"] = bars[i - 1]["ts"] + 60
        last_ts = bars[-1]["ts"]
        assert evaluate_condition(SOURCE, bars, as_of=last_ts + 180)["triggered"] is True
        assert evaluate_condition(SOURCE, bars, as_of=last_ts + 181)["stale"] is True


class TestDeterminism:
    def test_two_runs_byte_identical(self) -> None:
        bars = rising_bars()
        first = evaluate_condition(SOURCE, bars)
        second = evaluate_condition(SOURCE, bars)
        assert first == second

    def test_stale_refusal_deterministic(self) -> None:
        bars = rising_bars()
        as_of = bars[-1]["ts"] + 10_000
        assert evaluate_condition(SOURCE, bars, as_of=as_of) == evaluate_condition(
            SOURCE, bars, as_of=as_of
        )

    def test_errors_deterministic(self) -> None:
        assert evaluate_condition("ENTRY close >", rising_bars()) == evaluate_condition(
            "ENTRY close >", rising_bars()
        )


class TestSelfAudit:
    # mirrors the test_strategy_dsl_sandbox audit style: the file read happens
    # here in the test only, never in domain code.
    FORBIDDEN_TOKENS = (
        "eval(",
        "exec(",
        "__import__",
        "socket",
        "requests",
        "httpx",
        "urllib",
    )
    SCHEDULER_TOKENS = ("threading", "asyncio", "create_task", "BackgroundTasks")

    def test_no_forbidden_execution_or_egress_primitives(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        findings = audit_forbidden_tokens(text, self.FORBIDDEN_TOKENS)
        assert findings == []

    def test_no_scheduler_plumbing(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        findings = audit_forbidden_tokens(text, self.SCHEDULER_TOKENS)
        assert findings == []

    def test_no_file_or_network_io_calls(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        findings = audit_forbidden_tokens(
            text, ("open(", "Path(", "subprocess", "os.system", "popen")
        )
        assert findings == []

    def test_audit_tool_works(self) -> None:
        # sanity: the audit detects a synthetic violation (temp file, like the
        # sandbox suite's own audit sanity check)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.py"
            path.write_text("x = eval('1')\n", encoding="utf-8")
            findings = audit_forbidden_tokens(
                path.read_text(encoding="utf-8"), self.FORBIDDEN_TOKENS
            )
            assert len(findings) == 1 and "eval(" in findings[0]


def audit_forbidden_tokens(text: str, tokens: tuple[str, ...]) -> list[str]:
    """Return one finding per forbidden token present in ``text``."""
    return [f"contains forbidden token {token!r}" for token in tokens if token in text]
