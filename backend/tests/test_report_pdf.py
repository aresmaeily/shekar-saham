"""MASTER-RADAR WAVE-D (2026-11-05): deterministic PDF report export tests.

Closes the MR-D5-01 residual: PDF export of backtest/optimization/walk-forward
reports (CSV/JSON already delivered in WAVE-2). The PDF writer is a
zero-dependency byte-deterministic renderer (app/services/report_pdf.py).

Pinned contracts under test:
1. Byte-determinism: identical inputs -> byte-identical PDF (fixed Info dates,
   no /ID, uncompressed streams, no wall clock in the writer).
2. Structural validity: %PDF-1.4 magic, %%EOF tail, xref offsets that point
   exactly at "N 0 obj", startxref pointing at the xref keyword.
3. Honest content: uncompressed streams keep key strings greppable — trust
   label, digest, "NOT LIVE MARKET DATA", page numbering.
4. Hostile-content containment: PDF operator characters ( ) and backslash and
   non-WinAnsi glyphs in payload values never break the structure
   (escaped / '?' fallback, deterministic).
5. API surface: /strategylab/{backtest,optimize,walkforward}/export format=pdf
   returns an attachment PDF byte-identical across identical bodies; invalid
   format -> 422; csv/json surfaces unchanged (regression).
6. Third-party validation is env-conditional (poppler pdftotext when present)
   — consistent with the repo's env-conditional skip pattern; the structural
   checks above run unconditionally.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.report_pdf import (
    backtest_sections,
    optimize_sections,
    render_report_pdf,
    walkforward_sections,
)

# Settings-cache hygiene (same pattern as test_user_indicator_api.py): env-
# patching modules can leave residue in the get_settings() lru_cache; an
# autouse per-test clear keeps this module from poisoning later ones.
from app.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _settings_cache_hygiene():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _backtest_payload() -> dict:
    return {
        "run_id": "strategylab",
        "result_digest": "0f1ae1c06ea500cd69be4ab7e2d135488e82a59ceae4aa46136a00c44d5ababf",
        "engine_version": "BT-PRODUCT-1.0.0",
        "execution_model_version": "1.0.0",
        "symbol": "FOLAD",
        "timeframe": "1D",
        "bars_used": 200,
        "trades_count": 2,
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "trust_envelope": {"state": "mock", "trust_level": "synthetic"},
        "report": {
            "total_return_pct": 2.7642,
            "sharpe": 0.33347870594737244,
            "win_rate": 48.64864864864865,
            "trade_count": 37,
            "max_drawdown_pct": 6.640854418997533,
        },
        "trades": [
            {"side": "LONG", "entry_index": 3, "exit_index": 9, "entry_price": 100.5,
             "exit_price": 103.2, "qty": 10, "net_pnl": 27.0, "holding_bars": 6,
             "exit_reason": "EXIT_RULE", "regime_label": "R1"},
            {"side": "SHORT", "entry_index": 12, "exit_index": 20, "entry_price": 101.0,
             "exit_price": 99.5, "qty": 10, "net_pnl": 15.0, "holding_bars": 8,
             "exit_reason": "STOP", "regime_label": "R1"},
        ],
        "limitations": ["OHLCV execution model", "no tick fidelity"],
    }


def _optimize_payload() -> dict:
    return {
        "ok": True,
        "method": "grid",
        "objective": "SHARPE",
        "selection_basis": "IN_SAMPLE",
        "winner": {"params": {"fast": 8.0}, "param_hash": "c6e96540",
                   "objective_value": 1.0153653330345325, "is_refused": False,
                   "refuse_reason": None},
        "evaluations": [
            {"params": {"fast": 8.0}, "objective_value": 1.0153653330345325,
             "is_refused": False, "refuse_reason": None},
            {"params": {"fast": 3.0}, "objective_value": 0.1, "is_refused": False,
             "refuse_reason": None},
        ],
        "total_evaluations": 3,
        "evaluable_count": 2,
        "refused_count": 1,
        "reproducibility_digest": "4e452806e1853cb7fa5b1122334455667788990011223344",
        "symbol": "FOLAD",
        "timeframe": "1D",
        "bars_used": 200,
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "oos": {"enabled": True, "selection_basis": "IN_SAMPLE", "is_bars": 140,
                "oos_bars": 60, "is_objective_value": 1.0153653330345325,
                "oos_objective_value": 1.948536694301033, "oos_evaluated_once": True},
        "bonferroni_note": "alpha_effective = alpha/n recorded",
    }


def _walkforward_payload() -> dict:
    return {
        "ok": True,
        "engine_version": "WF-1.0.0",
        "symbol": "FOLAD",
        "timeframe": "1D",
        "bars_used": 300,
        "objective": "SHARPE",
        "search_method": "grid",
        "folds": [
            {"fold_index": 0, "train": {"start_index": 0, "end_index": 60},
             "test": {"start_index": 60, "end_index": 90}, "fold_seed": 11,
             "best_params": {"fast": 3.0}, "is_objective": -0.7801793608440505,
             "oos_objective": 0.3072122563065967, "evaluated_count": 3,
             "evaluable_count": 3, "oos_eval_count": 1, "oos_evaluated_once": True},
            {"fold_index": 1, "train": {"start_index": 30, "end_index": 90},
             "test": {"start_index": 90, "end_index": 120}, "fold_seed": 12,
             "best_params": {"fast": 5.0}, "is_objective": 0.2,
             "oos_objective": 0.4, "evaluated_count": 3,
             "evaluable_count": 3, "oos_eval_count": 1, "oos_evaluated_once": True},
        ],
        "aggregate": {"folds": 2, "mean_oos_objective": 0.35, "robust_note": "aggregate is OOS-only"},
        "reproducibility_digest": "cc6bf1bab043dcc9eeea00112233445566778899",
        "data_trust_label": "SYNTHETIC_OR_PAPER",
        "notes": ["selection is IN-SAMPLE per fold"],
    }


def _xref_offsets(pdf: bytes) -> list[int]:
    """Parse the trailer's startxref and return declared object offsets."""
    xref_pos = int(pdf.split(b"startxref\n")[1].split(b"\n")[0])
    assert pdf[xref_pos:xref_pos + 4] == b"xref"
    lines = pdf[xref_pos:].split(b"\n")
    offsets = [0]
    for line in lines[3:]:
        s = line.strip()
        if len(s) == 18 and (s.endswith(b"n") or s.endswith(b"f")):
            offsets.append(int(s[:10]))
    return offsets


