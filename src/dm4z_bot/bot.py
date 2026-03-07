from __future__ import annotations

import logging

import discord

from dm4z_bot.config import Settings
from dm4z_bot.database.db import Database
from dm4z_bot.services.aoe2_api import Aoe2Api
from dm4z_bot.services.games.aoe2_service import Aoe2Service
from dm4z_bot.services.games.cs2_service import Cs2Service
from dm4z_bot.services.games.registry import GameRegistry
from dm4z_bot.tasks.stat_fetcher import StatFetcher

logger = logging.getLogger(__name__)

COMMAND_EXTENSIONS: tuple[str, ...] = (
    "dm4z_bot.commands.age",
    "dm4z_bot.commands.match_info",
    "dm4z_bot.commands.rank",
    "dm4z_bot.commands.team_rank",
    "dm4z_bot.commands.leaderboard",
    "dm4z_bot.commands.link",
    "dm4z_bot.commands.approve",
    "dm4z_bot.commands.profile",
    "dm4z_bot.commands.stats",
    "dm4z_bot.commands.guild_config",
)

EVENT_EXTENSIONS: tuple[str, ...] = (
    "dm4z_bot.events.message_handler",
    "dm4z_bot.events.guild_events",
    "dm4z_bot.events.member_events",
)


class Dm4zBot(discord.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        debug_guilds = [settings.debug_guild_id] if settings.debug_guild_id else None

        if debug_guilds:
            logger.info("Debug mode enabled for guild: %s", settings.debug_guild_id)
        else:
            logger.info("Global command mode enabled")

        super().__init__(intents=intents, debug_guilds=debug_guilds)

        self.aoe2_api = Aoe2Api()
        self.db = Database(settings.database_path)
        self.game_registry = GameRegistry()
        self.game_registry.register(Aoe2Service(self.aoe2_api))
        self.game_registry.register(Cs2Service())
        self.stat_fetcher = StatFetcher(self.db, self.game_registry)
        self._setup_complete = False
        self.before_invoke(self._before_invoke_hook)

    async def setup_hook(self) -> None:
        if self._setup_complete:
            logger.info("Setup already completed, skipping")
            return

        await self.db.connect()

        logger.info("Loading %d extensions...", len(COMMAND_EXTENSIONS) + len(EVENT_EXTENSIONS))

        for extension in (*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS):
            try:
                self.load_extension(extension)
                logger.info("Loaded extension: %s", extension)
            except Exception as e:
                logger.error("Failed to load extension %s: %s", extension, e)

        logger.info("Extensions loaded. Pending commands: %d", len(self.pending_application_commands))

        try:
            synced = await self.sync_commands()
            if synced is not None:
                logger.info("Synced %d command(s)", len(synced))
            else:
                logger.info("Command sync completed (no commands to sync)")
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

        self.stat_fetcher.start()
        self._setup_complete = True

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Logged in as %s", self.user.name)

            if not self._setup_complete:
                logger.warning("Setup not completed - running setup_hook manually")
                await self.setup_hook()

            logger.info("Bot is ready! Loaded %d commands", len(self.pending_application_commands))

    async def _before_invoke_hook(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild_id is None:
            return
        logger.debug(
            "Command /%s invoked by %s in guild %d",
            ctx.command.qualified_name, ctx.author, ctx.guild_id,
        )
        try:
            await self.db.execute(
                "INSERT INTO command_usage (guild_id, member_id, command_name) VALUES (?, ?, ?)",
                (ctx.guild_id, ctx.author.id, ctx.command.qualified_name),
            )
        except Exception:
            logger.exception("Failed to track command usage")

    async def close(self) -> None:
        logger.info("Bot shutting down")
        self.stat_fetcher.stop()
        await self.db.close()
        await super().close()
