#!/usr/bin/env python3
"""
FastAPI webhook server — listens for Grafana alert POSTs on :8765/alert
and triggers an investigation run via the agent.

Runs as: homelab-agent-webhook.service (always-on)
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from db import init_db, is_duplicate_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="homelab-agent-webhook", docs_url=None, redoc_url=None)

AGENT_SCRIPT = Path(__file__).parent / "agent.py"

# Dedup window: ignore repeated alerts within 60 minutes
DEDUP_WINDOW_MINUTES = 60

# Bearer token for /alert — set via WEBHOOK_TOKEN env var.
# If unset, requests are accepted without auth (warn on startup).
_WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")


@app.on_event("startup")
async def startup() -> None:
    init_db()
    if not _WEBHOOK_TOKEN:
        log.warning("WEBHOOK_TOKEN is not set — /alert endpoint accepts unauthenticated requests")


@app.post("/alert")
async def receive_alert(request: Request) -> JSONResponse:
    """
    Receive a Grafana webhook alert and trigger an investigation.
    Grafana webhook payload: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
    """
    if _WEBHOOK_TOKEN:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {_WEBHOOK_TOKEN}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    log.info("Alert received: %s", json.dumps(payload, default=str)[:500])

    # Build a fingerprint from alertname + labels to dedup rapid-fire alerts.
    # Grafana unified alerting wraps alerts in a "alerts" list.
    alerts = payload.get("alerts", [payload])
    dedup_labels = {
        "alertname": payload.get("commonLabels", {}).get("alertname", payload.get("title", "unknown")),
        **payload.get("commonLabels", {}),
    }
    if is_duplicate_alert(dedup_labels, window_minutes=DEDUP_WINDOW_MINUTES):
        log.info("Duplicate alert suppressed (within %dm window): %s", DEDUP_WINDOW_MINUTES, dedup_labels)
        return JSONResponse({"status": "suppressed", "reason": "duplicate"})

    # Run investigation asynchronously (don't block the webhook response).
    # Inherit parent's stdout/stderr so output reaches systemd journal.
    alert_json = json.dumps(payload)
    subprocess.Popen(
        [sys.executable, str(AGENT_SCRIPT), "--mode", "investigate", "--alert", alert_json],
    )

    return JSONResponse({"status": "investigating"})


@app.get("/healthz")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
