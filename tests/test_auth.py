"""
tests/test_auth.py
Tests unitaires de base pour l'authentification.
Lance avec : pytest tests/ -v
"""

import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
import uuid


class TestSecurity:
    def test_hash_and_verify_password(self):
        plain = "MonMotDePasse123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_create_and_decode_token(self):
        user_id = uuid.uuid4()
        token = create_access_token(subject=user_id)
        assert token is not None

        decoded = decode_access_token(token)
        assert decoded == str(user_id)

    def test_invalid_token_returns_none(self):
        result = decode_access_token("not.a.valid.token")
        assert result is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(subject=uuid.uuid4())
        tampered = token[:-5] + "XXXXX"
        assert decode_access_token(tampered) is None
