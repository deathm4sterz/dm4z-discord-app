# dm4z-discord-app

AoE2 community Discord bot implemented in Python with `py-cord`.

## Features

- `/age`: displays account creation date for the selected user (or yourself)
- `/match_info`: extracts a 9-digit match id from text/link and posts quick action buttons
- `/rank`: shows 1v1 rank data via aoe2companion nightbot API
- `/team_rank`: shows team-rank data via aoe2companion nightbot API
- `/leaderboard`: shows server-local leaderboard via aoe2insights
- Automatic message listener for `aoe2de` links in channel messages

## Requirements

- Python 3.12+
- Poetry 1.8+
- Discord bot token with message content intent enabled

## Local setup

```bash
poetry install --with dev
```

Create a `.env` file:

```env
DISCORD_TOKEN=your_token_here
LOG_LEVEL=INFO
```

Run locally:

```bash
poetry run python -m src.main
```

## Test Suite

Run lint and tests locally:

```bash
poetry run ruff check .
poetry run pytest
```

If you are using the project virtualenv (`pyvenv`) directly:

```bash
. pyvenv/Scripts/activate
PYTHONPATH=src python -m ruff check .
PYTHONPATH=src python -m pytest -q
```

### Reviewing Results

- `ruff check` passes when output is `All checks passed!`.
- `pytest` is configured to enforce code coverage:
  - coverage source: `src/`
  - minimum required coverage: `100%`
  - failing coverage exits non-zero (`--cov-fail-under=100`)
- terminal coverage details are shown with missing lines (`--cov-report=term-missing`)
- XML coverage report is written to `coverage.xml` for CI/report tooling
- expected successful test summary looks like:
  - `29 passed`
  - `Required test coverage of 100% reached. Total coverage: 100.00%`

### Common Failures

- `ModuleNotFoundError: dm4z_bot`:
  - run tests with `PYTHONPATH=src` (or use Poetry which resolves package paths)
- coverage failure:
  - pytest output includes exact files/lines below threshold
- upstream dependency warnings:
  - warnings from py-cord internals can appear without indicating a test failure

## Docker

Build and run:

```bash
docker compose up --build
```

The container expects:

- `DISCORD_TOKEN`
- `LOG_LEVEL` (optional, default `INFO`)

## Project layout

```text
src/
  dm4z_bot/
    bot.py
    config.py
    commands/
    events/
    services/
    utils/
  main.py
tests/
```

