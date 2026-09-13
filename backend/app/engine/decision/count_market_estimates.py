"""Corner/card/fouls market estimates — probability only, no value/risk score.

**Why these never enter the risk ladder**: `build_risk_ladder` (selection.py)
computes value and risk from a `Candidate`, which requires both a model
probability AND a real bookmaker price. football-data.co.uk — the only real
odds source wired into this project (see DATA_SOURCES.md) — does not publish
corner, card or fouls odds at all (verified against the real CSV column list;
only 1X2, Over/Under 2.5 goals and Asian handicap have odds columns). So for
these three markets there is currently no real price to compute value/edge
against, anywhere in this codebase's data.

Rather than either (a) inventing a synthetic price to force these into the
same pipeline, or (b) silently doing nothing, this module computes and
persists the model's genuine probability estimate for these markets — exposed
via the API as `additional_estimates`, explicitly labeled as a statistical
estimate with no market value — so the modeling work is visible and useful
(e.g. for a user who has their own quote for these markets, or once a source
with corner/card/fouls odds is added) without pretending an edge exists where
no market price does.

FOULS specifically: added after backtesting confirmed real, well-calibrated
skill on this project's own data (unlike CORNERS/CARDS, which show marked
overconfidence in the high-probability tail) — see BACKTEST_SPEC.md for the
real numbers that justified enabling it, not just "why not add a third
market for completeness".
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.statistical.count_market_model import CountMatchInput, PoissonCountModel
from app.models.match import Match, MatchStatus
from app.models.stats import TeamMatchStats

MIN_TRAINING_MATCHES = 40

# Conventional total-count lines used in the corners/cards/fouls betting
# markets (publicly known market convention, not a bookmaker's proprietary
# price) — used only to express the model's probability at a recognizable
# line, never presented as an actual quoted line from any specific
# bookmaker. FOULS=24.5 is close to this project's own real observed
# average total (~24.0 fouls/match across both competitions' full ingested
# history, see BACKTEST_SPEC.md), not an invented number.
STANDARD_LINES = {"CORNERS": 9.5, "CARDS": 3.5, "FOULS": 24.5}

NO_ODDS_NOTE = (
    "Stima statistica del modello — nessuna quota di mercato disponibile per "
    "questo mercato nelle fonti dati attualmente integrate (v. DATA_SOURCES.md). "
    "Value/risk non calcolabili senza un prezzo di mercato reale."
)


@dataclass(frozen=True)
class CountMarketEstimate:
    market_category: str  # "CORNERS" | "CARDS"
    line: float
    probability_over: float
    probability_under: float
    expected_home: float
    expected_away: float
    n_training_matches: int
    note: str = NO_ODDS_NOTE


def compute_count_market_estimates(
    db: Session, match: Match, model_fit_cache: dict | None = None
) -> list[CountMarketEstimate]:
    """`model_fit_cache`, when provided, lets `analyze_matches_batch` share one
    fitted PoissonCountModel per (category, competition, kickoff) across every
    match in a batch that shares a kickoff slot — same rationale/correctness
    argument as `analysis_runner.run_analysis_for_match`'s `model_fit_cache`
    (see its docstring). `None` (the default) preserves the original
    always-refit behavior for every existing caller/test."""
    from app.models.core import Season

    competition_id = db.get(Season, match.season_id).competition_id
    estimates: list[CountMarketEstimate] = []

    corners_matches = _load_count_training_matches(db, match, _corners_extractor)
    corners_estimate = _try_fit_and_estimate(
        "CORNERS", corners_matches, match, STANDARD_LINES["CORNERS"], competition_id, model_fit_cache
    )
    if corners_estimate is not None:
        estimates.append(corners_estimate)

    cards_matches = _load_count_training_matches(db, match, _cards_extractor)
    cards_estimate = _try_fit_and_estimate(
        "CARDS", cards_matches, match, STANDARD_LINES["CARDS"], competition_id, model_fit_cache
    )
    if cards_estimate is not None:
        estimates.append(cards_estimate)

    fouls_matches = _load_count_training_matches(db, match, _fouls_extractor)
    fouls_estimate = _try_fit_and_estimate(
        "FOULS", fouls_matches, match, STANDARD_LINES["FOULS"], competition_id, model_fit_cache
    )
    if fouls_estimate is not None:
        estimates.append(fouls_estimate)

    return estimates


def _try_fit_and_estimate(
    category: str,
    training_matches: list[CountMatchInput],
    match: Match,
    line: float,
    competition_id: int,
    model_fit_cache: dict | None = None,
) -> CountMarketEstimate | None:
    if len(training_matches) < MIN_TRAINING_MATCHES:
        return None
    home_name, away_name = match.home_team.name, match.away_team.name

    cache_key = ("count", category, competition_id, match.kickoff_utc)
    if model_fit_cache is not None and cache_key in model_fit_cache:
        model = model_fit_cache[cache_key]
    else:
        model = PoissonCountModel()
        model.fit(training_matches, as_of=match.kickoff_utc.date())
        if model_fit_cache is not None:
            model_fit_cache[cache_key] = model
    if home_name not in model.params.teams or away_name not in model.params.teams:
        return None

    probs = model.match_total_probabilities(home_name, away_name, line=line)
    expected_home, expected_away = model.expected_counts(home_name, away_name)
    return CountMarketEstimate(
        market_category=category,
        line=line,
        probability_over=probs["OVER"],
        probability_under=probs["UNDER"],
        expected_home=expected_home,
        expected_away=expected_away,
        n_training_matches=len(training_matches),
    )


def _corners_extractor(stats: TeamMatchStats) -> int | None:
    return stats.corners


def _cards_extractor(stats: TeamMatchStats) -> int | None:
    if stats.yellow_cards is None and stats.red_cards is None:
        return None
    return (stats.yellow_cards or 0) + (stats.red_cards or 0)


def _fouls_extractor(stats: TeamMatchStats) -> int | None:
    return stats.fouls_committed


def _load_count_training_matches(db: Session, match: Match, extractor) -> list[CountMatchInput]:
    """No-leakage: only FINISHED matches in the same competition strictly
    before this match's kickoff, same boundary as
    `analysis_runner._load_training_matches`."""
    from app.models.core import Season

    season = db.get(Season, match.season_id)
    prior_matches = db.scalars(
        select(Match)
        .join(Season, Match.season_id == Season.id)
        .where(
            Season.competition_id == season.competition_id,
            Match.status == MatchStatus.FINISHED,
            Match.kickoff_utc < match.kickoff_utc,
        )
    ).all()

    # One batched query for every prior match's stats, instead of one query per
    # match in the loop below (a real N+1: this was ~3800 individual round-trips
    # for a full 10-season history, found via a real timing check during this
    # session's performance audit — see CHANGELOG.md).
    prior_match_ids = [m.id for m in prior_matches]
    stats_by_match_id: dict[int, list[TeamMatchStats]] = {}
    if prior_match_ids:
        all_stats = db.scalars(
            select(TeamMatchStats).where(TeamMatchStats.match_id.in_(prior_match_ids))
        ).all()
        for s in all_stats:
            stats_by_match_id.setdefault(s.match_id, []).append(s)

    results: list[CountMatchInput] = []
    for m in prior_matches:
        stats = stats_by_match_id.get(m.id, [])
        if len(stats) != 2:
            continue
        home_stats = next((s for s in stats if s.is_home), None)
        away_stats = next((s for s in stats if not s.is_home), None)
        if home_stats is None or away_stats is None:
            continue
        home_value = extractor(home_stats)
        away_value = extractor(away_stats)
        if home_value is None or away_value is None:
            continue
        results.append(
            CountMatchInput(
                home_team=m.home_team.name,
                away_team=m.away_team.name,
                home_count=home_value,
                away_count=away_value,
                match_date=m.kickoff_utc.date(),
            )
        )
    return results
