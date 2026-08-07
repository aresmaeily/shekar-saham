"""Safe Filter DSL for Iran market screening.

The DSL is intentionally declarative and limited. It never uses Python
``eval``/``exec`` and it does not allow arbitrary imports, attributes,
subscripts, filesystem, network or shell access.

Examples:
  buy_power >= 2 and volume_ratio >= 2 and plp <= 0
  entry_score >= 65 and (hot_net > 20 or big_player_bias > 0.3)
  industry contains فلز and tval >= 1e10
  close > sma(20) and rsi(14) < 35
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Literal

# فیلدهای مجاز در DSL
ALLOWED_FIELDS: dict[str, str] = {
    # snapshot
    "pl": "آخرین قیمت",
    "plp": "درصد آخرین",
    "pc": "پایانی",
    "pcp": "درصد پایانی",
    "tvol": "حجم",
    "tval": "ارزش معاملات",
    "tno": "تعداد معاملات",
    "pe": "P/E",
    "eps": "EPS",
    "mv": "ارزش بازار",
    "bvol": "حجم مبنا",
    "py": "دیروز",
    "tmax": "سقف مجاز",
    "tmin": "کف مجاز",
    "qd1": "حجم بهترین خرید",
    "qo1": "حجم بهترین فروش",
    "pd1": "قیمت بهترین خرید",
    "po1": "قیمت بهترین فروش",
    "Buy_I_Volume": "حجم خرید حقیقی",
    "Sell_I_Volume": "حجم فروش حقیقی",
    "Buy_N_Volume": "حجم خرید حقوقی",
    "Sell_N_Volume": "حجم فروش حقوقی",
    "Buy_CountI": "تعداد خریدار حقیقی",
    "Sell_CountI": "تعداد فروشنده حقیقی",
    # common aliases / indicator-ready references
    "close": "آخرین قیمت (alias)",
    "price": "قیمت (alias)",
    "volume": "حجم (alias)",
    "avg_volume": "میانگین حجم",
    "rsi": "RSI فعلی/آخرین",
    # metrics
    "buy_power": "قدرت خریدار",
    "buy_per_capita": "سرانه خرید",
    "sell_per_capita": "سرانه فروش",
    "volume_ratio": "نسبت حجم",
    "value_ratio": "نسبت ارزش",
    "individual_net_value": "خالص حقیقی",
    "individual_net_volume": "خالص حجم حقیقی",
    "legal_to_individual": "حقوقی به حقیقی",
    "hot_net": "برآیند پول داغ",
    "hot_buy_score": "امتیاز خرید داغ",
    "hot_sell_score": "امتیاز فروش داغ",
    "entry_score": "امتیاز ورود",
    "exit_score": "امتیاز خروج",
    "watch_score": "امتیاز رصد",
    "big_player_bias": "بایاس بزرگان",
    "mid_player_bias": "بایاس متوسط",
    "retail_bias": "بایاس خرد",
    "pe_score": "امتیاز P/E",
    "dist_to_ceiling_pct": "فاصله تا سقف٪",
    "dist_to_floor_pct": "فاصله تا کف٪",
    # tablocastic
    "d_plus": "D+",
    "m_plus": "M+",
    "m_over_d": "M/D",
    "golden_number": "عدد طلایی",
    "quality_score": "کیفیت تابلو",
    "queue_power": "قدرت صف",
    "demand_pressure": "فشار تقاضا",
    "supply_pressure": "فشار عرضه",
    "smart_flow": "جریان هوشمند",
    # fundamental
    "fund_score": "امتیاز بنیادی",
    "roe": "ROE",
    "roa": "ROA",
    "profit_growth": "رشد سود٪",
    "revenue_growth": "رشد فروش٪",
    "debt_ratio": "نسبت بدهی",
    # bools as 0/1
    "is_volume_spike": "حجم مشکوک",
    "is_strong_volume_spike": "حجم خیلی مشکوک",
    "near_buy_queue": "نزدیک صف خرید",
    "near_sell_queue": "نزدیک صف فروش",
    "in_buy_queue": "صف خرید",
    "in_sell_queue": "صف فروش",
    "fundamental_ok": "بنیادی خوب",
    "hour_pattern": "الگوی ساعت",
    # string helpers via special ops
    "industry": "صنعت",
    "symbol": "نماد",
    "name": "نام",
    "grade": "درجه",
    "side": "سمت سیگنال",
}

FIELD_ALIASES: dict[str, str] = {
    "close": "pl",
    "price": "pl",
    "volume": "tvol",
    "avg_volume": "avg_vol_30d",
}

ALLOWED_FUNCTIONS: dict[str, str] = {
    "contains": "contains(field, text) string containment",
    "sma": "sma(period) reads sma_<period>, ma<period>, ma_<period>",
    "avg_volume": "avg_volume(period) reads avg_volume_<period>, avg_vol_<period>, avg_vol_30d",
    "rsi": "rsi(period) reads rsi_<period> or rsi",
    "high": "high(period) reads high_<period> or pmax",
    "low": "low(period) reads low_<period> or pmin",
}

PRESETS: list[dict[str, str]] = [
    {"id": "smart_neg", "name": "شکار منفی + پول هوشمند", "expr": "plp <= 0 and buy_power >= 1.8 and volume_ratio >= 2 and entry_score >= 60"},
    {"id": "hot_buy", "name": "پول داغ خرید", "expr": "hot_net >= 25 and buy_per_capita >= 100000000 and volume_ratio >= 1.5"},
    {"id": "fund_value", "name": "بنیادی ارزنده", "expr": "pe > 0 and pe <= 10 and fund_score >= 60 and entry_score >= 50"},
    {"id": "near_queue", "name": "نزدیک صف خرید", "expr": "near_buy_queue == 1 and buy_power >= 1.5 and individual_net_value > 0"},
    {"id": "exit_risk", "name": "ریسک خروج", "expr": "exit_score >= 60 and (hot_net < 0 or buy_power < 0.8)"},
    {"id": "golden_a", "name": "تابلو کستیک A", "expr": "golden_number >= 70 and quality_score >= 70 and d_plus >= 50"},
    {"id": "legal_to_real", "name": "حقوقی به حقیقی", "expr": "legal_to_individual > 0 and buy_power >= 1.5 and volume_ratio >= 1.5"},
    {"id": "big_inflow", "name": "ورود بزرگان", "expr": "big_player_bias >= 0.4 and individual_net_value > 0 and volume_ratio >= 1.3"},
]

MAX_EXPR_LEN = 1000
MAX_AST_NODES = 160
MAX_AST_DEPTH = 24

NodeKind = Literal["bool", "compare", "field", "constant", "call", "arithmetic", "not"]


class FilterError(ValueError):
    pass


@dataclass(frozen=True)
class FilterExpression:
    """Compiled safe Filter DSL expression."""

    raw: str
    normalized: str
    tree: ast.Expression
    fields: tuple[str, ...] = field(default_factory=tuple)
    functions: tuple[str, ...] = field(default_factory=tuple)
    node_count: int = 0


@dataclass(frozen=True)
class ExpressionNode:
    """Lightweight expression model for diagnostics and future AI/strategy consumers."""

    kind: NodeKind
    value: str
    children: tuple["ExpressionNode", ...] = ()


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def normalize_expr(expr: str) -> str:
    e = (expr or "").strip()
    if not e:
        raise FilterError("عبارت خالی است")
    if len(e) > MAX_EXPR_LEN:
        raise FilterError("عبارت بیش از حد طولانی است")
    # Persian/Arabic digits
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    e = e.translate(trans)
    # aliases
    e = re.sub(r"\bAND\b", "and", e, flags=re.I)
    e = re.sub(r"\bOR\b", "or", e, flags=re.I)
    e = re.sub(r"\bNOT\b", "not", e, flags=re.I)
    e = e.replace("&&", " and ").replace("||", " or ")
    # contains sugar: industry contains 'x' -> contains(industry, 'x')
    e = re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s+contains\s+('([^']*)'|\"([^\"]*)\"|([^\s\)]+))",
        lambda m: f"contains({m.group(1)}, '{m.group(3) or m.group(4) or m.group(5)}')",
        e,
        flags=re.I,
    )
    return e


def _depth(node: ast.AST) -> int:
    children = list(ast.iter_child_nodes(node))
    if not children:
        return 1
    return 1 + max(_depth(c) for c in children)


def _literal_period(node: ast.AST) -> int:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, (int, float)):
        raise FilterError("پارامتر اندیکاتور باید عدد ثابت باشد")
    period = int(node.value)
    if period <= 0 or period > 300:
        raise FilterError("دوره اندیکاتور خارج از محدوده مجاز است")
    return period


def _collect_and_validate(tree: ast.Expression) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise FilterError("عبارت بیش از حد پیچیده است")
    if _depth(tree) > MAX_AST_DEPTH:
        raise FilterError("عمق عبارت بیش از حد مجاز است")

    fields: set[str] = set()
    functions: set[str] = set()

    for node in nodes:
        if isinstance(node, (ast.Expression, ast.Load, ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Add, ast.Sub, ast.Mult, ast.Div)):
            continue
        if isinstance(node, (ast.BoolOp, ast.UnaryOp, ast.Compare, ast.BinOp, ast.Constant)):
            continue
        if isinstance(node, ast.Name):
            if node.id in ALLOWED_FUNCTIONS:
                continue
            if node.id not in ALLOWED_FIELDS:
                raise FilterError(f"فیلد ناشناخته: {str(node.id)[:60]}")
            fields.add(node.id)
            continue
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FilterError("تابع غیرمجاز")
            name = node.func.id
            if name not in ALLOWED_FUNCTIONS:
                raise FilterError(f"تابع غیرمجاز: {name[:60]}")
            if node.keywords:
                raise FilterError("پارامتر نام‌دار در DSL مجاز نیست")
            if name == "contains":
                if len(node.args) != 2:
                    raise FilterError("contains(field, text)")
            else:
                if len(node.args) != 1:
                    raise FilterError(f"{name}(period)")
                _literal_period(node.args[0])
            functions.add(name)
            continue
        raise FilterError(f"عبارت غیرمجاز: {type(node).__name__}")

    return tuple(sorted(fields)), tuple(sorted(functions)), len(nodes)


def parse_filter(expr: str) -> FilterExpression:
    normalized = normalize_expr(expr)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise FilterError(f"خطای نحوی: {exc.msg}") from exc
    fields, functions, node_count = _collect_and_validate(tree)  # validate before execution
    return FilterExpression(raw=expr, normalized=normalized, tree=tree, fields=fields, functions=functions, node_count=node_count)


def compile_filter(expr: str) -> ast.Expression:
    """Backward-compatible compile API returning a validated Python AST expression."""
    return parse_filter(expr).tree


def validate_filter(expr: str) -> dict[str, Any]:
    compiled = parse_filter(expr)
    return {
        "ok": True,
        "raw": compiled.raw,
        "normalized": compiled.normalized,
        "fields": list(compiled.fields),
        "functions": list(compiled.functions),
        "node_count": compiled.node_count,
    }


def _indicator_value(name: str, period: int, ctx: dict[str, Any]) -> Any:
    if name == "sma":
        for key in (f"sma_{period}", f"ma{period}", f"ma_{period}"):
            if key in ctx:
                return ctx.get(key)
        return ctx.get("pl")
    if name == "avg_volume":
        for key in (f"avg_volume_{period}", f"avg_vol_{period}", "avg_vol_30d"):
            if key in ctx:
                return ctx.get(key)
        return ctx.get("tvol")
    if name == "rsi":
        for key in (f"rsi_{period}", "rsi"):
            if key in ctx:
                return ctx.get(key)
        return 50.0
    if name == "high":
        for key in (f"high_{period}", "pmax", "tmax"):
            if key in ctx:
                return ctx.get(key)
        return ctx.get("pl")
    if name == "low":
        for key in (f"low_{period}", "pmin", "tmin"):
            if key in ctx:
                return ctx.get(key)
        return ctx.get("pl")
    raise FilterError(f"تابع غیرمجاز: {name}")


class _SafeEval(ast.NodeVisitor):
    """ارزیابی امن عبارت بولی."""

    def __init__(self, ctx: dict[str, Any]) -> None:
        self.ctx = ctx

    def visit(self, node):  # type: ignore[override]
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self.visit(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(self.visit(v) for v in node.values)
            raise FilterError("عملگر منطقی پشتیبانی نمی‌شود")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self.visit(node.operand)
        if isinstance(node, ast.Compare):
            left = self.visit(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self.visit(comp)
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Lt):
                    ok = _num(left) < _num(right)
                elif isinstance(op, ast.LtE):
                    ok = _num(left) <= _num(right)
                elif isinstance(op, ast.Gt):
                    ok = _num(left) > _num(right)
                elif isinstance(op, ast.GtE):
                    ok = _num(left) >= _num(right)
                elif isinstance(op, ast.In):
                    ok = str(right) in str(left)
                elif isinstance(op, ast.NotIn):
                    ok = str(right) not in str(left)
                else:
                    raise FilterError("عملگر مقایسه پشتیبانی نمی‌شود")
                if not ok:
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FilterError("تابع غیرمجاز")
            name = node.func.id
            if name == "contains":
                if len(node.args) != 2:
                    raise FilterError("contains(field, text)")
                a = str(self.visit(node.args[0]))
                b = str(self.visit(node.args[1]))
                return b in a
            if name in {"sma", "avg_volume", "rsi", "high", "low"}:
                return _indicator_value(name, _literal_period(node.args[0]), self.ctx)
            raise FilterError("تابع غیرمجاز")
        if isinstance(node, ast.Name):
            if node.id not in ALLOWED_FIELDS:
                raise FilterError(f"فیلد ناشناخته: {str(node.id)[:60]}")
            return self.ctx.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = _num(self.visit(node.left)), _num(self.visit(node.right))
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            return a / b if b else 0.0
        raise FilterError(f"عبارت غیرمجاز: {type(node).__name__}")


def _execution_context(row: dict[str, Any]) -> dict[str, Any]:
    ctx = {k: row.get(k) for k in ALLOWED_FIELDS}
    # keep indicator extension keys even if not in fields list, but never expose arbitrary objects
    for k, v in row.items():
        if re.match(r"^(sma|ma|avg_volume|avg_vol|rsi|high|low)_?\d+$", str(k)) or k in {"rsi", "avg_vol_30d"}:
            ctx[k] = v
    for alias, original in FIELD_ALIASES.items():
        if ctx.get(alias) is None:
            ctx[alias] = row.get(original)
    for k, v in list(ctx.items()):
        if isinstance(v, bool):
            ctx[k] = 1 if v else 0
    return ctx


def eval_filter(expr: str, row: dict[str, Any]) -> bool:
    compiled = parse_filter(expr)
    try:
        return bool(_SafeEval(_execution_context(row)).visit(compiled.tree))
    except FilterError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FilterError(str(exc)) from exc


def run_filter(expr: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compiled = parse_filter(expr)
    out = []
    for r in rows:
        try:
            if _SafeEval(_execution_context(r)).visit(compiled.tree):
                out.append(r)
        except FilterError:
            raise
    return out


def fields_help() -> list[dict[str, str]]:
    return [{"key": k, "label": v} for k, v in ALLOWED_FIELDS.items()]


def functions_help() -> list[dict[str, str]]:
    return [{"key": k, "description": v} for k, v in ALLOWED_FUNCTIONS.items()]


def expression_tree(expr: str) -> ExpressionNode:
    compiled = parse_filter(expr)

    def conv(node: ast.AST) -> ExpressionNode:
        if isinstance(node, ast.Expression):
            return conv(node.body)
        if isinstance(node, ast.BoolOp):
            op = "and" if isinstance(node.op, ast.And) else "or"
            return ExpressionNode("bool", op, tuple(conv(v) for v in node.values))
        if isinstance(node, ast.UnaryOp):
            return ExpressionNode("not", "not", (conv(node.operand),))
        if isinstance(node, ast.Compare):
            return ExpressionNode("compare", "compare", (conv(node.left),) + tuple(conv(c) for c in node.comparators))
        if isinstance(node, ast.BinOp):
            return ExpressionNode("arithmetic", type(node.op).__name__, (conv(node.left), conv(node.right)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return ExpressionNode("call", node.func.id, tuple(conv(a) for a in node.args))
        if isinstance(node, ast.Name):
            return ExpressionNode("field", node.id)
        if isinstance(node, ast.Constant):
            return ExpressionNode("constant", repr(node.value))
        raise FilterError(f"عبارت غیرمجاز: {type(node).__name__}")

    return conv(compiled.tree)
