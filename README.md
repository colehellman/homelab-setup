# Homelab Setup

Infrastructure documentation for a Proxmox-based homelab.

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
