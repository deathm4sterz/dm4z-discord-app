# Agent Guidelines for dm4z-discord-app

AI agent guidelines for this AoE2 Discord bot project.

## Pre-Commit Testing Protocol

**CRITICAL**: Always run complete linter and test suite before committing.

```bash
# Required commands (both must pass)
poetry run ruff check .      # Must show "All checks passed!"
poetry run pytest           # Must show 100% coverage, ~29 tests pass
```

**Alternative (virtualenv):**
```bash
. pyvenv/Scripts/activate
PYTHONPATH=src python -m ruff check .
PYTHONPATH=src python -m pytest -q
```

**Error Handling:** Fix linting/test failures or prompt user with exact errors for domain-specific issues.

## Project Architecture

- **Structure**: `src/dm4z_bot/` → `commands/`, `events/`, `services/`, `utils/`
- **Commands**: Discord commands as separate Cogs in `commands/`
- **Events**: Discord event handlers in `events/`
- **Services**: External APIs (like `aoe2_api.py`) in `services/`
- **Config**: Frozen dataclasses for settings

## Python Standards

```python
from __future__ import annotations  # Always first import
# Type hints: int | None (not Optional[int])
# Dataclasses: @dataclass(frozen=True) for immutable data
# Async: All Discord interactions must be async
```

## Discord Bot Patterns

```python
# Command setup pattern
class CommandCog(discord.Cog):
    def __init__(self, bot: discord.Bot, api: Aoe2Api) -> None:
        self.bot = bot
        self.api = api

def setup(bot: discord.Bot) -> None:
    api = cast(Aoe2Api, bot.aoe2_api)
    bot.add_cog(CommandCog(bot, api))
```

**Key Patterns:**
- Always `await ctx.defer()` for long-running commands
- Use `ctx.respond()` for immediate, `ctx.followup.send()` for deferred
- Module-level loggers: `logger = logging.getLogger(__name__)`

## Testing Requirements

- **100% Coverage**: Mandatory, no exceptions
- **Async Tests**: Use `@pytest.mark.asyncio`
- **Mock Pattern**: Create `Fake*` classes (see `FakeContext`, `FakeApi`)
- **Test Structure**: Mirror source in `tests/` directory
- **Callback Testing**: Test command callbacks directly

## Environment & Configuration

```python
# Required: DISCORD_TOKEN (mandatory), LOG_LEVEL (optional)
# Optional: DEBUG_GUILD_ID (for testing)
# Pattern: load_settings() → frozen dataclass
# Always: load_dotenv() before getenv()
# Errors: raise RuntimeError for missing required vars
```

## API Integration

```python
# HTTP: httpx.AsyncClient with 5s timeout
# Headers: Always set DEFAULT_USER_AGENT
# Errors: Convert HTTP errors to descriptive exceptions
# URLs: Use urllib.parse.urlencode for queries
```

## Error Handling

```python
# User messages: "❌ Failed to fetch..." (friendly)
# Internal: logger.error() with actual exception
# Timeouts: Handle httpx.TimeoutException specifically
# Chaining: raise Exception(...) from e
```

## Docker Standards

- Multi-stage build (Poetry export → Alpine runtime)
- Non-root user (`botuser`)
- Environment: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`
- Entry: `python -m main` from `/app/src`

## Development Workflow

- **CI Pipeline**: Lint → Test → Coverage → Docker
- **Coverage**: Automatic Codecov upload
- **Registry**: `ghcr.io` for Docker images
- **Versioning**: Semantic in `pyproject.toml`
- **Dependencies**: Poetry + Dependabot

## Security

- **Tokens**: Environment only, never commit
- **Validation**: All user inputs (match IDs, names)
- **Docker**: Non-root containers
- **APIs**: Timeout all external calls

## Performance

- **Connections**: `async with httpx.AsyncClient()` context managers
- **Deferring**: Always defer API-calling commands
- **Timeouts**: 5s default for external APIs
- **Memory**: Frozen dataclasses prevent mutations

## Quick Reference

**Tech Stack:** Python 3.12 + py-cord + httpx + Poetry  
**Commands:** `/age`, `/match_info`, `/rank`, `/team_rank`, `/leaderboard`  
**APIs:** aoe2companion nightbot, aoe2insights  
**Coverage:** 100% required via pytest-cov  
**Linting:** ruff (line-length=100, target=py312)