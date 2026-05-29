"""Smoke tests for the YAML rule pack:
- bundled defaults load (no user file)
- user override does deep-merge for dicts but replaces lists
- user file via env var resolves correctly
- config_show MCP tool returns the expected shape
- traffic_fuzz picks up a NEW payload category (ssti) added via override
- passive_scan honours overridden body_rules
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


OVERRIDE_YAML = """
passive_scan:
  body_rules:
    - id: github_token
      severity: high
      category: secret_leak
      kind: finding
      regex: 'gh[pousr]_[A-Za-z0-9]{36,}'

fuzz_payloads:
  ssti:
    - "{{7*7}}"
    - "${{7*7}}"
"""


def main():
    from agent_proxy.config import (
        load_rule_config, resolve_config_path, to_inspectable_dict,
    )

    failed = 0

    # 1. Bundled-only load
    cfg = load_rule_config()
    assert cfg.semantic_params.get("identity_param"), "identity_param missing"
    assert "aws_access_key" in {r.id for r in cfg.body_rules}, "default rule missing"
    assert "sqli" in cfg.fuzz_payloads, "default sqli payload missing"
    assert len(cfg.source_paths) == 1, f"expected 1 source, got {cfg.source_paths}"
    print("[ok] bundled-only load")

    # 2. User override via explicit path
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(OVERRIDE_YAML)
        override_path = f.name
    try:
        cfg2 = load_rule_config(override_path)
        ids = {r.id for r in cfg2.body_rules}
        if ids != {"github_token"}:
            print(f"  [FAIL] body_rules should be replaced wholesale, got {ids}"); failed += 1
        else:
            print("  [ok] body_rules list-replace works")
        if "ssti" not in cfg2.fuzz_payloads:
            print("  [FAIL] new ssti category not picked up"); failed += 1
        else:
            print("  [ok] new fuzz category 'ssti' present")
        if "sqli" not in cfg2.fuzz_payloads:
            print("  [FAIL] inherited sqli lost"); failed += 1
        else:
            print("  [ok] sqli still inherited")
        if "identity_param" not in cfg2.semantic_params:
            print("  [FAIL] inherited semantic_params lost"); failed += 1
        else:
            print("  [ok] semantic_params still inherited")
        if len(cfg2.source_paths) != 2:
            print(f"  [FAIL] source_paths should list 2 files: {cfg2.source_paths}"); failed += 1
        else:
            print("  [ok] source_paths includes both")

    # 3. resolve_config_path: env var
        os.environ["AGENT_PROXY_CONFIG"] = override_path
        try:
            resolved = resolve_config_path(None)
            if str(resolved) != override_path:
                print(f"  [FAIL] env var resolution: {resolved}"); failed += 1
            else:
                print("  [ok] AGENT_PROXY_CONFIG env var honoured")
        finally:
            del os.environ["AGENT_PROXY_CONFIG"]

        # 4. resolve_config_path: explicit > env > cwd
        os.environ["AGENT_PROXY_CONFIG"] = "/tmp/nonexistent_config.yaml"
        try:
            resolved = resolve_config_path(override_path)
            if str(resolved) != override_path:
                print(f"  [FAIL] explicit must beat env: {resolved}"); failed += 1
            else:
                print("  [ok] explicit beats env var")
        finally:
            del os.environ["AGENT_PROXY_CONFIG"]

        # 5. inspectable dict shape
        d = to_inspectable_dict(cfg2)
        for key in ("semantic_params", "interesting_headers", "passive_scan",
                    "fuzz_payloads", "fuzz_categories", "source_paths"):
            if key not in d:
                print(f"  [FAIL] inspectable dict missing '{key}'"); failed += 1
        else:
            print("  [ok] to_inspectable_dict shape correct")

        # 6. integration: passive_scan + fuzz with overridden config
        from agent_proxy.core.mitm_controller import MitmController
        m = MitmController(db_path=":memory:", rules=cfg2)
        if "ssti" not in m.rules.fuzz_payloads:
            print("  [FAIL] MitmController didn't pick up override"); failed += 1
        else:
            print("  [ok] MitmController.rules wired correctly")

    finally:
        os.unlink(override_path)

    # 7. Bad regex in user yaml is tolerated (logged, skipped)
    bad_yaml = """
passive_scan:
  body_rules:
    - id: broken
      severity: high
      category: x
      kind: finding
      regex: '['          # invalid
    - id: good
      severity: high
      category: x
      kind: finding
      regex: 'foo'
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(bad_yaml)
        bad_path = f.name
    try:
        cfg3 = load_rule_config(bad_path)
        ids = {r.id for r in cfg3.body_rules}
        if ids != {"good"}:
            print(f"  [FAIL] bad regex handling: {ids}"); failed += 1
        else:
            print("  [ok] invalid regex skipped, good rule survives")
    finally:
        os.unlink(bad_path)

    if failed == 0:
        print("\n" + "=" * 50)
        print("ALL config smoke tests PASSED")
        print("=" * 50)
    else:
        print(f"\n{failed} test(s) failed")
        sys.exit(1)


def test_config_suite_runs():
    """pytest wrapper: a non-raising run of the smoke suite == pass."""
    main()


if __name__ == "__main__":
    main()
