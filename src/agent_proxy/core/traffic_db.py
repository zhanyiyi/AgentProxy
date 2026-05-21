import json
import shlex
import sqlite3
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from mitmproxy import http


MAX_BODY_BYTES = 256 * 1024
BINARY_CT_PREFIXES = ("image/", "video/", "audio/", "font/")
BINARY_CT_EXACT = {"application/octet-stream", "application/pdf", "application/zip"}


def _is_binary_content_type(ct: str) -> bool:
    if not ct:
        return False
    ct = ct.lower().split(";", 1)[0].strip()
    if ct in BINARY_CT_EXACT:
        return True
    return any(ct.startswith(p) for p in BINARY_CT_PREFIXES)


def _parse_headers(raw: str) -> Dict[str, str]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return {k: v for k, v in parsed}
    return parsed


def _parse_headers_ordered(raw: str) -> List[List[str]]:
    if not raw:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    return [[k, v] for k, v in parsed.items()]


class SimpleRequest:
    def __init__(self, method: str, url: str, headers: Dict[str, str], body: Optional[str]):
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body


class SimpleResponse:
    def __init__(self, status_code: Optional[int], headers: Optional[Dict[str, str]], body: Optional[str]):
        self.status_code = status_code
        self.headers = headers
        self.body = body


class TrafficDB:
    def __init__(self, db_path: str = "agent_proxy_traffic.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flows (
                    id TEXT PRIMARY KEY,
                    url TEXT,
                    method TEXT,
                    status_code INTEGER,
                    request_headers TEXT,
                    request_body TEXT,
                    response_headers TEXT,
                    response_body TEXT,
                    timestamp REAL,
                    size INTEGER,
                    request_body_truncated INTEGER DEFAULT 0,
                    response_body_truncated INTEGER DEFAULT 0,
                    response_body_omitted TEXT
                )
            """)
            for col, ddl in [
                ("request_body_truncated", "INTEGER DEFAULT 0"),
                ("response_body_truncated", "INTEGER DEFAULT 0"),
                ("response_body_omitted", "TEXT"),
                ("profile_label", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE flows ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON flows(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON flows(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_method ON flows(method)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_label ON flows(profile_label)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    evidence TEXT,
                    created_at REAL NOT NULL,
                    UNIQUE(flow_id, rule_id, evidence)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_flow ON findings(flow_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity)")

            # findings.kind: "finding" (default) or "signal" (lower-confidence signals)
            try:
                conn.execute("ALTER TABLE findings ADD COLUMN kind TEXT NOT NULL DEFAULT 'finding'")
            except sqlite3.OperationalError:
                pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_tags (
                    flow_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (flow_id, tag)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_tags_tag ON flow_tags(tag)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_links (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (source_id, target_id, relation)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_links_src ON flow_links(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_links_dst ON flow_links(target_id)")

            # Triage notes — one per flow_id, agent-authored after researching it.
            # Structured into the four sections that real SRC researchers fill out.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_notes (
                    flow_id TEXT PRIMARY KEY,
                    verdict TEXT NOT NULL,
                    scenario TEXT,
                    sensitive_fields TEXT,
                    test_steps TEXT,
                    conclusion TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_notes_verdict ON flow_notes(verdict)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_notes_updated ON flow_notes(updated_at)")

    def save_flow(self, flow: http.HTTPFlow, profile_label: Optional[str] = None):
        req_body, req_truncated = self._extract_body(flow.request)
        resp_body, resp_truncated, resp_omitted = (None, 0, None)
        if flow.response:
            resp_body, resp_truncated = self._extract_body(flow.response)
            if resp_body is None and flow.response.content:
                resp_omitted = "binary"
        status_code = flow.response.status_code if flow.response else None
        size = len(flow.response.content) if flow.response and flow.response.content else 0

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO flows (
                    id, url, method, status_code,
                    request_headers, request_body,
                    response_headers, response_body,
                    timestamp, size,
                    request_body_truncated, response_body_truncated, response_body_omitted,
                    profile_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url,
                    method=excluded.method,
                    status_code=excluded.status_code,
                    request_headers=excluded.request_headers,
                    request_body=excluded.request_body,
                    response_headers=excluded.response_headers,
                    response_body=excluded.response_body,
                    size=excluded.size,
                    request_body_truncated=excluded.request_body_truncated,
                    response_body_truncated=excluded.response_body_truncated,
                    response_body_omitted=excluded.response_body_omitted,
                    profile_label=COALESCE(excluded.profile_label, flows.profile_label)
            """,
                (
                    flow.id,
                    flow.request.url,
                    flow.request.method,
                    status_code,
                    json.dumps(
                        [[k.decode("latin-1"), v.decode("latin-1")] for k, v in flow.request.headers.fields]
                    ),
                    req_body,
                    json.dumps(
                        [[k.decode("latin-1"), v.decode("latin-1")] for k, v in flow.response.headers.fields]
                    ) if flow.response else None,
                    resp_body,
                    flow.request.timestamp_start,
                    size,
                    req_truncated,
                    resp_truncated,
                    resp_omitted,
                    profile_label,
                ),
            )

    @staticmethod
    def _extract_body(message) -> tuple:
        """Returns (text_body_or_None, truncated_flag).
        Skips binary content types entirely, truncates large bodies."""
        if message is None:
            return None, 0
        ct = ""
        try:
            ct = message.headers.get("content-type", "") or ""
        except Exception:
            pass
        if _is_binary_content_type(ct):
            return None, 0
        try:
            content = getattr(message, "content", None)
            if content is None:
                return None, 0
            if isinstance(content, (bytes, bytearray)):
                truncated = 0
                if len(content) > MAX_BODY_BYTES:
                    content = content[:MAX_BODY_BYTES]
                    truncated = 1
                return content.decode("utf-8", errors="replace"), truncated
            text = str(content)
            if len(text) > MAX_BODY_BYTES:
                return text[:MAX_BODY_BYTES], 1
            return text, 0
        except Exception:
            return None, 0

    @staticmethod
    def _get_safe_text(message) -> Optional[str]:
        """Legacy helper used by interceptor replace_body — keeps a unified text view."""
        if message is None:
            return None
        try:
            content = getattr(message, "content", None) or getattr(message, "text", None)
            if content is None:
                return None
            if isinstance(content, (bytes, bytearray)):
                return content.decode("utf-8", errors="replace")
            return str(content)
        except Exception:
            return None

    def get_summary(self, limit: int = 20, offset: int = 0, with_findings: bool = False) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, url, method, status_code, size FROM flows "
                "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()
            result = []
            findings_counts: Dict[str, int] = {}
            if with_findings and rows:
                ids = [r["id"] for r in rows]
                placeholders = ",".join(["?"] * len(ids))
                fc = conn.execute(
                    f"SELECT flow_id, COUNT(*) c FROM findings WHERE flow_id IN ({placeholders}) GROUP BY flow_id",
                    ids,
                ).fetchall()
                findings_counts = {r["flow_id"]: r["c"] for r in fc}
            for row in rows:
                entry = {
                    "id": row["id"],
                    "method": row["method"],
                    "url": row["url"],
                    "status_code": row["status_code"],
                    "size": row["size"],
                }
                if with_findings:
                    entry["findings"] = findings_counts.get(row["id"], 0)
                result.append(entry)
            return result

    def get_detail(
        self,
        flow_id: str,
        level: str = "preview",
        body_preview_length: int = 2000,
    ) -> Optional[Dict[str, Any]]:
        """Layered detail view.
        - meta: headers only
        - preview: headers + body truncated to body_preview_length (default 2KB)
        - full: complete body (still capped at MAX_BODY_BYTES at storage time)
        """
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
            row = cursor.fetchone()
            if not row:
                return None

            req_headers = _parse_headers(row["request_headers"])
            resp_headers = _parse_headers(row["response_headers"]) if row["response_headers"] else None

            def _shape_body(raw, truncated_flag, omitted):
                if level == "meta":
                    return None, None
                if omitted:
                    return None, omitted
                if raw is None:
                    return None, None
                if level == "preview" and len(raw) > body_preview_length:
                    return raw[:body_preview_length], "preview_truncated"
                if truncated_flag:
                    return raw, "stored_truncated_256kb"
                return raw, None

            req_body, req_note = _shape_body(
                row["request_body"], row["request_body_truncated"], None
            )
            resp_body, resp_note = _shape_body(
                row["response_body"], row["response_body_truncated"], row["response_body_omitted"]
            )

            request_obj = {
                "method": row["method"],
                "url": row["url"],
                "headers": req_headers,
            }
            if level != "meta":
                request_obj["body"] = req_body
                request_obj["body_preview"] = req_body  # legacy alias
                if req_note:
                    request_obj["body_note"] = req_note

            response_obj = None
            if row["status_code"] is not None:
                response_obj = {
                    "status_code": row["status_code"],
                    "headers": resp_headers,
                }
                if level != "meta":
                    response_obj["body"] = resp_body
                    response_obj["body_preview"] = resp_body  # legacy alias
                    if resp_note:
                        response_obj["body_note"] = resp_note

            simple_request = SimpleRequest(
                method=row["method"], url=row["url"],
                headers=req_headers, body=row["request_body"],
            )
            return {
                "id": row["id"],
                "request": request_obj,
                "response": response_obj,
                "curl_command": self._generate_curl(simple_request),
            }

    def search(self, query: str = None, domain: str = None, method: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT id, url, method, status_code, timestamp FROM flows WHERE 1=1"
        params = []
        if domain:
            sql += " AND url LIKE ?"
            params.append(f"%{domain}%")
        if method:
            sql += " AND method = ?"
            params.append(method.upper())
        if query:
            sql += " AND (url LIKE ? OR request_body LIKE ? OR response_body LIKE ?)"
            wildcard = f"%{query}%"
            params.extend([wildcard, wildcard, wildcard])
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def clear(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM flows")
            conn.execute("DELETE FROM findings")
            conn.execute("DELETE FROM flow_tags")
            conn.execute("DELETE FROM flow_links")
            conn.execute("DELETE FROM flow_notes")

    def add_finding(self, flow_id: str, rule_id: str, severity: str, category: str, evidence: str = "", kind: str = "finding") -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO findings (flow_id, rule_id, severity, category, evidence, created_at, kind) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (flow_id, rule_id, severity, category, evidence[:500], time.time(), kind),
                )
            return True
        except Exception:
            return False

    def list_findings(
        self,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        rule_id: Optional[str] = None,
        flow_id: Optional[str] = None,
        kind: Optional[str] = "finding",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT id, flow_id, rule_id, severity, category, evidence, kind, created_at FROM findings WHERE 1=1"
        params: list = []
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if rule_id:
            sql += " AND rule_id = ?"
            params.append(rule_id)
        if flow_id:
            sql += " AND flow_id = ?"
            params.append(flow_id)
        if kind and kind != "all":
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def findings_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) c FROM findings").fetchone()["c"]
            sev_kind = conn.execute(
                "SELECT kind, severity, COUNT(*) c FROM findings GROUP BY kind, severity"
            ).fetchall()
            cat_kind = conn.execute(
                "SELECT kind, category, COUNT(*) c FROM findings GROUP BY kind, category"
            ).fetchall()
            findings_sev = {r["severity"]: r["c"] for r in sev_kind if r["kind"] == "finding"}
            findings_cat = {r["category"]: r["c"] for r in cat_kind if r["kind"] == "finding"}
            signals_sev = {r["severity"]: r["c"] for r in sev_kind if r["kind"] == "signal"}
            signals_cat = {r["category"]: r["c"] for r in cat_kind if r["kind"] == "signal"}
            return {
                "total": total,
                "findings": {"by_severity": findings_sev, "by_category": findings_cat,
                             "count": sum(findings_sev.values())},
                "signals": {"by_severity": signals_sev, "by_category": signals_cat,
                            "count": sum(signals_sev.values())},
            }

    # ----- Tag/Link/Chain (multi-step trace) -----

    def add_tag(self, flow_id: str, tag: str) -> bool:
        if not tag.strip():
            return False
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO flow_tags (flow_id, tag, created_at) VALUES (?, ?, ?)",
                    (flow_id, tag.strip(), time.time()),
                )
            return True
        except Exception:
            return False

    def remove_tag(self, flow_id: str, tag: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM flow_tags WHERE flow_id = ? AND tag = ?",
                (flow_id, tag.strip()),
            )
            return cur.rowcount > 0

    def get_tags(self, flow_id: str) -> List[str]:
        with self._get_conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT tag FROM flow_tags WHERE flow_id = ? ORDER BY created_at", (flow_id,)
            ).fetchall()]

    def find_by_tag(self, tag: str) -> List[str]:
        with self._get_conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT flow_id FROM flow_tags WHERE tag = ? ORDER BY created_at DESC",
                (tag.strip(),),
            ).fetchall()]

    def add_link(self, source_id: str, target_id: str, relation: str = "") -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO flow_links (source_id, target_id, relation, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (source_id, target_id, relation.strip(), time.time()),
                )
            return True
        except Exception:
            return False

    def remove_link(self, source_id: str, target_id: str, relation: str = "") -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM flow_links WHERE source_id = ? AND target_id = ? AND relation = ?",
                (source_id, target_id, relation.strip()),
            )
            return cur.rowcount > 0

    def get_chain(self, flow_id: str, depth: int = 2) -> Dict[str, Any]:
        """BFS the link graph from `flow_id` up to `depth` hops on each side.
        Returns a flat structure (no recursion) so the agent can read it cheaply."""
        depth = max(0, min(depth, 5))
        seen = {flow_id}

        def _walk(start_id: str, direction: str, hops: int) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            frontier = [(start_id, 0)]
            while frontier:
                cur, lvl = frontier.pop(0)
                if lvl >= hops:
                    continue
                with self._get_conn() as conn:
                    if direction == "up":
                        rows = conn.execute(
                            "SELECT source_id, relation FROM flow_links WHERE target_id = ?",
                            (cur,),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT target_id, relation FROM flow_links WHERE source_id = ?",
                            (cur,),
                        ).fetchall()
                for nid, rel in rows:
                    if nid in seen:
                        continue
                    seen.add(nid)
                    results.append({"flow_id": nid, "relation": rel, "depth": lvl + 1})
                    frontier.append((nid, lvl + 1))
            return results

        return {
            "flow_id": flow_id,
            "tags": self.get_tags(flow_id),
            "upstream": _walk(flow_id, "up", depth),
            "downstream": _walk(flow_id, "down", depth),
        }

    # ----- Triage notes -----

    NOTE_VERDICTS = ("vulnerable", "not_vulnerable", "inconclusive")
    NOTE_FIELD_LIMIT = 1500  # per-section character cap; keep notes context-cheap

    @classmethod
    def _trim_note_field(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        if len(s) > cls.NOTE_FIELD_LIMIT:
            return s[: cls.NOTE_FIELD_LIMIT - 3] + "..."
        return s

    def upsert_note(
        self,
        flow_id: str,
        verdict: str,
        scenario: Optional[str] = None,
        sensitive_fields: Optional[str] = None,
        test_steps: Optional[str] = None,
        conclusion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or replace a triage note for a single flow. One note per flow_id —
        repeated calls overwrite. Returns the stored note (with timestamps)."""
        if verdict not in self.NOTE_VERDICTS:
            raise ValueError(f"verdict must be one of {self.NOTE_VERDICTS}")
        scenario = self._trim_note_field(scenario)
        sensitive_fields = self._trim_note_field(sensitive_fields)
        test_steps = self._trim_note_field(test_steps)
        conclusion = self._trim_note_field(conclusion)
        now = time.time()
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT created_at FROM flow_notes WHERE flow_id = ?", (flow_id,)
            ).fetchone()
            created_at = existing[0] if existing else now
            conn.execute(
                """
                INSERT INTO flow_notes
                    (flow_id, verdict, scenario, sensitive_fields, test_steps,
                     conclusion, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(flow_id) DO UPDATE SET
                    verdict=excluded.verdict,
                    scenario=excluded.scenario,
                    sensitive_fields=excluded.sensitive_fields,
                    test_steps=excluded.test_steps,
                    conclusion=excluded.conclusion,
                    updated_at=excluded.updated_at
                """,
                (flow_id, verdict, scenario, sensitive_fields, test_steps,
                 conclusion, created_at, now),
            )
        return self.get_note(flow_id)

    def get_note(self, flow_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM flow_notes WHERE flow_id = ?", (flow_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_notes(
        self,
        verdict: Optional[str] = None,
        flow_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM flow_notes WHERE 1=1"
        params: list = []
        if verdict:
            sql += " AND verdict = ?"
            params.append(verdict)
        if flow_id:
            sql += " AND flow_id = ?"
            params.append(flow_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def remove_note(self, flow_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM flow_notes WHERE flow_id = ?", (flow_id,))
            return cur.rowcount > 0

    def notes_stats(self) -> Dict[str, int]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) c FROM flow_notes").fetchone()["c"]
            by_verdict = {
                r["verdict"]: r["c"]
                for r in conn.execute(
                    "SELECT verdict, COUNT(*) c FROM flow_notes GROUP BY verdict"
                ).fetchall()
            }
            return {"total": total, "by_verdict": by_verdict}

    def find_replay_match(self, url: str, method: str, since_ts: float) -> Optional[str]:
        """Find the most recent flow matching url+method captured after since_ts.
        Used by replay tools to return new_flow_id for closed-loop diff/evidence."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM flows WHERE url = ? AND method = ? AND timestamp > ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (url, method.upper(), since_ts),
            ).fetchone()
            return row[0] if row else None

    def get_all_for_analysis(self, limit: Optional[int] = None, lightweight: bool = False) -> List[Dict[str, Any]]:
        cols = "id, url, method, status_code, request_headers, response_headers" if lightweight else "*"
        sql = f"SELECT {cols} FROM flows ORDER BY timestamp DESC"
        params: list = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                entry = {
                    "id": row["id"],
                    "request": {
                        "url": row["url"],
                        "method": row["method"],
                        "headers": _parse_headers(row["request_headers"]),
                        **({"body": row["request_body"]} if not lightweight else {}),
                    },
                    "response": {
                        "status_code": row["status_code"],
                        "headers": _parse_headers(row["response_headers"]) if row["response_headers"] else {},
                        **({"body": row["response_body"]} if not lightweight else {}),
                    }
                    if row["status_code"]
                    else None,
                }
                results.append(entry)
            return results

    def get_by_ids(self, flow_ids: List[str], columns: Optional[List[str]] = None, ordered_headers: bool = False) -> List[Dict[str, Any]]:
        if not flow_ids:
            return []
        allowed_cols = {"id", "url", "method", "status_code", "request_headers", "request_body", "response_headers", "response_body", "timestamp", "size"}
        if columns:
            invalid_cols = [c for c in columns if c not in allowed_cols]
            if invalid_cols:
                raise ValueError(f"Invalid columns: {invalid_cols}")
            cols = ", ".join(columns)
        else:
            cols = "*"

        placeholders = ",".join(["?"] * len(flow_ids))
        header_fn = _parse_headers_ordered if ordered_headers else _parse_headers

        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT {cols} FROM flows WHERE id IN ({placeholders})", flow_ids)
            rows = cursor.fetchall()
            row_keys = set(rows[0].keys()) if rows else set()
            results = []
            for row in rows:
                entry: Dict[str, Any] = {"id": row["id"]}
                req: Dict[str, Any] = {}
                if "url" in row_keys:
                    req["url"] = row["url"]
                if "method" in row_keys:
                    req["method"] = row["method"]
                if "request_headers" in row_keys and row["request_headers"]:
                    req["headers"] = header_fn(row["request_headers"])
                if "request_body" in row_keys:
                    req["body"] = row["request_body"]
                if req:
                    entry["request"] = req

                if "status_code" in row_keys and row["status_code"] is not None:
                    resp: Dict[str, Any] = {"status_code": row["status_code"]}
                    if "response_headers" in row_keys and row["response_headers"]:
                        resp["headers"] = header_fn(row["response_headers"])
                    if "response_body" in row_keys:
                        resp["body"] = row["response_body"]
                    entry["response"] = resp
                results.append(entry)
            return results

    def get_flow_object(self, flow_id: str) -> Optional[SimpleRequest]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT method, url, request_headers, request_body FROM flows WHERE id = ?",
                (flow_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            headers = _parse_headers(row["request_headers"])
            return SimpleRequest(
                method=row["method"],
                url=row["url"],
                headers=headers,
                body=row["request_body"],
            )

    def _generate_curl(self, request: SimpleRequest) -> str:
        try:
            cmd = ["curl", "-X", request.method]
            cmd.append(shlex.quote(request.url))
            for key, value in request.headers.items():
                cmd.append("-H")
                cmd.append(shlex.quote(f"{key}: {value}"))
            if request.body:
                cmd.append("-d")
                cmd.append(shlex.quote(request.body))
            return " ".join(cmd)
        except Exception:
            return "Error generating curl command"
