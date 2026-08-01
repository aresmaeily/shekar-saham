"""
risk_manager.py - v0.7.0 Excellent - Creative: Risk management & position sizing
"""
from __future__ import annotations

from typing import Any, Dict
import math

class RiskManager:
    def calculate_position_size(self, portfolio_value: float, entry_price: float, stop_loss_price: float, risk_per_trade_pct: float = 1.0) -> Dict[str, Any]:
        """
        Position sizing based on risk management - Kelly Criterion inspired
        """
        if entry_price <= 0 or stop_loss_price <= 0 or portfolio_value <=0:
            return {"error": "Invalid prices"}
        
        risk_amount = portfolio_value * (risk_per_trade_pct / 100)
        loss_per_share = abs(entry_price - stop_loss_price)
        if loss_per_share == 0:
            return {"error": "Stop loss same as entry"}
        
        shares = math.floor(risk_amount / loss_per_share)
        position_value = shares * entry_price
        position_pct = (position_value / portfolio_value * 100) if portfolio_value else 0
        
        return {
            "shares": shares,
            "position_value": position_value,
            "position_pct": round(position_pct, 2),
            "risk_amount": risk_amount,
            "risk_pct": risk_per_trade_pct,
            "reward_risk_hint": "برای نسبت RR 2:1، حد سود را 2 برابر فاصله حد ضرر قرار دهید"
        }
    
    def calculate_var(self, returns: list[float], confidence: float = 0.95, portfolio_value: float = 100_000_000) -> Dict[str, Any]:
        """
        Value at Risk - simple historical
        """
        if not returns:
            return {"var": 0, "message": "No returns history"}
        sorted_ret = sorted(returns)
        index = int((1-confidence) * len(sorted_ret))
        var_return = sorted_ret[index] if index < len(sorted_ret) else sorted_ret[0]
        var_value = portfolio_value * abs(var_return) / 100
        
        return {
            "var_pct": round(abs(var_return), 2),
            "var_value": round(var_value, 2),
            "confidence": confidence,
            "message": f"با اطمینان {confidence*100}% حداکثر زیان {abs(var_return):.2f}% در یک دوره"
        }
    
    def suggest_stop_loss(self, entry: float, atr: float = None, support: float = None) -> Dict[str, Any]:
        suggestions = {}
        if atr:
            suggestions["atr_based"] = round(entry - atr * 1.5, 2)
        if support:
            suggestions["support_based"] = round(support * 0.98, 2)
        # Fixed %: 3% for conservative, 5% for aggressive
        suggestions["conservative_3pct"] = round(entry * 0.97, 2)
        suggestions["moderate_5pct"] = round(entry * 0.95, 2)
        return suggestions

risk_manager = RiskManager()
