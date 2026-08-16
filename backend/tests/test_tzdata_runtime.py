"""P3.90.2: Windows runtime requires the IANA tzdata package.

stdlib zoneinfo has no timezone database on Windows. market_session.py
does ZoneInfo(\"Asia/Tehran\") at import time, so tzdata must be declared
in backend/requirements.txt and importable after install.ps1.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "backend" / "requirements.txt"


def test_tzdata_is_pinned_in_requirements():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "tzdata==2026.3" in text


def test_tzdata_package_importable():
    import tzdata

    assert tzdata is not None


def test_asia_tehran_zoneinfo_resolves():
    from zoneinfo import ZoneInfo

    tehran = ZoneInfo("Asia/Tehran")
    assert str(tehran) == "Asia/Tehran"


def test_market_session_module_imports_without_zoneinfo_error():
    from app.domain.market_session import TEHRAN, infer_iran_market_session

    assert str(TEHRAN) == "Asia/Tehran"
    session = infer_iran_market_session()
    assert session.timezone == "Asia/Tehran"
