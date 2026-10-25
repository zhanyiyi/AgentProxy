"""Persist the current browser step without replaying browser operations.

A checkpoint is an observation cursor, not a runnable workflow. In particular,
an interrupted action has an unknown result: a restarted process must ask for
review even when the same page is still present.
"""
import json
import time
from typing import Any, Dict, Optional

from .traffic_db import TrafficDB


class CheckpointStore:
    """Keep one cursor per context in the existing traffic database.

    Writes are small synchronous transactions. They use TrafficDB's connection
    policy rather than a separate writer whose queue could outlive an action.
    Action metadata is allowlisted so entered values and credentials never
    become recovery instructions.
    """

    def __init__(self, db: TrafficDB):
        self.db = db
        with self.db._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                    context TEXT PRIMARY KEY,
                    entry TEXT NOT NULL,
                    updated REAL NOT NULL
                )
            """)
            # The old process cannot report whether an in-flight operation took
            # effect. Preserve that uncertainty instead of offering a retry.
            for (raw,) in conn.execute("SELECT entry FROM workflow_checkpoints").fetchall():
                entry = json.loads(raw)
                if entry["status"] in ("inflight", "requires_dialog"):
                    entry.update(status="needs_review", action_status="unknown",
                                 error_type="ProcessInterrupted")
                    self._write(conn, entry)

    @staticmethod
    def _read(conn, context: str) -> Dict[str, Any]:
        row = conn.execute(
            "SELECT entry FROM workflow_checkpoints WHERE context = ?", (context,)
        ).fetchone()
        return json.loads(row[0]) if row else {
            "context": context, "tab_id": None, "url": None, "title": None,
            "last_action_id": None, "step": 0, "status": "ready",
        }

    @staticmethod
    def _write(conn, entry: Dict[str, Any]) -> Dict[str, Any]:
        entry["updated"] = time.time()
        conn.execute(
            "INSERT INTO workflow_checkpoints (context, entry, updated) VALUES (?, ?, ?) "
            "ON CONFLICT(context) DO UPDATE SET entry=excluded.entry, updated=excluded.updated",
            (entry["context"], json.dumps(entry, ensure_ascii=False), entry["updated"]),
        )
        return entry

    @staticmethod
    def _action_metadata(action: Dict[str, Any]) -> Dict[str, Any]:
        # Never persist `value`, prompt text, headers, cookies, or exception logs.
        return {key: action[key] for key in ("action", "target", "selector", "ref", "frame")
                if key in action and action[key] is not None}

    def latest(self, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Read a context cursor, or the most recently updated context."""
        with self.db._get_conn() as conn:
            if context is None:
                row = conn.execute(
                    "SELECT entry FROM workflow_checkpoints ORDER BY updated DESC, rowid DESC LIMIT 1"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT entry FROM workflow_checkpoints WHERE context = ?", (context,)
                ).fetchone()
        return json.loads(row[0]) if row else None

    def observe(self, page: Dict[str, Any], *, context: str = "default",
                step: Optional[int] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """Refresh page facts without resolving an uncertain action.

        An explicit status='ready' acknowledges a place to continue. It does
        not change the previous action_status, which may still be 'unknown'.
        """
        with self.db._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            entry = self._read(conn, context)
            entry.update({key: page[key] for key in ("tab_id", "url", "title", "instance_id") if key in page})
            if step is not None:
                entry["step"] = step
            if status is not None:
                entry["status"] = status
            return self._write(conn, entry)

    def begin(self, action: Dict[str, Any], *, context: str = "default") -> Dict[str, Any]:
        """Commit the intent before execution so cancellation cannot erase it."""
        with self.db._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            entry = self._read(conn, context)
            entry.update(step=entry["step"] + 1, status="inflight",
                         action_status="inflight", last_action_id=None,
                         action=self._action_metadata(action))
            entry.pop("error_type", None)
            return self._write(conn, entry)

    def finish(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Save only returned facts; a primitive receipt is not business success."""
        context = receipt.get("context", "default")
        with self.db._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            entry = self._read(conn, context)
            page = receipt.get("page", {})
            entry.update({key: page[key] for key in ("tab_id", "url", "title") if key in page})
            entry["last_action_id"] = receipt.get("action_id") or receipt.get("id")
            # Receipts may omit the locator ref/frame supplied at begin().
            entry.setdefault("action", {}).update(self._action_metadata(receipt))
            entry["action_status"] = receipt.get("action_status", receipt["status"])
            if receipt.get("dialogs") or receipt["status"] == "dialog_pending":
                entry["status"] = "requires_dialog"
            elif entry["action_status"] == "completed":
                entry["status"] = "completed"
            elif entry["action_status"] == "not_started":
                entry["status"] = "ready"
            else:
                entry["status"] = "needs_review"
            entry.pop("error_type", None)
            return self._write(conn, entry)

    def interrupted(self, error_type: str, *, context: str = "default") -> Dict[str, Any]:
        """Record an exception class, never its possibly sensitive call log."""
        with self.db._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            entry = self._read(conn, context)
            entry.update(status="needs_review", action_status="unknown", error_type=error_type)
            return self._write(conn, entry)

    def reset(self, context: Optional[str] = None) -> int:
        """Forget one cursor or all cursors without touching captured traffic."""
        with self.db._get_conn() as conn:
            if context is None:
                result = conn.execute("DELETE FROM workflow_checkpoints")
            else:
                result = conn.execute("DELETE FROM workflow_checkpoints WHERE context = ?", (context,))
            return result.rowcount
