"""Bounded local persistence for already captured response attachments.

Paths are generated from hashes, never from response filenames. This module
does not fetch URLs or extract documents; it preserves the captured bytes.
"""
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
_ARTIFACT_TYPES = {
    "application/pdf", "application/zip", "application/x-zip-compressed",
    "application/octet-stream", "application/msword", "application/rtf",
    "application/vnd.ms-excel", "application/vnd.ms-powerpoint", "text/csv",
}
_SUFFIXES = {"application/pdf": ".pdf", "application/zip": ".zip", "text/csv": ".csv"}


def is_artifact(headers) -> bool:
    media_type = (headers.get("content-type", "") or "").split(";", 1)[0].strip().lower()
    disposition = (headers.get("content-disposition", "") or "").split(";", 1)[0].strip().lower()
    return (
        disposition == "attachment"
        or media_type in _ARTIFACT_TYPES
        or media_type.startswith("application/vnd.openxmlformats-officedocument.")
        or media_type.startswith("application/vnd.oasis.opendocument.")
    )


class ArtifactStore:
    def __init__(self, db_path: str):
        # A real DB path gives attachments the same instance isolation as flows.
        # Do not invent a shared location for in-memory or SQLite URI databases.
        self.directory: Optional[Path] = None
        if db_path and db_path != ":memory:" and not db_path.startswith("file:"):
            self.directory = Path(db_path + ".artifacts").absolute()

    def save(self, flow_id: str, content: Optional[bytes], headers) -> Dict[str, Any]:
        info = {"path": None, "sha256": None, "size": len(content) if content is not None else 0,
                "omitted": None, "limit_bytes": MAX_ARTIFACT_BYTES}
        if content is None:
            info["omitted"] = "content_unavailable"
            return info
        if len(content) > MAX_ARTIFACT_BYTES:
            info["omitted"] = "size_limit_exceeded"
            return info
        if self.directory is None:
            info["omitted"] = "persistent_database_path_required"
            return info

        digest = hashlib.sha256(content).hexdigest()
        flow_key = hashlib.sha256(str(flow_id).encode("utf-8")).hexdigest()[:24]
        media_type = (headers.get("content-type", "") or "").split(";", 1)[0].strip().lower()
        destination = self.directory / (flow_key + "_" + digest + _SUFFIXES.get(media_type, ".bin"))
        temporary = None
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            # mkstemp restricts file permissions on POSIX and avoids partial
            # files being published if a write fails midway.
            fd, temporary = tempfile.mkstemp(prefix=".capture-", dir=str(self.directory))
            with os.fdopen(fd, "wb") as output:
                output.write(content)
            os.replace(temporary, destination)
            temporary = None
            info.update(path=str(destination), sha256=digest)
        except OSError:
            # A full/unwritable disk must not discard the flow's HTTP metadata.
            info["omitted"] = "write_failed"
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
        return info
