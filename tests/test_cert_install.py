"""Smoke tests for the cert installer.

certutil is an optional system dependency (libnss3-tools). The suite
exercises everything that doesn't actually invoke certutil so it stays
green on dev machines without it. The certutil-dependent flow is
gated behind shutil.which('certutil')."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_proxy.core import cert_installer as ci


def _seed_firefox_profile(home: Path, name: str = "abcd.default") -> Path:
    p = home / ".mozilla" / "firefox" / name
    p.mkdir(parents=True, exist_ok=True)
    (p / "cert9.db").write_bytes(b"")
    return p


def _seed_chrome_db(home: Path) -> Path:
    p = home / ".pki" / "nssdb"
    p.mkdir(parents=True, exist_ok=True)
    (p / "cert9.db").write_bytes(b"")
    return p


def _gen_self_signed_pem(path: Path):
    """Generate a real PEM so certutil -A doesn't reject it."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-mitm-ci")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def test_discovery():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        # empty home → empty results
        assert ci.list_firefox_profiles(home) == []
        assert ci.list_chrome_nss_dbs(home) == []
        # seed both
        ff = _seed_firefox_profile(home)
        ck = _seed_chrome_db(home)
        assert ci.list_firefox_profiles(home) == [ff]
        assert ci.list_chrome_nss_dbs(home) == [ck]
    print("  [ok] firefox / chrome discovery handles empty + populated homes")


def test_status_when_no_certutil(monkeypatch_path=None):
    """If certutil isn't on PATH, status reports it cleanly without crashing."""
    saved = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = "/nonexistent"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _seed_firefox_profile(home)
            res = ci.cert_status(ca_path="/dev/null", home=home)
            assert res["certutil_available"] is False
            assert "libnss3-tools" in (res.get("hint") or "")
            assert res["firefox"][0]["installed"] is False
    finally:
        os.environ["PATH"] = saved
    print("  [ok] cert_status reports missing certutil with apt-install hint")


def test_install_when_no_certutil():
    saved = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = "/nonexistent"
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _seed_firefox_profile(home)
            r = ci.install_firefox(ca_path="/dev/null", home=home)
            assert r["ok"] is False
            assert "libnss3-tools" in r["error"]
    finally:
        os.environ["PATH"] = saved
    print("  [ok] install_firefox refuses gracefully when certutil missing")


def test_install_when_no_profiles_found():
    if not shutil.which("certutil"):
        print("  [skip] no certutil installed — skipping no-profile case")
        return
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        r = ci.install_firefox(ca_path="/dev/null", home=home)
        assert r["ok"] is False
        assert "No Firefox profile" in r["error"]
    print("  [ok] install_firefox bails out cleanly when no profile exists")


def test_real_install_round_trip():
    if not shutil.which("certutil"):
        print("  [skip] no certutil — skipping real round-trip test")
        return
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        ca = home / "ca.pem"
        _gen_self_signed_pem(ca)
        # Bootstrap an empty NSS db that certutil can read/write.
        prof = home / ".mozilla" / "firefox" / "test.default"
        prof.mkdir(parents=True)
        # certutil -N initialises the empty DB without a password.
        subprocess.run(
            ["certutil", "-N", "-d", f"sql:{prof}", "--empty-password"],
            check=True, capture_output=True,
        )
        # Now there's a real cert9.db so list_firefox_profiles picks it up.
        assert ci.list_firefox_profiles(home) == [prof]

        before = ci.cert_status(ca_path=str(ca), home=home)
        assert before["firefox"][0]["installed"] is False

        r = ci.install_firefox(ca_path=str(ca), home=home, nickname="ci-test-mitm")
        assert r["ok"] is True, r
        assert r["results"][0]["ok"] is True

        after = ci.cert_status(ca_path=str(ca), nickname="ci-test-mitm", home=home)
        assert after["firefox"][0]["installed"] is True

        # Idempotent: install again, still ok.
        r2 = ci.install_firefox(ca_path=str(ca), home=home, nickname="ci-test-mitm")
        assert r2["ok"] is True
    print("  [ok] real install round-trip: status flips False -> True, idempotent")


def main():
    test_discovery()
    test_status_when_no_certutil()
    test_install_when_no_certutil()
    test_install_when_no_profiles_found()
    test_real_install_round_trip()
    print("\n" + "=" * 50)
    print("ALL cert-installer smoke tests PASSED")
    print("=" * 50)


if __name__ == "__main__":
    main()
