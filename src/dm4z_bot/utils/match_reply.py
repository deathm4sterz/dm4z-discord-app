from __future__ import annotations

import discord


def build_match_response_text(match_id: str) -> str:
    return f"Extracted Match ID: **{match_id}**"


def build_match_view(match_id: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label="Join lobby in game",
            style=discord.ButtonStyle.link,
            url=f"https://httpbin.org/redirect-to?url=aoe2de://0/{match_id}",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Spectate match by clicking here",
            style=discord.ButtonStyle.link,
            url=f"https://httpbin.org/redirect-to?url=aoe2de://1/{match_id}",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Post-match analysis (on aoe2insights)",
            style=discord.ButtonStyle.link,
            url=f"https://www.aoe2insights.com/match/{match_id}/",
        )
    )
    return view

