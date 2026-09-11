"""Real SportsDataProvider for football-data.co.uk (DATA_SOURCES.md category A).

football-data.co.uk publishes free, anonymous, no-key CSV downloads of historical
match results and bookmaker closing odds at:

    https://www.football-data.co.uk/mmz4281/<season>/<div>.csv

where <season> is a 4-digit code (e.g. "2425" = 2024/25) and <div> is the
competition code ("E0" = English Premier League, "I1" = Italian Serie A).

Column layout (verified directly against the live https://www.football-data.co.uk/notes.txt
and a real downloaded 2024/25 Premier League file — see DATA_SOURCES.md):
Div, Date, Time, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR, Referee,
HS, AS, HST, AST, HC, AC, HF, AF, HY, AY, HR, AR, plus a variable set of
per-bookmaker 1X2 odds columns (e.g. B365H/D/A, PSH/PSD/PSA) and Over/Under 2.5
columns (e.g. B365>2.5/B365<2.5).

Crucially, the site publishes **two** snapshots per bookmaker: the plain column
(e.g. `B365H`) is a **pre-closing** quote (collected Fri/Tue afternoon per the
site's own notes), while the same prefix with a "C" inserted before the H/D/A
(or before the >/< for totals) — e.g. `B365CH`, `PC>2.5` — is the true **closing**
quote. This provider surfaces both, under bookmaker keys `"<Name>"` (pre-closing)
and `"<Name> (closing)"`, so callers that want the closing line (the standard,
more efficient benchmark for backtesting — see BACKTEST_SPEC.md) can select it
explicitly instead of silently getting pre-closing data.

The exact bookmaker panel varies by season, so this provider discovers odds
columns generically against a known prefix→name table instead of assuming a
fixed panel (see `_extract_1x2_odds` / `_extract_ou25_odds`).

This provider has been verified with a real HTTP GET against the live site
(2024/25 Premier League file, 380 rows, matching this exact column layout).
"""

import io
from datetime import UTC, datetime

import httpx
import pandas as pd

from app.models.enums import DataSourceCategory
from app.providers.base.dto import HistoricalMatchRecord
from app.providers.base.sports_data_provider import SportsDataProvider

BASE_URL = "https://www.football-data.co.uk/mmz4281"

# Competition code -> football-data.co.uk division code.
COMPETITION_TO_DIV = {
    "EPL": "E0",
    "SERIE_A": "I1",
}


def season_label_to_code(season_label: str) -> str:
    """"2024/2025" -> "2425"."""
    start, end = season_label.split("/")
    return f"{start[-2:]}{end[-2:]}"


class FootballDataCoUkProvider(SportsDataProvider):
    source_key = "football_data_co_uk"
    category = DataSourceCategory.A_UNRESTRICTED

    def __init__(self, http_client: httpx.Client | None = None, timeout_s: float = 30.0) -> None:
        self._client = http_client or httpx.Client(timeout=timeout_s, follow_redirects=True)

    def is_available(self) -> bool:
        # No credentials required; availability is really a network-reachability
        # question, which we don't probe eagerly here to avoid an extra request
        # on every check — a failed download simply raises, which callers/ingestion
        # scripts must handle explicitly rather than falling back to fake data.
        return True

    def build_csv_url(self, competition_code: str, season_label: str) -> str:
        if competition_code not in COMPETITION_TO_DIV:
            raise ValueError(
                f"Unsupported competition_code {competition_code!r}; "
                f"known: {sorted(COMPETITION_TO_DIV)}"
            )
        div = COMPETITION_TO_DIV[competition_code]
        season_code = season_label_to_code(season_label)
        return f"{BASE_URL}/{season_code}/{div}.csv"

    def get_historical_matches(
        self, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        url = self.build_csv_url(competition_code, season_label)
        response = self._client.get(url)
        response.raise_for_status()
        return self.parse_csv(response.text, competition_code, season_label)

    def parse_csv(
        self, csv_text: str, competition_code: str, season_label: str
    ) -> list[HistoricalMatchRecord]:
        df = pd.read_csv(io.StringIO(csv_text))
        df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])

        records: list[HistoricalMatchRecord] = []
        for _, row in df.iterrows():
            kickoff = _parse_kickoff(row.get("Date"), row.get("Time"))
            records.append(
                HistoricalMatchRecord(
                    competition_code=competition_code,
                    season_label=season_label,
                    kickoff_utc=kickoff,
                    home_team_name=str(row["HomeTeam"]).strip(),
                    away_team_name=str(row["AwayTeam"]).strip(),
                    home_goals_ft=int(row["FTHG"]),
                    away_goals_ft=int(row["FTAG"]),
                    home_goals_ht=_safe_int(row.get("HTHG")),
                    away_goals_ht=_safe_int(row.get("HTAG")),
                    referee_name=_safe_str(row.get("Referee")),
                    home_shots=_safe_int(row.get("HS")),
                    away_shots=_safe_int(row.get("AS")),
                    home_shots_on_target=_safe_int(row.get("HST")),
                    away_shots_on_target=_safe_int(row.get("AST")),
                    home_corners=_safe_int(row.get("HC")),
                    away_corners=_safe_int(row.get("AC")),
                    home_fouls=_safe_int(row.get("HF")),
                    away_fouls=_safe_int(row.get("AF")),
                    home_yellow_cards=_safe_int(row.get("HY")),
                    away_yellow_cards=_safe_int(row.get("AY")),
                    home_red_cards=_safe_int(row.get("HR")),
                    away_red_cards=_safe_int(row.get("AR")),
                    closing_odds_1x2=_extract_1x2_odds(row),
                    closing_odds_over_under_2_5=_extract_ou25_odds(row),
                    external_ref=(
                        f"{competition_code}:{season_label}:"
                        f"{row['HomeTeam']}:{row['AwayTeam']}:{row.get('Date')}"
                    ),
                )
            )
        return records


