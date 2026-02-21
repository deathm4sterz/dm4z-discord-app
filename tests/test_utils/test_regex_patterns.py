from dm4z_bot.utils.regex_patterns import extract_match_id


def test_extract_match_id_from_plain_digits() -> None:
    assert extract_match_id("123456789") == "123456789"


def test_extract_match_id_from_link() -> None:
    value = "https://httpbin.org/redirect-to?url=aoe2de://0/987654321"
    assert extract_match_id(value) == "987654321"


def test_extract_match_id_returns_none_when_missing() -> None:
    assert extract_match_id("no match id here") is None

