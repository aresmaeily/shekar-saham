import pytest
from app.engines.metrics import compute_metrics
from app.models.schemas import SymbolSnapshot

def test_compute_metrics_finite():
    s = SymbolSnapshot(l18="فملی", l30="ملی مس", pl=1000, pc=990, py=980, tvol=1e6, tval=1e9, Buy_I_Volume=5e5, Sell_I_Volume=3e5, Buy_CountI=10, Sell_CountI=5)
    from app.core.config import get_settings
    m = compute_metrics(s, get_settings())
    assert 0 <= m.entry_score <= 100
    assert 0 <= m.exit_score <= 100
    assert m.buy_power is not None

def test_flow_coverage():
    from app.engines.big_moves import flow_coverage_sec
    from app.data.store import Store
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mktemp())
    store = Store(tmp)
    # empty should be 0
    assert flow_coverage_sec(store) == 0.0
    tmp.unlink(missing_ok=True)

def test_filter_injection_blocked():
    from app.engines.filter_dsl import eval_filter
    import pytest
    with pytest.raises(Exception):
        eval_filter("__import__('os').system('id')", {"buy_power": 1})
    with pytest.raises(Exception):
        eval_filter("eval('1+1')", {"buy_power": 1})
