from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal


class InterceptionRule(BaseModel):
    id: str
    active: bool = True
    url_pattern: Optional[str] = None
    method: Optional[str] = None
    phase: Literal["request", "response"] = "request"
    action_type: Literal["inject_header", "replace_body", "block"] = "inject_header"
    key: Optional[str] = None
    value: Optional[str] = None
    search_pattern: Optional[str] = None

    model_config = {"extra": "ignore"}


class ScopeConfig(BaseModel):
    allowed_domains: List[str] = Field(default_factory=list)
    ignore_extensions: List[str] = Field(
        default_factory=lambda: [
            ".jpg", ".jpeg", ".png", ".gif", ".css", ".woff",
            ".ico", ".svg", ".webp", ".mp4", ".mp3", ".ts",
            ".m3u8", ".pdf", ".woff2",
        ]
    )
    ignore_methods: List[str] = Field(default_factory=lambda: ["OPTIONS"])


class SessionConfig(BaseModel):
    proxy_port: int = 8080
    proxy_host: str = "127.0.0.1"
    headless: bool = True
    ignore_https_errors: bool = True
    browser_timeout: int = 30000
    max_traffic_display: int = 50
    body_preview_length: int = 2000
    detail_body_limit: int = 51200


class FlowSummary(BaseModel):
    id: str
    url: str
    method: str
    status_code: Optional[int] = None
    content_type: str = "unknown"
    size: int = 0
    timestamp: Optional[float] = None


class FlowDetail(BaseModel):
    id: str
    request: Dict
    response: Optional[Dict] = None
    curl_command: Optional[str] = None


class AuthSignal(BaseModel):
    detected: bool = False
    signals: List[str] = Field(default_factory=list)
    flows: List[str] = Field(default_factory=list)


class AuthDetectionResult(BaseModel):
    detected_auth_types: List[str] = Field(default_factory=list)
    details: Dict[str, AuthSignal] = Field(default_factory=dict)


class FuzzAnomaly(BaseModel):
    payload: str
    anomaly: str
    status: Optional[int] = None
    len: Optional[int] = None


class FuzzResult(BaseModel):
    baseline_status: int
    baseline_len: int
    anomalies: List[FuzzAnomaly] = Field(default_factory=list)


class BrowserState(BaseModel):
    url: str = ""
    title: str = ""
    running: bool = False
