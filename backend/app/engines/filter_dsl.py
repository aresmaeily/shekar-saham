"""موتور فیلترنویسی ساده — شبیه فیلدهای tsetmc با عملگرهای منطقی.

مثال:
  buy_power >= 2 and volume_ratio >= 2 and plp <= 0 and pe > 0 and pe <= 12
  entry_score >= 65 and (hot_net > 20 or big_player_bias > 0.3)
  industry contains فلز and tval >= 1e10
"""

from __future__ import annotations

import ast
import re
from typing import Any

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

PRESETS: list[dict[str, str]] = [
    {
        "id": "smart_neg",
        "name": "شکار منفی + پول هوشمند",
        "expr": "plp <= 0 and buy_power >= 1.8 and volume_ratio >= 2 and entry_score >= 60",
    },
    {
        "id": "hot_buy",
        "name": "پول داغ خرید",
        "expr": "hot_net >= 25 and buy_per_capita >= 100000000 and volume_ratio >= 1.5",
    },
    {
        "id": "fund_value",
        "name": "بنیادی ارزنده",
        "expr": "pe > 0 and pe <= 10 and fund_score >= 60 and entry_score >= 50",
    },
    {
        "id": "near_queue",
        "name": "نزدیک صف خرید",
        "expr": "near_buy_queue == 1 and buy_power >= 1.5 and individual_net_value > 0",
    },
    {
        "id": "exit_risk",
        "name": "ریسک خروج",
        "expr": "exit_score >= 60 and (hot_net < 0 or buy_power < 0.8)",
    },
    {
        "id": "golden_a",
        "name": "تابلو کستیک A",
        "expr": "golden_number >= 70 and quality_score >= 70 and d_plus >= 50",
    },
    {
        "id": "legal_to_real",
        "name": "حقوقی به حقیقی",
        "expr": "legal_to_individual > 0 and buy_power >= 1.5 and volume_ratio >= 1.5",
    },
    {
        "id": "big_inflow",
        "name": "ورود بزرگان",
        "expr": "big_player_bias >= 0.4 and individual_net_value > 0 and volume_ratio >= 1.3",
    },
]


class FilterError(ValueError):
    pass


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
            # contains(field, 'text') or field.contains — only contains(x,y)
            if isinstance(node.func, ast.Name) and node.func.id == "contains":
                if len(node.args) != 2:
                    raise FilterError("contains(field, text)")
                a = str(self.visit(node.args[0]))
                b = str(self.visit(node.args[1]))
                return b in a
            raise FilterError("تابع غیرمجاز")
        if isinstance(node, ast.Name):
            if node.id not in self.ctx and node.id not in ALLOWED_FIELDS:
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


def compile_filter(expr: str) -> ast.Expression:
    e = normalize_expr(expr)
    try:
        tree = ast.parse(e, mode="eval")
    except SyntaxError as exc:
        raise FilterError(f"خطای نحوی: {exc.msg}") from exc
    return tree  # type: ignore[return-value]


def eval_filter(expr: str, row: dict[str, Any]) -> bool:
    tree = compile_filter(expr)
    ctx = {k: row.get(k) for k in ALLOWED_FIELDS}
    # bools as 0/1 also keep original
    for k, v in list(ctx.items()):
        if isinstance(v, bool):
            ctx[k] = 1 if v else 0
    try:
        return bool(_SafeEval(ctx).visit(tree))
    except FilterError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FilterError(str(exc)) from exc


def run_filter(expr: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        try:
            if eval_filter(expr, r):
                out.append(r)
        except FilterError:
            raise
    return out


def fields_help() -> list[dict[str, str]]:
    return [{"key": k, "label": v} for k, v in ALLOWED_FIELDS.items()]
