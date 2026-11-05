"""report_pdf — deterministic PDF report writer for Strategy Lab exports.

MASTER-RADAR WAVE-D (2026-11-05): closes the MR-D5-01 residual "PDF export of
backtest/optimization/walk-forward reports" (CSV/JSON already delivered in
WAVE-2) WITHOUT adding any third-party dependency.

Design contract (pinned):

1. **Byte-determinism**: identical section input -> byte-identical PDF. The
   Info dictionary carries fixed dates (20000101000000Z) and no file /ID, no
   random values, no wall clock anywhere. Streams are UNCOMPRESSED so key
   strings stay greppable (testability + honest inspection).
2. **Base-14 fonts only** (Helvetica, Helvetica-Bold, Courier): no font
   embedding, so glyphs outside WinAnsiEncoding cannot render. The export is
   therefore an ENGLISH-LABEL projection (same convention as the CSV export:
   "English keys, documented"). Persian text renders in the product UI, not
   in this PDF — stated on every PDF as an explicit limitation line.
3. **Honesty block on every report**: the report carries the engine's own
   data_trust label, the synthetic note, and the note that the JSON export
   remains the full-fidelity report. The PDF writer NEVER invents values: it
   renders the payload projection it is given, and `None` renders as "".
4. **No escape hatches**: text is escaped per PDF string syntax; the writer
   never interprets payload content as operators; output is bytes.
5. **Fail-closed sizing**: text wider than the column is hard-truncated by
   glyph count (measured via an average-width estimate for Helvetica; Courier
   is fixed-width and exact). No dynamic layout decisions from data values.
"""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

# A4 in points
_PAGE_W = 595.28
_PAGE_H = 841.89
_MARGIN = 40.0
_LINE_H = 12.0
_BOTTOM_LIMIT = 56.0
_MAX_Y = _PAGE_H - _MARGIN

# Column x positions for label/value rows (points)
_COL_LABEL_X = _MARGIN
_COL_VALUE_X = 230.0
_RIGHT_LIMIT = _PAGE_W - _MARGIN

# Rough average glyph width for Helvetica 9pt (deterministic truncation basis)
_AVG_GLYPH_W = 4.6
_COURIER_GLYPH_W = 5.4  # Courier 9pt is fixed: 0.6 em


