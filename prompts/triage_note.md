---
description: |
  Walk through the four-step triage checklist for a flow and save it.
  Invoke this prompt whenever you finish researching a flow — it primes you
  with the structure SRC researchers actually use, so notes are consistent
  across the session and the agent doesn't skip steps.
arguments:
  - name: flow_id
    description: The flow id you just finished researching.
    required: true
---

You just finished researching flow `{{ flow_id }}`:

- **{{ method }}** `{{ url }}`
- Status: `{{ status_code }}`
{{ existing_block }}
Now write a triage note via `note_add`. Fill ALL FOUR sections — keep each
to 1–3 short sentences. Don't skip a section just because nothing happened
there; "tested X, no anomaly" is exactly the kind of note future-you will
thank present-you for.

1. **scenario** — What is this endpoint doing in business terms? What could
   go wrong? What's notable in the captured traffic (auth headers? identity
   params? unusual response fields?)?

2. **sensitive_fields** — Which params / headers / cookies were testable?
   List their names + the semantic tags from `traffic_params` (identity,
   ssrf, sql, redirect, etc.). If you didn't run traffic_params yet, do
   that first.

3. **test_steps** — What did you actually try? Replays, mutations, diffs,
   fuzz. For each, what was the response? Cite concrete flow_ids when you
   created replay flows.

4. **conclusion** — Pick a verdict and justify it:
   - `vulnerable` — name the impact and point at the proof flow_id.
   - `not_vulnerable` — what makes you confident? Which angles did you
     cover? Note any assumptions.
   - `inconclusive` — what's still missing? Different account? Other
     payload class? OOB callback? Mention angles you skipped.

Then call:
note_add(flow_id="{{ flow_id }}", verdict="...", scenario="...",
         sensitive_fields="...", test_steps="...", conclusion="...")
