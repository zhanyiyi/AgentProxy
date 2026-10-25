"""Bounded baselines for snapshots already delivered to the caller.

Playwright owns element identities and iframe routing. This module only formats
changes and checks that a requested ref belongs to the delivered observation.
"""
from collections import OrderedDict
from dataclasses import dataclass
from difflib import unified_diff
import re
import uuid
from typing import FrozenSet, Optional

import yaml


_NODE_HEADER = re.compile(
    r'^[a-z][a-z0-9-]*(?: "(?:[^"\\]|\\.)*"| /.*?/)?'
    r'(?P<attributes>(?: \[[^\]\n]*\])*)$'
)
_REF = re.compile(r" \[ref=((?:f\d+)?e\d+)\]")


def _rendered_refs(text: str) -> FrozenSet[str]:
    """Read refs from node metadata, never from names or inline text values."""
    refs = set()

    def header(value):
        match = _NODE_HEADER.fullmatch(value)
        if match:
            refs.update(_REF.findall(match["attributes"]))

    def visit(node):
        if isinstance(node, list):
            for child in node:
                if isinstance(child, str):
                    header(child)
                else:
                    visit(child)
        elif isinstance(node, dict):
            for key, child in node.items():
                if isinstance(key, str):
                    header(key)
                if isinstance(child, (list, dict)):
                    visit(child)

    visit(yaml.safe_load(text))
    return frozenset(refs)


@dataclass(frozen=True)
class _Snapshot:
    snapshot_id: str
    text: Optional[str]
    refs: FrozenSet[str]


class SnapshotStore:
    """One latest observation per tab/frame, capped across all open scopes.

    A delta describes the complete next tree relative to its named baseline.
    Truncated output authorizes only its visible refs and cannot seed a delta.
    """

    def __init__(self, max_scopes: int = 32):
        self._latest = OrderedDict()
        self.max_scopes = max_scopes

    def clear(self):
        self._latest.clear()

    def drop_tab(self, tab_id: str):
        for key in list(self._latest):
            if key[0] == tab_id:
                del self._latest[key]

    def render(self, tab_id: str, frame: Optional[str], text: str,
               incremental: bool, max_chars: int):
        key = (tab_id, frame)
        previous = self._latest.get(key)
        snapshot_id = "snapshot_" + uuid.uuid4().hex[:12]
        truncated = len(text) > max_chars
        visible = text
        if truncated:
            # Never deliver a partial YAML node or authorize its hidden ref.
            last_newline = text.rfind("\n", 0, max_chars + 1)
            visible = text[:last_newline] if last_newline >= 0 else ""
        refs = _rendered_refs(visible)
        kind, base_snapshot_id, output = "full", None, visible
        if incremental and not truncated and previous and previous.text is not None:
            delta = "\n".join(unified_diff(
                previous.text.splitlines(), text.splitlines(),
                fromfile=previous.snapshot_id, tofile=snapshot_id, lineterm="",
            ))
            # Large replacements are clearer and cheaper as a fresh full tree.
            if len(delta) < len(text) and len(delta) <= max_chars:
                kind, base_snapshot_id, output = "delta", previous.snapshot_id, delta
        if truncated:
            output += f"\n...[truncated {len(text) - len(visible)} chars of {len(text)}]"
        self._latest[key] = _Snapshot(snapshot_id, None if truncated else text, refs)
        self._latest.move_to_end(key)
        while len(self._latest) > self.max_scopes:
            self._latest.popitem(last=False)
        return {"kind": kind, "snapshot_id": snapshot_id,
                "base_snapshot_id": base_snapshot_id, "snapshot": output,
                "truncated": truncated, "ref_count": len(refs)}

    def validate_ref(self, tab_id: str, frame: Optional[str],
                     snapshot_id: str, ref: str):
        current = self._latest.get((tab_id, frame))
        if current is None or current.snapshot_id != snapshot_id:
            raise ValueError("snapshot_id is stale or belongs to another tab/frame; request a new snapshot")
        if ref not in current.refs:
            raise ValueError("ref was not delivered in this snapshot; request a new snapshot")
