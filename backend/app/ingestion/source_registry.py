"""Canonical registry of every data source considered for this project.

This is the single source of truth backing the `sources` table and
DATA_SOURCES.md — the categories below must stay consistent with that document.
"""

from dataclasses import dataclass

from app.models.enums import DataSourceCategory


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    category: DataSourceCategory
    is_implemented: bool
    notes: str


SOURCE_REGISTRY: list[SourceDefinition] = [
    SourceDefinition(
        key="football_data_co_uk",
        name="football-data.co.uk",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=True,
        notes="Historical results + closing bookmaker odds CSV, no key required. Primary source.",
    ),
    SourceDefinition(
        key="api_football",
        name="API-Football (api-football.com)",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=True,
        notes="Free tier: 100 req/day (search-corroborated, not read from the live pricing page "
        "in this session). Requires API key. See DATA_SOURCES.md.",
    ),
    SourceDefinition(
        key="understat",
        name="understat.com",
        category=DataSourceCategory.B_PERSONAL_USE_ONLY,
        is_implemented=True,
        notes="xG/xA/PPDA/deep-completions via GET /getLeagueData/{league}/{season} "
        "(session-cookie based, verified with real requests this session — old "
        "embedded-<script> approach is broken, site redesigned). Reclassified A->B: "
        "robots.txt disallows all (Disallow: / for User-agent: *), no published ToS "
        "found. Requires acknowledge_personal_use_only=True. EPL/Serie A since 2014/15.",
    ),
    SourceDefinition(
        key="fbref",
        name="fbref.com",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=True,
        notes="Advanced team/player stats. Rate-limited to 10 req/min (enforced in-process).",
    ),
    SourceDefinition(
        key="statsbomb_open_data",
        name="StatsBomb Open Data",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=False,
        notes="Verified: only 2015/16 + one archival season each for PL/Serie A men's club "
        "football. Not usable as a current-season feed; useful only for methodology "
        "validation on those frozen seasons. Not implemented as a provider in this slice.",
    ),
    SourceDefinition(
        key="aia_figc",
        name="AIA-FIGC referee designations",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=False,
        notes="Public HTML pages (not an API). Parser not yet implemented in this slice.",
    ),
    SourceDefinition(
        key="pgmol_premier_league",
        name="Premier League / PGMOL match officials",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=False,
        notes="Published as per-matchweek news articles on premierleague.com. Parser not yet "
        "implemented in this slice.",
    ),
    SourceDefinition(
        key="transfermarkt",
        name="Transfermarkt",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=False,
        notes="ToS/robots.txt not directly read in this session (low confidence, see "
        "DATA_SOURCES.md) — widely scraped in practice. Not implemented in this slice.",
    ),
    SourceDefinition(
        key="open_meteo",
        name="Open-Meteo",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=True,
        notes="Free public weather forecast API, no key required.",
    ),
    SourceDefinition(
        key="rss_generic",
        name="Generic RSS/Atom news feed",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=True,
        notes="Feed URL supplied by configuration, not a specific hardcoded site.",
    ),
    SourceDefinition(
        key="whoscored",
        name="WhoScored",
        category=DataSourceCategory.B_PERSONAL_USE_ONLY,
        is_implemented=False,
        notes="ToS explicitly requires a licence for betting-platform use. Personal-use-only "
        "flag required to instantiate; scraping itself not implemented (unverified endpoints).",
    ),
    SourceDefinition(
        key="sofascore",
        name="SofaScore",
        category=DataSourceCategory.B_PERSONAL_USE_ONLY,
        is_implemented=False,
        notes="ToS prohibits commercial/data-mining use and disclaims supplying bookmakers. "
        "Personal-use-only flag required to instantiate; scraping not implemented.",
    ),
    SourceDefinition(
        key="sos_fanta",
        name="SOS Fanta (probable lineups)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="ToS/endpoints not verified in this project; interface only.",
    ),
    SourceDefinition(
        key="gazzetta_dello_sport",
        name="Gazzetta dello Sport (probable lineups)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="ToS/endpoints not verified in this project; interface only.",
    ),
    SourceDefinition(
        key="eplay24",
        name="ePlay24",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="No known public API/odds feed found. ADM-licensed bookmaker; ToS not directly "
        "read in this session. Abstract OddsProvider only — see DATA_SOURCES.md.",
    ),
    SourceDefinition(
        key="synthetic_dev_fixture",
        name="Synthetic dev fixture",
        category=DataSourceCategory.A_UNRESTRICTED,
        is_implemented=True,
        notes="SYNTHETIC TEST FIXTURE — NOT REAL DATA. Generated locally by "
        "scripts/seed_dev_fixture.py purely to smoke-test DB/API/frontend wiring end "
        "to end. Never used for real analysis; must never be confused with a real "
        "sports-data source. See README.md.",
    ),
    SourceDefinition(
        key="legaseriea",
        name="Lega Serie A (legaseriea.it)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Own terms explicitly forbid data mining; official match data exclusively "
        "licensed to Genius Sports through 2028/29. Abstract interface only.",
    ),
]
