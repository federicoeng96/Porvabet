#!/usr/bin/env python3
"""Ingest REAL historical match data from football-data.co.uk.

Downloads multiple seasons of Premier League and/or Serie A results + closing
bookmaker odds and upserts them into the database via
`app.ingestion.match_ingestion`. This is the real counterpart to
`scripts/seed_dev_fixture.py` (which is synthetic-only) — running this script
requires actual outbound network access to football-data.co.uk.

Usage:
    python scripts/ingest_football_data.py --competitions EPL SERIE_A --seasons 2015 2024

`--seasons START END` ingests season labels "START/START+1" through
"END/END+1" inclusive (e.g. `--seasons 2015 2024` ingests 2015/2016 through
2024/2025, 10 seasons).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.ingestion.match_ingestion import ingest_historical_match
from app.ingestion.source_registry import SOURCE_REGISTRY
from app.models.core import Source
from app.providers.football_data_co_uk.provider import FootballDataCoUkProvider


def season_labels(start_year: int, end_year: int) -> list[str]:
    return [f"{y}/{y + 1}" for y in range(start_year, end_year + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competitions", nargs="+", default=["EPL", "SERIE_A"], choices=["EPL", "SERIE_A"])
    parser.add_argument("--seasons", nargs=2, type=int, metavar=("START", "END"), default=(2015, 2024))
    args = parser.parse_args()

    labels = season_labels(*args.seasons)
    provider = FootballDataCoUkProvider()

    db = SessionLocal()
    try:
        _seed_sources(db)

        total_ingested = 0
        for competition in args.competitions:
            for season_label in labels:
                try:
                    records = provider.get_historical_matches(competition, season_label)
                except Exception as exc:  # noqa: BLE001 — report and continue with other seasons
                    print(f"  [SKIP] {competition} {season_label}: {exc}")
                    continue

                for record in records:
                    ingest_historical_match(db, record)
                db.commit()
                total_ingested += len(records)
                print(f"  [OK]   {competition} {season_label}: {len(records)} matches")

        print(f"\nDone. {total_ingested} real matches ingested (source=football_data_co_uk).")
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
