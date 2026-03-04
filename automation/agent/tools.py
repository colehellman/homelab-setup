"""
Tool implementations and Claude tool schemas for the homelab agent.

TOOL_SCHEMAS       — read-only tools used by scheduled runs (weekly/monthly/investigate)
WRITE_TOOL_SCHEMAS — additional write tools available only to the Discord bot
ALL_TOOL_SCHEMAS   — union of both, used by the interactive bot
"""

import os
import json
import requests
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
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
        f"https://{PROXMOX_HOST}/api2/json/nodes/proxmox/lxc",
        headers=_PROXMOX_HEADERS, verify=False, timeout=10
    )
    r.raise_for_status()
    return r.json().get("data", [])


def proxmox_container_status(vmid: int) -> dict:
    r = requests.get(
        f"https://{PROXMOX_HOST}/api2/json/nodes/proxmox/lxc/{vmid}/status/current",
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
        "start": int(time.time()) - range_minutes * 60,
        "end": int(time.time()),
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


# --- Write tool implementations (interactive / Discord bot only) ---

# SSH is allowed only to these hosts. homelab-agent's key must be in authorized_keys.
_SSH_ALLOWED_HOSTS = {
    "192.168.1.69",   # Proxmox host
    "192.168.1.250",  # TrueNAS
}


def proxmox_container_power(vmid: int, action: str) -> dict:
    """
    action: start | stop | reboot | shutdown
    Requires HomelabAgentRW role on the Proxmox token (VM.PowerMgmt).
    """
    valid = {"start", "stop", "reboot", "shutdown"}
    if action not in valid:
        return {"error": f"Invalid action '{action}'. Must be one of: {valid}"}
    r = requests.post(
        f"https://{PROXMOX_HOST}/api2/json/nodes/proxmox/lxc/{vmid}/status/{action}",
        headers=_PROXMOX_HEADERS, verify=False, timeout=30,
    )
    r.raise_for_status()
    return {"status": "accepted", "vmid": vmid, "action": action, "task": r.json().get("data")}


def proxmox_vm_power(vmid: int, action: str) -> dict:
    """Same as proxmox_container_power but for QEMU VMs."""
    valid = {"start", "stop", "reboot", "shutdown"}
    if action not in valid:
        return {"error": f"Invalid action '{action}'. Must be one of: {valid}"}
    r = requests.post(
        f"https://{PROXMOX_HOST}/api2/json/nodes/proxmox/qemu/{vmid}/status/{action}",
        headers=_PROXMOX_HEADERS, verify=False, timeout=30,
    )
    r.raise_for_status()
    return {"status": "accepted", "vmid": vmid, "action": action, "task": r.json().get("data")}


def proxmox_container_snapshot(vmid: int, name: str) -> dict:
    """
    Create a snapshot of an LXC container.
    Requires VM.Snapshot on the Proxmox token.
    """
    r = requests.post(
        f"https://{PROXMOX_HOST}/api2/json/nodes/proxmox/lxc/{vmid}/snapshot",
        headers=_PROXMOX_HEADERS,
        json={"snapname": name, "description": "auto by homelab-agent"},
        verify=False, timeout=30,
    )
    r.raise_for_status()
    return {"status": "accepted", "vmid": vmid, "snapshot": name, "task": r.json().get("data")}


def proxmox_list_vms() -> list[dict]:
    """List QEMU VMs on the Proxmox host."""
    r = requests.get(
        f"https://{PROXMOX_HOST}/api2/json/nodes/proxmox/qemu",
        headers=_PROXMOX_HEADERS, verify=False, timeout=10,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def docker_containers(vmid: int | None = None) -> list[dict]:
    """
    Get Docker container status for one or all running LXC containers.
    Uses 'pct exec <vmid> -- docker ps' via SSH to the Proxmox host.
    No direct SSH to LXCs required.
    """
    proxmox_ip = PROXMOX_HOST.split(":")[0]  # strip port if present

    def _ssh(cmd: str) -> str:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=10", f"root@{proxmox_ip}", cmd],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout

    # Determine which VMIDs to query
    if vmid is not None:
        vmids = [vmid]
    else:
        containers = proxmox_list_containers()
        vmids = [int(c["vmid"]) for c in containers if c.get("status") == "running"]

    results = []
    for vid in vmids:
        raw = _ssh(
            f"pct exec {vid} -- docker ps --format "
            "'{{.ID}}\\t{{.Image}}\\t{{.Status}}\\t{{.Names}}' 2>/dev/null"
        )
        containers_out = []
        for line in raw.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 4:
                containers_out.append({
                    "id": parts[0],
                    "image": parts[1],
                    "status": parts[2],
                    "name": parts[3],
                })
        results.append({"vmid": vid, "containers": containers_out})

    return results


def truenas_pool_scrub(pool_name: str) -> dict:
    """Start a ZFS scrub on a TrueNAS pool."""
    r = requests.post(
        f"{TRUENAS_URL}/api/v2.0/pool/id/{pool_name}/scrub",
        headers=_TRUENAS_HEADERS,
        json={"action": "START"},
        verify=False, timeout=15,
    )
    r.raise_for_status()
    return {"status": "scrub started", "pool": pool_name}


def check_url(url: str, timeout_s: int = 10) -> dict:
    """HTTP GET a URL and return status code, response time, and reachability."""
    try:
        start = time.time()
        r = requests.get(url, timeout=timeout_s, allow_redirects=True, verify=False)
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "url": url,
            "status_code": r.status_code,
            "ok": r.ok,
            "response_ms": elapsed_ms,
        }
    except requests.exceptions.Timeout:
        return {"url": url, "ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError as exc:
        return {"url": url, "ok": False, "error": str(exc)}


def ssh_run(host: str, command: str) -> dict:
    """
    Run a shell command on a whitelisted host via SSH.
    The homelab-agent SSH key (~/.ssh/id_ed25519) must be in authorized_keys on the target.
    Blocked commands: rm -rf, mkfs, fdisk, wipefs, dd if=
    """
    if host not in _SSH_ALLOWED_HOSTS:
        return {"error": f"Host {host!r} not in allowed list: {sorted(_SSH_ALLOWED_HOSTS)}"}

    # Rudimentary safety — block obviously destructive patterns
    _blocked = ["rm -rf", "mkfs", "fdisk", "wipefs", "dd if=", "> /dev/"]
    lower_cmd = command.lower()
    for pat in _blocked:
        if pat in lower_cmd:
            return {"error": f"Blocked: command contains '{pat}'"}

    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
         "-o", "ConnectTimeout=10", f"root@{host}", command],
        capture_output=True, text=True, timeout=60,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-1000:],
    }


