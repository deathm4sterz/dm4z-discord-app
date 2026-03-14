from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import discord

from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api
from dm4z_bot.services.aoe2_websocket import Aoe2WebSocket
from dm4z_bot.utils.constants import AOE2_INSIGHTS_ANALYZE_URL
from dm4z_bot.utils.match_embeds import (
    build_active_match_embed,
    build_active_match_view,
    build_finished_match_embed,
    build_finished_match_view,
)
from dm4z_bot.utils.mod_notifications import notify_mod_channels

logger = logging.getLogger(__name__)

MATCH_RESULT_RETRY_DELAY = 5.0


class MatchTracker:
    def __init__(self, bot: discord.Bot, db: Database, api: Aoe2Api) -> None:
        self.bot = bot
        self.db = db
        self.api = api
        self._ws = Aoe2WebSocket()
        self._task: asyncio.Task[None] | None = None
        self._reconnect_event = asyncio.Event()

    async def _get_tracked_profiles(self) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT ga.account_identifier, ga.member_id, ga.guild_id "
            "FROM game_accounts ga "
            "WHERE ga.status = 'approved' AND ga.tracking = 1 AND ga.game = 'aoe2'"
        )
        logger.debug("Fetched %d tracked profiles from DB", len(rows))
        return [dict(r) for r in rows]

    async def _get_guild_tracking_counts(self) -> dict[int, int]:
        rows = await self.db.fetch_all(
            "SELECT guild_id, COUNT(*) as cnt FROM game_accounts "
            "WHERE status = 'approved' AND tracking = 1 AND game = 'aoe2' "
            "GROUP BY guild_id"
        )
        return {r["guild_id"]: r["cnt"] for r in rows}

    async def _notify_tracking_status(self, message_template: str) -> None:
        counts = await self._get_guild_tracking_counts()
        for _guild_id, count in counts.items():
            msg = message_template.format(n=count)
            await notify_mod_channels(self.bot, self.db, msg)
            break  # notify_mod_channels already sends to all guilds
        if not counts:
            await notify_mod_channels(self.bot, self.db, message_template.format(n=0))

    async def _notify_per_guild(self, message_template: str) -> None:
        """Send per-guild notifications with guild-specific player counts."""
        counts = await self._get_guild_tracking_counts()
        all_guilds = await self.db.fetch_all(
            "SELECT guild_id, mod_channel_id FROM guilds WHERE mod_channel_id IS NOT NULL"
        )
        for guild_row in all_guilds:
            guild_id = guild_row["guild_id"]
            count = counts.get(guild_id, 0)
            if count == 0:
                continue
            channel = self.bot.get_channel(guild_row["mod_channel_id"])
            if channel is None:
                logger.warning("Mod channel %d not found for guild %d", guild_row["mod_channel_id"], guild_id)
                continue
            try:
                await channel.send(message_template.format(n=count))
            except Exception:
                logger.exception("Failed to send tracking notification to guild %d", guild_id)

    async def _resolve_match_guilds(
        self, player_profile_ids: list[str],
    ) -> dict[int, dict[str, Any]]:
        """For a list of profileIds in a match, find which guilds track them.

        Returns {guild_id: {"tracked_ids": set[str], "member_map": {profile_id: member_id}, "channel_id": int}}
        """
        if not player_profile_ids:
            return {}

        placeholders = ",".join("?" * len(player_profile_ids))
        rows = await self.db.fetch_all(
            f"SELECT ga.account_identifier, ga.member_id, ga.guild_id, gg.channel_id "
            f"FROM game_accounts ga "
            f"JOIN guild_games gg ON ga.guild_id = gg.guild_id AND gg.game = 'aoe2' AND gg.enabled = 1 "
            f"WHERE ga.account_identifier IN ({placeholders}) "
            f"AND ga.tracking = 1 AND ga.status = 'approved'",
            player_profile_ids,
        )

        guilds: dict[int, dict[str, Any]] = {}
        for row in rows:
            gid = row["guild_id"]
            if gid not in guilds:
                guilds[gid] = {
                    "tracked_ids": set(),
                    "member_map": {},
                    "channel_id": row["channel_id"],
                }
            guilds[gid]["tracked_ids"].add(row["account_identifier"])
            guilds[gid]["member_map"][row["account_identifier"]] = row["member_id"]

        return guilds

    async def _handle_match_added(self, match_data: dict[str, Any]) -> None:
        match_id = match_data["matchId"]
        players = match_data.get("players", [])
        profile_ids = [str(p["profileId"]) for p in players]

        guild_map = await self._resolve_match_guilds(profile_ids)
        if not guild_map:
            logger.debug("No guilds tracking players in match %d", match_id)
            return

        app_emojis = getattr(self.bot, "emoji_cache", {})

        for guild_id, info in guild_map.items():
            channel = self.bot.get_channel(info["channel_id"])
            if channel is None:
                logger.warning("Game channel %d not found for guild %d", info["channel_id"], guild_id)
                continue

            embed = build_active_match_embed(
                match_data, info["tracked_ids"], info["member_map"], app_emojis,
            )
            view = build_active_match_view(match_id)

            try:
                msg = await channel.send(embed=embed, view=view)
                logger.info("Sent match tracking message for match %d in guild %d", match_id, guild_id)

                account_row = await self.db.fetch_one(
                    "SELECT id FROM game_accounts "
                    "WHERE account_identifier IN ({}) AND guild_id = ? AND tracking = 1 LIMIT 1".format(
                        ",".join("?" * len(list(info["tracked_ids"])))
                    ),
                    [*list(info["tracked_ids"]), guild_id],
                )
                account_id = account_row["id"] if account_row else 0

                await self.db.execute(
                    "INSERT INTO tracked_matches "
                    "(match_id, guild_id, channel_id, message_id, account_id, status, match_data) "
                    "VALUES (?, ?, ?, ?, ?, 'active', ?)",
                    (str(match_id), guild_id, info["channel_id"], msg.id, account_id, json.dumps(match_data)),
                )
            except Exception:
                logger.exception("Failed to send/store match %d for guild %d", match_id, guild_id)

    async def _handle_match_removed(self, match_id: int) -> None:
        rows = await self.db.fetch_all(
            "SELECT id, guild_id, channel_id, message_id, match_data FROM tracked_matches "
            "WHERE match_id = ? AND status = 'active'",
            (str(match_id),),
        )
        if not rows:
            logger.debug("No tracked messages found for match %d", match_id)
            return

        result_data = await self._fetch_match_result(match_id)
        app_emojis = getattr(self.bot, "emoji_cache", {})

        self._trigger_analysis(match_id)

        for row in rows:
            channel = self.bot.get_channel(row["channel_id"])
            if channel is None:
                logger.warning("Channel %d not found for match %d edit", row["channel_id"], match_id)
                continue

            try:
                original_data = json.loads(row["match_data"]) if row["match_data"] else {}
                profile_ids = [str(p["profileId"]) for p in original_data.get("players", [])]
                guild_info = await self._resolve_match_guilds(profile_ids)
                info = guild_info.get(row["guild_id"], {"tracked_ids": set(), "member_map": {}})

                embed = build_finished_match_embed(
                    original_data, result_data, info["tracked_ids"], info["member_map"], app_emojis,
                )
                view = build_finished_match_view(match_id)

                message = await channel.fetch_message(row["message_id"])
                await message.edit(embed=embed, view=view)
                logger.info("Edited match %d message in guild %d", match_id, row["guild_id"])

                await self.db.execute(
                    "UPDATE tracked_matches SET status = 'finished', updated_at = datetime('now') WHERE id = ?",
                    (row["id"],),
                )
            except Exception:
                logger.exception("Failed to edit match %d message in guild %d", match_id, row["guild_id"])

    async def _fetch_match_result(self, match_id: int) -> dict[str, Any] | None:
        try:
            result = await self.api.fetch_match(match_id)
            if result and result.get("finished"):
                return result
            logger.debug("Match %d result not ready, retrying after delay", match_id)
            await asyncio.sleep(MATCH_RESULT_RETRY_DELAY)
            return await self.api.fetch_match(match_id)
        except Exception:
            logger.exception("Failed to fetch match result for %d", match_id)
            return None

    def _trigger_analysis(self, match_id: int) -> None:
        async def _fire_and_forget() -> None:
            url = AOE2_INSIGHTS_ANALYZE_URL.format(match_id=match_id)
            try:
                await self.api.fetch_text(url)
                logger.debug("Triggered analysis for match %d", match_id)
            except Exception:
                logger.debug("Analysis trigger for match %d failed (non-critical)", match_id)

        asyncio.create_task(_fire_and_forget())

    async def _run(self) -> None:
        while True:
            profiles = await self._get_tracked_profiles()
            profile_ids = list({p["account_identifier"] for p in profiles})

            self._ws = Aoe2WebSocket(profile_ids=profile_ids)
            self._reconnect_event.clear()

            if not profile_ids:
                logger.info("No profiles to track, idling")
                await self._reconnect_event.wait()
                continue

            logger.info("Starting WebSocket with %d profile(s)", len(profile_ids))

            listen_task = asyncio.ensure_future(self._consume_events())
            reconnect_task = asyncio.ensure_future(self._reconnect_event.wait())

            done, pending = await asyncio.wait(
                {listen_task, reconnect_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            await self._ws.close()

            if reconnect_task in done:
                logger.info("Reconnect requested, cycling connection")
                await self._notify_per_guild("Tracking list updated. Now monitoring {n} player(s).")
            else:
                logger.info("WebSocket listen ended, restarting")

    async def _consume_events(self) -> None:
        async for event in self._ws.listen():
            if event.type == "__connected__":
                await self._notify_per_guild("Match tracking connected. Monitoring {n} player(s).")
            elif event.type == "__disconnected__":
                await notify_mod_channels(self.bot, self.db, "Match tracking disconnected. Reconnecting...")
            elif event.type == "matchAdded":
                await self._handle_match_added(event.data)
            elif event.type == "matchRemoved":
                await self._handle_match_removed(event.match_id)
            else:
                logger.debug("Unhandled event type: %s", event.type)

    def start(self) -> None:
        if self._task is None or self._task.done():
            logger.info("Starting match tracker")
            self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task and not self._task.done():
            logger.info("Stopping match tracker")
            self._task.cancel()
        self._ws._closed = True

    async def reconnect(self) -> None:
        logger.info("Match tracker reconnect requested")
        self._reconnect_event.set()
