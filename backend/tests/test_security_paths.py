"""
test_security_paths.py - تست رگرسیون مسیرهای عمومی/خصوصی
(P0: باگ startswith("/") که همه مسیرها را عمومی می‌کرد)
"""
from app.core.security import is_public_path, is_sensitive_path


def test_public_paths_only_whitelisted():
    # این‌ها باید عمومی باشند
    assert is_public_path("/") is True
    assert is_public_path("/symbol") is True
    assert is_public_path("/symbol/فملی") is True
    assert is_public_path("/api/health") is True
    assert is_public_path("/api/status") is True
    assert is_public_path("/api/live/status") is True
    assert is_public_path("/docs") is True
    assert is_public_path("/openapi.json") is True
    assert is_public_path("/static/js/app.js") is True
    assert is_public_path("/favicon.svg") is True


def test_api_endpoints_not_public():
    # این‌ها باید خصوصی باشند (P0 regression)
    assert is_public_path("/api/analyze") is False
    assert is_public_path("/api/analyze?force=true") is False
    assert is_public_path("/api/overview") is False
    assert is_public_path("/api/notify/log") is False
    assert is_public_path("/api/portfolio") is False
    assert is_public_path("/api/config/thresholds") is False
    assert is_public_path("/api/filter/run") is False
    assert is_public_path("/api/backtest/history") is False
    assert is_public_path("/api/symbol/فملی/full") is False
    assert is_public_path("/api/v09/forex/GC1") is False
    assert is_public_path("/api/auth/login") is False


def test_sensitive_paths():
    assert is_sensitive_path("/api/notify/config") is True
    assert is_sensitive_path("/api/portfolio") is True
    assert is_sensitive_path("/api/config/thresholds") is True
    assert is_sensitive_path("/api/analyze") is False
