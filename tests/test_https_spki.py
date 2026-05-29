"""Tests for browser_controller's mitmproxy CA SPKI helper.

The helper feeds Chromium's --ignore-certificate-errors-spki-list so the
"Not Secure" lock disappears for mitmproxy-signed traffic without
globally disabling cert validation. We assert:

- Missing CA file -> None (so we fall back cleanly).
- Real CA file -> 44-char base64 SHA-256 SPKI digest.
- A regenerated CA produces a different digest (sanity: we hash SPKI,
  not a constant).
"""
import base64
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_proxy.core.browser_controller import _mitmproxy_ca_spki_b64


def _make_self_signed_pem(path: str):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-mitm")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    with open(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def test_missing_ca_returns_none(tmp_path):
    assert _mitmproxy_ca_spki_b64(str(tmp_path / "nope.pem")) is None


def test_real_cert_yields_44char_b64_sha256(tmp_path):
    pem = tmp_path / "ca.pem"
    _make_self_signed_pem(str(pem))
    out = _mitmproxy_ca_spki_b64(str(pem))
    assert out is not None
    raw = base64.b64decode(out)
    assert len(raw) == 32  # SHA-256
    assert len(out) == 44  # base64 of 32 bytes incl padding


def test_different_keys_produce_different_digests(tmp_path):
    a, b = tmp_path / "a.pem", tmp_path / "b.pem"
    _make_self_signed_pem(str(a))
    _make_self_signed_pem(str(b))
    assert _mitmproxy_ca_spki_b64(str(a)) != _mitmproxy_ca_spki_b64(str(b))


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
