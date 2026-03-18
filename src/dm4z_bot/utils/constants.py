PLAYER_IDS: tuple[str, ...] = (
    "9997875",  # Kratos
    "6903668",  # Nagraj
    "1489563",  # deadmeat
    "15625569",  # CVS
    "2543215",  # marathaSun
    "14257193",  # Silincer
    "15144378",  # joettli
    "11959979",  # Dancing Doggo
    "1228227",  # hjpotter92
    "5968579",  # N.O.P.E
)

PROFILE_API_URL = "https://data.aoe2companion.com/api/profiles"
PROFILE_URL = "https://www.aoe2companion.com/players/{profile_id}"
LEADERBOARD_URL_TEMPLATE = (
    "https://www.aoe2insights.com/nightbot/leaderboard/3/"
    "?user_ids={user_ids}&rank=global&limit=5"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)

PLATFORM_ICONS: dict[str, str] = {
    "steam": "https://cdn3.emoji.gg/emojis/steam.png",
    "playstation": "https://cdn3.emoji.gg/emojis/83525-playstationwhite.png",
    "xbox": "https://cdn3.emoji.gg/emojis/41927-xbox.png",
}

MATCH_API_URL = "https://data.aoe2companion.com/api/matches"
AOE2_COMPANION_MATCH_URL = "https://www.aoe2companion.com/match/{match_id}"
AOE2_INSIGHTS_MATCH_URL = "https://www.aoe2insights.com/match/{match_id}/"
AOE2_INSIGHTS_ANALYZE_URL = "https://www.aoe2insights.com/match/{match_id}/analyze/"
SPECTATE_URL = "https://httpbin.org/redirect-to?url=aoe2de://1/{match_id}"
REPLAY_URL = "https://aoe.ms/replay/?gameId={match_id}&profileId={profile_id}"
AOE2_TECH_TREE_URL = "https://aoe2techtree.net/#{civ_name}"

LEETIFY_LOGO = "https://leetify.com/assets/images/meta/logo.png"
LEETIFY_PROFILE_URL = "https://leetify.com/app/profile/{steam64_id}"
LEETIFY_PINK = 0xF84982

LEETIFY_BASE_URL = "https://api-public.cs-prod.leetify.com"
LEETIFY_PROFILE_PATH = "/v3/profile"
LEETIFY_API_KEY_HEADER = "_leetify_key"
