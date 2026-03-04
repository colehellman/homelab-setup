# LXC Container Inventory

Last synced from Proxmox: 2026-03-03 (audit pass)

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
| open-webui | ghcr.io/open-webui/open-webui:main | 3000 |
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
| watchtower | containrrr/watchtower:latest | — |

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
| watchtower | containrrr/watchtower:latest | — |

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

- `tailscaled` — running as an advertised exit node, `tag:server` + `tag:exit-node`

**Notes:**
- IPv6 forwarding enabled 2026-03-03 (`net.ipv6.conf.all.forwarding=1` in `/etc/sysctl.d/99-tailscale.conf`) — required for exit node relay
- Tailscale ACL applied 2026-03-03 — tag-based policy, see `tailscale/acl.hujson`

**Tailscale peers (from this node — live as of 2026-03-03):**

| Node | IP | OS | Status |
|------|----|----|--------|
| tailscale-exit | 100.90.65.3 | Linux | active — **offers exit node** |
| truenas-main | 100.102.196.76 | Linux | active — **offers exit node** (fallback) |
| coles-mac-mini | 100.127.93.22 | macOS | online |
| cole-phone | 100.106.119.69 | iOS | offline (last seen 2026-03-01) |
| macbook-air | 100.68.41.123 | macOS | offline (last seen 2026-02-25) |
| game-pc-1 | 100.96.94.77 | Windows | online |
| pihole240 | 100.118.22.112 | Linux | online |
| pihole241 | 100.101.158.118 | Linux | online |
| truenas-offsite | 100.107.13.28 | Linux | online |
| zer02w | 100.119.144.52 | Linux | online |

---

## 200 — pbs

| Field | Value |
|-------|-------|
| Hostname | pbs |
| IP | 192.168.1.200 |
| OS | Debian 12 (bookworm) |
| vCPUs | 2 |
| RAM | 4096 MB |
| Disk | 32 GB (OS + PBS metadata + chunk cache) |
| GPU passthrough | No |

**Services:**

- `proxmox-backup-server` v3.4.8 — web UI at https://192.168.1.200:8007
- `proxmox-backup-proxy` — TLS proxy (fingerprint: `32:af:ad:7b:6a:09:0d:02:12:20:d7:d7:5d:62:70:c3:ef:c8:ed:48:49:c5:7b:5a:bc:01:7c:51:ad:a6:1c:ff`)

**Storage:**
- NFS mount: `192.168.1.250:/mnt/homeboy/proxmox-backups` → `/mnt/pbs-store` (persisted in `/etc/fstab`)
- TrueNAS dataset: `homeboy/proxmox-backups` — 500 GB quota, `acltype=off`, NFS share with `maproot_user=root`
- Datastore name: `homeboy-backups`

**Backup job `nightly-all`:** daily — VMs 100,101,102,190,210 — retention: 7 daily / 4 weekly / 3 monthly — mode: snapshot, compression: zstd

**Setup notes:**
- Container must be **privileged** (`unprivileged: 0`) for NFS mounting to work
- After initial install, ownership of `/etc/proxmox-backup` and `/var/lib/proxmox-backup` must be fixed if container was ever run unprivileged (uid shift from 100000+X → X)
- `mount.nfs` setuid ownership must be `root:root` — verify with `ls -la /sbin/mount.nfs`

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
| Journal cap | 200 MB / 2 weeks (`/etc/systemd/journald.conf.d/size.conf`) |

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

**Compose notes (2026-03-03):**
- Stacks in `/opt/stacks/` — media, arrr, metrics, nicotine, automation
- Secrets (`RD_TOKEN`) in `/opt/stacks/media/.env` — not in compose files
- rclone VFS cache at `/srv/media/cache/rclone`, cap 50 GB (`--cache-dir`)
- zurg `check_for_changes_every_secs: 60`
