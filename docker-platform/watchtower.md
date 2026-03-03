# Watchtower — Docker Auto-Update

[Watchtower](https://containrrr.dev/watchtower/) monitors running Docker containers and automatically pulls + restarts them when a new image is available.

## Deployment Status

| LXC | Compose Path | Status |
|-----|-------------|--------|
| 101 (gateway-npm) | `/opt/npm/docker-compose.yml` | ✅ Running |
| 102 (monitoring) | `/opt/monitoring/docker-compose.yml` | ✅ Running |
| 100 (app-core) | `/opt/stacks/watchtower/compose.yaml` | ⏳ Import in Dockge |
| 210 (hellflix) | `/opt/stacks/watchtower/compose.yaml` | ⏳ Import in Dockge |

## Schedule

Watchtower runs **daily at 03:00** (`WATCHTOWER_SCHEDULE=0 0 3 * * *`).
`WATCHTOWER_CLEANUP=true` removes old images after update.

## Known Workaround: Docker API Version

Watchtower 1.7.1 hardcodes Docker API 1.25 for client negotiation, which Docker 29+ rejects (minimum 1.44). All compose files include:

```yaml
environment:
  - DOCKER_API_VERSION=1.47
```

This will no longer be needed once Watchtower ships with a newer Docker SDK.

## Discord Notifications

Each LXC has a `.env` file at the compose directory with:

```env
DISCORD_WEBHOOK_URL=FILL_IN_YOUR_DISCORD_WEBHOOK_URL_HERE
```

The compose service references `${DISCORD_WEBHOOK_URL}/slack` using Discord's Slack-compatible endpoint.

**To enable notifications:**
1. Get your Discord webhook URL from Server Settings → Integrations → Webhooks
2. On each LXC, edit the `.env` file at the compose directory
3. Replace the placeholder with your actual webhook URL
4. Restart Watchtower: `docker compose up -d watchtower`

For LXC 100 and 210 (Dockge-managed), fill in the `.env` at `/opt/stacks/watchtower/.env`.

## Importing on LXC 100 and 210 via Dockge

The compose file exists at `/opt/stacks/watchtower/compose.yaml` on both LXCs.
Dockge auto-discovers stacks under `/opt/stacks/` — the watchtower stack should appear in the UI automatically.
Click **Start** to launch it.

## Excluding Containers from Auto-Update

Add this label to any container you want to pin at a specific version:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=false"
```

## References

- [Watchtower docs](https://containrrr.dev/watchtower/)
- [Discord Slack-compatible webhooks](https://discord.com/developers/docs/resources/webhook#execute-slackcompatible-webhook)
- [GitHub issue: Docker 29 API compat](https://github.com/containrrr/watchtower/issues/1892)