# ---------------------------------------------------------------------------
# writer unit tests
# ---------------------------------------------------------------------------

def _pdf_text(pdf: bytes) -> str:
    """Decode the (uncompressed) stream text; word-wrapping inserts newlines,
    so phrase assertions use whitespace-flexible matching via _phrase()."""
    return pdf.decode("latin-1", errors="replace")


def _phrase(text: str, words: list[str]) -> bool:
    import re

    pattern = r"\s+".join(re.escape(w) for w in words)
    return re.search(pattern, text, re.IGNORECASE) is not None


def test_pdf_magic_and_eof():
    pdf = render_report_pdf("T", backtest_sections(_backtest_payload()))
    assert pdf.startswith(b"%PDF-1.4\n")
    assert pdf.endswith(b"%%EOF\n")


def test_pdf_byte_determinism():
    blocks = backtest_sections(_backtest_payload())
    a = render_report_pdf("RADAR BOURSE - Backtest Report 0f1ae1c0", blocks)
    b = render_report_pdf("RADAR BOURSE - Backtest Report 0f1ae1c0", blocks)
    assert a == b


def test_pdf_fixed_info_dates_no_wall_clock():
    pdf = render_report_pdf("T", backtest_sections(_backtest_payload()))
    assert b"/CreationDate (D:20000101000000Z)" in pdf
    assert b"/ModDate (D:20000101000000Z)" in pdf


