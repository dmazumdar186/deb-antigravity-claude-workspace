"""Unit tests for testflight_invite.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TF_SCRIPT = PROJECT_ROOT / "execution" / "mobile_apps" / "testflight_invite.py"


def _import_tf():
    import testflight_invite
    return testflight_invite


def test_generate_jwt_header_and_payload(tmp_path, monkeypatch):
    """Verify JWT header (alg=ES256, kid=ASC_KEY_ID) and payload claims (iss, aud)."""
    tf = _import_tf()
    # Generate a fresh EC private key for the test (PEM format)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path = tmp_path / "asc_key.p8"
    key_path.write_bytes(pem)

    token = tf.generate_jwt("FAKE_KEY_ID", "FAKE_ISSUER_ID", key_path)

    # Decode without verifying (we just inspect header/payload)
    import jwt as pyjwt
    header = pyjwt.get_unverified_header(token)
    assert header["alg"] == "ES256"
    assert header["kid"] == "FAKE_KEY_ID"
    assert header["typ"] == "JWT"

    payload = pyjwt.decode(token, options={"verify_signature": False})
    assert payload["iss"] == "FAKE_ISSUER_ID"
    assert payload["aud"] == "appstoreconnect-v1"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_generate_jwt_missing_pyjwt(monkeypatch, tmp_path):
    tf = _import_tf()
    monkeypatch.setattr(tf, "jwt", None)
    with pytest.raises(SystemExit, match="PyJWT"):
        tf.generate_jwt("k", "i", tmp_path / "missing.p8")


def test_generate_jwt_missing_key_file(tmp_path):
    tf = _import_tf()
    with pytest.raises(SystemExit, match="private key not found"):
        tf.generate_jwt("k", "i", tmp_path / "does-not-exist.p8")


def test_require_env_raises_on_missing(monkeypatch):
    tf = _import_tf()
    monkeypatch.delenv("FAKE_NOT_SET_VAR_XYZ", raising=False)
    with pytest.raises(SystemExit, match="FAKE_NOT_SET_VAR_XYZ"):
        tf.require_env("FAKE_NOT_SET_VAR_XYZ")


def test_require_env_returns_value(monkeypatch):
    tf = _import_tf()
    monkeypatch.setenv("TEST_VAR_TF", "myvalue")
    assert tf.require_env("TEST_VAR_TF") == "myvalue"


def test_help_exits_zero():
    rc = subprocess.run(
        [sys.executable, str(TF_SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode == 0
    assert "emails" in rc.stdout


def test_argparse_rejects_bad_group():
    rc = subprocess.run(
        [sys.executable, str(TF_SCRIPT),
         "--app", "x", "--emails", "a@b.com", "--group", "unknown"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode != 0
    assert "invalid choice" in rc.stderr or "unknown" in rc.stderr


def test_argparse_requires_emails():
    rc = subprocess.run(
        [sys.executable, str(TF_SCRIPT),
         "--app", "x", "--group", "internal"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode != 0
