#!/usr/bin/env python3
"""
Homelab agent Discord bot — interactive homelab management via chat.

Listens in DISCORD_CONTROL_CHANNEL_ID for any message. Maintains per-channel
conversation history so follow-up messages have full context.

Usage: run as homelab-agent-discord.service (systemd)

Proxmox write ops require upgrading the API token role:
  pveum role add HomelabAgentRW --privs "VM.PowerMgmt VM.Snapshot Sys.Audit VM.Audit"
  pveum aclmod / --tokens homelab-agent@pam!agent --roles HomelabAgentRW
"""

import asyncio
import json
import logging
import os
from collections import defaultdict

import anthropic
import discord

from db import init_db, log_run
from tools import ALL_TOOL_SCHEMAS, execute_tool, load_context

log = logging.getLogger("homelab-bot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL = "claude-sonnet-4-6"
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DISCORD_CONTROL_CHANNEL_ID = int(os.environ["DISCORD_CONTROL_CHANNEL_ID"])

MAX_HISTORY = 20     # user+assistant message pairs kept per channel
MAX_MSG_LEN = 1900   # Discord limit is 2000; leave headroom


INTERACTIVE_SYSTEM_PROMPT = """\
You are the homelab management bot. You have read AND write access to the \
homelab infrastructure. You're talking directly to the homelab owner in Discord.

Write capabilities you have:
- Start / stop / reboot / shutdown LXC containers and VMs (Proxmox API)
- Create Proxmox snapshots
- Run shell commands on whitelisted hosts via SSH (Proxmox at 192.168.1.69)
- Trigger TrueNAS pool scrubs
- Check if any URL/service is reachable

Rules:
1. CONFIRM before destructive ops (stop, shutdown, delete). Ask: \
   "Stop LXC 205 (homeassistant) — confirm?" and wait for yes/confirm. \
   Skip confirmation only if the user said "force" or already confirmed.
2. Snapshot before rebooting any container that has been running > 24h.
3. Be concise. This is chat — no walls of text. Use bullet points.
4. Report outcome of every write action (success or failure with detail).
5. NEVER run: rm -rf, mkfs, fdisk, wipefs, or any command that destroys data.
6. If a task will take > 10 seconds, say so upfront.

Current homelab context:
{context}
"""


def _run_claude(user_message: str, history: list[dict], context: str) -> tuple[str, list[dict]]:
    """
    One conversation turn. Runs the Claude tool-use loop to completion.
    Returns (response_text, updated_history).
    history contains only text-based user/assistant dicts (no raw content blocks).
    """
    client = anthropic.Anthropic()
    system = INTERACTIVE_SYSTEM_PROMPT.format(context=context)

    # Build the full message list for this turn
    messages: list[dict] = list(history) + [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=ALL_TOOL_SCHEMAS,
            messages=messages,
        )

        # Append raw response (may contain tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "(no response)"
            )
            # Store only text in persistent history — content blocks aren't re-serialisable
            updated = list(history) + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": text},
            ]
            return text, updated

        if response.stop_reason != "tool_use":
            return f"Unexpected stop reason: {response.stop_reason}", history

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

        messages.append({"role": "user", "content": tool_results})


def _chunk(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """Split a long response into Discord-safe chunks, preferring newline breaks."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split = text.rfind("\n", 0, limit)
        if split == -1:
            split = limit
        chunks.append(text[:split])
        text = text[split:].lstrip("\n")
    return chunks


class HomelabBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        # channel_id -> list of {role, content} (text only)
        self._history: dict[int, list[dict]] = defaultdict(list)
        self._context = ""

    async def on_ready(self) -> None:
        loop = asyncio.get_event_loop()
        self._context = await loop.run_in_executor(None, load_context)
        log.info("Ready as %s — watching channel %d", self.user, DISCORD_CONTROL_CHANNEL_ID)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id != DISCORD_CONTROL_CHANNEL_ID:
            return

        history = self._history[message.channel.id]

        async with message.channel.typing():
            loop = asyncio.get_event_loop()
            try:
                response_text, new_history = await loop.run_in_executor(
                    None,
                    _run_claude,
                    message.content,
                    list(history),  # snapshot so concurrent edits don't corrupt
                    self._context,
                )
            except Exception as exc:
                log.exception("Claude error on message: %s", message.content)
                response_text = f"⚠️ Error: {exc}"
                new_history = history  # don't update on error

        # Trim history and save
        if len(new_history) > MAX_HISTORY * 2:
            new_history = new_history[-(MAX_HISTORY * 2):]
        self._history[message.channel.id] = new_history

        for chunk in _chunk(response_text):
            await message.channel.send(chunk)

        log_run("chat", True, response_text[:500])


def main() -> None:
    init_db()
    bot = HomelabBot()
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
