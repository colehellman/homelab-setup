# Alerting

All alerts route to Discord. Two channels:
- **`#homelab-alerts`** — live alerts from Uptime Kuma, Grafana, TrueNAS, PBS, Watchtower
- **`#homelab-digest`** — weekly summary from the Claude agent (Phase 2)

---

## Grafana Alerts (LXC 102 — `192.168.1.177:3000`)

Contact point: **Discord-SRE** (Discord webhook, configured in Grafana → Alerting → Contact points)
Default routing: all alerts → Discord-SRE, critical alerts repeat every 1h

### Active Alert Rules

| Rule | Folder | Fires After | Description |
|------|--------|-------------|-------------|
| CRITICAL: RealDebrid API Failures | Hellflix Alerts | 2m | rclone error count spike |
| WARNING: High Disk Usage (>80%) | Infrastructure Alerts | 15m | Root fs >80% on any node-exporter host |
| CRITICAL: Disk Nearly Full (>90%) | Infrastructure Alerts | 5m | Root fs >90% — imminent service failures |
| WARNING: High CPU Usage (>85%) | Infrastructure Alerts | 10m | 10m avg CPU >85% on any host |
| WARNING: Low Memory (<15% free) | Infrastructure Alerts | 10m | Available RAM <15% on any host |

### Alert Annotations (all rules)

Every rule includes:
- `summary`: one-line description with templated metric value
- `description`: affected service, impact, and exact shell commands to diagnose

### Current Disk Usage (as of last check)

| Host | Usage |
|------|-------|
| proxmox-host | **81.5%** ⚠️ — already above warning threshold |
| hellflix (LXC 210) | 65.9% |
| monitoring (LXC 102) | 43.4% |
| app-core (LXC 100) | 35.9% |

**Action required:** proxmox-host root disk is >80%. Run `du -sh /var/lib/lxc/* | sort -rh | head -10` on the Proxmox host.

---

## Uptime Kuma (LXC 102 — `192.168.1.177:3001`)

Notification channel: **Discord #homelab-alerts** (Discord webhook)

### Monitors

| ID | Name | Type | Target | Notes |
|----|------|------|--------|-------|
| 1 | Immich | HTTP | 192.168.1.176:2283 | |
| 2 | dockge | HTTP | 192.168.1.176:5001 | |
| 3 | LXC 100 (app-core) host | ping | 192.168.1.176 | |
| 4 | Vaultwarden (External) | HTTP | vault.<domain> | Tests NPM + Cloudflared tunnel |
| 5 | pihole240 | HTTP | pihole240.<domain>/admin | |
| 6 | pihole241 | HTTP | 192.168.1.241/admin | |
| 7 | plex | HTTP | 192.168.1.210:32400 | |
| 8 | Prometheus | HTTP | prometheus:9090 | Internal Docker hostname |
| 9 | Grafana | HTTP | grafana:3000 | Internal Docker hostname |
| 10 | TrueNAS | HTTP | 192.168.1.250 | 3 failures/week (intermittent) |
| 11 | seerr | HTTP | requests.<domain> | DNS failures via external — likely Cloudflare flap |
| 13 | radarr | HTTP | 192.168.1.210:7878 | |
| 14 | sonarr | HTTP | 192.168.1.210:8989 | |
| 15 | prowlarr | HTTP | 192.168.1.210:9696 | |
| 16 | flaresolverr | HTTP | 192.168.1.210:8191 | |
| 17 | NPM | HTTP | 192.168.1.101:81 | |
| 18 | zurg | HTTP | 192.168.1.210:9999 | |
| 19 | Zurg FUSE Mount Health | push | — | maxretries=3 to avoid flap alerts on rclone restart |
| 22 | LXC 101 (gateway-npm) host | ping | 192.168.1.101 | Added 2026-03-03 |
| 23 | LXC 102 (monitoring) host | ping | 192.168.1.177 | Added 2026-03-03 |
| 24 | LXC 190 (tailscale-exit) host | ping | 192.168.1.249 | Added 2026-03-03 |
| 25 | LXC 210 (hellflix) host | ping | 192.168.1.210 | Added 2026-03-03 |

### Noise Reduction

- `resend_interval=0` on all monitors: one alert on DOWN, one on recovery (no spam)
- Monitor 19 (Zurg FUSE push): `maxretries=3` — requires 3 consecutive push misses (3min) before firing

---

## TrueNAS Alerts (`192.168.1.250`)

**Manual step required.** TrueNAS SCALE has native Slack-compatible webhook support.

1. TrueNAS UI → **System → Alert Settings → Add Service**
2. Type: **Slack**
3. URL: `https://discord.com/api/webhooks/<ID>/<TOKEN>/slack`
4. Save and **Test**

Covers: SMART failures, pool degraded/faulted, replication failures, snapshot errors, low disk space.

---

## PBS Alerts (`192.168.1.200`)

**Manual step required.** Proxmox Backup Server 3.x supports webhook notifications.

1. PBS UI → **Configuration → Notifications → Add Endpoint**
2. Type: **Webhook**
3. URL: Discord webhook (full URL, no `/slack` suffix needed — use Discordwebhook raw format)
4. Method: POST
5. Body template (Gotify-style JSON or custom)

Covers: backup job success/failure, datastore health.

---

## Watchtower (Docker auto-update)

See [docker-platform/watchtower.md](../docker-platform/watchtower.md).
Notifications configured via `${DISCORD_WEBHOOK_URL}` in `.env` on each LXC.
Status: running on LXC 101 + 102; pending Discord webhook URL fill-in + Dockge import on LXC 100 + 210.
