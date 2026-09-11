#!/usr/bin/env python3
"""Seeds the dev database with a SYNTHETIC, CLEARLY-LABELED fixture.

This is NOT real match data. It exists solely to smoke-test the full wiring —
DB schema -> ingestion -> statistical engine -> decision layer -> API -> frontend
— end to end in an environment where no real sports-data source can actually be
reached (this project's sandboxed development session has no general internet
egress; see DATA_SOURCES.md). Every row it creates is tagged with the
`synthetic_dev_fixture` source and team names are obviously fake
("FC Alpha", "FC Beta", ...) specifically so it can never be mistaken for a real
analysis in the UI.

Real usage requires running the actual providers (see app/providers/) from an
environment with normal internet access, e.g. via a real ingestion script
against football-data.co.uk.
"""

import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.engine.decision.analysis_runner import InsufficientDataError, run_analysis_for_match
from app.ingestion.match_ingestion import ingest_historical_match
from app.ingestion.source_registry import SOURCE_REGISTRY
from app.models.core import Source
from app.providers.base.dto import HistoricalMatchRecord

SYNTHETIC_TEAMS = ["FC Alpha", "FC Beta", "FC Gamma", "FC Delta", "FC Epsilon", "FC Zeta"]
COMPETITION_CODE = "EPL"
SEASON_LABEL = "2024/2025"


def generate_synthetic_matches(n_rounds: int = 20, seed: int = 20260911) -> list[HistoricalMatchRecord]:
    rng = random.Random(seed)
    strength = {t: rng.uniform(0.7, 1.9) for t in SYNTHETIC_TEAMS}
    records = []
    start = datetime(2024, 8, 10, 15, 0, tzinfo=UTC)
    day_offset = 0
    for round_i in range(n_rounds):
        teams = SYNTHETIC_TEAMS[:]
        rng.shuffle(teams)
        for i in range(0, len(teams), 2):
            home, away = teams[i], teams[i + 1]
            lam = strength[home] * 1.3
            mu = strength[away]
            home_goals = min(int(rng.gammavariate(max(lam, 0.1), 1)), 7)
            away_goals = min(int(rng.gammavariate(max(mu, 0.1), 1)), 7)

            p_home_proxy = lam / (lam + mu + 0.6)
            margin = 1.07
            odds_h = round(margin / max(p_home_proxy, 0.06), 2)
            odds_a = round(margin / max(1 - p_home_proxy - 0.24, 0.06), 2)
            odds_d = round(margin / 0.24, 2)
            odds_over = round(margin / 0.53, 2)
            odds_under = round(margin / 0.47, 2)

            kickoff = start + timedelta(days=day_offset)
            records.append(
                HistoricalMatchRecord(
                    competition_code=COMPETITION_CODE,
                    season_label=SEASON_LABEL,
                    kickoff_utc=kickoff,
                    home_team_name=home,
                    away_team_name=away,
                    home_goals_ft=home_goals,
                    away_goals_ft=away_goals,
                    home_goals_ht=None,
                    away_goals_ht=None,
                    closing_odds_1x2={"Market Average": {"H": odds_h, "D": odds_d, "A": odds_a}},
                    closing_odds_over_under_2_5={
                        "Market Average": {"OVER": odds_over, "UNDER": odds_under}
                    },
                    external_ref=f"synthetic:{COMPETITION_CODE}:{SEASON_LABEL}:{home}:{away}:{kickoff.isoformat()}",
                )
            )
        day_offset += 7
    return records


def main() -> None:
    db = SessionLocal()
    try:
        _seed_sources(db)
        records = generate_synthetic_matches()
        matches = [ingest_historical_match(db, r) for r in records]
        db.commit()
        print(f"Ingested {len(matches)} SYNTHETIC matches (source=synthetic_dev_fixture).")

        # Run a full analysis on the last few matches, where enough prior
        # (synthetic) history exists to fit the model responsibly.
        analyzed = 0
        for match in matches[-6:]:
            try:
                result = run_analysis_for_match(db, match.id)
                db.commit()
                print(
                    f"Analyzed match {match.id} ({match.home_team.name} vs "
                    f"{match.away_team.name}): analysis_version={result.analysis_version_id}, "
                    f"risk levels computed={len(result.risk_levels)}"
                )
                analyzed += 1
            except InsufficientDataError as exc:
                db.rollback()
                print(f"Skipped match {match.id}: {exc}")

        print(f"Done. {analyzed} match(es) fully analyzed and ready to serve via the API.")
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
