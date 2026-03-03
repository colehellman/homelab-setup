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
 │  └── 210  hellflix        192.168.1.210   │             │
 │                                           │             │
 │  TrueNAS (homeboy pool)   192.168.1.250   │             │
 └───────────────────────────────────────────┼─────────────┘
                                             │ Tailscale mesh
                                             │ (100.x.x.x / fd7a:...)
                                ┌────────────┴────────────────┐
                                │  REMOTE                      │
                                │  Backup server  100.107.13.28│
                                └──────────────────────────────┘
```

### Tailscale Overlay (Tailnet: `nv4pjfqn2k@`)

| Node | Tailscale IP | Role | Status |
|------|-------------|------|--------|
| tailscale-exit | 100.90.65.3 | Exit node (LXC 190) | online |
| coles-mac-mini | 100.127.93.22 | Admin workstation | online |
| truenas-main | 100.102.196.76 | Primary NAS | online |
| truenas-offsite | 100.107.13.28 | Offsite TrueNAS | online (active) |
| pihole240 | 100.118.22.112 | Pi-hole DNS | online (active) |
| pihole241 | 100.101.158.118 | Pi-hole DNS | online (active) |
| zer02w | 100.119.144.52 | Linux node | online |
| cole-phone | 100.106.119.69 | Mobile client | offline (last seen 2026-03-01) |
| macbook-air | 100.68.41.123 | Laptop | offline (last seen 2026-02-25) |
| game-pc | 100.69.227.27 | Windows desktop | ⚠️ key expired 2025-09-07 |

The `tailscale-exit` LXC (VMID 190) advertises a subnet route and acts as the exit node for all tailnet clients, giving remote devices access to the full `192.168.1.0/24` LAN.

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
| 190 | tailscale-exit | 192.168.1.249 / 100.90.65.3 | Tailscale exit node | No |
| 210 | hellflix | 192.168.1.210 | Media stack — Plex, \*arr, Seerr, Decypharr, Zurg | **Yes** (NVIDIA) |

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

---

## Health Status

_Last checked: 2026-03-02 19:04 CST (outside maintenance window)_

| Check | Result |
|-------|--------|
| Tailscale mesh | healthy — 7 peers online |
| Mobile (cole-phone) | offline — last seen 2026-03-01 |
| game-pc Tailscale key | ⚠️ expired 2025-09-07 — needs renewal |
| CPU (app-core) | ~0.1% avg over 1h |
| CPU (hellflix) | ~0.45% avg over 1h |
| CPU (monitoring) | ~0.41% avg over 1h |
| truenas-offsite | online + active over Tailscale |
| Exit node (tailscale-exit) | online |
