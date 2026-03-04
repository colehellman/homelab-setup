# Automation

Homelab automation in three layers, each additive and independent.

## Layer 0 — Alert Cleanup (Done)

Existing tools fixed to be non-noisy before adding new ones.
See [`monitoring-security/alerts.md`](../monitoring-security/alerts.md).

## Layer 1 — Existing Tools Configured (Done/Partial)

| Tool | Where | Status |
|------|-------|--------|
| Watchtower | LXC 101, 102 | ✅ Running (daily 03:00) |
| Watchtower | LXC 100, 210 | ⏳ Import in Dockge + fill `.env` |
| TrueNAS alerts → Discord | 192.168.1.250 | ⏳ Manual: System → Alert Settings → Slack |
| PBS alerts → Discord | 192.168.1.200 | ⏳ Manual: Configuration → Notifications → Webhook |

See [`docker-platform/watchtower.md`](../docker-platform/watchtower.md) for Watchtower docs.

## Layer 2 — Claude Agent (Ready to Deploy)

A minimal Python agent that handles what the tools above cannot:
- Weekly digest: synthesize all sources → single Discord summary + doc commit
- Monthly suggestions: analyze 30-day trends → GitHub issues
- Alert investigation: Grafana webhook → query sources → Discord diagnosis

**The agent is read-only by default.** It cannot restart containers, modify configs,
or touch infrastructure. It queries, thinks, and communicates.

### Files

```
automation/
├── agent/
│   ├── agent.py            Entry point (--mode weekly|monthly|investigate)
│   ├── tools.py            All tool implementations + Claude tool schemas
│   ├── db.py               SQLite run log + alert dedup
│   ├── webhook_server.py   FastAPI :8765 — receives Grafana alert POSTs
│   └── requirements.txt
├── ansible/
│   ├── site.yml            Provision LXC 220
│   ├── inventory.yml       Set agent IP here after LXC creation
│   ├── vault.yml.example   Copy → vault.yml, encrypt, fill in secrets
│   └── roles/homelab-agent/
│       ├── tasks/main.yml
│       └── templates/agent.env.j2
└── systemd/
    ├── homelab-agent-webhook.service   Always-on FastAPI
    ├── homelab-agent@.service          One-shot parametrized run
    ├── homelab-agent-weekly.timer      Sun 04:00
    └── homelab-agent-monthly.timer     1st of month 05:00
```

### Deployment Steps

1. **Create LXC 220** in Proxmox (Debian 12, 1 vCPU, 1GB RAM, 8GB disk)
2. **Update inventory**: set `ansible_host` in `automation/ansible/inventory.yml`
3. **Create API tokens** (read-only):
   - Proxmox: Datacenter → API Tokens → create token with `PVEAuditor` role
   - TrueNAS: System → API Keys → create key (Readonly group)
   - Grafana: Administration → Service accounts → Viewer role
   - Tailscale: admin.tailscale.com → Settings → Keys → API key (Devices: read)
   - GitHub: github.com → Settings → Developer settings → Fine-grained token
     - Scope: `homelab-setup` repo only; permissions: `issues: write`, `contents: write`
4. **Fill in vault**: `cp vault.yml.example vault.yml && ansible-vault encrypt vault.yml`
   Then edit with `ansible-vault edit vault.yml`
5. **Run playbook**: `ansible-playbook automation/ansible/site.yml -i automation/ansible/inventory.yml --ask-vault-pass`
6. **Connect Grafana to webhook**: Alerting → Contact points → Add webhook: `http://192.168.1.LXC220:8765/alert`
7. **Test**: `ssh root@192.168.1.LXC220 "sudo -u homelab-agent /opt/homelab-agent/venv/bin/python /opt/homelab-agent/agent.py --mode weekly"`

### Security

- Agent runs as `homelab-agent` system user (no login shell)
- Secrets in `/etc/homelab-agent/agent.env` (640 root:homelab-agent)
- systemd hardening: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`
- API tokens are read-only on all services except GitHub (issues+contents on one repo)
- Webhook server has no auth (internal-only, not exposed via NPM)
