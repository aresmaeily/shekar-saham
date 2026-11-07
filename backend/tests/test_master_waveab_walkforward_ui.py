"""WAVE-AB2 (2026-11-08): static gates for the Walk-Forward UI trigger.

Closes the recorded WAVE-AD residual ("walk-forward UI trigger honestly ABSENT;
API+38 tests") by pinning the frontend surface that now binds to the
already-tested API:

- ``POST /api/v10/strategylab/walkforward``      (engine walk_forward.py)
- ``POST /api/v10/strategylab/walkforward/export`` (json/csv/pdf)

Discipline mirrored from test_master_radar_frontend_static.py:
- HTTP boundary: module must import api/apiBlob from core/api.js and must NOT
  use fetch()/eval()/new Function()/WebSocket directly.
- All interpolated strings escaped with esc().
- Trust labels only from the server payload (trust_envelope / data_trust),
  never self-declared "live".
- Required UI elements present in index.html with unique ids inside the
  existing forward-center panel (tab count stays 31 — no new tab).
- Persian-first labels present.
- Export buttons exist for json/csv/pdf (UI-to-API-to-result-to-export
  lifecycle leg for walk-forward).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FC = (ROOT / "frontend" / "js" / "modules" / "render" / "forward_center.js").read_text(encoding="utf-8")


def test_walkforward_ui_elements_present_in_forward_center_panel():
    panel_start = INDEX.find('id="tab-forwardcenter"')
    assert panel_start != -1, "forward-center panel must exist"
    panel_end = INDEX.find("</section>", panel_start)
    panel = INDEX[panel_start:panel_end]
    for element_id in [
        "fcWfRun",
        "fcWfN",
        "fcWfTrain",
        "fcWfTest",
        "fcWfMaxEvals",
        "fcWfSeed",
        "fcWfObjective",
        "fcWfSpace",
        "fcWfNote",
        "fcWfFoldsBody",
        "fcWfAggregateBody",
        "fcWfExportJson",
        "fcWfExportCsv",
        "fcWfExportPdf",
    ]:
        assert f'id="{element_id}"' in panel, f"missing walk-forward UI element: {element_id}"


def test_walkforward_ui_ids_are_globally_unique():
    for element_id in ["fcWfRun", "fcWfSeed", "fcWfSpace", "fcWfFoldsBody", "fcWfAggregateBody", "fcWfExportPdf"]:
        assert INDEX.count(f'id="{element_id}"') == 1, f"duplicate id: {element_id}"


def test_walkforward_module_binds_only_the_tested_api_paths():
    assert '"/api/v10/strategylab/walkforward"' in FC
    assert '"/api/v10/strategylab/walkforward/export"' in FC
    # no other endpoint is introduced by this module
    for path in FC.split('"'):
        if path.startswith("/api/"):
            assert path in (
                "/api/v10/strategylab/paper-replay",
                "/api/v10/strategylab/walkforward",
                "/api/v10/strategylab/walkforward/export",
            ), f"unexpected endpoint in forward_center.js: {path}"


def test_walkforward_module_respects_http_and_dynamic_code_boundary():
    assert 'from "../../core/api.js"' in FC
    assert "apiBlob" in FC, "exports must go through the api() / apiBlob() boundary"
    assert "fetch(" not in FC, "direct fetch is banned"
    assert "eval(" not in FC
    assert "new Function" not in FC
    assert "WebSocket" not in FC


def test_walkforward_ui_escapes_interpolated_content():
    # every innerHTML assignment in the module interpolates through esc()/cell()
    assert "esc(" in FC
    # a raw ${...} innerHTML interpolation of request/response text is banned:
    # the module builds rows with cell()/esc() helpers only (spot-checks)
    for raw in ["${res.", "${fold.", "${ev."]:
        assert raw not in FC, f"unescaped interpolation pattern found: {raw}"


def test_walkforward_ui_persian_labels_present():
    for label in ["اجرای walk-forward", "خروجی JSON", "خروجی CSV", "خروجی PDF", "فولدها", "بذر"]:
        assert label in FC or label in INDEX, f"missing Persian label: {label}"
    # Persian-first honesty notes
    assert "دقیقاً یک‌بار" in FC, "OOS-evaluated-once honesty note must be present"
    assert "چیزی جعل نمی‌شود" in FC, "honest-empty placeholder discipline must hold"


def test_walkforward_exports_require_a_prior_run():
    # honest gate: export without a prior run is refused client-side
    assert "ابتدا walk-forward را اجرا کنید" in FC
    assert "lastWalkforwardBody" in FC


def test_walkforward_ui_never_self_declares_live():
    lowered = FC.lower()
    assert "live_verified" not in lowered.replace("live_verified never", "")
    assert '"live"' not in FC, "the module must not mint its own live label"
    assert "trust_envelope" in FC, "trust only from the server envelope"


def test_forward_center_tab_count_stays_31():
    # COUNTER-PIN BUMP (recorded, WAVE-AI 2026-11-08): 31 -> 32 — the new governed
    # AI-MA tab (aima, WP-C UI) added after the walk-forward section shipped here.
    tab_count = INDEX.count('data-tab="')
    assert tab_count == 32, f"tab count changed: {tab_count} (pinned at 32)"
