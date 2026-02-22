from __future__ import annotations

import logging

import discord

from dm4z_bot.config import load_settings
from dm4z_bot.services.aoe2_api import Aoe2Api

logger = logging.getLogger(__name__)

COMMAND_EXTENSIONS: tuple[str, ...] = (
    "dm4z_bot.commands.age",
    "dm4z_bot.commands.match_info",
    "dm4z_bot.commands.rank",
    "dm4z_bot.commands.team_rank",
    "dm4z_bot.commands.leaderboard",
)

EVENT_EXTENSIONS: tuple[str, ...] = ("dm4z_bot.events.message_handler",)


class Dm4zBot(discord.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        
        # Load settings to get debug guild ID if set
        settings = load_settings()
        debug_guilds = [settings.debug_guild_id] if settings.debug_guild_id else None
        
        if debug_guilds:
            logger.info("Debug mode enabled for guild: %s", settings.debug_guild_id)
        else:
            logger.info("Global command mode enabled")
        
        super().__init__(intents=intents, debug_guilds=debug_guilds)
        self.aoe2_api = Aoe2Api()
        self._setup_complete = False

    async def setup_hook(self) -> None:
        if self._setup_complete:
            logger.info("Setup already completed, skipping")
            return
            
        logger.info("Loading %d extensions...", len(COMMAND_EXTENSIONS) + len(EVENT_EXTENSIONS))
        
        for extension in (*COMMAND_EXTENSIONS, *EVENT_EXTENSIONS):
            try:
                self.load_extension(extension)
                logger.info("Loaded extension: %s", extension)
            except Exception as e:
                logger.error("Failed to load extension %s: %s", extension, e)
        
        logger.info("Extensions loaded. Pending commands: %d", len(self.pending_application_commands))
        
        # Sync commands with Discord
        try:
            synced = await self.sync_commands()
            if synced is not None:
                logger.info("Synced %d command(s)", len(synced))
            else:
                logger.info("Command sync completed (no commands to sync)")
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)
        
        self._setup_complete = True

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Logged in as %s", self.user.name)
            
            # Ensure setup_hook was called - if not, call it now
            if not self._setup_complete:
                logger.warning("Setup not completed - running setup_hook manually")
                await self.setup_hook()
            
            logger.info("Bot is ready! Loaded %d commands", len(self.pending_application_commands))

