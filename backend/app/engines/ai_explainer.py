"""
ai_explainer.py - v0.7.0 Excellent - Creative: AI-powered signal explanation
"""
from __future__ import annotations

from typing import Any
from app.models.schemas import SymbolSnapshot

class AISignalExplainer:
    """
    Creative: Instead of just score, explain in natural language why buy/sell
    Uses rule-based LLM-like explanation (no external API needed)
    """
    
    def explain_entry(self, snapshot: SymbolSnapshot, metrics: Any, tablocastic: Any, fundamental: Any = None) -> str:
        reasons = []
        
        # Technical
        if getattr(metrics, 'buy_power', 0) >= 2.0:
            reasons.append(f"قدرت خریدار بسیار قوی ({metrics.buy_power:.1f} برابر) نشان از ورود پول هوشمند دارد")
        elif getattr(metrics, 'buy_power', 0) >= 1.5:
            reasons.append(f"قدرت خریدار مناسب ({metrics.buy_power:.1f}) - خریداران بر فروشندگان غالب‌اند")
        
        if getattr(metrics, 'volume_ratio', 0) >= 2.5:
            reasons.append(f"حجم معاملات {metrics.volume_ratio:.1f} برابر میانگین - توجه بازار جلب شده")
        
        if getattr(metrics, 'individual_net_value', 0) > 5e9:
            reasons.append(f"ورود پول حقیقی {metrics.individual_net_value/1e9:.1f} میلیارد تومان - علامت مثبت")
        
        # Price action
        if getattr(snapshot, 'plp', 0) < -2:
            reasons.append(f"قیمت در محدوده منفی {snapshot.plp:.1f}% - فرصت خرید در کف")
        elif getattr(snapshot, 'plp', 0) < 0:
            reasons.append(f"قیمت کمی منفی {snapshot.plp:.1f}% - نزدیک به حمایت")
        
        # Tablocastic
        if getattr(tablocastic, 'golden_number', 0) >= 70:
            reasons.append(f"عدد طلایی {tablocastic.golden_number:.0f} - ترکیب عالی تابلو")
        
        if getattr(tablocastic, 'd_plus', 0) >= 60:
            reasons.append(f"D+ {tablocastic.d_plus:.0f} - تقاضای قوی")
        
        # Fundamental
        if fundamental and getattr(fundamental, 'value_score', 0) >= 70:
            reasons.append(f"بنیادی ارزنده با امتیاز {fundamental.value_score:.0f} - P/E مناسب و ROE خوب")
        
        if not reasons:
            reasons.append("سیگنال ورود بر اساس ترکیب امتیازات تابلو و بنیادی")
        
        # Combine into paragraph
        explanation = " ".join(reasons[:3]) + "."
        
        # Risk note
        explanation += " ⚠️ این تحلیل مبتنی بر تابلوخوانی است و تضمین سود نیست - حد ضرر را رعایت کنید."
        
        return explanation
    
    def explain_exit(self, snapshot: SymbolSnapshot, metrics: Any) -> str:
        reasons = []
        if getattr(metrics, 'exit_score', 0) >= 70:
            reasons.append(f"امتیاز خروج بالا ({metrics.exit_score:.0f}) - فشار فروش دیده می‌شود")
        if getattr(snapshot, 'plp', 0) > 3:
            reasons.append(f"رشد {snapshot.plp:.1f}% و احتمال شناسایی سود توسط بزرگان")
        if getattr(metrics, 'buy_power', 0) < 0.8:
            reasons.append(f"قدرت خریدار ضعیف ({metrics.buy_power:.1f}) - فروشندگان قوی‌تر")
        
        if not reasons:
            reasons.append("سیگنال خروج بر اساس خروج پول و تضعیف تقاضا")
        
        return " ".join(reasons) + ". مراقب حد ضرر باشید."

explainer = AISignalExplainer()
