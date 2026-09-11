from app.providers.football_data_co_uk.provider import (
    FootballDataCoUkProvider,
    season_label_to_code,
)
from tests.fixtures.synthetic_football_data_sample import SYNTHETIC_FOOTBALL_DATA_CSV


def test_season_label_to_code():
    assert season_label_to_code("2024/2025") == "2425"
    assert season_label_to_code("2023/2024") == "2324"


def test_build_csv_url():
    provider = FootballDataCoUkProvider()
    assert provider.build_csv_url("EPL", "2024/2025") == (
        "https://www.football-data.co.uk/mmz4281/2425/E0.csv"
    )
    assert provider.build_csv_url("SERIE_A", "2023/2024") == (
        "https://www.football-data.co.uk/mmz4281/2324/I1.csv"
    )


def test_parse_csv_extracts_results_and_generic_bookmaker_odds():
    provider = FootballDataCoUkProvider()
    records = provider.parse_csv(SYNTHETIC_FOOTBALL_DATA_CSV, "EPL", "2023/2024")

    assert len(records) == 3
    first = records[0]
    assert first.home_team_name == "Synthetic United"
    assert first.away_team_name == "Synthetic City"
    assert first.home_goals_ft == 2
    assert first.away_goals_ft == 1
    assert first.referee_name == "A. Referee"
    assert first.home_shots == 14
    assert first.home_corners == 7

    # Bookmaker odds discovered generically (Bet365, Pinnacle, Market Max/Avg).
    assert first.closing_odds_1x2["Bet365"] == {"H": 1.90, "D": 3.60, "A": 4.20}
    assert first.closing_odds_1x2["Pinnacle"] == {"H": 1.95, "D": 3.55, "A": 4.10}
    assert first.closing_odds_1x2["Market Average"] == {"H": 1.92, "D": 3.58, "A": 4.15}
    assert first.closing_odds_over_under_2_5["Bet365"] == {"OVER": 1.85, "UNDER": 1.95}

    # True closing-line columns ("B365CH", "PC>2.5", ...) are surfaced under a
    # separate "(closing)" bookmaker key, never conflated with the pre-closing
    # quote under the same bookmaker name.
    assert first.closing_odds_1x2["Bet365 (closing)"] == {"H": 1.88, "D": 3.65, "A": 4.10}
    assert first.closing_odds_1x2["Pinnacle (closing)"] == {"H": 1.93, "D": 3.50, "A": 4.05}
    assert first.closing_odds_over_under_2_5["Bet365 (closing)"] == {"OVER": 1.83, "UNDER": 1.97}
    assert first.closing_odds_over_under_2_5["Pinnacle (closing)"] == {"OVER": 1.86, "UNDER": 1.94}


def test_parse_csv_handles_kickoff_datetime():
    provider = FootballDataCoUkProvider()
    records = provider.parse_csv(SYNTHETIC_FOOTBALL_DATA_CSV, "EPL", "2023/2024")
    assert records[0].kickoff_utc.year == 2023
    assert records[0].kickoff_utc.month == 8
    assert records[0].kickoff_utc.day == 12
    assert records[0].kickoff_utc.hour == 15
