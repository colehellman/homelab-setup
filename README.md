# Homelab Setup

Infrastructure documentation for a hybrid-cloud homelab: local Proxmox node + TrueNAS storage + remote backup server bridged over Tailscale.

## Hybrid-Cloud Architecture

```
 ┌─────────────────────────────────────────────────────────┐
 │  LOCAL (192.168.1.0/24)                                 │
 │                                                         │
 │  Proxmox Host                                           │
 │  ├── 100  dockge          192.168.1.176                 │
 │  ├── 101  gateway-npm     192.168.1.101                 │
 │  ├── 102  monitoring      192.168.1.177                 │
 │  ├── 190  tailscale-exit  192.168.1.249 ──┐             │
 │  ├── 200  pbs             192.168.1.200   │             │
 │  └── 210  hellflix        192.168.1.210   │             │
 │                                           │             │
 │  TrueNAS (homeboy pool)   192.168.1.250 ──┤ (exit node) │
 │  └── NFS: proxmox-backups ◄── PBS         │             │
 └───────────────────────────────────────────┼─────────────┘
                                             │ Tailscale mesh
                                             │ (100.x.x.x / fd7a:...)
                                ┌────────────┴────────────────┐
                                │  REMOTE                      │
                                │  TrueNAS offsite 100.107.13.28│
                                │  └── ZFS replication target  │
                                └──────────────────────────────┘
```

### Tailscale Overlay (Tailnet: `nv4pjfqn2k@`)

| Node | Tailscale IP | Role | Status |
|------|-------------|------|--------|
| tailscale-exit | 100.90.65.3 | Exit node — LXC 190 (Proxmox) (`tag:server`, `tag:exit-node`) | online |
| truenas-main | 100.102.196.76 | Exit node — TrueNAS local fallback (`tag:server`, `tag:exit-node`) | online |
| coles-mac-mini | 100.127.93.22 | Admin workstation (`tag:admin`) | online |
| truenas-offsite | 100.107.13.28 | Offsite TrueNAS (`tag:server`) | online (active) |
| pihole240 | 100.118.22.112 | Pi-hole DNS (`tag:server`) | online (active) |
| pihole241 | 100.101.158.118 | Pi-hole DNS (`tag:server`) | online (active) |
| zer02w | 100.119.144.52 | Linux node (`tag:server`) | online |
| cole-phone | 100.106.119.69 | Mobile client (`tag:client`) | offline (last seen 2026-03-04) |
| macbook-air | 100.68.41.123 | Laptop (`tag:client`) | offline (last seen 2026-02-25) |
| game-pc-1 | 100.96.94.77 | Windows desktop (`tag:client`) | online |

Two exit nodes advertise `192.168.1.0/24` subnet routing: `tailscale-exit` (LXC 190, runs on Proxmox) and `truenas-main` (runs independently on TrueNAS hardware). If Proxmox goes down, switch to `truenas-main` in your Tailscale client to maintain LAN access.

ACL policy is tag-based (`tailscale/acl.hujson`): `tag:client` devices reach approved service ports only; SSH and Proxmox/PBS web UIs are restricted to `tag:admin`.

### TrueNAS Storage

| Host | Pool | Role |
|------|------|------|
| 192.168.1.250 | `homeboy` | Primary NAS — SMB shares, app datasets |
| 100.107.13.28 | TBD | Offsite TrueNAS (`truenas-offsite`) — replication target |

---

## LXC Containers

| VMID | Name | IP | Role | GPU |
|------|------|----|------|-----|
| 100 | dockge | 192.168.1.176 | Docker host — Immich, Vaultwarden, Syncthing, Cloudflared | No |
| 101 | gateway-npm | 192.168.1.101 | Reverse proxy — Nginx Proxy Manager, CrowdSec | No |
| 102 | monitoring | 192.168.1.177 | Observability — Grafana, Prometheus, Uptime Kuma, cAdvisor | No |
| 190 | tailscale-exit | 192.168.1.249 / 100.90.65.3 | Tailscale exit node (primary) | No |
| 200 | pbs | 192.168.1.200 | Proxmox Backup Server — nightly snapshots of all LXCs | No |
| 210 | hellflix | 192.168.1.210 | Media stack — Plex, \*arr, Seerr, Decypharr, Zurg | **Yes** (NVIDIA) |
| 220 | homelab-agent | 192.168.1.116 | Claude AI agent — Discord bot, webhook, scheduled digests | No |

See [`inventory/containers.md`](inventory/containers.md) for full specs and service details.

## Directory Structure

| Path | Purpose |
|------|---------|
| `automation/` | Ansible playbooks and automation docs |
| `best-practices/` | Disaster recovery, passwords/2FA, physical security |
| `docker-platform/` | Docker install, Portainer, Watchtower |
| `filesync-backup/` | Borg, Syncthing, Immich, iMazing, Time Machine |
| `inventory/` | Live container inventory (synced from Proxmox) |
| `media/` | Plex, Sonarr/Radarr, Overseerr, debrid config |
| `monitoring-security/` | Grafana, Prometheus, Loki, CrowdSec, alerts |
| `network/` | VLANs, firewall, OpenWRT |
| `proxmox/` | Proxmox host config, hardware tuning, VM/LXC planning |
| `reverse-proxy/` | Traefik/NPM, SSL |
| `tailscale/` | ACL policy (`acl.hujson`) — apply manually in Tailscale admin console |

---

## Health Status

_Last checked: 2026-03-04 CST_

| Check | Result |
|-------|--------|
| Tailscale mesh | healthy — 8 peers online |
| Exit node (tailscale-exit, LXC 190) | online — IPv6 forwarding fixed 2026-03-03 |
| Exit node (truenas-main, fallback) | online — exit node + subnet route active |
| Tailscale ACL | active — tag-based policy applied 2026-03-03 |
| game-pc-1 | online — new auth key active, expires 2026-08-30 |
| PBS (LXC 200) | online — first backup job running 2026-03-03 |
| Mobile (cole-phone) | offline — last seen 2026-03-01 |
| truenas-offsite | online + active over Tailscale |
| Exit node (tailscale-exit) | online |
| Watchtower (LXC 101, 102) | running — auto-update daily 03:00 |
| Grafana alerts | 5 rules active → Discord-SRE |
| Uptime Kuma | 19 monitors → Discord #homelab-alerts |
| **Proxmox host disk** | **⚠️ 81.5% full — WARNING threshold exceeded** |
| hellflix (LXC 210) disk | 65.9% |
| monitoring (LXC 102) disk | 43.4% |
| app-core (LXC 100) disk | 35.9% |
