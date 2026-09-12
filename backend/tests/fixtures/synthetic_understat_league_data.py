"""A hand-written payload matching understat.com's REAL verified
`getLeagueData/{league}/{season}` JSON schema (see
app/providers/understat/provider.py — `teams`/`dates`/`players` keys,
per-match `history` entries with h_a/xG/xGA/npxG/ppda/deep, `dates` entries
with h/a team dicts + goals + datetime), but with entirely SYNTHETIC team
names and values — not a real season. Exists only to unit-test the parser
without needing network access on every test run. Must never be treated as
real match/xG data.
"""

SYNTHETIC_UNDERSTAT_LEAGUE_DATA = {
    "teams": {
        "101": {
            "id": "101",
            "title": "Synthetic United",
            "history": [
                {
                    "h_a": "h",
                    "xG": 1.82,
                    "xGA": 0.74,
                    "npxG": 1.60,
                    "npxGA": 0.74,
                    "ppda": {"att": 210, "def": 18},
                    "ppda_allowed": {"att": 300, "def": 25},
                    "deep": 8,
                    "deep_allowed": 3,
                    "scored": 2,
                    "missed": 1,
                    "date": "2023-08-12 15:00:00",
                    "result": "w",
                },
            ],
        },
        "102": {
            "id": "102",
            "title": "Synthetic City",
            "history": [
                {
                    "h_a": "a",
                    "xG": 0.74,
                    "xGA": 1.82,
                    "npxG": 0.74,
                    "npxGA": 1.60,
                    "ppda": {"att": 300, "def": 25},
                    "ppda_allowed": {"att": 210, "def": 18},
                    "deep": 3,
                    "deep_allowed": 8,
                    "scored": 1,
                    "missed": 2,
                    "date": "2023-08-12 15:00:00",
                    "result": "l",
                },
            ],
        },
    },
    "dates": [
        {
            "id": "9001",
            "isResult": True,
            "h": {"id": "101", "title": "Synthetic United", "short_title": "SUN"},
            "a": {"id": "102", "title": "Synthetic City", "short_title": "SCI"},
            "goals": {"h": "2", "a": "1"},
            "xG": {"h": "1.82", "a": "0.74"},
            "datetime": "2023-08-12 15:00:00",
            "forecast": {"w": "0.60", "d": "0.25", "l": "0.15"},
        },
        {
            "id": "9002",
            "isResult": False,
            "h": {"id": "102", "title": "Synthetic City", "short_title": "SCI"},
            "a": {"id": "101", "title": "Synthetic United", "short_title": "SUN"},
            "goals": {"h": None, "a": None},
            "xG": {"h": "0", "a": "0"},
            "datetime": "2023-08-19 15:00:00",
            "forecast": {"w": "0.30", "d": "0.30", "l": "0.40"},
        },
    ],
    "players": [],
}
