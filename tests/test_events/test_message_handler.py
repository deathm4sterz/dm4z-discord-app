import pytest

from dm4z_bot.events.message_handler import MessageEvents


class FakeAuthor:
    def __init__(self, bot: bool) -> None:
        self.bot = bot


class FakeChannel:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, content: str, view: object) -> None:
        self.messages.append(content)


class FakeMessage:
    def __init__(self, content: str, bot_author: bool = False) -> None:
        self.content = content
        self.author = FakeAuthor(bot_author)
        self.channel = FakeChannel()


class FakeBot:
    def __init__(self) -> None:
        self.cogs: list[str] = []

    def add_cog(self, cog: object) -> None:
        self.cogs.append(type(cog).__name__)


@pytest.mark.asyncio
async def test_on_message_sends_match_reply_for_aoe2de_link() -> None:
    cog = MessageEvents(bot=None)  # type: ignore[arg-type]
    message = FakeMessage("aoe2de://0/123456789")
    await cog.on_message(message)  # type: ignore[arg-type]
    assert message.channel.messages == ["Extracted Match ID: **123456789**"]


@pytest.mark.asyncio
async def test_on_message_ignores_non_aoe_content() -> None:
    cog = MessageEvents(bot=None)  # type: ignore[arg-type]
    message = FakeMessage("hello world")
    await cog.on_message(message)  # type: ignore[arg-type]
    assert message.channel.messages == []


@pytest.mark.asyncio
async def test_on_message_ignores_bot_messages() -> None:
    cog = MessageEvents(bot=None)  # type: ignore[arg-type]
    message = FakeMessage("aoe2de://0/123456789", bot_author=True)
    await cog.on_message(message)  # type: ignore[arg-type]
    assert message.channel.messages == []


@pytest.mark.asyncio
async def test_on_message_aoe2de_without_match_id_does_not_send() -> None:
    cog = MessageEvents(bot=None)  # type: ignore[arg-type]
    message = FakeMessage("aoe2de://0/not-a-match")
    await cog.on_message(message)  # type: ignore[arg-type]
    assert message.channel.messages == []


def test_setup_registers_event_cog() -> None:
    from dm4z_bot.events import message_handler

    bot = FakeBot()
    message_handler.setup(bot)  # type: ignore[arg-type]
    assert bot.cogs == ["MessageEvents"]

