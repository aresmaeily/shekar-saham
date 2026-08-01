"""ماژول اختیار معامله — Black-Scholes + پیشنهاد استراتژی + زنجیره مصنوعی TSE-like."""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any
from app.models.schemas import SymbolSnapshot


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes(
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    vol: float,
    option_type: str = "call",
) -> dict[str, float]:
    spot = max(float(spot), 1e-9)
    strike = max(float(strike), 1e-9)
    t_years = max(float(t_years), 1e-6)
    vol = max(float(vol), 1e-6)
    rate = float(rate)
    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * t_years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    if option_type == "put":
        price = strike * math.exp(-rate * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
    else:
        price = spot * _norm_cdf(d1) - strike * math.exp(-rate * t_years) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
    gamma = _norm_pdf(d1) / (spot * vol * sqrt_t)
    vega = spot * _norm_pdf(d1) * sqrt_t / 100.0  # per 1% vol
    theta_call = (
        -spot * _norm_pdf(d1) * vol / (2 * sqrt_t)
        - rate * strike * math.exp(-rate * t_years) * _norm_cdf(d2)
    ) / 365.0
    theta_put = (
        -spot * _norm_pdf(d1) * vol / (2 * sqrt_t)
        + rate * strike * math.exp(-rate * t_years) * _norm_cdf(-d2)
    ) / 365.0
    theta = theta_put if option_type == "put" else theta_call
    rho = (
        strike * t_years * math.exp(-rate * t_years) * (_norm_cdf(d2) if option_type == "call" else -_norm_cdf(-d2))
    ) / 100.0
    intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
    return {
        "price": round(max(price, 0.0), 2),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "vega": round(vega, 4),
        "theta": round(theta, 4),
        "rho": round(rho, 4),
        "intrinsic": round(intrinsic, 2),
        "time_value": round(max(price, 0) - intrinsic, 2),
        "d1": round(d1, 4),
        "d2": round(d2, 4),
    }


def implied_move(spot: float, vol: float, days: float) -> float:
    return spot * vol * math.sqrt(max(days, 1) / 365.0)


@dataclass
class StrategyLeg:
    side: str  # buy/sell
    option_type: str  # call/put
    strike: float
    premium: float
    qty: int = 1


def strategy_payoff(legs: list[StrategyLeg], spots: list[float]) -> list[dict[str, float]]:
    out = []
    for s in spots:
        pnl = 0.0
        for leg in legs:
            if leg.option_type == "call":
                val = max(0.0, s - leg.strike)
            else:
                val = max(0.0, leg.strike - s)
            sign = 1 if leg.side == "buy" else -1
            pnl += sign * (val - leg.premium) * leg.qty
        out.append({"spot": round(s, 2), "pnl": round(pnl, 2)})
    return out


def build_chain_for_symbol(s: SymbolSnapshot, rate: float = 0.25, base_vol: float = 0.35) -> dict[str, Any]:
    r = random.Random(int(hashlib.md5(s.l18.encode()).hexdigest()[:8], 16))
    spot = float(s.pl or 1000)
    # vol from recent range proxy
    if s.pmax and s.pmin and s.pl:
        rng = (s.pmax - s.pmin) / max(s.pl, 1)
        vol = min(0.9, max(0.18, base_vol + rng * 2 + r.uniform(-0.05, 0.05)))
    else:
        vol = base_vol
    expiries = []
    today = date.today()
    for days in (14, 30, 60):
        exp = today + timedelta(days=days)
        t = days / 365.0
        strikes = []
        for k in range(-4, 5):
            strike = round(spot * (1 + k * 0.03) / 10) * 10
            call = black_scholes(spot, strike, t, rate, vol, "call")
            put = black_scholes(spot, strike, t, rate, vol, "put")
            # add slight market premium noise
            call["market"] = round(call["price"] * r.uniform(0.95, 1.08), 2)
            put["market"] = round(put["price"] * r.uniform(0.95, 1.08), 2)
            call["oi"] = int(r.uniform(50, 5000))
            put["oi"] = int(r.uniform(50, 5000))
            call["volume"] = int(r.uniform(0, 800))
            put["volume"] = int(r.uniform(0, 800))
            strikes.append(
                {
                    "strike": strike,
                    "moneyness": round(strike / spot, 3),
                    "call": call,
                    "put": put,
                }
            )
        expiries.append(
            {
                "expiry": exp.isoformat(),
                "days": days,
                "t_years": round(t, 4),
                "strikes": strikes,
            }
        )
    return {
        "symbol": s.l18,
        "name": s.l30,
        "spot": spot,
        "plp": s.plp,
        "vol": round(vol, 3),
        "rate": rate,
        "implied_move_30d": round(implied_move(spot, vol, 30), 2),
        "expiries": expiries,
        "source": "synthetic_bs",
    }


def recommend_strategies(
    s: SymbolSnapshot,
    entry_score: float = 50,
    exit_score: float = 20,
    vol: float = 0.35,
) -> list[dict[str, Any]]:
    spot = float(s.pl or 1000)
    rate = 0.25
    t = 30 / 365.0
    atm = round(spot / 10) * 10
    otm_call = round(spot * 1.05 / 10) * 10
    otm_put = round(spot * 0.95 / 10) * 10
    c_atm = black_scholes(spot, atm, t, rate, vol, "call")
    c_otm = black_scholes(spot, otm_call, t, rate, vol, "call")
    p_otm = black_scholes(spot, otm_put, t, rate, vol, "put")

    recs: list[dict[str, Any]] = []
    # bullish
    if entry_score >= 65 or (s.plp is not None and s.plp < 0 and entry_score >= 50):
        legs = [StrategyLeg("buy", "call", otm_call, c_otm["price"])]
        spots = [spot * x / 100 for x in range(80, 126, 2)]
        recs.append(
            {
                "id": "long_call",
                "name": "خرید کال OTM",
                "bias": "bullish",
                "score": round(min(100, entry_score), 1),
                "summary": "مناسب دید صعودی با ریسک محدود به پرمیوم",
                "max_loss": c_otm["price"],
                "breakeven": otm_call + c_otm["price"],
                "legs": [asdict(l) for l in legs],
                "payoff": strategy_payoff(legs, spots),
            }
        )
        # bull call spread
        legs2 = [
            StrategyLeg("buy", "call", atm, c_atm["price"]),
            StrategyLeg("sell", "call", otm_call, c_otm["price"]),
        ]
        debit = c_atm["price"] - c_otm["price"]
        recs.append(
            {
                "id": "bull_call_spread",
                "name": "اسپرد کال صعودی",
                "bias": "bullish",
                "score": round(min(100, entry_score - 5), 1),
                "summary": "صعودی با هزینه کمتر از long call",
                "max_loss": max(debit, 0),
                "max_profit": max((otm_call - atm) - debit, 0),
                "breakeven": atm + debit,
                "legs": [asdict(l) for l in legs2],
                "payoff": strategy_payoff(legs2, spots),
            }
        )
    # bearish / hedge
    if exit_score >= 55 or entry_score < 40:
        legs = [StrategyLeg("buy", "put", otm_put, p_otm["price"])]
        spots = [spot * x / 100 for x in range(75, 121, 2)]
        recs.append(
            {
                "id": "long_put",
                "name": "خرید پوت OTM",
                "bias": "bearish",
                "score": round(min(100, max(exit_score, 50)), 1),
                "summary": "محافظت یا دید نزولی",
                "max_loss": p_otm["price"],
                "breakeven": otm_put - p_otm["price"],
                "legs": [asdict(l) for l in legs],
                "payoff": strategy_payoff(legs, spots),
            }
        )
    # neutral
    legs_strangle = [
        StrategyLeg("sell", "call", otm_call, c_otm["price"]),
        StrategyLeg("sell", "put", otm_put, p_otm["price"]),
    ]
    credit = c_otm["price"] + p_otm["price"]
    spots = [spot * x / 100 for x in range(80, 126, 2)]
    if 40 <= entry_score <= 70 and exit_score < 55:
        recs.append(
            {
                "id": "short_strangle",
                "name": "شورت استرنگل (خنثی)",
                "bias": "neutral",
                "score": 55,
                "summary": "سود از بی‌نوسانی — ریسک نامحدود؛ فقط آموزشی",
                "max_profit": credit,
                "legs": [asdict(l) for l in legs_strangle],
                "payoff": strategy_payoff(legs_strangle, spots),
            }
        )
    # covered call educational
    legs_cc = [StrategyLeg("sell", "call", otm_call, c_otm["price"])]
    recs.append(
        {
            "id": "covered_call",
            "name": "کاورلد کال (روی دارایی)",
            "bias": "mild_bullish",
            "score": 60 if entry_score >= 50 else 45,
            "summary": "اگر سهام دارید؛ درآمد از پرمیوم با سقف سود",
            "premium_income": c_otm["price"],
            "legs": [asdict(l) for l in legs_cc],
            "payoff": strategy_payoff(legs_cc, spots),
            "note": "نیاز به مالکیت سهم پایه",
        }
    )
    recs.sort(key=lambda x: x.get("score", 0), reverse=True)
    return recs


def price_custom(
    spot: float,
    strike: float,
    days: float,
    vol: float,
    rate: float,
    option_type: str,
    side: str = "buy",
) -> dict[str, Any]:
    t = max(days, 1) / 365.0
    greeks = black_scholes(spot, strike, t, rate, vol, option_type)
    spots = [spot * x / 100 for x in range(70, 131, 2)]
    leg = StrategyLeg(side, option_type, strike, greeks["price"])
    return {
        "inputs": {
            "spot": spot,
            "strike": strike,
            "days": days,
            "vol": vol,
            "rate": rate,
            "option_type": option_type,
            "side": side,
        },
        "greeks": greeks,
        "payoff": strategy_payoff([leg], spots),
        "implied_move": round(implied_move(spot, vol, days), 2),
    }
