"""Optional file-system prompt loader.

Loads MCP prompts from a local `prompts/` directory at the repo root. Each
prompt is a Markdown file with optional YAML front-matter (description +
argument schema) and an optional sibling `.py` file that produces dynamic
substitutions via a `context(session) -> dict` function.

Why a directory rather than packaged Python:
  - prompts are *private* intel curated by the operator (SRC playbook,
    target-specific tactics). They live alongside the project but are
    intentionally git-ignored — `pip install` does NOT ship them.
  - dropping new prompts in is a file-system action; no code edit, no
    rebuild, no deployment.

Format (one .md per prompt; .py is optional):

    prompts/<name>.md
        ---
        description: |
          Short, single-line is fine; multi-line YAML works too.
        arguments:
          - name: flow_id
            description: ...
            required: false
        ---
        Prompt body in markdown.

        Use {{ placeholder }} for any value that comes from the .py
        sibling's context() return value, or {{ arg_name }} to inline a
        prompt argument the caller passed.

    prompts/<name>.py    (OPTIONAL)
        def context(session, **args) -> dict:
            \"\"\"Return a flat str→str dict; keys map to {{ placeholder }}
            in the .md body. `session` is the SessionManager. **args
            are the prompt arguments declared in front-matter.\"\"\"
            return {"placeholder": "value"}

If the prompts directory is missing or empty the loader is a no-op and
AgentProxy operates normally with whatever in-code prompts are defined.
"""
from __future__ import annotations

import importlib.util
import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import Prompt

logger = logging.getLogger("agent_proxy.prompt_loader")


_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _split_front_matter(raw: str) -> tuple[Dict[str, Any], str]:
    """Return (metadata, body). Metadata is {} when no front-matter present."""
    m = _FRONT_MATTER_RE.match(raw)
    if not m:
        return {}, raw
    meta_text, body = m.group(1), m.group(2)
    try:
        meta = yaml.safe_load(meta_text) or {}
    except yaml.YAMLError as e:
        logger.warning("front-matter YAML invalid: %s; treating as plain markdown", e)
        return {}, raw
    if not isinstance(meta, dict):
        return {}, raw
    return meta, body


def _import_sibling_module(py_path: Path, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, py_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _render(body: str, context: Dict[str, Any]) -> str:
    """Substitute {{ key }} → context[key]. Missing keys render as empty string."""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in context:
            logger.debug("placeholder {{%s}} not in context; rendering empty", key)
        return str(context.get(key, ""))
    return _PLACEHOLDER_RE.sub(repl, body)


def _resolve_prompts_dir(explicit: Optional[Path] = None) -> Optional[Path]:
    """Find the prompts directory. None if absent.

    Order:
      1. Explicit argument (used by tests).
      2. AGENT_PROXY_PROMPTS_DIR environment variable.
      3. <cwd>/prompts/.
      4. <repo_root>/prompts/ (resolved by walking up from this file).
    """
    if explicit is not None:
        return explicit if explicit.is_dir() else None
    import os
    env = os.environ.get("AGENT_PROXY_PROMPTS_DIR")
    if env:
        p = Path(env).expanduser()
        return p if p.is_dir() else None
    cwd_candidate = Path.cwd() / "prompts"
    if cwd_candidate.is_dir():
        return cwd_candidate
    # repo-root fallback: src/agent_proxy/<this>.py → repo_root is parents[2]
    here = Path(__file__).resolve()
    repo_root_candidate = here.parents[2] / "prompts" if len(here.parents) >= 3 else None
    if repo_root_candidate and repo_root_candidate.is_dir():
        return repo_root_candidate
    return None


def _build_prompt_callable(
    name: str,
    description: str,
    body: str,
    arg_specs: List[Dict[str, Any]],
    context_fn: Optional[Callable[..., Dict[str, Any]]],
    session,
) -> Callable[..., Any]:
    """Synthesise an async function with a real signature matching arg_specs,
    so FastMCP's introspection produces the right MCP prompt schema."""
    arg_names = [str(a["name"]) for a in arg_specs]
    required = {a["name"] for a in arg_specs if a.get("required", False)}

    async def _runner(**kwargs):
        # Validate required args (FastMCP itself enforces, but be explicit)
        for r in required:
            if r not in kwargs or kwargs[r] is None:
                return f"Prompt `{name}` requires argument `{r}`."
        ctx: Dict[str, Any] = dict(kwargs)
        if context_fn is not None:
            try:
                supplied = context_fn(session=session, **kwargs)
                if supplied:
                    ctx.update(supplied)
            except Exception as e:
                logger.error("context() of prompt '%s' failed: %s", name, e)
                return (f"Prompt `{name}` context provider raised: {e}. "
                        "Check prompts/<name>.py for bugs.")
        return _render(body, ctx)

    if not arg_names:
        # FastMCP introspects the signature; a no-arg prompt should have no params.
        async def _noarg():
            return await _runner()
        _noarg.__name__ = name
        _noarg.__doc__ = description
        return _noarg

    # Build a real signature matching arg_names so MCP schema reflects it.
    # Required args have no default; optional args default to None.
    sig_parts = []
    for spec in arg_specs:
        n = str(spec["name"])
        if spec.get("required", False):
            sig_parts.append(f"{n}: str")
        else:
            sig_parts.append(f"{n}: str = None")
    sig_params = ", ".join(sig_parts)
    src = (
        f"async def _wrapper({sig_params}):\n"
        f"    return await _runner({', '.join(f'{n}={n}' for n in arg_names)})\n"
    )
    local_ns: Dict[str, Any] = {"_runner": _runner}
    exec(src, local_ns)
    fn = local_ns["_wrapper"]
    fn.__name__ = name
    fn.__doc__ = description
    return fn


def load_prompts(mcp: FastMCP, session, prompts_dir: Optional[Path] = None) -> int:
    """Discover and register every prompt in `prompts_dir`. Returns count."""
    pdir = _resolve_prompts_dir(prompts_dir)
    if pdir is None:
        logger.info("no prompts/ directory found — running without filesystem prompts")
        return 0
    md_files = sorted(
        p for p in pdir.glob("*.md")
        if p.is_file() and p.stem.lower() != "readme"
    )
    if not md_files:
        logger.info("prompts directory %s has no .md files", pdir)
        return 0

    count = 0
    for md_path in md_files:
        name = md_path.stem
        try:
            raw = md_path.read_text(encoding="utf-8")
            meta, body = _split_front_matter(raw)
            description = str(meta.get("description") or f"Prompt loaded from {md_path.name}").strip()
            arg_specs = list(meta.get("arguments") or [])

            py_sibling = md_path.with_suffix(".py")
            context_fn = None
            if py_sibling.exists():
                mod = _import_sibling_module(py_sibling, f"agent_proxy_prompt_{name}")
                if mod is None:
                    logger.warning("could not import %s; skipping context()", py_sibling)
                else:
                    context_fn = getattr(mod, "context", None)
                    if context_fn is None:
                        logger.warning("%s has no context() function; ignoring", py_sibling)

            fn = _build_prompt_callable(name, description, body, arg_specs, context_fn, session)
            mcp.add_prompt(Prompt.from_function(fn, name=name, description=description))
            logger.info("registered prompt '%s' from %s%s",
                        name, md_path.name,
                        " + .py" if context_fn else "")
            count += 1
        except Exception as e:
            logger.error("failed to register prompt from %s: %s", md_path, e)
    logger.info("prompt loader registered %d prompt(s) from %s", count, pdir)
    return count
