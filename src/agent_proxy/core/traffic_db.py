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
            ]:
                try:
                    conn.execute(f"ALTER TABLE flows ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON flows(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON flows(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_method ON flows(method)")

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

    def save_flow(self, flow: http.HTTPFlow):
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
                    request_body_truncated, response_body_truncated, response_body_omitted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    response_body_omitted=excluded.response_body_omitted
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

    def add_finding(self, flow_id: str, rule_id: str, severity: str, category: str, evidence: str = "") -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO findings (flow_id, rule_id, severity, category, evidence, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (flow_id, rule_id, severity, category, evidence[:500], time.time()),
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
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT id, flow_id, rule_id, severity, category, evidence, created_at FROM findings WHERE 1=1"
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
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def findings_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) c FROM findings").fetchone()["c"]
            by_sev = {r["severity"]: r["c"] for r in conn.execute(
                "SELECT severity, COUNT(*) c FROM findings GROUP BY severity"
            ).fetchall()}
            by_cat = {r["category"]: r["c"] for r in conn.execute(
                "SELECT category, COUNT(*) c FROM findings GROUP BY category"
            ).fetchall()}
            return {"total": total, "by_severity": by_sev, "by_category": by_cat}

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
