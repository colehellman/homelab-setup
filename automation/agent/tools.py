"""
Tool implementations and Claude tool schemas for the homelab agent.
All API calls are read-only. Write tools are scoped to Discord, GitHub, and the docs repo.
"""

import os
import json
import requests
import subprocess
from datetime import datetime, timezone
from typing import Any

# --- Config ---

PROXMOX_HOST = os.environ["PROXMOX_HOST"]
PROXMOX_TOKEN_ID = os.environ["PROXMOX_TOKEN_ID"]
PROXMOX_TOKEN_SECRET = os.environ["PROXMOX_TOKEN_SECRET"]
TRUENAS_URL = os.environ["TRUENAS_LOCAL_URL"]
TRUENAS_API_KEY = os.environ["TRUENAS_LOCAL_API_KEY"]
GRAFANA_URL = os.environ["GRAFANA_URL"]
GRAFANA_API_KEY = os.environ["GRAFANA_API_KEY"]
TAILSCALE_API_KEY = os.environ["TAILSCALE_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
HOMELAB_REPO_PATH = os.environ.get("HOMELAB_REPO_PATH", "/opt/homelab-setup")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "colehellman/homelab-setup")
# Grafana datasource proxy ID for Prometheus. Find it at Grafana → Connections → Data Sources.
GRAFANA_PROMETHEUS_DS_ID = int(os.environ.get("GRAFANA_PROMETHEUS_DS_ID", "1"))

_PROXMOX_HEADERS = {"Authorization": f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"}
_GRAFANA_HEADERS = {"Authorization": f"Bearer {GRAFANA_API_KEY}", "Content-Type": "application/json"}
_TRUENAS_HEADERS = {"Authorization": f"Bearer {TRUENAS_API_KEY}"}
_GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# --- Tool implementations ---

def proxmox_list_containers() -> list[dict]:
    r = requests.get(
        f"https://{PROXMOX_HOST}/api2/json/nodes/pve/lxc",
        headers=_PROXMOX_HEADERS, verify=False, timeout=10
    )
    r.raise_for_status()
    return r.json().get("data", [])


def proxmox_container_status(vmid: int) -> dict:
    r = requests.get(
        f"https://{PROXMOX_HOST}/api2/json/nodes/pve/lxc/{vmid}/status/current",
        headers=_PROXMOX_HEADERS, verify=False, timeout=10
    )
    r.raise_for_status()
    return r.json().get("data", {})


def truenas_replication_jobs() -> list[dict]:
    r = requests.get(
        f"{TRUENAS_URL}/api/v2.0/replication",
        headers=_TRUENAS_HEADERS, verify=False, timeout=15
    )
    r.raise_for_status()
    jobs = r.json()
    # Return only relevant fields to keep context small
    return [
        {
            "name": j.get("name"),
            "state": j.get("state", {}).get("state"),
            "last_run": j.get("state", {}).get("datetime", {}).get("$date"),
            "error": j.get("state", {}).get("error"),
        }
        for j in jobs
    ]


def truenas_snapshot_counts() -> list[dict]:
    r = requests.get(
        f"{TRUENAS_URL}/api/v2.0/zfs/snapshot?limit=0",
        headers=_TRUENAS_HEADERS, verify=False, timeout=15
    )
    r.raise_for_status()
    snaps = r.json()
    counts: dict[str, int] = {}
    for s in snaps:
        ds = s.get("dataset", "unknown")
        counts[ds] = counts.get(ds, 0) + 1
    return [{"dataset": k, "count": v} for k, v in sorted(counts.items())]


def grafana_query(expr: str, range_minutes: int = 60) -> list[dict]:
    params = {
        "query": expr,
        "start": f"now-{range_minutes}m",
        "end": "now",
        "step": "60",
    }
    r = requests.get(
        f"{GRAFANA_URL}/api/datasources/proxy/{GRAFANA_PROMETHEUS_DS_ID}/api/v1/query_range",
        headers=_GRAFANA_HEADERS, params=params, timeout=15
    )
    r.raise_for_status()
    result = r.json().get("data", {}).get("result", [])
    # Summarize to last value per series
    return [
        {
            "labels": series.get("metric", {}),
            "last_value": series["values"][-1][1] if series.get("values") else None,
        }
        for series in result
    ]


def grafana_alert_history(hours: int = 168) -> list[dict]:
    """Return fired alerts from the past N hours (default 7 days)."""
    r = requests.get(
        f"{GRAFANA_URL}/api/v1/provisioning/alert-rules",
        headers=_GRAFANA_HEADERS, timeout=10
    )
    r.raise_for_status()
    return [
        {"title": rule.get("title"), "state": rule.get("state"), "folder": rule.get("folderUID")}
        for rule in r.json()
    ]


def tailscale_peers() -> list[dict]:
    r = requests.get(
        "https://api.tailscale.com/api/v2/tailnet/-/devices",
        headers={"Authorization": f"Bearer {TAILSCALE_API_KEY}"}, timeout=10
    )
    r.raise_for_status()
    devices = r.json().get("devices", [])
    now = datetime.now(timezone.utc)
    return [
        {
            "hostname": d.get("hostname"),
            "ip": d.get("addresses", [None])[0],
            "last_seen": d.get("lastSeen"),
            "online": d.get("online", False),
        }
        for d in devices
    ]


def discord_send(level: str, title: str, body: str, fields: list[dict] | None = None) -> dict:
    """
    level: 'info' | 'warning' | 'critical'
    fields: [{"name": str, "value": str, "inline": bool}]
    """
    color_map = {"info": 0x5865F2, "warning": 0xFEE75C, "critical": 0xED4245}
    color = color_map.get(level, 0x5865F2)
    embed = {
        "title": title,
        "description": body,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "homelab-agent"},
    }
    if fields:
        embed["fields"] = fields
    payload = {"embeds": [embed]}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    r.raise_for_status()
    return {"status": "sent"}


