# LXC Container Inventory

Last synced from Proxmox: 2026-03-02 (audit pass)

All containers are currently **running**.

---

## 100 — dockge

| Field | Value |
|-------|-------|
| Hostname | dockge |
| IP | 192.168.1.176 |
| OS | Ubuntu 22.04.5 LTS |
| vCPUs | 2 |
| RAM | 6240 MB |
| Disk | 30 GB |
| GPU passthrough | No |

**Services (Docker):**

| Container | Image | Ports |
|-----------|-------|-------|
| dockge-dockge-1 | louislam/dockge:1 | 5001 |
| immich_server | ghcr.io/immich-app/immich-server:release | 2283 |
| immich_postgres | ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0 | 5432 (internal) |
| immich_redis | valkey/valkey:8-bookworm | 6379 (internal) |
| vaultwarden | vaultwarden/server:latest | 80 (internal) |
| syncthing | lscr.io/linuxserver/syncthing:latest | 8384, 22000, 21027 |
| cloudflared | cloudflare/cloudflared:latest | — |

---

## 101 — gateway-npm

| Field | Value |
|-------|-------|
| Hostname | gateway-npm |
| IP | 192.168.1.101 |
| OS | Debian 12 (bookworm) |
| vCPUs | 1 |
| RAM | 512 MB |
| Disk | 7.8 GB |
| GPU passthrough | No |

**Services (Docker):**

| Container | Image | Ports |
|-----------|-------|-------|
| npm-core | jc21/nginx-proxy-manager:latest | 80, 81, 443 |
| npm-db | jc21/mariadb-aria:latest | 3306 (internal) |
| crowdsec | crowdsecurity/crowdsec:latest | 8080 |

---

## 102 — monitoring

| Field | Value |
|-------|-------|
| Hostname | monitoring |
| IP | 192.168.1.177 |
| OS | Ubuntu 22.04.5 LTS |
| vCPUs | 2 |
| RAM | 2048 MB |
| Disk | 20 GB |
| GPU passthrough | No — NVIDIA kernel modules visible from host but no `/dev/dri/card*` device passed through |

**Services (Docker):**

| Container | Image | Ports |
|-----------|-------|-------|
| grafana | grafana/grafana:latest | 3000 |
| prometheus | prom/prometheus:latest | 9090 |
| uptime-kuma | louislam/uptime-kuma:2 | 3001 |
| cadvisor | gcr.io/cadvisor/cadvisor:latest | 8080 |
| node-exporter | prom/node-exporter:latest | — |

---

## 190 — tailscale-exit

| Field | Value |
|-------|-------|
| Hostname | tailscale-exit |
| IP (LAN) | 192.168.1.249 |
| IP (Tailscale) | 100.90.65.3 |
| OS | Debian 12 (bookworm) |
| vCPUs | 1 |
| RAM | 512 MB |
| Disk | 3.9 GB |
| GPU passthrough | No |

**Services:**

- `tailscaled` — running as an advertised exit node

**Tailscale peers (from this node — live as of 2026-03-02):**

| Node | IP | OS | Status |
|------|----|----|--------|
| tailscale-exit | 100.90.65.3 | Linux | active — idle, **offers exit node** |
| coles-mac-mini | 100.127.93.22 | macOS | online |
| cole-phone | 100.106.119.69 | iOS | offline (last seen 1d ago) |
| macbook-air | 100.68.41.123 | macOS | offline (last seen 5d ago) |
| game-pc | 100.69.227.27 | Windows | offline (last seen 255d ago) |

> **Note:** Remote backup server `100.107.13.28` is not currently visible in this tailnet's peer list — verify it is joined and approved in the Tailscale admin console.

---

## 210 — hellflix

| Field | Value |
|-------|-------|
| Hostname | hellflix |
| IP | 192.168.1.210 |
| OS | Ubuntu 24.04.3 LTS |
| vCPUs | 4 |
| RAM | 17000 MB (~16.6 GB) |
| Disk | 94 GB |
| GPU passthrough | **Yes** — `/dev/dri/card0` + `/dev/dri/renderD128` |
| NVIDIA driver | 535.261.03 |

**Services (Docker):**

| Container | Image | Ports |
|-----------|-------|-------|
| plex | lscr.io/linuxserver/plex:latest | — (host network) |
| sonarr | lscr.io/linuxserver/sonarr:latest | 8989 |
| radarr | lscr.io/linuxserver/radarr:latest | 7878 |
| prowlarr | lscr.io/linuxserver/prowlarr:latest | 9696 |
| seerr | ghcr.io/seerr-team/seerr:latest | 5055 |
| decypharr | ghcr.io/sirrobot01/decypharr:latest | 8282 |
| flaresolverr | flaresolverr/flaresolverr:latest | 8191 |
| zurg | ghcr.io/debridmediamanager/zurg:latest | — |
| rclone | rclone/rclone:latest | — |
| tautulli | tautulli/tautulli:latest | — |
| cadvisor | gcr.io/cadvisor/cadvisor:latest | 8080 |
| node-exporter | prom/node-exporter:latest | — |
| dockge-dockge-1 | louislam/dockge (local build) | 5001 |