# --- Write tool schemas ---

WRITE_TOOL_SCHEMAS = [
    {
        "name": "proxmox_container_power",
        "description": (
            "Start, stop, reboot, or shutdown an LXC container. "
            "ALWAYS confirm with the user before stop or shutdown. "
            "Snapshot first if the container has been running > 24h."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer", "description": "LXC container VMID"},
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "reboot", "shutdown"],
                    "description": "Power action to perform",
                },
            },
            "required": ["vmid", "action"],
        },
    },
    {
        "name": "proxmox_vm_power",
        "description": (
            "Start, stop, reboot, or shutdown a QEMU VM. "
            "ALWAYS confirm with the user before stop or shutdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer", "description": "QEMU VM VMID"},
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "reboot", "shutdown"],
                },
            },
            "required": ["vmid", "action"],
        },
    },
    {
        "name": "proxmox_container_snapshot",
        "description": "Create a snapshot of an LXC container. Use before risky operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer"},
                "name": {
                    "type": "string",
                    "description": "Snapshot name (alphanumeric, dashes OK, no spaces). E.g. 'pre-update-2026-03-04'",
                },
            },
            "required": ["vmid", "name"],
        },
    },
    {
        "name": "proxmox_list_vms",
        "description": "List QEMU VMs on the Proxmox host.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "docker_containers",
        "description": (
            "List Docker containers running inside LXC containers on Proxmox. "
            "Pass vmid to query a single container, or omit to query all running LXCs. "
            "Uses pct exec via Proxmox SSH — no direct LXC SSH required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {
                    "type": "integer",
                    "description": "LXC VMID to query. Omit to query all running LXCs.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "truenas_pool_scrub",
        "description": "Start a ZFS scrub on a TrueNAS pool to check for data errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pool_name": {"type": "string", "description": "TrueNAS pool name (e.g. 'data', 'tank')"},
            },
            "required": ["pool_name"],
        },
    },
    {
        "name": "check_url",
        "description": (
            "HTTP GET a URL and return status code, response time, and reachability. "
            "Use to check if a service is up from the homelab's perspective."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to check (e.g. 'http://192.168.1.100:8096/health')"},
                "timeout_s": {"type": "integer", "description": "Timeout in seconds (default 10)", "default": 10},
            },
            "required": ["url"],
        },
    },
    {
        "name": "ssh_run",
        "description": (
            "Run a shell command on a whitelisted host (192.168.1.69 = Proxmox, "
            "192.168.1.250 = TrueNAS) via SSH. "
            "Use for docker commands, journalctl, systemctl status, etc. "
            "Blocked: rm -rf, mkfs, fdisk, wipefs, dd if=."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Target host IP"},
                "command": {"type": "string", "description": "Shell command to run"},
            },
            "required": ["host", "command"],
        },
    },
]

ALL_TOOL_SCHEMAS = TOOL_SCHEMAS + WRITE_TOOL_SCHEMAS


# --- Context loader (shared with discord_bot) ---

def load_context() -> str:
    """Load README + containers.md from the homelab repo."""
    parts = []
    for rel in ["README.md", "inventory/containers.md"]:
        path = Path(HOMELAB_REPO_PATH) / rel
        if path.exists():
            parts.append(f"### {rel}\n\n{path.read_text()}")
    return "\n\n---\n\n".join(parts) if parts else "(docs not found)"


def execute_tool(name: str, inputs: dict) -> Any:
    """Dispatch a tool call to its implementation."""
    dispatch = {
        # Read tools
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
        # Write tools
        "proxmox_container_power": lambda i: proxmox_container_power(i["vmid"], i["action"]),
        "proxmox_vm_power": lambda i: proxmox_vm_power(i["vmid"], i["action"]),
        "proxmox_container_snapshot": lambda i: proxmox_container_snapshot(i["vmid"], i["name"]),
        "proxmox_list_vms": lambda i: proxmox_list_vms(),
        "docker_containers": lambda i: docker_containers(i.get("vmid")),
        "truenas_pool_scrub": lambda i: truenas_pool_scrub(i["pool_name"]),
        "check_url": lambda i: check_url(i["url"], i.get("timeout_s", 10)),
        "ssh_run": lambda i: ssh_run(i["host"], i["command"]),
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(inputs)
    except Exception as e:
        return {"error": str(e), "tool": name}
