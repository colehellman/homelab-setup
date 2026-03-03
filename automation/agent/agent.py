#!/usr/bin/env python3
"""
Homelab management agent.

Usage:
  python agent.py --mode weekly      # Sunday 04:00 via systemd timer
  python agent.py --mode monthly     # 1st of month 05:00 via systemd timer
  python agent.py --mode investigate --alert '{"alertname": "...", ...}'
"""

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

import anthropic

from db import init_db, log_run, recent_runs
from tools import TOOL_SCHEMAS, execute_tool

MODEL = "claude-sonnet-4-6"
HOMELAB_REPO_PATH = os.environ.get("HOMELAB_REPO_PATH", "/opt/homelab-setup")


# --- Context loading ---

def load_context() -> str:
    """Load README + containers.md from the repo to give the agent current homelab state."""
    parts = []
    for rel in ["README.md", "inventory/containers.md"]:
        path = Path(HOMELAB_REPO_PATH) / rel
        if path.exists():
            parts.append(f"### {rel}\n\n{path.read_text()}")
    return "\n\n---\n\n".join(parts) if parts else "(docs not found)"


# --- System prompt ---

SYSTEM_PROMPT = """\
You are an autonomous homelab management agent. You have read-only access to \
the homelab's infrastructure APIs and write access only to Discord notifications, \
GitHub issues, and the documentation repo.

Rules (non-negotiable):
1. Read widely, act narrowly. Query everything relevant before drawing conclusions.
2. Never take infrastructure actions (restart containers, modify configs, touch TrueNAS/Proxmox settings).
3. Post to Discord before and after any write action (GitHub issue, git commit).
4. Do not repeat findings already in recent run logs.
5. Be terse. Discord messages should be scannable in 30 seconds.
6. Only create GitHub issues for actionable, non-obvious improvements with clear benefit.
7. When suggesting doc updates, write the full updated content — do not summarize.

Homelab context (current state):

{context}
"""


# --- Agent loop ---

def run_agent(task_prompt: str, context: str, mode: str) -> str:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": task_prompt}]
    system = SYSTEM_PROMPT.format(context=context)

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8096,
            system=system,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract final text summary
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "(no text output)"

        if response.stop_reason != "tool_use":
            return f"Unexpected stop reason: {response.stop_reason}"

        # Execute tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

        messages.append({"role": "user", "content": tool_results})


# --- Schedule task prompts ---

WEEKLY_PROMPT = """\
Run the weekly homelab health digest. Steps:

1. Query all LXC containers (Proxmox) — check any stopped/degraded
2. Query Prometheus: disk usage (all instances), CPU 10m avg (all instances), memory % free
3. Check TrueNAS replication jobs — did they run in the last 26 hours?
4. Check TrueNAS snapshot counts per dataset — any dataset with 0 snapshots?
5. Check Tailscale peers — any offline > 48 hours?
6. Check Grafana alert rules — any currently firing?

Then:
- Post a single Discord digest (level='info') summarizing the week. \
  Include a fields list with one field per check. Flag anomalies clearly.
- If disk on any host is >75%, create a GitHub issue labeled ['maintenance'] \
  with specific remediation steps.
- Update README.md Health Status section with current data. \
  Commit with message: 'health-check: weekly digest YYYY-MM-DD'

Keep the Discord message under 20 lines. No fluff.
"""

MONTHLY_PROMPT = """\
Run the monthly homelab improvement analysis. Steps:

1. Query Prometheus for 30-day resource trends:
   - Average CPU per instance: avg_over_time(100 - rate(node_cpu_seconds_total{mode="idle"}[30d])[30d:1d])
   - Average memory free %: avg_over_time((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100)[30d:1d])
   - Peak disk usage: max_over_time((1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})[30d:1d])

2. Based on these trends, identify:
   a. Containers consistently under 10% CPU + memory — candidates for right-sizing
   b. Any container approaching disk/memory limits (>70% sustained)
   c. Services that could be consolidated

3. For each finding, create a GitHub issue labeled ['suggestion'] if:
   - The finding is actionable and specific (not generic advice)
   - The benefit is clear (cost, reliability, or performance)

4. Post a brief Discord summary (level='info') with issue links.

Do not create issues for obvious/known issues already tracked.
"""


def investigate_prompt(alert_payload: dict) -> str:
    return f"""\
Grafana alert received. Investigate and post diagnosis to Discord.

Alert payload:
{json.dumps(alert_payload, indent=2)}

Steps:
1. Query Prometheus for the specific metric mentioned in the alert
2. Check related LXC container status via Proxmox if applicable
3. Check recent Grafana alert history
4. If disk-related: query disk usage for all instances
5. If service-related: check Tailscale peer status

Then post ONE Discord message (level matching alert severity) with:
- What is wrong (1 sentence)
- Current metric value
- Likely cause
- Exact commands to diagnose/resolve

Do NOT take any infrastructure action. Diagnose only.
"""


# --- Entry point ---

def main():
    parser = argparse.ArgumentParser(description="Homelab management agent")
    parser.add_argument("--mode", required=True, choices=["weekly", "monthly", "investigate"])
    parser.add_argument("--alert", help="JSON alert payload (for investigate mode)")
    args = parser.parse_args()

    init_db()
    context = load_context()

    if args.mode == "weekly":
        prior = recent_runs("weekly", limit=3)
        prior_block = "\n".join(
            f"- {r['ts']} ({'OK' if r['success'] else 'FAIL'}): {r['summary']}"
            for r in prior
        )
        task = WEEKLY_PROMPT + (
            f"\n\nPrior weekly runs (do not repeat findings already reported):\n{prior_block}\n"
            if prior else ""
        )
    elif args.mode == "monthly":
        prior = recent_runs("monthly", limit=2)
        prior_block = "\n".join(
            f"- {r['ts']} ({'OK' if r['success'] else 'FAIL'}): {r['summary']}"
            for r in prior
        )
        task = MONTHLY_PROMPT + (
            f"\n\nPrior monthly runs (avoid duplicate GitHub issues):\n{prior_block}\n"
            if prior else ""
        )
    elif args.mode == "investigate":
        if not args.alert:
            print("--alert JSON required for investigate mode", file=sys.stderr)
            sys.exit(1)
        try:
            alert = json.loads(args.alert)
        except json.JSONDecodeError as e:
            print(f"Invalid alert JSON: {e}", file=sys.stderr)
            sys.exit(1)
        task = investigate_prompt(alert)
    else:
        sys.exit(1)

    success = True
    summary = ""
    try:
        summary = run_agent(task, context, args.mode)
        print(summary)
    except Exception:
        success = False
        summary = traceback.format_exc()
        print(summary, file=sys.stderr)
        sys.exit(1)
    finally:
        log_run(args.mode, success, summary[:500])


if __name__ == "__main__":
    main()