def github_create_issue(title: str, body: str, labels: list[str] | None = None) -> dict:
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers=_GITHUB_HEADERS, json=payload, timeout=10
    )
    r.raise_for_status()
    return {"url": r.json().get("html_url"), "number": r.json().get("number")}


def git_commit_docs(files: list[str], message: str) -> dict:
    """Commit updated doc files in the homelab repo."""
    try:
        subprocess.run(["git", "-C", HOMELAB_REPO_PATH, "add"] + files, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "-C", HOMELAB_REPO_PATH, "commit", "-m", message],
            capture_output=True, text=True
        )
        if result.returncode not in (0, 1):  # 1 = nothing to commit
            return {"status": "error", "detail": result.stderr}
        return {"status": "committed", "output": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "detail": str(e)}


# --- Claude tool schemas ---

TOOL_SCHEMAS = [
    {
        "name": "proxmox_list_containers",
        "description": "List all LXC containers on the Proxmox host with their status, CPU, and memory usage.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "proxmox_container_status",
        "description": "Get detailed resource usage for a specific LXC container by VMID.",
        "input_schema": {
            "type": "object",
            "properties": {"vmid": {"type": "integer", "description": "The LXC container VMID (e.g. 100, 101)"}},
            "required": ["vmid"],
        },
    },
    {
        "name": "truenas_replication_jobs",
        "description": "Get TrueNAS ZFS replication job status — last run time, state (SUCCESS/FAILED), and any errors.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "truenas_snapshot_counts",
        "description": "Get snapshot count per dataset on TrueNAS. Use to verify backup retention is working.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "grafana_query",
        "description": "Execute a PromQL query against Prometheus via Grafana. Returns last value per series.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expr": {"type": "string", "description": "PromQL expression"},
                "range_minutes": {"type": "integer", "description": "Query window in minutes (default 60)", "default": 60},
            },
            "required": ["expr"],
        },
    },
    {
        "name": "grafana_alert_history",
        "description": "List current state of all Grafana alert rules (firing/normal/pending).",
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "Look-back window in hours (default 168 = 7 days)", "default": 168}
            },
            "required": [],
        },
    },
    {
        "name": "tailscale_peers",
        "description": "Get all Tailscale peers with online/offline status and last-seen timestamp.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "discord_send",
        "description": "Send a Discord embed message to #homelab-alerts. level: 'info' | 'warning' | 'critical'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["info", "warning", "critical"]},
                "title": {"type": "string"},
                "body": {"type": "string", "description": "Markdown body text"},
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "inline": {"type": "boolean"},
                        },
                    },
                    "description": "Optional embed fields for structured data",
                },
            },
            "required": ["level", "title", "body"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a GitHub issue in the homelab-setup repo for tracking suggestions or action items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string", "description": "Markdown issue body"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['suggestion', 'maintenance']"},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "git_commit_docs",
        "description": "Commit updated documentation files to the homelab-setup git repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {"type": "array", "items": {"type": "string"}, "description": "Relative file paths to stage"},
                "message": {"type": "string", "description": "Git commit message"},
            },
            "required": ["files", "message"],
        },
    },
]


def execute_tool(name: str, inputs: dict) -> Any:
    """Dispatch a tool call to its implementation."""
    dispatch = {
        "proxmox_list_containers": lambda i: proxmox_list_containers(),
        "proxmox_container_status": lambda i: proxmox_container_status(i["vmid"]),
        "truenas_replication_jobs": lambda i: truenas_replication_jobs(),
        "truenas_snapshot_counts": lambda i: truenas_snapshot_counts(),
        "grafana_query": lambda i: grafana_query(i["expr"], i.get("range_minutes", 60)),
        "grafana_alert_history": lambda i: grafana_alert_history(i.get("hours", 168)),
        "tailscale_peers": lambda i: tailscale_peers(),
        "discord_send": lambda i: discord_send(i["level"], i["title"], i["body"], i.get("fields")),
        "github_create_issue": lambda i: github_create_issue(i["title"], i["body"], i.get("labels")),
        "git_commit_docs": lambda i: git_commit_docs(i["files"], i["message"]),
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(inputs)
    except Exception as e:
        return {"error": str(e), "tool": name}
