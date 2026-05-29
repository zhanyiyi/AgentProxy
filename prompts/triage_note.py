"""Dynamic context for triage_note.md.

Pulls flow's method/url/status (cheap, level=meta) and detects whether a note
already exists for the flow_id, so the markdown can warn the agent about
overwrite.
"""


def context(session, flow_id=None, **_args):
    if not flow_id:
        return {
            "flow_id": "",
            "method": "?",
            "url": "(no flow_id provided)",
            "status_code": "?",
            "existing_block": "",
        }

    detail = session.mitm.db.get_detail(flow_id, level="meta")
    if not detail:
        return {
            "flow_id": flow_id,
            "method": "?",
            "url": f"(flow `{flow_id}` not found — use traffic_list to find a valid id)",
            "status_code": "?",
            "existing_block": "",
        }

    req = detail.get("request") or {}
    resp = detail.get("response") or {}
    existing = session.mitm.db.get_note(flow_id)

    existing_block = ""
    if existing:
        existing_block = (
            "\n**An existing note is present** — calling note_add will OVERWRITE it. "
            f"Current verdict: `{existing['verdict']}`. Re-read with note_get if needed.\n"
        )

    return {
        "flow_id": flow_id,
        "method": req.get("method") or "?",
        "url": req.get("url") or "?",
        "status_code": resp.get("status_code") if resp else "?",
        "existing_block": existing_block,
    }
