"""
test_auth.py - v1.5 تست حالت خصوصی (فقط مالک)
"""
from app.core.security import (
    issue_session_token,
    verify_session_token,
    authorize_request,
)


def test_token_issue_and_verify():
    token = issue_session_token("secret", {"sub": "owner"}, ttl_sec=3600)
    assert "." in token
    payload = verify_session_token(token, "secret")
    assert payload and payload["sub"] == "owner"
    # امضای اشتباه
    assert verify_session_token(token, "wrong-secret") is None
    # دستکاری payload
    parts = token.split(".")
    tampered = "ZGVm" + "." + parts[1]  # 'def' base64 - invalid payload
    assert verify_session_token(tampered, "secret") is None


def test_token_expired():
    token = issue_session_token("secret", {"sub": "owner"}, ttl_sec=-10)
    assert verify_session_token(token, "secret") is None


def test_token_garbage():
    assert verify_session_token("not-a-token", "secret") is None
    assert verify_session_token("a.b.c.d", "secret") is None


def test_authorize_request_api_key():
    from types import SimpleNamespace
    s = SimpleNamespace(api_key="k123", private_password="", auth_required=True)
    assert authorize_request("k123", None, settings=s)
    assert not authorize_request("bad", None, settings=s)
    assert not authorize_request(None, None, settings=s)


def test_authorize_request_bearer():
    from types import SimpleNamespace
    s = SimpleNamespace(api_key="secret", private_password="secret", auth_required=True)
    token = issue_session_token("secret", {"sub": "owner"}, ttl_sec=600)
    assert authorize_request(None, token, settings=s)
    assert not authorize_request(None, "bogus.token", settings=s)
