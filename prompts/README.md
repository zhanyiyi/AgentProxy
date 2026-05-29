# AgentProxy `prompts/` directory

Local, **private** MCP prompts that get auto-loaded when AgentProxy starts.
Anything in here is your operator-curated playbook — high-value SRC tactics
you don't necessarily want shipped publicly with the package.

## Contract

- The repo's `.gitignore` excludes `prompts/` so nothing here is committed
  unless you opt in.
- Each `.md` file becomes one MCP prompt (name = filename stem).
- Optional `.py` sibling provides dynamic context.
- If `prompts/` is missing or empty, AgentProxy still starts normally —
  it just registers zero prompts.

## File layout per prompt

```
prompts/
├── pentest_workflow.md     ← required: front-matter + body
├── pentest_workflow.py     ← optional: context(session, **args) -> dict
├── triage_note.md
└── triage_note.py
```

## .md format

```yaml
---
description: One-line description (shown in MCP prompt list)
arguments:
  - name: flow_id           # appears as a prompt argument
    description: target flow id
    required: false
---

Markdown body. Use {{ placeholder }} to inject values from the .py
sibling's context() function or to inline a prompt argument by name.
```

## .py format (optional)

```python
def context(session, **args) -> dict:
    """Return a flat dict of placeholder substitutions.
    `session` is the live SessionManager; **args are the prompt
    arguments declared in the .md front-matter."""
    status = session.get_status()
    return {
        "snapshot": "...",
        "stage_hint": "...",
    }
```

If a placeholder is referenced in the .md but not provided by `context()`
or arguments, it renders as empty string (with a debug log).

## Loader resolution order

1. Argument passed explicitly by tests/embed
2. `AGENT_PROXY_PROMPTS_DIR` env var
3. `<cwd>/prompts/`
4. `<repo_root>/prompts/` (this directory)
5. None — loader is a no-op

## Why .md not .yaml

Prompt bodies are 100+ line markdown documents. YAML's block-scalars are
hostile to multi-line markdown editing (preview, fold, copy-paste, formatter
support all suffer). Front-matter on top of native markdown gives the
metadata we need without making the body a YAML string.

## Adding a new prompt

```bash
# minimal static prompt (no dynamic state)
cat > prompts/example.md <<'EOF'
---
description: Example prompt
---
This is the body. Calling `example` returns this text.
EOF
# restart AgentProxy → prompt is registered
```

For a dynamic prompt, drop a `prompts/example.py` next to it with a
`context(session)` function. See `pentest_workflow.py` for a reference
implementation.

## Privacy & secrets

This directory is local intel. Treat it like `.env`:

- never commit (the repo's .gitignore enforces this)
- never include real customer / target identifiers
- credentials should still go in environment variables, not prompt bodies