def _esc(text: str) -> str:
    """Escape a string for a PDF literal text operator ( ) \\ and non-latin."""
    out: List[str] = []
    for ch in text:
        o = ord(ch)
        if ch in ("\\", "(", ")"):
            out.append("\\" + ch)
        elif 32 <= o <= 126:
            out.append(ch)
        else:
            # WinAnsi-unreachable glyph -> deterministic ASCII fallback
            out.append("?")
    return "".join(out)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _fmt_value(value: Any) -> str:
    """Deterministic value rendering: str() as-is (floats keep the engine's
    shortest round-trip repr, same convention as the CSV export); None -> ''."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (dict, list)):
        import json

        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            return str(value)
    return str(value)


# ---------------------------------------------------------------------------
# Section model: an ordered list of blocks the renderer lays out verbatim.
# Block kinds: ("heading", text) | ("kv", [(label, value)]) | ("table", header
# list, rows, col-width-chars list) | ("text", paragraph) | ("rule",)
# ---------------------------------------------------------------------------

Block = Tuple[str, Any]


def backtest_sections(payload: dict) -> List[Block]:
    """Projection of the /backtest payload (mirror of the CSV export's
    documented column order, plus the report/limitations the JSON carries)."""
    report: dict = payload.get("report") or {}
    digest = str(payload.get("result_digest") or "")
    blocks: List[Block] = [
        ("text", "Report: Strategy Lab deterministic backtest (engine "
        + str(payload.get("engine_version") or "n/a")
        + ", execution model "
        + str(payload.get("execution_model_version") or "n/a")
        + ")"),
        ("kv", [("result_digest", digest)]),
        ("kv", [(k, payload.get(k)) for k in (
            "run_id", "symbol", "timeframe", "bars_used", "trades_count")]),
        ("heading", "METRICS"),
        ("kv", [(k, report.get(k)) for k in (
            "total_return_pct", "annualized_return_pct", "cagr_pct",
            "max_drawdown_pct", "max_drawdown_duration_bars", "sharpe",
            "sortino", "calmar", "profit_factor", "expectancy", "win_rate",
            "avg_win", "avg_loss", "trade_count", "exposure_pct",
            "avg_holding_bars", "turnover", "fees_total")]),
        ("heading", "TRADES"),
        ("table",
         ["#", "side", "entry_idx", "exit_idx", "entry_price", "exit_price",
          "qty", "net_pnl", "hold", "exit_reason", "regime"],
         _trade_rows(payload),
         [5, 7, 10, 10, 13, 13, 10, 13, 6, 12, 10]),
        ("heading", "LIMITATIONS AND HONESTY"),
        *( [("text", f"Trades table is capped at 200 rows for this projection; "
                      f"{len(payload.get('trades') or []) - 200} more rows are omitted "
                      f"(the JSON export carries the full trade list).")] if len(payload.get("trades") or []) > 200 else () ),
        ("text", "Data trust: " + str(payload.get("data_trust_label")
         or (payload.get("trust_envelope") or {}).get("state") or "n/a")
         + " - SYNTHETIC SEEDED SERIES, NOT LIVE MARKET DATA."),
        ("text", "This PDF is a fixed-layout projection in English labels; the "
         "JSON export remains the full-fidelity report (equity curve, calendar "
         "rows, full trust envelope). Persian text renders in the product UI, "
         "not in this PDF (base-14 fonts)."),
    ]
    limitations = payload.get("limitations")
    if isinstance(limitations, (list, tuple)) and limitations:
        blocks.append(("text", "Engine-reported limitations: " + "; ".join(str(x) for x in limitations)))
    return blocks


def _trade_rows(payload: dict) -> List[List[str]]:
    rows: List[List[str]] = []
    trades = payload.get("trades") or []
    for i, t in enumerate(trades[:200]):  # deterministic cap, stated in a text block
        rows.append([
            str(i + 1),
            _fmt_value(t.get("side")),
            _fmt_value(t.get("entry_index")),
            _fmt_value(t.get("exit_index")),
            _fmt_value(t.get("entry_price")),
            _fmt_value(t.get("exit_price")),
            _fmt_value(t.get("qty")),
            _fmt_value(t.get("net_pnl")),
            _fmt_value(t.get("holding_bars")),
            _fmt_value(t.get("exit_reason")),
            _fmt_value(t.get("regime_label")),
        ])
    return rows


def optimize_sections(payload: dict) -> List[Block]:
    """Projection of the /optimize payload (IS selection + OOS-once)."""
    winner = payload.get("winner") or {}
    oos = payload.get("oos") or {}
    evals = payload.get("evaluations") or []
    blocks: List[Block] = [
        ("text", "Report: Strategy Lab optimizer (method "
        + str(payload.get("method") or "n/a")
        + ", objective " + str(payload.get("objective") or "n/a")
        + ", selection basis " + str(payload.get("selection_basis") or "n/a") + ")"),
        ("kv", [("reproducibility_digest", str(payload.get("reproducibility_digest") or ""))]),
        ("kv", [(k, payload.get(k)) for k in (
            "symbol", "timeframe", "bars_used", "total_evaluations",
            "evaluable_count", "refused_count", "n_constraint_skips",
            "budget_exhausted", "cancelled")]),
        ("heading", "WINNER (IN-SAMPLE SELECTION)"),
        ("kv", [
            ("params", winner.get("params")),
            ("objective_value", winner.get("objective_value")),
            ("is_refused", winner.get("is_refused")),
            ("refuse_reason", winner.get("refuse_reason")),
        ]),
        ("heading", "OOS CONFIRMATION (EVALUATED EXACTLY ONCE)"),
        ("kv", [
            ("enabled", oos.get("enabled")),
            ("selection_basis", oos.get("selection_basis")),
            ("is_bars", oos.get("is_bars")),
            ("oos_bars", oos.get("oos_bars")),
            ("is_objective_value", oos.get("is_objective_value")),
            ("oos_objective_value", oos.get("oos_objective_value")),
            ("oos_evaluated_once", oos.get("oos_evaluated_once")),
        ]),
        ("heading", "EVALUATIONS (CAP 200)"),
        ("table",
         ["#", "params", "objective", "refused", "reason"],
         [[str(i + 1),
           _fmt_value(e.get("params")),
           _fmt_value(e.get("objective_value")),
           _fmt_value(e.get("is_refused")),
           _fmt_value(e.get("refuse_reason"))]
          for i, e in enumerate(evals[:200])],
         [5, 34, 14, 8, 20]),
        ("heading", "LIMITATIONS AND HONESTY"),
        ("text", "Data trust: " + str(payload.get("data_trust_label") or "n/a")
         + " - SYNTHETIC SEEDED SERIES, NOT LIVE MARKET DATA."),
        ("text", "Selection is IN-SAMPLE; out-of-sample (if enabled) is "
         "evaluated exactly once after the winner is frozen and never "
         "influences selection. " + str(payload.get("bonferroni_note") or "")),
        ("text", "This PDF is a fixed-layout projection in English labels; the "
         "JSON response remains the full-fidelity report. Persian text renders "
         "in the product UI, not in this PDF (base-14 fonts)."),
    ]
    return blocks


def walkforward_sections(payload: dict) -> List[Block]:
    """Projection of the /walkforward payload (per-fold IS selection +
    OOS-confirmed-once discipline)."""
    folds = payload.get("folds") or []
    aggregate = payload.get("aggregate") or {}
    blocks: List[Block] = [
        ("text", "Report: Strategy Lab walk-forward analysis (engine "
        + str(payload.get("engine_version") or "n/a")
        + ", objective " + str(payload.get("objective") or "n/a")
        + ", selection IN_SAMPLE_PER_FOLD)"),
        ("kv", [("reproducibility_digest", str(payload.get("reproducibility_digest") or ""))]),
        ("kv", [(k, payload.get(k)) for k in (
            "symbol", "timeframe", "bars_used")]),
        ("heading", "FOLD TABLE"),
        ("table",
         ["fold", "train", "test", "seed", "best_params", "IS_objective",
          "OOS_objective", "evals", "oos_once"],
         [[str(f.get("fold_index")),
           f"{f.get('train', {}).get('start_index')}-{f.get('train', {}).get('end_index')}",
           f"{f.get('test', {}).get('start_index')}-{f.get('test', {}).get('end_index')}",
           str(f.get("fold_seed")),
           _fmt_value(f.get("best_params")),
           _fmt_value(f.get("is_objective")),
           _fmt_value(f.get("oos_objective")),
           str(f.get("evaluable_count")),
           _fmt_value(f.get("oos_evaluated_once"))]
          for f in folds],
         [6, 12, 12, 7, 18, 13, 13, 8, 9]),
        ("heading", "AGGREGATE"),
        ("kv", [(k, aggregate.get(k)) for k in sorted(aggregate.keys()) if isinstance(
            aggregate.get(k), (str, int, float, bool, type(None)))]),
        ("heading", "LIMITATIONS AND HONESTY"),
        ("text", "Data trust: " + str(payload.get("data_trust_label") or "n/a")
         + " - SYNTHETIC SEEDED SERIES, NOT LIVE MARKET DATA."),
        ("text", "Per-fold selection is IN-SAMPLE; each fold's test window is "
         "evaluated EXACTLY ONCE with the already-frozen best params "
         "(oos_eval_count recorded per fold); no fold's test data can "
         "influence its selection."),
        ("text", "This PDF is a fixed-layout projection in English labels; the "
         "JSON response remains the full-fidelity report. Persian text renders "
         "in the product UI, not in this PDF (base-14 fonts)."),
    ]
    notes = payload.get("notes")
    if isinstance(notes, (list, tuple)) and notes:
        blocks.append(("text", "Engine notes: " + "; ".join(str(x) for x in notes)))
    return blocks


# ---------------------------------------------------------------------------
# Low-level deterministic PDF assembly (PDF 1.4, uncompressed streams)
# ---------------------------------------------------------------------------

def _text_lines_for_block(block: Block) -> List[Tuple[str, str, str]]:
    """Flatten a block into (font, size, content) draw lines at x=0 (handled
    by the layout stage). Content is ALREADY escaped text-operator-safe.
    Returns lines with an explicit x offset embedded via a marker tuple
    (x_offset_pt, font, size, escaped_content)."""
    kind = block[0]
    lines: List[Tuple[float, str, float, str]] = []
    if kind == "heading":
        lines.append((_COL_LABEL_X, "F2", 11.0, _esc(str(block[1]))))
    elif kind == "text":
        for chunk in _wrap(str(block[1]), max_chars=int((_RIGHT_LIMIT - _COL_LABEL_X) / _AVG_GLYPH_W)):
            lines.append((_COL_LABEL_X, "F1", 9.0, _esc(chunk)))
    elif kind == "kv":
        for label, value in block[1]:
            v = _truncate(_fmt_value(value), max_chars=int((_RIGHT_LIMIT - _COL_VALUE_X) / _AVG_GLYPH_W))
            lines.append((_COL_LABEL_X, "F1", 9.0, _esc(_truncate(str(label), 40))))
            lines.append((_COL_VALUE_X, "F3", 9.0, _esc(v)))
    elif kind == "table":
        _, header, rows, widths = block
        lines.append((_COL_LABEL_X, "F2", 8.0, _esc(_table_row(header, widths))))
        for r in rows:
            lines.append((_COL_LABEL_X, "F3", 8.0, _esc(_table_row(r, widths))))
    return lines


def _table_row(cells: Sequence[str], widths: Sequence[int]) -> str:
    parts: List[str] = []
    for i, w in enumerate(widths):
        cell = cells[i] if i < len(cells) else ""
        parts.append(_truncate(cell, w).ljust(w))
    return " ".join(parts).rstrip()


def _wrap(text: str, max_chars: int) -> List[str]:
    """Word-wrap on spaces; single long tokens are hard-split (deterministic)."""
    out: List[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            candidate = (cur + " " + w).strip() if cur else w
            if len(candidate) <= max_chars:
                cur = candidate
            else:
                if cur:
                    out.append(cur)
                while len(w) > max_chars:
                    out.append(w[:max_chars])
                    w = w[max_chars:]
                cur = w
        if cur:
            out.append(cur)
    return out or [""]


def _page_stream(lines: List[Tuple[float, str, float, str]], title: str, page_no: int, page_count: int) -> bytes:
    """Assemble one page's content stream. Title/footer on every page."""
    ops: List[str] = []
    # header
    ops.append("BT /F2 12 Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET" % (_COL_LABEL_X, _MAX_Y, _esc(_truncate(title, 80))))
    ops.append("0.6 w 40 %.2f m %.2f %.2f l S" % (_MAX_Y - 8, _PAGE_W - _MARGIN, _MAX_Y - 8))
    y = _MAX_Y - 24.0
    for x, font, size, content in lines:
        y -= _LINE_H if size <= 9.0 else 14.0
        ops.append("BT /%s %.1f Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET" % (font, size, x, y, content))
    # footer with page numbers (page_count known by the caller)
    ops.append("BT /F1 8 Tf 1 0 0 1 %.2f %.2f Tm (Page %d of %d) Tj ET"
               % (_COL_LABEL_X, _BOTTOM_LIMIT - 12, page_no, page_count))
    ops.append("BT /F1 8 Tf 1 0 0 1 %.2f %.2f Tm (RADAR BOURSE - Strategy Lab - deterministic export) Tj ET"
               % (_COL_VALUE_X, _BOTTOM_LIMIT - 12))
    return ("\n".join(ops)).encode("latin-1", errors="replace")


