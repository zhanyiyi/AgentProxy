"""Smoke tests for the file-system prompt loader.

Covers:
- empty/missing prompts dir → no-op
- static prompt (md only, no front-matter) registers with default description
- prompt with front-matter description loads description correctly
- prompt with arguments + .py sibling renders dynamic context
- required vs optional argument schema is reflected in MCP prompt args
- README.md is skipped (case-insensitive)
- bad YAML front-matter is logged and falls back to plain markdown
- {{ placeholder }} substitution works; missing placeholders render empty
"""
import asyncio
import os
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_proxy.core.session_manager import SessionManager   # noqa: E402
from agent_proxy.models import SessionConfig   # noqa: E402
from agent_proxy.prompt_loader import load_prompts   # noqa: E402


def _make_mcp():
    from mcp.server.fastmcp import FastMCP
    return FastMCP("Test")


def _make_session():
    return SessionManager(config=SessionConfig(proxy_port=29999, headless=True))


async def main():
    failed = 0

    # 1. Missing dir → no-op (returns 0, registers nothing)
    mcp = _make_mcp()
    s = _make_session()
    n = load_prompts(mcp, s, prompts_dir=Path("/definitely/not/here"))
    if n != 0:
        print(f"  [FAIL] missing dir should return 0, got {n}"); failed += 1
    else:
        print("  [ok] missing prompts dir → no-op")

    with tempfile.TemporaryDirectory() as tmp:
        pdir = Path(tmp)

        # 2. Empty dir → no-op
        mcp = _make_mcp()
        n = load_prompts(mcp, _make_session(), prompts_dir=pdir)
        if n != 0:
            print(f"  [FAIL] empty dir should return 0, got {n}"); failed += 1
        else:
            print("  [ok] empty prompts dir → no-op")

        # 3. Static prompt — no front-matter
        (pdir / "static.md").write_text("Hello, world.")
        mcp = _make_mcp()
        n = load_prompts(mcp, _make_session(), prompts_dir=pdir)
        if n != 1:
            print(f"  [FAIL] static.md should register; got {n}"); failed += 1
        else:
            prompts = await mcp.list_prompts()
            names = {p.name for p in prompts}
            if "static" not in names:
                print(f"  [FAIL] static prompt missing: {names}"); failed += 1
            else:
                rendered = await mcp.get_prompt("static", {})
                if "Hello, world." in rendered.messages[0].content.text:
                    print("  [ok] static prompt renders body verbatim")
                else:
                    print(f"  [FAIL] body not rendered"); failed += 1

        # 4. Front-matter with description + placeholder via arg
        (pdir / "greet.md").write_text(textwrap.dedent("""\
            ---
            description: Greet a user by name
            arguments:
              - name: who
                required: true
            ---
            Hello, {{ who }}!
            """))
        mcp = _make_mcp()
        n = load_prompts(mcp, _make_session(), prompts_dir=pdir)
        prompts = await mcp.list_prompts()
        greet = next((p for p in prompts if p.name == "greet"), None)
        if not greet:
            print("  [FAIL] greet not registered"); failed += 1
        elif greet.description != "Greet a user by name":
            print(f"  [FAIL] description: {greet.description!r}"); failed += 1
        elif not greet.arguments or greet.arguments[0].name != "who":
            print(f"  [FAIL] who arg missing"); failed += 1
        elif greet.arguments[0].required is not True:
            print(f"  [FAIL] who should be required: {greet.arguments[0].required}")
            failed += 1
        else:
            print("  [ok] front-matter description + required arg")
            rendered = await mcp.get_prompt("greet", {"who": "alice"})
            if "Hello, alice!" in rendered.messages[0].content.text:
                print("  [ok] argument substituted via {{ who }}")
            else:
                print(f"  [FAIL] sub: {rendered.messages[0].content.text!r}")
                failed += 1

        # 5. Optional argument
        (pdir / "opt.md").write_text(textwrap.dedent("""\
            ---
            description: Optional arg test
            arguments:
              - name: tag
                required: false
            ---
            Tag={{ tag }}
            """))
        mcp = _make_mcp()
        load_prompts(mcp, _make_session(), prompts_dir=pdir)
        prompts = await mcp.list_prompts()
        opt = next(p for p in prompts if p.name == "opt")
        if opt.arguments[0].required:
            print(f"  [FAIL] opt arg should be NOT required"); failed += 1
        else:
            print("  [ok] optional arg correctly NOT required")

        # 6. .py sibling provides context
        (pdir / "dyn.md").write_text(textwrap.dedent("""\
            ---
            description: Uses sibling context
            ---
            count={{ count }}, who={{ who }}
            """))
        (pdir / "dyn.py").write_text(textwrap.dedent("""\
            def context(session, **args):
                return {"count": 42, "who": "bob"}
            """))
        mcp = _make_mcp()
        load_prompts(mcp, _make_session(), prompts_dir=pdir)
        rendered = await mcp.get_prompt("dyn", {})
        body = rendered.messages[0].content.text
        if "count=42" in body and "who=bob" in body:
            print("  [ok] sibling context() values substituted")
        else:
            print(f"  [FAIL] sibling sub: {body!r}"); failed += 1

        # 7. README.md is skipped
        (pdir / "README.md").write_text("just docs")
        mcp = _make_mcp()
        n = load_prompts(mcp, _make_session(), prompts_dir=pdir)
        names = {p.name for p in (await mcp.list_prompts())}
        if "README" in names:
            print("  [FAIL] README.md should be skipped"); failed += 1
        else:
            print("  [ok] README.md skipped")

        # 8. Bad YAML → fallback to plain markdown
        (pdir / "bad.md").write_text(textwrap.dedent("""\
            ---
            description: [unterminated
            ---
            But the body is fine.
            """))
        mcp = _make_mcp()
        load_prompts(mcp, _make_session(), prompts_dir=pdir)
        prompts = await mcp.list_prompts()
        bad = next((p for p in prompts if p.name == "bad"), None)
        if not bad:
            print("  [FAIL] bad.md should register as plain md"); failed += 1
        else:
            rendered = await mcp.get_prompt("bad", {})
            txt = rendered.messages[0].content.text
            if "But the body is fine." in txt:
                print("  [ok] malformed front-matter falls back gracefully")
            else:
                print(f"  [FAIL] body lost: {txt!r}"); failed += 1

        # 9. Missing placeholder → empty (not crash)
        (pdir / "miss.md").write_text("missing={{ nope }}, present={{ y }}")
        (pdir / "miss.py").write_text("def context(session, **args): return {'y': 'YES'}")
        mcp = _make_mcp()
        load_prompts(mcp, _make_session(), prompts_dir=pdir)
        rendered = await mcp.get_prompt("miss", {})
        txt = rendered.messages[0].content.text
        if "missing=, present=YES" in txt:
            print("  [ok] missing placeholder renders empty")
        else:
            print(f"  [FAIL] missing handling: {txt!r}"); failed += 1

        # 10. Crashing context() returns descriptive error, doesn't kill server
        (pdir / "boom.md").write_text("---\ndescription: boom\n---\nx={{ x }}")
        (pdir / "boom.py").write_text("def context(session, **args): raise RuntimeError('kaboom')")
        mcp = _make_mcp()
        load_prompts(mcp, _make_session(), prompts_dir=pdir)
        rendered = await mcp.get_prompt("boom", {})
        txt = rendered.messages[0].content.text
        if "kaboom" in txt and "context provider raised" in txt:
            print("  [ok] context() exception → descriptive error to caller")
        else:
            print(f"  [FAIL] crash handling: {txt!r}"); failed += 1

    if failed == 0:
        print("\n" + "=" * 50)
        print("ALL prompt-loader smoke tests PASSED")
        print("=" * 50)
    else:
        print(f"\n{failed} test(s) failed")
        sys.exit(1)


async def test_prompt_loader_suite_runs():
    """pytest wrapper (asyncio_mode=auto): non-raising run == pass."""
    await main()


if __name__ == "__main__":
    asyncio.run(main())