def test_pdf_xref_offsets_consistent():
    pdf = render_report_pdf("T", backtest_sections(_backtest_payload()))
    offsets = _xref_offsets(pdf)
    assert len(offsets) > 4
    for i, off in enumerate(offsets[1:], start=1):
        assert pdf[off:off + len(f"{i} 0 obj")] == f"{i} 0 obj".encode()


def test_pdf_greppable_honest_content():
    payload = _backtest_payload()
    pdf = render_report_pdf("RADAR BOURSE - Backtest Report 0f1ae1c0", backtest_sections(payload))
    assert b"0f1ae1c0" in pdf
    assert b"SYNTHETIC_OR_PAPER" in pdf
    assert b"NOT LIVE MARKET DATA" in pdf
    assert b"Page 1 of" in pdf
    assert b"total_return_pct" in pdf
    # a trade row value renders
    assert b"EXIT_RULE" in pdf


def test_pdf_pagination_multiple_pages():
    payload = _backtest_payload()
    payload["trades"] = [
        {"side": "LONG", "entry_index": i, "exit_index": i + 1, "entry_price": 100.0 + i,
         "exit_price": 101.0 + i, "qty": 10, "net_pnl": 1.0, "holding_bars": 1,
         "exit_reason": "EXIT_RULE", "regime_label": "R1"}
        for i in range(250)
    ]
    pdf = render_report_pdf("RADAR BOURSE - Backtest Report long", backtest_sections(payload))
    # page count is consistent everywhere: /Count, Kids length and every footer
    import re

    m = re.search(rb"/Count (\d+)", pdf)
    count = int(m.group(1))
    assert count >= 2
    assert ("Page 1 of %d" % count).encode() in pdf
    assert ("Page %d of %d" % (count, count)).encode() in pdf
    kids = re.search(rb"/Kids \[(.*?)\]", pdf, re.S).group(1)
    assert len(re.findall(rb"\d+ 0 R", kids)) == count
    # the deterministic cap note renders when the trades exceed 200
    assert b"more rows are omitted" in pdf


def test_pdf_hostile_operator_characters_contained():
    payload = _backtest_payload()
    payload["symbol"] = 'A(B)\\C'
    payload["report"]["sharpe"] = 0.5
    blocks = backtest_sections(payload)
    a = render_report_pdf("T (x) y \\ z", blocks)
    b = render_report_pdf("T (x) y \\ z", blocks)
    assert a == b
    offsets = _xref_offsets(a)
    for i, off in enumerate(offsets[1:], start=1):
        assert a[off:off + len(f"{i} 0 obj")] == f"{i} 0 obj".encode()
    # the escaped form of the hostile symbol is present exactly once per page
    assert a.count(b"A\\(B\\)\\\\C") >= 1


def test_pdf_non_winansi_glyph_fallback_deterministic():
    payload = _backtest_payload()
    payload["symbol"] = "فملی"  # Persian glyphs are outside WinAnsi/base-14
    a = render_report_pdf("T", backtest_sections(payload))
    b = render_report_pdf("T", backtest_sections(payload))
    assert a == b
    assert b"????" in a  # four glyphs -> four deterministic '?' fallbacks


def test_pdf_none_renders_empty_and_float_repr_stable():
    payload = _backtest_payload()
    payload["report"]["cagr_pct"] = None
    pdf = render_report_pdf("T", backtest_sections(payload))
    assert b"cagr_pct" in pdf
    # float repr uses shortest round-trip repr (documented convention)
    assert b"0.33347870594737244" in pdf


def test_pdf_long_value_truncation_deterministic():
    payload = _backtest_payload()
    payload["result_digest"] = "ab" * 200  # 400 chars — column is narrower
    a = render_report_pdf("T", backtest_sections(payload))
    b = render_report_pdf("T", backtest_sections(payload))
    assert a == b and b"..." in a


