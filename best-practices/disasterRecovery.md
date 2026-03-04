# Disaster Recovery

Last updated: 2026-03-03 (PBS provisioned, first backup verified OK, offsite replication active)

---

## Backup Architecture

| Layer | Tool | Source | Destination | Schedule |
|-------|------|--------|-------------|----------|
| LXC snapshots | Proxmox Backup Server (PBS) | All 5 LXCs (100,101,102,190,210) | TrueNAS `homeboy/proxmox-backups` via NFS | Nightly 02:00 |
| PBS datastore replication | TrueNAS ZFS replication | `homeboy/proxmox-backups` + `homeboy/proxmox_backups` | truenas-offsite (100.107.13.28) | Daily (configured 2026-03-03) |
| Personal data | Syncthing + Immich | dockge (LXC 100) | TrueNAS + cloud | Continuous |
| macOS | Time Machine | Macs | TrueNAS SMB share | Hourly |

**PBS LXC:** VMID 200 at 192.168.1.200, web UI at https://192.168.1.200:8007
**PBS version:** 3.4.8
**Fingerprint:** verify locally via PBS web UI → Dashboard → Fingerprint (do not commit to public repo)
**Datastore name:** `homeboy-backups`
**NFS mount inside PBS:** `/mnt/pbs-store` → `192.168.1.250:/mnt/homeboy/proxmox-backups`

---

## Retention Policy

Configured in PBS backup job `nightly-all`:

| Retention | Count |
|-----------|-------|
| Daily | 7 |
| Weekly | 4 |
| Monthly | 3 |

Compression: `zstd`. Mode: `snapshot` (falls back to `suspend`).

---

## Restoring an LXC from PBS

### Scenario: single container corrupted or deleted

1. Log into **Proxmox web UI** (https://192.168.1.69:8006)
2. Navigate to **Datacenter → Storage → homeboy-backups**
3. Find the container backup by VMID and date
4. Click **Restore**:
   - Target storage: `local-lvm` (or whichever local storage has capacity)
   - VMID: use original or assign a new one
   - **Uncheck** "Start after restore" — verify config before starting
5. After restore completes, review the container's network config (confirm IP hasn't conflicted)
6. Start the container and verify services

### Scenario: Proxmox host catastrophic failure

1. Reinstall Proxmox on replacement hardware (same version — check `/etc/pve/nodes/` from backup)
2. Install PBS client or add PBS storage to new Proxmox node:
   - Datacenter → Storage → Add → Proxmox Backup Server
   - Server: `192.168.1.200`, Datastore: `homeboy-backups`
   - Fingerprint: from PBS UI → Dashboard → Show Fingerprint
3. Restore each container from PBS in priority order:
   1. **190 tailscale-exit** — restores remote access first
   2. **101 gateway-npm** — restores reverse proxy / external access
   3. **102 monitoring** — restores observability
   4. **100 dockge** — restores Immich, Vaultwarden, Syncthing
   5. **210 hellflix** — restores media stack (NVIDIA passthrough requires host driver match)
4. Start containers one at a time, verify each before proceeding

### Scenario: PBS LXC itself is lost

PBS metadata (chunk index) lives in the datastore on TrueNAS, not inside the PBS LXC.
The raw backup chunks are intact on TrueNAS even if LXC 200 is gone.

1. Provision a new PBS LXC (VMID 200, Debian 12, same specs)
2. Install `proxmox-backup-server` package
3. Mount the existing NFS share: `192.168.1.250:/mnt/homeboy/proxmox-backups` → `/mnt/pbs-store`
4. In PBS UI, add the existing datastore path `/mnt/pbs-store` — PBS will read existing chunks
5. Re-add PBS storage in Proxmox UI with new fingerprint

### Scenario: TrueNAS local failure (homeboy pool lost)

1. Retrieve backup chunks from offsite TrueNAS:
   - SSH into truenas-offsite (100.107.13.28)
   - Confirm `proxmox-backups` dataset exists and is intact
2. Options:
   - **a)** Set up a new PBS pointing at the offsite NFS share temporarily
   - **b)** Restore TrueNAS from ZFS replication to new hardware, then restore normally
3. Once a PBS datastore is accessible, follow the standard LXC restore procedure above

---

## PBS Setup Reference

### TrueNAS Dataset + NFS Share

```
Dataset: homeboy/proxmox-backups
Path:    /mnt/homeboy/proxmox-backups
NFS:     allowed hosts = 192.168.1.200, rw, no_root_squash
```

### PBS Installation (Debian 12)

```bash
echo "deb http://download.proxmox.com/debian/pbs bookworm pbs-no-subscription" \
  > /etc/apt/sources.list.d/pbs.list
curl -sL https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg \
  -o /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

apt update && apt install -y proxmox-backup-server nfs-common

mkdir -p /mnt/pbs-store
echo "192.168.1.250:/mnt/homeboy/proxmox-backups /mnt/pbs-store nfs defaults,_netdev 0 0" \
  >> /etc/fstab
mount -a
```

### Proxmox → PBS Integration

Datacenter → Storage → Add → Proxmox Backup Server:
- Server: `192.168.1.200`
- Datastore: `homeboy-backups`
- Fingerprint: PBS Dashboard → Show Fingerprint

---

## Second Tailscale Exit Node

truenas-main (100.102.196.76) is configured as a second exit node, independent of Proxmox.
If the Proxmox host goes down (taking LXC 190 with it), switch to truenas-main in Tailscale client.

Advertises:
- Exit node: enabled
- Subnet route: `192.168.1.0/24`

To enable on TrueNAS:
```bash
tailscale up --advertise-exit-node --advertise-routes=192.168.1.0/24 --accept-dns=false
```
Then approve in Tailscale admin console → Machines → truenas-main → Edit route settings.

---

## Recovery Priority Order

1. Network/DNS (pihole240/241 are independent Tailscale nodes — usually survive Proxmox outage)
2. Tailscale access (tailscale-exit LXC 190, or truenas-main as fallback)
3. Reverse proxy (LXC 101 gateway-npm) — external access depends on this
4. Core services (LXC 100 dockge — Vaultwarden, Immich)
5. Observability (LXC 102 monitoring)
6. Media (LXC 210 hellflix — lowest priority)
