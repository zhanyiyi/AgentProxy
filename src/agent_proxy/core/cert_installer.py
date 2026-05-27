"""Install / verify the mitmproxy CA in NSS-backed cert stores.

Firefox keeps its own per-profile cert9.db. Chrome on Linux uses
~/.pki/nssdb. Both stores are managed by NSS's `certutil` binary
(libnss3-tools on Debian/Kali/Ubuntu). The OS trust store is
deliberately *not* touched — installing a MITM CA system-wide widens
the attack surface for everyday browsing.

The functions here are pure side-effecting helpers; the MCP tool layer
in tools/tools.py wraps them with a thin JSON return shape."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_proxy.cert")

DEFAULT_CA_PATH = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")
DEFAULT_NICKNAME = "mitmproxy"

CERTUTIL_HINT = (
    "certutil not found. Install it with `sudo apt-get install -y "
    "libnss3-tools` (Debian/Kali/Ubuntu) or the equivalent for your distro."
)


def _certutil() -> Optional[str]:
    return shutil.which("certutil")


def list_firefox_profiles(home: Optional[Path] = None) -> List[Path]:
    """Return every Firefox profile directory that holds a cert9.db.
    Covers ~/.mozilla/firefox/*.default* and *.default-esr layouts; also
    looks at the snap install location since some Kali setups use it."""
    home = home or Path.home()
    candidates: List[Path] = []
    for base in (
        home / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
    ):
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if (child / "cert9.db").is_file():
                candidates.append(child)
    return candidates


def list_chrome_nss_dbs(home: Optional[Path] = None) -> List[Path]:
    """Chrome / Chromium on Linux share ~/.pki/nssdb; only one location to
    return, but kept symmetrical with Firefox for the tool layer."""
    home = home or Path.home()
    db = home / ".pki" / "nssdb"
    return [db] if (db / "cert9.db").is_file() or (db / "key4.db").is_file() else []


def _is_installed(db: Path, nickname: str) -> bool:
    cu = _certutil()
    if not cu:
        return False
    try:
        out = subprocess.run(
            [cu, "-L", "-d", f"sql:{db}", "-n", nickname],
            capture_output=True, text=True, timeout=5,
        )
        return out.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _install(db: Path, ca_path: str, nickname: str) -> Dict[str, Any]:
    """Add (or refresh) the CA in db. certutil rejects a duplicate
    nickname, so we delete any existing one first — idempotent."""
    cu = _certutil()
    if not cu:
        return {"db": str(db), "ok": False, "error": CERTUTIL_HINT}
    if not Path(ca_path).is_file():
        return {"db": str(db), "ok": False, "error": f"CA not found: {ca_path}"}
    db.mkdir(parents=True, exist_ok=True)
    # Best-effort delete of any stale entry under the same nickname.
    subprocess.run(
        [cu, "-D", "-d", f"sql:{db}", "-n", nickname],
        capture_output=True, text=True, timeout=5,
    )
    proc = subprocess.run(
        [cu, "-A", "-d", f"sql:{db}", "-t", "C,,", "-n", nickname, "-i", ca_path],
        capture_output=True, text=True, timeout=10,
    )
    if proc.returncode != 0:
        return {
            "db": str(db),
            "ok": False,
            "error": (proc.stderr or proc.stdout or "certutil failed").strip(),
        }
    return {"db": str(db), "ok": True, "nickname": nickname}


def install_firefox(
    ca_path: str = DEFAULT_CA_PATH, nickname: str = DEFAULT_NICKNAME,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    if not _certutil():
        return {"ok": False, "error": CERTUTIL_HINT, "results": []}
    profiles = list_firefox_profiles(home)
    if not profiles:
        return {
            "ok": False,
            "error": (
                "No Firefox profile found under ~/.mozilla/firefox/. "
                "Open Firefox once to create one, then retry."
            ),
            "results": [],
        }
    results = [_install(p, ca_path, nickname) for p in profiles]
    return {
        "ok": all(r["ok"] for r in results),
        "ca_path": ca_path,
        "results": results,
        "note": "Restart Firefox to pick up the new trust anchor.",
    }


def install_chrome(
    ca_path: str = DEFAULT_CA_PATH, nickname: str = DEFAULT_NICKNAME,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    if not _certutil():
        return {"ok": False, "error": CERTUTIL_HINT, "results": []}
    home = home or Path.home()
    db = home / ".pki" / "nssdb"
    db.mkdir(parents=True, exist_ok=True)
    res = _install(db, ca_path, nickname)
    return {
        "ok": res["ok"],
        "ca_path": ca_path,
        "results": [res],
        "note": "Restart Chrome/Chromium to pick up the new trust anchor.",
    }


def cert_status(
    ca_path: str = DEFAULT_CA_PATH, nickname: str = DEFAULT_NICKNAME,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Read-only sweep: which NSS DBs have the CA installed under
    `nickname`. Use it before installing to know what'll change, or
    after to confirm."""
    cu = _certutil()
    return {
        "certutil_available": bool(cu),
        "ca_path": ca_path,
        "ca_exists": Path(ca_path).is_file(),
        "firefox": [
            {"db": str(p), "installed": _is_installed(p, nickname)}
            for p in list_firefox_profiles(home)
        ],
        "chrome": [
            {"db": str(p), "installed": _is_installed(p, nickname)}
            for p in list_chrome_nss_dbs(home)
        ],
        "hint": CERTUTIL_HINT if not cu else None,
    }
