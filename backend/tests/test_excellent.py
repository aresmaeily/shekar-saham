"""Tests for v0.7.0 excellent features"""
from app.engines.data_quality import quality_scorer
from app.engines.anomaly import anomaly_detector
from app.engines.ai_explainer import explainer
from app.engines.risk_manager import risk_manager
from app.models.schemas import SymbolSnapshot

def test_data_quality_scorer():
    s = SymbolSnapshot(l18="فملی", l30="ملی مس", pl=1000, pc=990, py=980, tvol=1e6, Buy_I_Volume=5e5, Sell_I_Volume=3e5, Buy_CountI=10, Sell_CountI=5)
    result = quality_scorer.score_symbol(s)
    assert "score" in result
    assert 0 <= result["score"] <= 100
    assert "trust" in result

def test_data_quality_batch():
    s1 = SymbolSnapshot(l18="فملی", pl=1000, pc=990, py=980, tvol=1e6, Buy_I_Volume=5e5, Sell_I_Volume=3e5, Buy_CountI=10, Sell_CountI=5)
    s2 = SymbolSnapshot(l18="فولاد", pl=500, pc=490, py=480, tvol=2e6, Buy_I_Volume=1e6, Sell_I_Volume=0.5e6, Buy_CountI=20, Sell_CountI=10)
    batch = quality_scorer.score_batch([s1, s2])
    assert batch["total"] == 2
    assert "avg_score" in batch

def test_anomaly_detector_price_jump():
    s = SymbolSnapshot(l18="فملی", pl=1100, pc=1000, py=990, tvol=1e6)
    prev = {"pl": 1000}
    res = anomaly_detector.detect_price_jump(s, prev)
    assert "anomaly" in res
    # 10% jump should be anomaly
    assert res["anomaly"] == True
    assert res["type"] == "price_jump"

def test_anomaly_no_jump():
    s = SymbolSnapshot(l18="فملی", pl=1010, pc=1000, py=990, tvol=1e6)
    prev = {"pl": 1000}
    res = anomaly_detector.detect_price_jump(s, prev)
    assert res["anomaly"] == False

def test_ai_explainer():
    s = SymbolSnapshot(l18="فملی", l30="ملی مس", pl=1000, pc=1000, py=1000, plp=-2.5, tvol=1e6)
    class M:
        buy_power = 2.1
        volume_ratio = 3.0
        individual_net_value = 6e9
        entry_score = 80
        exit_score = 20
    class TC:
        golden_number = 75
        d_plus = 65
    exp = explainer.explain_entry(s, M(), TC())
    assert isinstance(exp, str)
    assert len(exp) > 20
    assert "قدرت خریدار" in exp or "حجم" in exp

def test_risk_position_size():
    res = risk_manager.calculate_position_size(portfolio_value=100_000_000, entry_price=1000, stop_loss_price=970, risk_per_trade_pct=1.0)
    assert "shares" in res
    assert res["shares"] > 0
    assert res["risk_pct"] == 1.0

def test_risk_stop_loss():
    res = risk_manager.suggest_stop_loss(entry=1000, atr=20, support=950)
    assert "conservative_3pct" in res
    assert res["conservative_3pct"] == 970

def test_event_bus():
    from app.domain.events import event_bus, DomainEvent
    import asyncio
    async def test():
        event = DomainEvent("test_event", {"symbol": "فملی"})
        await event_bus.publish(event)
        history = event_bus.get_history("test_event", limit=5)
        assert len(history) >= 1
    asyncio.run(test())

def test_metrics():
    from app.core.metrics_prom import metrics
    metrics.inc("test_counter", {"path": "/api/test"})
    metrics.set_gauge("test_gauge", 42.5)
    metrics.observe("test_hist", 0.123)
    prom = metrics.to_prometheus()
    assert "test_counter" in prom
    assert "test_gauge" in prom
