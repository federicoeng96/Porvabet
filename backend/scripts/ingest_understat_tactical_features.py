"""Persists real per-match tactical features (xG, xGA, npxG, PPDA components,
deep completions) from understat.com into `TacticalFeature` rows — the real
extraction ROADMAP.md item 5 (Matchup Engine) asked for.

Scope, deliberately: one row per (team, match date, feature) at
`window_matches=1` — the raw single-match value, not a rolling-window
aggregate. A rolling no-leakage aggregate (mirroring the walk-forward
discipline used elsewhere in this project) is a real design decision of its
own — which window, which aggregation — better made once a consumer (the
Matchup/Intelligence Engine) actually needs it, than guessed here. These raw
rows are exactly what such an aggregate would later be computed from.

Requires `UnderstatProvider(acknowledge_personal_use_only=True)` — see
DATA_SOURCES.md: understat was reclassified category B this session
(robots.txt disallows all). Team names are resolvable via
`resolve_understat_team_name` (see app/ingestion/match_ingestion.py) for
already-ingested teams only — an understat team name with no existing `Team`
row (not yet ingested from football-data.co.uk) is skipped and reported,
never guessed/created here.
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.ingestion.match_ingestion import get_or_create_source, resolve_understat_team_name
from app.models.core import Competition, Season
from app.models.enums import DataSourceCategory
from app.models.stats import TacticalFeature
from app.providers.understat.provider import UnderstatProvider

SEASONS = ["2023/2024"]
COMPETITIONS = ["EPL", "SERIE_A"]

FEATURE_NAMES = ("xg", "xga", "npxg", "npxga", "deep", "deep_allowed")


def persist_season(db, provider: UnderstatProvider, source, competition_code: str, season_label: str) -> None:
    comp = db.scalar(select(Competition).where(Competition.code == competition_code))
    season = db.scalar(
        select(Season).where(Season.competition_id == comp.id, Season.label == season_label)
    )
    if season is None:
        print(f"{competition_code} {season_label}: no matching Season row in DB, skipping")
        return

    stats = provider.get_team_match_tactical_stats(competition_code, season_label)
    resolved_cache: dict[str, object] = {}
    unresolved: set[str] = set()
    written = 0

    for s in stats:
        if s.team_name not in resolved_cache:
            resolved_cache[s.team_name] = resolve_understat_team_name(db, s.team_name)
        team = resolved_cache[s.team_name]
        if team is None:
            unresolved.add(s.team_name)
            continue

        values = {
            "xg": s.xg,
            "xga": s.xga,
            "npxg": s.npxg,
            "npxga": s.npxga,
            "deep": float(s.deep),
            "deep_allowed": float(s.deep_allowed),
        }
        for feature_name in FEATURE_NAMES:
            existing = db.scalar(
                select(TacticalFeature).where(
                    TacticalFeature.team_id == team.id,
                    TacticalFeature.as_of_date == s.match_date,
                    TacticalFeature.feature_name == feature_name,
                    TacticalFeature.window_matches == 1,
                )
            )
            if existing is not None:
                continue  # idempotent re-run
            db.add(
                TacticalFeature(
                    team_id=team.id,
                    as_of_date=s.match_date,
                    feature_name=feature_name,
                    value=values[feature_name],
                    window_matches=1,
                    opponent_adjusted=False,
                    source_id=source.id,
                )
            )
            written += 1
        # PPDA is a ratio of two raw counts — kept as one feature computed
        # here (not stored as two separate "att"/"def" features) since a
        # ratio is what the Matchup Engine would actually consume; the raw
        # components are only in understat's response, not persisted
        # separately, to avoid two conflicting sources of truth for the same
        # derived number.
        if s.ppda_def > 0:
            ppda_existing = db.scalar(
                select(TacticalFeature).where(
                    TacticalFeature.team_id == team.id,
                    TacticalFeature.as_of_date == s.match_date,
                    TacticalFeature.feature_name == "ppda",
                    TacticalFeature.window_matches == 1,
                )
            )
            if ppda_existing is None:
                db.add(
                    TacticalFeature(
                        team_id=team.id,
                        as_of_date=s.match_date,
                        feature_name="ppda",
                        value=s.ppda_att / s.ppda_def,
                        window_matches=1,
                        opponent_adjusted=False,
                        source_id=source.id,
                    )
                )
                written += 1

    db.commit()
    print(
        f"{competition_code} {season_label}: {written} TacticalFeature rows written, "
        f"{len(unresolved)} team names unresolved: {sorted(unresolved)}"
    )


def main() -> None:
    db = SessionLocal()
    provider = UnderstatProvider(acknowledge_personal_use_only=True)
    source = get_or_create_source(
        db,
        key="understat",
        name="understat.com",
        category=DataSourceCategory.B_PERSONAL_USE_ONLY,
        is_implemented=True,
    )
    db.commit()
    try:
        for competition_code in COMPETITIONS:
            for season_label in SEASONS:
                persist_season(db, provider, source, competition_code, season_label)
    finally:
        db.close()


if __name__ == "__main__":
    main()