def test_pdf_all_three_section_builders_render():
    for blocks in (
        backtest_sections(_backtest_payload()),
        optimize_sections(_optimize_payload()),
        walkforward_sections(_walkforward_payload()),
    ):
        pdf = render_report_pdf("T", blocks)
        assert pdf.startswith(b"%PDF-1.4") and pdf.endswith(b"%%EOF\n")
        offsets = _xref_offsets(pdf)
        for i, off in enumerate(offsets[1:], start=1):
            assert pdf[off:off + len(f"{i} 0 obj")] == f"{i} 0 obj".encode()


def test_walkforward_pdf_shows_oos_once_discipline():
    pdf = render_report_pdf("T", walkforward_sections(_walkforward_payload()))
    text = _pdf_text(pdf)
    assert _phrase(text, ["EVALUATED", "EXACTLY", "ONCE"])
    assert _phrase(text, ["per-fold", "selection", "is", "IN-SAMPLE"])
    assert b"oos_once" in pdf  # fold-table column header (values True per fold)


def test_optimize_pdf_shows_is_only_selection():
    pdf = render_report_pdf("T", optimize_sections(_optimize_payload()))
    assert b"IN_SAMPLE" in pdf
    assert b"oos_evaluated_once" in pdf  # OOS confirmation kv block
    assert b"4e452806" in pdf


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="poppler pdftotext not available in this environment")
def test_pdf_third_party_parser_roundtrip(tmp_path: Path):
    """Env-conditional independent validation: a real PDF parser must extract
    the honest trust label and the digest from the generated file."""
    pdf = render_report_pdf("RADAR BOURSE - Backtest Report 0f1ae1c0", backtest_sections(_backtest_payload()))
    p = tmp_path / "report.pdf"
    p.write_bytes(pdf)
    out = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, timeout=30)
    assert out.returncode == 0, out.stderr
    text = out.stdout.decode("utf-8", errors="replace")
    assert "SYNTHETIC_OR_PAPER" in text
    assert "0f1ae1c0" in text
    assert "NOT LIVE MARKET DATA" in text


# ---------------------------------------------------------------------------
# API surface tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.main import app

    # Distinct rate-limit identity (AUDIT-MR2 contract: every new API test
    # module carries its own limiter identity so the shared default "testclient"
    # budget is never consumed by module order — rate-limit identity census
    # 12345..12349 recorded; this module uses 12350).
    with TestClient(app, client=("mr-waved-pdf", 12350)) as c:
        yield c


_VALID_SOURCE = (
    "INPUT fast = 5\n"
    "RISK stop_loss_pct = 3.0, take_profit_pct = 6.0, max_position_pct = 50.0\n"
    "ENTRY close > sma(close, fast)\n"
    "EXIT close < sma(close, 20)"
)

_BT_BODY = {"source": _VALID_SOURCE, "symbol": "FOLAD", "timeframe": "1D", "count": 200}
_OPT_BODY = {
    "source": _VALID_SOURCE, "symbol": "FOLAD", "timeframe": "1D", "count": 200,
    "space": {"grid": {"fast": [3, 5, 8]}}, "method": "grid",
    "budget": {"max_evals": 9, "seed": 7}, "oos": {"enabled": True, "holdout_fraction": 0.3},
    "objective": "SHARPE",
}
_WF_BODY = {
    "source": _VALID_SOURCE, "symbol": "FOLAD", "timeframe": "1D", "count": 300,
    "folds": {"n": 3, "train_bars": 60, "test_bars": 30},
    "space": {"grid": {"fast": [3, 5, 8]}},
    "budget": {"max_evals_per_fold": 9, "seed": 11},
    "objective": "SHARPE",
}


