from app.core.crypto import encrypt_token, decrypt_token, get_fernet, is_encrypted

def test_crypto_singleton():
    f1 = get_fernet()
    f2 = get_fernet()
    assert f1 is f2

def test_encrypt_decrypt():
    ct = encrypt_token("my-secret-123")
    assert is_encrypted(ct)
    pt = decrypt_token(ct)
    assert pt == "my-secret-123"

def test_empty():
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""
