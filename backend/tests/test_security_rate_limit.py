"""
test_security_rate_limit.py - تست‌های محدودسازی ورود و اعتماد به XFF
"""
from app.core.rate_limiter import InMemoryRateLimiter
from app.core.security import is_public_path


def test_auth_rate_limit_5_per_min():
    lim = InMemoryRateLimiter()
    ip = "203.0.113.7"
    path = "/api/auth/login"
    results = []
    for _ in range(7):
        limited, _, _ = lim.check_limit(ip, path)
        results.append(limited)
        if not limited:
            lim.record(ip, path)
    # تلاش‌های ۱-۵ مجاز، ششم+ محدود
    assert results == [False, False, False, False, False, True, True]


def test_auth_rate_limit_20_per_hour():
    import time
    lim = InMemoryRateLimiter()
    ip = "203.0.113.8"
    path = "/api/auth/login"
    hkey = f"auth_hour:{path}:{ip}"
    now = time.time()
    # 20 تلاش در ۱ ساعت گذشته (تاریخ‌ها عقب‌تر از ۶۰ ثانیه تا محدودیت دقیقه‌ای فعال نشود)
    for i in range(20):
        lim.path_specific[hkey].append(now - 120 + i)
    # تلاش بعدی باید مسدود شود
    limited, msg, retry = lim.check_limit(ip, path)
    assert limited is True
    assert retry == 3600


def test_get_client_ip_ignores_xff_by_default():
    """بدون TRUST_PROXY نباید XFF جعلی پذیرفته شود (رفع دور زدن rate limit)"""
    from types import SimpleNamespace

    class FakeRequest:
        headers = {"x-forwarded-for": "1.2.3.4"}
        client = SimpleNamespace(host="127.0.0.1")

    lim = InMemoryRateLimiter()
    # بدون trust_proxy
    assert lim.get_client_ip(FakeRequest()) == "127.0.0.1"


def test_public_path_regression_login():
    # login نباید عمومی باشد (تا خودش احراز کند) اما نباید در دام قفل هم بیفتد
    assert is_public_path("/api/auth/login") is False
    assert is_public_path("/api/health") is True
