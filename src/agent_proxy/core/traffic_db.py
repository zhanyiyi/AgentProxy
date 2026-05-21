import json
import shlex
import sqlite3
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from mitmproxy import http


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
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._get_conn() as conn:
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
                    size INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON flows(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON flows(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_method ON flows(method)")

    def save_flow(self, flow: http.HTTPFlow):
        req_body = self._get_safe_text(flow.request)
        resp_body = self._get_safe_text(flow.response) if flow.response else None
        status_code = flow.response.status_code if flow.response else None
        size = len(flow.response.content) if flow.response and flow.response.content else 0

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO flows (
                    id, url, method, status_code,
                    request_headers, request_body,
                    response_headers, response_body,
                    timestamp, size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url,
                    method=excluded.method,
                    status_code=excluded.status_code,
                    request_headers=excluded.request_headers,
                    request_body=excluded.request_body,
                    response_headers=excluded.response_headers,
                    response_body=excluded.response_body,
                    size=excluded.size
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
                ),
            )

    @staticmethod
    def _get_safe_text(message) -> Optional[str]:
        if message is None:
            return None
        try:
            content = getattr(message, 'content', None) or getattr(message, 'text', None)
            if content is None:
                return None
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return str(content)
        except Exception:
            return None

    def get_summary(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, url, method, status_code, response_headers, timestamp, size "
                "FROM flows ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                content_type = "unknown"
                if row["response_headers"]:
                    headers = _parse_headers(row["response_headers"])
                    content_type = headers.get("content-type", headers.get("Content-Type", "unknown"))
                result.append({
                    "id": row["id"],
                    "url": row["url"],
                    "method": row["method"],
                    "status_code": row["status_code"],
                    "content_type": content_type,
                    "size": row["size"],
                    "timestamp": row["timestamp"],
                })
            return result

    def get_detail(self, flow_id: str, body_preview_length: int = 2000) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
            row = cursor.fetchone()
            if not row:
                return None

            req_headers = _parse_headers(row["request_headers"])
            resp_headers = _parse_headers(row["response_headers"]) if row["response_headers"] else None

            simple_request = SimpleRequest(
                method=row["method"],
                url=row["url"],
                headers=req_headers,
                body=row["request_body"],
            )
            simple_response = (
                SimpleResponse(
                    status_code=row["status_code"],
                    headers=resp_headers,
                    body=row["response_body"],
                )
                if row["status_code"] is not None
                else None
            )

            return {
                "id": row["id"],
                "request": {
                    "method": simple_request.method,
                    "url": simple_request.url,
                    "headers": simple_request.headers,
                    "body_preview": (simple_request.body[:body_preview_length] if simple_request.body else None),
                },
                "response": {
                    "status_code": simple_response.status_code,
                    "headers": simple_response.headers,
                    "body_preview": (simple_response.body[:body_preview_length] if simple_response.body else None),
                }
                if simple_response
                else None,
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
