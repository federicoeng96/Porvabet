#!/usr/bin/env python3
"""Ingest REAL upcoming fixtures (next matchday only) from football-data.org.

Requires a free API key (`FOOTBALL_DATA_ORG_API_KEY` env var — register at
https://www.football-data.org, "Get started"). Fetches the current matchday
for Premier League/Serie A via `/v4/competitions/{code}` (never a guessed
matchday number) and upserts each not-yet-played fixture as a `SCHEDULED`
`Match` row via `app.ingestion.match_ingestion.ingest_upcoming_fixture`.

Never fabricates a fixture: a competition with no reachable matchday, or a
matchday where every fixture has already been played/postponed, contributes
zero rows — this script reports that plainly rather than inventing a match.

Usage:
    python scripts/ingest_upcoming_fixtures.py --competitions EPL SERIE_A
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.ingestion.match_ingestion import ingest_upcoming_fixture
from app.ingestion.source_registry import SOURCE_REGISTRY
from app.models.core import Source
from app.providers.football_data_org.provider import (
    FootballDataOrgApiKeyMissingError,
    FootballDataOrgFixtureProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competitions", nargs="+", default=["EPL", "SERIE_A"], choices=["EPL", "SERIE_A"])
    args = parser.parse_args()

    provider = FootballDataOrgFixtureProvider()
    if not provider.is_available():
        print(
            "FOOTBALL_DATA_ORG_API_KEY not configured — nothing to do. "
            "Register a free key at https://www.football-data.org and set it in .env."
        )
        return

    db = SessionLocal()
    try:
        _seed_sources(db)

        total_ingested = 0
        for competition in args.competitions:
            try:
                records = provider.get_next_matchday_fixtures(competition)
            except FootballDataOrgApiKeyMissingError as exc:
                print(f"  [SKIP] {competition}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 — report and continue with other competitions
                print(f"  [SKIP] {competition}: {exc}")
                continue

            for record in records:
                ingest_upcoming_fixture(db, record)
            db.commit()
            total_ingested += len(records)
            print(f"  [OK]   {competition}: {len(records)} upcoming fixtures")

        print(f"\nDone. {total_ingested} real upcoming fixtures ingested (source=football_data_org).")
    finally:
        db.close()


def _seed_sources(db) -> None:
    for definition in SOURCE_REGISTRY:
        existing = db.query(Source).filter(Source.key == definition.key).one_or_none()
        if existing is None:
            db.add(
                Source(
                    key=definition.key,
                    name=definition.name,
                    category=definition.category,
                    is_implemented=definition.is_implemented,
                    notes=definition.notes,
                )
            )
    db.commit()


if __name__ == "__main__":
    main()