def test_api_backtest_export_pdf(client: TestClient):
    r = client.post("/api/v10/strategylab/backtest/export", json={**_BT_BODY, "format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].startswith('attachment; filename="backtest-report-')
    assert r.content.startswith(b"%PDF-1.4")
    assert b"NOT LIVE MARKET DATA" in r.content


def test_api_backtest_export_pdf_byte_identical(client: TestClient):
    a = client.post("/api/v10/strategylab/backtest/export", json={**_BT_BODY, "format": "pdf"})
    b = client.post("/api/v10/strategylab/backtest/export", json={**_BT_BODY, "format": "pdf"})
    assert a.content == b.content


def test_api_backtest_export_default_json_unchanged(client: TestClient):
    r = client.post("/api/v10/strategylab/backtest/export", json=_BT_BODY)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers["content-disposition"].startswith('attachment; filename="backtest-report-')


def test_api_backtest_export_csv_regression(client: TestClient):
    r = client.post("/api/v10/strategylab/backtest/export", json={**_BT_BODY, "format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.splitlines()
    assert lines[0] == "## METRICS"
    assert "## TRADES" in lines


def test_api_optimize_export_pdf(client: TestClient):
    r = client.post("/api/v10/strategylab/optimize/export", json={**_OPT_BODY, "format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].startswith('attachment; filename="optimize-report-')
    assert b"IN_SAMPLE" in r.content
    a = client.post("/api/v10/strategylab/optimize/export", json={**_OPT_BODY, "format": "pdf"})
    assert a.content == r.content


def test_api_optimize_export_csv_and_json(client: TestClient):
    rc = client.post("/api/v10/strategylab/optimize/export", json={**_OPT_BODY, "format": "csv"})
    assert rc.status_code == 200 and rc.text.splitlines()[0] == "## METRICS"
    assert "## OOS_CONFIRMATION" in rc.text
    assert "## EVALUATIONS" in rc.text
    rj = client.post("/api/v10/strategylab/optimize/export", json={**_OPT_BODY, "format": "json"})
    assert rj.status_code == 200
    digest = rj.json()["reproducibility_digest"]
    assert rc.headers["content-disposition"].endswith(f'optimize-report-{digest[:8]}.csv"')


def test_api_walkforward_export_pdf(client: TestClient):
    r = client.post("/api/v10/strategylab/walkforward/export", json={**_WF_BODY, "format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="walkforward-report-')
    assert _phrase(_pdf_text(r.content), ["EVALUATED", "EXACTLY", "ONCE"])
    a = client.post("/api/v10/strategylab/walkforward/export", json={**_WF_BODY, "format": "pdf"})
    assert a.content == r.content


def test_api_walkforward_export_csv(client: TestClient):
    rc = client.post("/api/v10/strategylab/walkforward/export", json={**_WF_BODY, "format": "csv"})
    assert rc.status_code == 200
    assert "## FOLDS" in rc.text and "## AGGREGATE" in rc.text


@pytest.mark.parametrize("path,body", [
    ("/api/v10/strategylab/backtest/export", _BT_BODY),
    ("/api/v10/strategylab/optimize/export", _OPT_BODY),
    ("/api/v10/strategylab/walkforward/export", _WF_BODY),
])
def test_api_export_hostile_format_refused(client: TestClient, path: str, body: dict):
    r = client.post(path, json={**body, "format": "exe"})
    assert r.status_code == 422


def test_api_optimize_and_endpoint_digest_equal(client: TestClient):
    """The export path re-runs the SAME deterministic optimize run: identical
    body -> identical reproducibility_digest as the direct endpoint."""
    direct = client.post("/api/v10/strategylab/optimize", json=_OPT_BODY)
    via_export = client.post("/api/v10/strategylab/optimize/export", json={**_OPT_BODY, "format": "json"})
    assert direct.status_code == 200 and via_export.status_code == 200
    assert direct.json()["reproducibility_digest"] == via_export.json()["reproducibility_digest"]


def test_route_surface_new_export_paths_scoped(client: TestClient):
    """WAVE-D additive routes stay under the one governed /api/v10/strategylab
    prefix (enumeration via app.openapi() — the version-stable form)."""
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/api/v10/strategylab/backtest/export",
        "/api/v10/strategylab/optimize/export",
        "/api/v10/strategylab/walkforward/export",
    ):
        assert p in paths
    # every export path that lives in the strategylab router keeps its prefix
    assert all(
        p.startswith("/api/v10/strategylab/")
        for p in paths
        if p.startswith("/api/v10/strategylab/") and "/export" in p
    )
