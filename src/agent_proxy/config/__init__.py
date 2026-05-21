"""Rule pack loader.

A `RuleConfig` is the merged, validated rule pack used by passive scanner,
parameter extractor, and fuzz engine. It comes from:

    bundled defaults.yaml  (always)
            ⊕
    user override yaml     (from --config / AGENT_PROXY_CONFIG / cwd lookup)

Merge is recursive for dicts; lists at the leaf level are *replaced*, not
appended. This is the simplest behaviour to reason about: if you want to add
one secret_leak rule, copy the whole `body_rules` list and append. Trying to
do "add but keep defaults" with a separate syntax invites confusion.
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

logger = logging.getLogger("agent_proxy.config")

_BUNDLED_DEFAULTS = Path(__file__).parent / "defaults.yaml"


@dataclass
class BodyRule:
    id: str
    severity: str
    category: str
    kind: str
    pattern: re.Pattern


@dataclass
class RuleConfig:
    semantic_params: Dict[str, Set[str]] = field(default_factory=dict)
    interesting_headers: Set[str] = field(default_factory=set)
    debug_paths: re.Pattern = field(default_factory=lambda: re.compile(r"^$"))
    sensitive_param_names: Set[str] = field(default_factory=set)
    body_rules: List[BodyRule] = field(default_factory=list)
    fuzz_payloads: Dict[str, List[str]] = field(default_factory=dict)
    source_paths: List[str] = field(default_factory=list)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge. Lists & scalars in `override` REPLACE those in `base`."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _compile_flags(flags_str: Optional[str]) -> int:
    if not flags_str:
        return 0
    f = 0
    for ch in flags_str.lower():
        if ch == "i":
            f |= re.IGNORECASE
        elif ch == "m":
            f |= re.MULTILINE
        elif ch == "s":
            f |= re.DOTALL
        elif ch == "x":
            f |= re.VERBOSE
    return f


def _build_debug_paths(paths: List[str]) -> re.Pattern:
    if not paths:
        return re.compile(r"^$")
    return re.compile("|".join(paths), re.IGNORECASE)


def _to_set(items) -> Set[str]:
    if not items:
        return set()
    return {str(x).lower() for x in items}


def _parse(raw: Dict[str, Any], source_paths: List[str]) -> RuleConfig:
    cfg = RuleConfig(source_paths=source_paths)

    sp = raw.get("semantic_params") or {}
    cfg.semantic_params = {
        cat: _to_set(words) for cat, words in sp.items()
    }

    cfg.interesting_headers = _to_set(raw.get("interesting_headers"))

    pscan = raw.get("passive_scan") or {}
    cfg.debug_paths = _build_debug_paths(pscan.get("debug_paths") or [])
    cfg.sensitive_param_names = _to_set(pscan.get("sensitive_param_names"))

    rules: List[BodyRule] = []
    for entry in pscan.get("body_rules") or []:
        try:
            pat = re.compile(entry["regex"], _compile_flags(entry.get("flags")))
        except re.error as e:
            logger.warning("body_rule '%s' has invalid regex (%s); skipped",
                           entry.get("id", "?"), e)
            continue
        rules.append(BodyRule(
            id=str(entry["id"]),
            severity=str(entry.get("severity", "info")),
            category=str(entry.get("category", "")),
            kind=str(entry.get("kind", "finding")),
            pattern=pat,
        ))
    cfg.body_rules = rules

    cfg.fuzz_payloads = {
        str(k): [str(p) for p in (v or [])]
        for k, v in (raw.get("fuzz_payloads") or {}).items()
    }
    return cfg


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    return data


def resolve_config_path(explicit: Optional[str] = None) -> Optional[Path]:
    """Find the user-supplied override yaml, in priority order:
    1. explicit argument (CLI flag)
    2. AGENT_PROXY_CONFIG env var
    3. ./agent_proxy.yaml in current working directory
    Returns None if no user file exists — bundled defaults will be the only source.
    """
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"--config path does not exist: {p}")
        return p
    env = os.environ.get("AGENT_PROXY_CONFIG")
    if env:
        p = Path(env).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"AGENT_PROXY_CONFIG does not exist: {p}")
        return p
    cwd_default = Path.cwd() / "agent_proxy.yaml"
    if cwd_default.exists():
        return cwd_default
    return None


def load_rule_config(user_config_path: Optional[str] = None) -> RuleConfig:
    sources: List[str] = []
    base = _read_yaml(_BUNDLED_DEFAULTS)
    sources.append(str(_BUNDLED_DEFAULTS))

    user_path = resolve_config_path(user_config_path)
    if user_path:
        try:
            user = _read_yaml(user_path)
            base = _deep_merge(base, user)
            sources.append(str(user_path))
            logger.info("rule_config_loaded user_override=%s", user_path)
        except Exception as e:
            logger.error("Failed to load user config %s: %s. Using bundled defaults only.",
                         user_path, e)
    else:
        logger.info("rule_config_loaded bundled_only=%s", _BUNDLED_DEFAULTS)

    return _parse(base, sources)


def to_inspectable_dict(cfg: RuleConfig) -> Dict[str, Any]:
    """Render a RuleConfig back into a plain dict for the config_show MCP tool."""
    return {
        "source_paths": cfg.source_paths,
        "semantic_params": {k: sorted(v) for k, v in cfg.semantic_params.items()},
        "interesting_headers": sorted(cfg.interesting_headers),
        "passive_scan": {
            "debug_paths_regex": cfg.debug_paths.pattern,
            "sensitive_param_names": sorted(cfg.sensitive_param_names),
            "body_rules": [
                {
                    "id": r.id, "severity": r.severity,
                    "category": r.category, "kind": r.kind,
                    "regex": r.pattern.pattern,
                }
                for r in cfg.body_rules
            ],
        },
        "fuzz_payloads": {k: list(v) for k, v in cfg.fuzz_payloads.items()},
        "fuzz_categories": sorted(cfg.fuzz_payloads.keys()),
    }
