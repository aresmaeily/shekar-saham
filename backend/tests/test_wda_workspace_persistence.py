"""WDA-1 — workspace persistence contract tests (static, established pattern).

These tests follow the repo's frontend test pattern (see
``test_frontend_static_script.py``): the browser JS is never executed in
pytest; the module source is read and pinned statically.

Pinned artifacts:
- ``frontend/js/modules/workspace.js`` — the WDA-1 workspace module:
  schema-versioned envelope, quarantine-on-corruption, injectable storage
  adapter, and a delimited pure-logic block (``__workspace_internal``).
- ``frontend/js/modules/render/chart_pro.js`` — the surgical wiring lines
  (import, init-time restore, debounced save hooks).

The two marker comments ``// >>> WDA-1 PURE LOGIC BEGIN`` / ``END`` delimit
the storage-free pure functions; the structural assertions below pin their
documented names so a rename cannot silently break the declared contract.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_JS = (ROOT / "frontend" / "js" / "modules" / "workspace.js").read_text(encoding="utf-8")
CHART_PRO_JS = (ROOT / "frontend" / "js" / "modules" / "render" / "chart_pro.js").read_text(encoding="utf-8")

PURE_BEGIN = "// >>> WDA-1 PURE LOGIC BEGIN"
PURE_END = "// >>> WDA-1 PURE LOGIC END"

FORBIDDEN_CALLS = ("fetch(", "XMLHttpRequest", "eval(", "new Function")


def test_pure_logic_block_is_delimited():
    """The pure-logic block must be explicitly delimited for static pinning."""
    assert PURE_BEGIN in WORKSPACE_JS
    assert PURE_END in WORKSPACE_JS
    assert WORKSPACE_JS.index(PURE_BEGIN) < WORKSPACE_JS.index(PURE_END)


def test_pure_block_contains_documented_function_names():
    """Documented pure functions live inside the delimited block only."""
    block = WORKSPACE_JS[WORKSPACE_JS.index(PURE_BEGIN) : WORKSPACE_JS.index(PURE_END)]
    for signature in (
        "function wsDefaultState()",
        "function wsValidatePayload(",
        "function wsWrapState(",
        "function wsSave(",
        "function wsLoad(",
        "function wsQuarantine(",
        "function wsReset(",
    ):
        assert signature in block, signature
    registry = "const __workspace_internal = {"
    assert registry in block
    for binding in (
        "save: wsSave",
        "load: wsLoad",
        "quarantine: wsQuarantine",
        "reset: wsReset",
        "validatePayload: wsValidatePayload",
        "defaultState: wsDefaultState",
        "wrapState: wsWrapState",
    ):
        assert binding in block, binding


def test_schema_versioned_envelope_fields_present():
    """Envelope contract: {schema: 1, saved_at_iso, payload}."""
    assert "const WORKSPACE_SCHEMA_VERSION = 1;" in WORKSPACE_JS
    assert "schema: WORKSPACE_SCHEMA_VERSION" in WORKSPACE_JS
    assert "saved_at_iso:" in WORKSPACE_JS
    assert "payload: validated.payload" in WORKSPACE_JS


def test_namespaced_storage_key_present():
    assert '"radar.workspace.v1"' in WORKSPACE_JS


def test_quarantine_evidence_key_present():
    assert '"radar.workspace.corrupted"' in WORKSPACE_JS


def test_unknown_schema_refusal_branch_does_not_destroy_data():
    """Future/unknown schema -> {ok:false, reason:"schema_unsupported"}; the
    saved payload is preserved (no quarantine write, no key removal) in that
    branch: it returns before the payload-shape quarantine path."""
    reason_idx = WORKSPACE_JS.index('reason: "schema_unsupported"')
    payload_not_object_idx = WORKSPACE_JS.index('return wsQuarantine(storage, raw, "payload_not_object")')
    assert reason_idx < payload_not_object_idx
    # Exactly two removeItem(WORKSPACE_KEY) call sites: quarantine-reset + explicit reset.
    assert WORKSPACE_JS.count("removeItem(WORKSPACE_KEY)") == 2


def test_corrupted_payload_quarantine_branch_order():
    """Corruption -> evidence written under the quarantine key BEFORE the main
    key is reset; both documented parse-failure causes are present."""
    assert 'reason: "corrupted_quarantined"' in WORKSPACE_JS
    assert '"json_parse_failed"' in WORKSPACE_JS
    assert '"envelope_not_object"' in WORKSPACE_JS
    assert '"payload_not_object"' in WORKSPACE_JS
    quarantine_set_idx = WORKSPACE_JS.index("storage.setItem(\n      WORKSPACE_CORRUPTED_KEY")
    first_remove_idx = WORKSPACE_JS.index("storage.removeItem(WORKSPACE_KEY)")
    assert quarantine_set_idx < first_remove_idx


def test_no_forbidden_browser_or_dynamic_calls():
    """No network calls, no dynamic code evaluation anywhere in the module."""
    for needle in FORBIDDEN_CALLS:
        assert needle not in WORKSPACE_JS, needle


def test_storage_adapter_injection_point_present():
    """All storage access goes through the injectable adapter; the default is
    window.localStorage and null-storage degrades to storage_unavailable."""
    assert "export function saveWorkspace(state, storage)" in WORKSPACE_JS
    assert "export function loadWorkspace(storage)" in WORKSPACE_JS
    assert "export function resetWorkspace(storage)" in WORKSPACE_JS
    assert "function defaultStorage()" in WORKSPACE_JS
    assert "window.localStorage" in WORKSPACE_JS
    assert "storage || defaultStorage()" in WORKSPACE_JS
    assert '"storage_unavailable"' in WORKSPACE_JS


def test_validation_allowlists_match_backend_and_ui_contract():
    """Timeframe grid equals the backend pattern ^(1m|5m|15m|1h|1D)$
    (backend/app/api/chart_pro.py); indicator and draw-tool keys equal the
    cpIndSeg/cpDrawSeg data attributes in index.html; issues are collected."""
    assert 'const WORKSPACE_TIMEFRAMES = ["1m", "5m", "15m", "1h", "1D"];' in WORKSPACE_JS
    assert 'const WORKSPACE_INDICATORS = ["ma20", "ma50", "ema20", "bb", "rsi", "macd"];' in WORKSPACE_JS
    assert 'const WORKSPACE_DRAW_TOOLS = ["trend", "hline", "fib", "delete"];' in WORKSPACE_JS
    assert "unknown fields dropped:" in WORKSPACE_JS
    assert "issues" in WORKSPACE_JS


def test_never_throw_contract_has_defensive_catch_paths():
    """Every public path is try/catch-guarded; the module must never throw to
    its caller (restart restoration always yields a valid state)."""
    assert WORKSPACE_JS.count("try {") >= 6
    assert WORKSPACE_JS.count("catch (err)") >= 6
    assert 'reason: "storage_write_failed"' in WORKSPACE_JS
    # Public API returns the adapter result directly — no unguarded storage call.
    public_api = WORKSPACE_JS[WORKSPACE_JS.index("// >>> WDA-1 PURE LOGIC END") :]
    assert "storage.setItem" not in public_api.split("function defaultStorage()")[0]


def test_chart_pro_imports_and_restores_workspace_on_init():
    """Surgical wiring: import line + init-time restore of symbol/timeframe/indicators."""
    assert 'import { loadWorkspace, saveWorkspace } from "../workspace.js";' in CHART_PRO_JS
    assert "const _ws = loadWorkspace();" in CHART_PRO_JS
    assert "this.onIndicators = { ...this.onIndicators, ..._ws.payload.indicators };" in CHART_PRO_JS
    assert 'if (_ws.payload.timeframe) this.timeframe = _ws.payload.timeframe;' in CHART_PRO_JS


def test_chart_pro_debounced_save_hooks_present():
    """Save path: debounced _queueWorkspaceSave with >=4 state-change hook sites."""
    assert CHART_PRO_JS.count("_queueWorkspaceSave() {") == 1
    assert "clearTimeout(this._wsTimer)" in CHART_PRO_JS
    assert "}, 600);" in CHART_PRO_JS  # debounce window
    assert "saveWorkspace({" in CHART_PRO_JS
    # Hook call sites (indicator toggle, drawings, alerts, symbol/timeframe load).
    assert CHART_PRO_JS.count("this._queueWorkspaceSave(); // WDA-1") >= 4


def test_chart_pro_persists_documented_workspace_fields():
    """The save payload covers the documented field set (symbol, timeframe,
    indicators, pane layout, drawing tools, alerts, window hints)."""
    save_block = CHART_PRO_JS[CHART_PRO_JS.index("saveWorkspace({") : CHART_PRO_JS.index("}, 600);")]
    for field in ("symbol:", "timeframe:", "indicators:", "pane_layout:", "drawing_tools:", "alerts:", "window_layout:"):
        assert field in save_block, field
