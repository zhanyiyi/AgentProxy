"""Parameter extractor with semantic tagging.

Goal: let the agent see "what can I mutate, and is anything sensitive" without
loading the request body. Each parameter (path/query/json/form/header/cookie)
is annotated with one or more semantic tags drawn from real SRC reports —
identity_param, ssrf_candidate, sql_candidate, state_token, etc.

The dictionaries themselves live in the YAML rule pack
(src/agent_proxy/config/defaults.yaml). Pass a `RuleConfig` to override them
at runtime.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs, parse_qsl

from ..config import RuleConfig


_PATH_NUMERIC = re.compile(r"^\d+$")
_PATH_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_PATH_OBJECTID = re.compile(r"^[0-9a-f]{24}$", re.I)


_DEFAULT_RULES: Optional[RuleConfig] = None


def _get_default_rules() -> RuleConfig:
    global _DEFAULT_RULES
    if _DEFAULT_RULES is None:
        from ..config import load_rule_config
        _DEFAULT_RULES = load_rule_config()
    return _DEFAULT_RULES


def _tags_for(name: str, semantic_dict: Dict[str, Set[str]]) -> List[str]:
    n = name.lower().strip()
    if not n:
        return []
    # Normalize: split on -, _, . into tokens; also keep the joined form for compound matches.
    tokens = set(re.split(r"[-_.\s]+", n))
    tokens.add(n)
    out: List[str] = []
    for cat, words in semantic_dict.items():
        if any(t in words for t in tokens):
            out.append(cat)
            continue
        # also catch "x_csrf_token" / "x-csrf" style by checking word-suffix match
        if any(n.endswith(w) or n.startswith(w) for w in words):
            out.append(cat)
    return out


def _walk_json(node: Any, prefix: str, sink: List[Dict[str, Any]],
               semantic_dict: Dict[str, Set[str]]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            tags = _tags_for(str(k), semantic_dict)
            sink.append({"name": key, "tags": tags})
            _walk_json(v, key, sink, semantic_dict)
    elif isinstance(node, list):
        # only descend the first item; flagged keys recur in the rest
        if node and isinstance(node[0], (dict, list)):
            _walk_json(node[0], f"{prefix}[]", sink, semantic_dict)


def _extract_path_params(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for seg in path.split("/"):
        if not seg:
            continue
        if _PATH_NUMERIC.match(seg):
            out.append({"name": "{id}", "tags": ["object_id_param"]})
        elif _PATH_UUID.match(seg):
            out.append({"name": "{uuid}", "tags": ["object_id_param"]})
        elif _PATH_OBJECTID.match(seg):
            out.append({"name": "{objectId}", "tags": ["object_id_param"]})
        elif len(seg) > 20 and re.match(r"^[a-zA-Z0-9_-]+$", seg):
            out.append({"name": "{token}", "tags": ["state_token"]})
    return out


def extract_params(flow_detail: Dict[str, Any],
                   rules: Optional[RuleConfig] = None) -> Dict[str, Any]:
    """Returns a layered parameter map keyed by location, each entry tagged with
    semantic categories drawn from the rule pack."""
    if not flow_detail:
        return {"error": "no flow"}
    if rules is None:
        rules = _get_default_rules()
    semantic_dict = rules.semantic_params
    interesting = rules.interesting_headers

    req = flow_detail.get("request") or {}
    url = req.get("url") or ""
    parsed = urlparse(url)
    headers = req.get("headers") or {}
    body = req.get("body") or ""

    out: Dict[str, Any] = {
        "method": req.get("method"),
        "url": url,
        "path": _extract_path_params(parsed.path),
        "query": [],
        "json": [],
        "form": [],
        "headers": [],
        "cookies": [],
    }

    for k in parse_qs(parsed.query).keys():
        out["query"].append({"name": k, "tags": _tags_for(k, semantic_dict)})

    ct = ""
    for hk, hv in headers.items():
        if hk.lower() == "content-type":
            ct = (hv or "").lower()
            break

    if body and len(body) <= 256 * 1024:
        if "application/json" in ct or (body.lstrip().startswith("{") or body.lstrip().startswith("[")):
            try:
                parsed_body = json.loads(body)
                _walk_json(parsed_body, "", out["json"], semantic_dict)
            except Exception:
                pass
        elif "x-www-form-urlencoded" in ct or "&" in body and "=" in body:
            try:
                for k, _ in parse_qsl(body):
                    out["form"].append({"name": k, "tags": _tags_for(k, semantic_dict)})
            except Exception:
                pass

    for hk, hv in headers.items():
        if hk.lower() in interesting:
            tags = _tags_for(hk, semantic_dict)
            value_kind = None
            if hk.lower() == "authorization" and isinstance(hv, str):
                if hv.startswith("Bearer "):
                    value_kind = "Bearer (JWT)" if hv[7:].count(".") == 2 else "Bearer"
                elif hv.startswith("Basic "):
                    value_kind = "Basic"
            if hk.lower() == "cookie" and isinstance(hv, str):
                cookie_names = [c.split("=", 1)[0].strip() for c in hv.split(";") if "=" in c]
                for cn in cookie_names:
                    out["cookies"].append({"name": cn, "tags": _tags_for(cn, semantic_dict)})
                value_kind = f"{len(cookie_names)} cookie(s)"
            out["headers"].append({"name": hk, "tags": tags, "kind": value_kind})

    return out
