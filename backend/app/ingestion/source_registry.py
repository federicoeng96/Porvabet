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
        notes="Verified this session: RCS Mediagroup network affiliate (Gazzanet), own "
        "footer confirms it; lineup content is free-text prose (rotations/doubts "
        "narrative), not structured fields. Not pursued — same corporate-network risk "
        "as Gazzetta plus unreliable-to-parse content. See DATA_SOURCES.md.",
    ),
    SourceDefinition(
        key="gazzetta_dello_sport",
        name="Gazzetta dello Sport (probable lineups)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Verified this session (not just unverified-C as before): RCS Mediagroup's "
        "own Data Mining Policy page explicitly reserves TDM/scraping rights under "
        "art. 70-quater, no personal-use exception — same absolute-prohibition "
        "treatment as diretta.it/Flashscore. New use case (tactics vs. player props) "
        "does not reopen this source. See DATA_SOURCES.md.",
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
    SourceDefinition(
        key="betson_diretta",
        name="Betson (odds shown via diretta.it/Flashscore)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="User-authorized explicit ToS override (LICENSE_RISK marks this distinctly "
        "from B_PERSONAL_USE_ONLY sources) — pre-match odds only, never live/in-play. "
        "Not implemented: odds render only after client JS runs, and this session's "
        "sandboxed network cannot get a real browser engine to any external host "
        "(verified against unrelated hosts too, not diretta.it-specific). See "
        "DATA_SOURCES.md.",
    ),
    SourceDefinition(
        key="livescore_com",
        name="livescore.com (backup for Betson/diretta.it pre-match odds)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Audited independently — LiveScore Limited, a distinct corporate group from "
        "Livesport/Flashscore. Real odds sit behind a country/user-gated affiliate "
        "widget system (isAdult/notSelfExcluded/hasBetFeatures), never observed with "
        "real bookmaker data in this session; full ToS text not retrievable via plain "
        "HTTP. Not implemented. See DATA_SOURCES.md.",
    ),
    SourceDefinition(
        key="fantalab",
        name="FantaLab (moduli/titolari/tiratori/ballottaggi Serie A) — ACCANTONATO",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Shelved on the user's explicit decision for authentication "
        "complexity/risk (AWS Cognito + automated Premium login), NOT for a ToS "
        "prohibition — no anti-scraping clause was ever found for this source, "
        "unlike the other C-category entries here (diretta.it/Betson, "
        "legaseriea.it). No plain data API exists (single-bundle SPA, only "
        "marketing/deep-link endpoints on api.fantalab.it); real data sits behind "
        "an authenticated Firebase Realtime Database (verified 401 without auth) "
        "reachable only via a Cognito login with no visible bridge to Firebase "
        "auth. The user declined to authorize automating their own Premium login "
        "given the account-suspension risk. See DATA_SOURCES.md.",
    ),
    SourceDefinition(
        key="corriere_dello_sport",
        name="Corriere dello Sport — Probabili Formazioni (Serie A, tactical formation only)",
        category=DataSourceCategory.B_PERSONAL_USE_ONLY,
        is_implemented=True,
        notes="Verified this session: real server-rendered Opta-sourced formation widget, "
        "robots.txt permissive, no TDM/scraping clause in main ToS (unlike RCS's "
        "Gazzetta), llms.txt explicitly authorizes informational/discovery use "
        "(prohibits only bulk extraction/commercial redistribution/model training). "
        "Formation shape only — never player names (none found in structured form on "
        "this source); player_names_starting is always []. Serie A only, no Premier "
        "League equivalent page found.",
    ),
    SourceDefinition(
        key="sky_sport_it",
        name="Sky Sport Italia (sport.sky.it)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Technically blocked, verified live: every request (homepage included) "
        "returns an Akamai edge error page (HTTP 200 body 'This page can't be "
        "displayed', server-timing: ak_p) — same class of block as ePlay24/fbref, "
        "not a ToS decision.",
    ),
    SourceDefinition(
        key="bbc_sport",
        name="BBC Sport (Premier League team news)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Verified live: robots.txt itself states in plain English 'No scraping, "
        "crawling, or systematic extraction... No text and data mining (TDM) under "
        "Article 4 of the EU Directive... The BBC reserves all rights... and "
        "expressly opts out of any statutory exceptions'. Most explicit prohibition "
        "found in this project, no personal-use ambiguity at all.",
    ),
    SourceDefinition(
        key="sky_sports_uk",
        name="Sky Sports UK (Premier League team news)",
        category=DataSourceCategory.C_ABSTRACT_ONLY,
        is_implemented=False,
        notes="Not pursued: no structured predicted-lineup page/widget found (team "
        "news appears embedded as prose in preview articles, not extracted "
        "structured fields); skysports.com's own specific ToS page was not located "
        "(the linked sky.com terms are unrelated broadcast T&Cs). Documented "
        "honestly as insufficiently verified/structured rather than forcing a "
        "fragile prose parser. No equivalent Premier League source found matching "
        "Corriere dello Sport's Serie A quality in this session.",
    ),
    SourceDefinition(
        key="betfair_exchange",
        name="Betfair Exchange (official Betting API, personal account)",
        category=DataSourceCategory.D_OFFICIAL_API_PERSONAL_ACCOUNT,
        is_implemented=True,
        notes="Not a scraped source — official, documented API (developer.betfair.com) "
        "accessed via the user's own account and a free Delayed Application Key "
        "(1-180s delayed, never the paid Live key). Uses betfairlightweight (real, "
        "actively-existing third-party client) with Interactive Login (no SSL cert "
        "needed). Exchange back price, not a bookmaker quote — always labeled "
        "'Betfair (exchange, dati ritardati 1-180s)'. Not exercised against live "
        "Betfair data in this session (no account/credentials available) — request-"
        "building/parsing logic unit-tested against betfairlightweight's own real "
        "resource classes, not live-verified. See DATA_SOURCES.md.",
    ),
]