def render_report_pdf(title: str, blocks: Sequence[Block]) -> bytes:
    """Render blocks into a byte-deterministic PDF (A4, paginated)."""
    # 1) flatten blocks into layout lines, tracking page breaks
    pages: List[List[Tuple[float, str, float, str]]] = []
    current: List[Tuple[float, str, float, str]] = []
    y = _MAX_Y - 24.0
    for block in blocks:
        for line in _text_lines_for_block(block):
            needed = _LINE_H if line[2] <= 9.0 else 14.0
            if y - needed < _BOTTOM_LIMIT:
                pages.append(current)
                current = []
                y = _MAX_Y - 24.0
            current.append(line)
            y -= needed
    pages.append(current)
    if not pages[0]:
        pages = pages[1:] or [[]]
    page_count = len(pages)

    # 2) assemble objects (fixed Info dates; no /ID; uncompressed streams)
    info = b"<< /Producer (RADAR BOURSE report_pdf) /CreationDate (D:20000101000000Z) /ModDate (D:20000101000000Z) /Title () >>"
    catalog_num = 1
    info_num = 3
    first_page_obj = 4
    objects: List[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(page_count))
    objects.append(f"<< /Type /Pages /Count {page_count} /Kids [{kids}] >>".encode())
    objects.append(info)
    for i, lines in enumerate(pages):
        stream = _page_stream(lines, title, i + 1, page_count)
        objects.append(b"<< /Type /Page >>")  # placeholder; rewritten below with real refs
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    # shared font objects (after page/content objects): numbers are derived
    # from the object layout and embedded into every page's resource dict.
    font_f1 = first_page_obj + 2 * page_count
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    # Rewrite the page objects' resource references with the real font numbers.
    page_obj_num = first_page_obj
    for i in range(page_count):
        objects[3 + 2 * i] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] "
            f"/Resources << /Font << /F1 {font_f1} 0 R /F2 {font_f1 + 1} 0 R /F3 {font_f1 + 2} 0 R >> >> "
            f"/Contents {page_obj_num + 1} 0 R >>".encode()
        )
        page_obj_num += 2

    # 3) serialize with exact xref offsets
    out = bytearray()
    out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets: List[int] = [0] * (len(objects) + 1)
    for idx, obj in enumerate(objects, start=1):
        offsets[idx] = len(out)
        out += f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for i in range(1, len(objects) + 1):
        out += ("%010d 00000 n \n" % offsets[i]).encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_num} 0 R /Info {info_num} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)
