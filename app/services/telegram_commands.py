"""Telegram bot command menu (setMyCommands)."""

from __future__ import annotations

# Shown in Telegram when the user types "/". Keep descriptions short (Telegram limit 256).
BOT_MENU_COMMANDS: list[dict[str, str]] = [
    {"command": "start", "description": "Link your hub account"},
    {"command": "link", "description": "How to link your account"},
    {"command": "help", "description": "Command list"},
    {"command": "status", "description": "Active tasks"},
    {"command": "transcribe", "description": "Transcribe audio (optional id)"},
    {"command": "summary", "description": "Summarize transcript; pick a skill"},
    {"command": "viewsummary", "description": "View a recent summary from the list"},
]