def _safe_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _parse_kickoff(date_value: object, time_value: object) -> datetime:
    date_str = str(date_value).strip()
    time_str = str(time_value).strip() if time_value is not None and str(time_value) != "nan" else "15:00"
    for date_fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", f"{date_fmt} %H:%M")  # noqa: DTZ007
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date/time format: {date_value!r} {time_value!r}")


# Odds columns are prefixed by a per-bookmaker code and suffixed H/D/A for 1X2
# (e.g. "B365H", "B365D", "B365A") or by ">2.5"/"<2.5" for the Over/Under 2.5
# market (e.g. "B365>2.5", "B365<2.5"). Table verified against the live
# notes.txt (2026) — includes both currently-used and legacy (pre-2020ish)
# bookmaker codes, since older season files still carry the latter.
_KNOWN_BOOKMAKER_PREFIXES = {
    "1XB": "1XBet",
    "B365": "Bet365",
    "BF": "Betfair",
    "BFD": "Betfred",
    "BMGM": "BetMGM",
    "BV": "BetVictor",
    "BS": "Blue Square",
    "BW": "Bet&Win",
    "CL": "Coral",
    "GB": "Gamebookers",
    "IW": "Interwetten",
    "LB": "Ladbrokes",
    "PP": "Paddy Power",
    "PS": "Pinnacle",
    "P": "Pinnacle",  # O/U totals (and some older 1X2 files) use "P" not "PS"
    "SK": "Skybet",
    "SO": "Sporting Odds",
    "SB": "Sportingbet",
    "SJ": "Stan James",
    "SY": "Stanleybet",
    "VC": "VC Bet",
    "WH": "William Hill",
    "Max": "Market Max",
    "Avg": "Market Average",
    "BFE": "Betfair Exchange",
}

# Same bookmakers, but the "C" (closing) column variant — e.g. "B365CH" instead
# of "B365H", "PC>2.5" instead of "P>2.5". Kept as a separate table (rather than
# derived by string-inserting "C" into the prefixes above) because the closing
# variant isn't always just "<prefix>C" for every prefix (e.g. Pinnacle O/U
# closing is "PC", derived from "P", not from "PS").
_KNOWN_CLOSING_BOOKMAKER_PREFIXES = {
    "1XBC": "1XBet (closing)",
    "B365C": "Bet365 (closing)",
    "BFC": "Betfair (closing)",
    "BFDC": "Betfred (closing)",
    "BWC": "Bet&Win (closing)",
    "PSC": "Pinnacle (closing)",
    "PC": "Pinnacle (closing)",
    "WHC": "William Hill (closing)",
    "MaxC": "Market Max (closing)",
    "AvgC": "Market Average (closing)",
    "BFEC": "Betfair Exchange (closing)",
}


def _extract_1x2_odds(row: pd.Series) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for prefix, name in {**_KNOWN_BOOKMAKER_PREFIXES, **_KNOWN_CLOSING_BOOKMAKER_PREFIXES}.items():
        h, d, a = f"{prefix}H", f"{prefix}D", f"{prefix}A"
        if h in row.index and d in row.index and a in row.index:
            h_val, d_val, a_val = _safe_int_odds(row[h]), _safe_int_odds(row[d]), _safe_int_odds(row[a])
            if h_val is not None and d_val is not None and a_val is not None:
                result[name] = {"H": h_val, "D": d_val, "A": a_val}
    return result


def _extract_ou25_odds(row: pd.Series) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for prefix, name in {**_KNOWN_BOOKMAKER_PREFIXES, **_KNOWN_CLOSING_BOOKMAKER_PREFIXES}.items():
        over_col, under_col = f"{prefix}>2.5", f"{prefix}<2.5"
        if over_col in row.index and under_col in row.index:
            over_val, under_val = _safe_int_odds(row[over_col]), _safe_int_odds(row[under_col])
            if over_val is not None and under_val is not None:
                result[name] = {"OVER": over_val, "UNDER": under_val}
    return result


def _safe_int_odds(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
