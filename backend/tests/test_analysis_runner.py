"""DB-backed tests for the analysis orchestration layer, using a small SYNTHETIC
round-robin of fictional teams (not real fixtures)."""

import random
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.backtest.metrics import BetRecord
from app.backtest.persistence import persist_backtest_run
from app.engine.decision.analysis_runner import (
    MIN_TRAINING_MATCHES,
    InsufficientDataError,
    run_analysis_for_match,
)
from app.ingestion.match_ingestion import (
    get_or_create_competition,
    get_or_create_season,
    get_or_create_team,
    ingest_historical_match,
)
from app.models.enums import MarketCategory, MatchStatus, ModelFamily
from app.models.market import Market, MarketOutcome, OddsQuote
from app.models.match import Match
from app.models.prediction import AnalysisVersion, Prediction, RiskSelection
from app.providers.base.dto import HistoricalMatchRecord, OddsQuoteRecord

SYNTHETIC_TEAMS = ["Synth A", "Synth B", "Synth C", "Synth D"]


def _seed_matches(db_session, n_rounds: int) -> list:
    rng = random.Random(123)
    strength = {t: rng.uniform(0.7, 1.8) for t in SYNTHETIC_TEAMS}
    start = datetime(2024, 8, 1, 15, 0, tzinfo=UTC)
    matches = []
    for round_i in range(n_rounds):
        teams = SYNTHETIC_TEAMS[:]
        rng.shuffle(teams)
        for i in range(0, len(teams), 2):
            home, away = teams[i], teams[i + 1]
            lam, mu = strength[home] * 1.3, strength[away]
            home_goals = min(int(rng.gammavariate(max(lam, 0.1), 1)), 6)
            away_goals = min(int(rng.gammavariate(max(mu, 0.1), 1)), 6)
            kickoff = start + timedelta(days=7 * round_i)
            record = HistoricalMatchRecord(
                competition_code="EPL",
                season_label="2024/2025",
                kickoff_utc=kickoff,
                home_team_name=home,
                away_team_name=away,
                home_goals_ft=home_goals,
                away_goals_ft=away_goals,
                home_goals_ht=None,
                away_goals_ht=None,
                closing_odds_1x2={"Market Average": {"H": 2.0, "D": 3.3, "A": 3.8}},
                closing_odds_over_under_2_5={"Market Average": {"OVER": 1.9, "UNDER": 1.9}},
                external_ref=f"synth:{round_i}:{home}:{away}",
            )
            matches.append(ingest_historical_match(db_session, record))
    db_session.flush()
    return matches


def test_run_analysis_raises_when_insufficient_history(db_session):
    matches = _seed_matches(db_session, n_rounds=3)  # only 6 matches, well under MIN_TRAINING_MATCHES
    with pytest.raises(InsufficientDataError):
        run_analysis_for_match(db_session, matches[-1].id)


def test_run_analysis_produces_full_ladder(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    target = matches[-1]

    result = run_analysis_for_match(db_session, target.id)
    db_session.flush()

    assert len(result.risk_levels) == 10

    analysis_version = db_session.get(AnalysisVersion, result.analysis_version_id)
    assert analysis_version.is_current is True

    selections = db_session.scalars(
        select(RiskSelection).where(RiskSelection.analysis_version_id == analysis_version.id)
    ).all()
    levels_present = {s.risk_level for s in selections}
    assert levels_present == set(range(1, 11))

    mains = [s for s in selections if s.rank == 1]
    assert len(mains) == 10


class _FakeLiveOddsProvider:
    """Minimal OddsProvider double — proves `run_analysis_for_match` actually
    calls whatever provider it's given for a not-yet-played fixture, without
    depending on real Betfair credentials/network."""

    source_key = "fake_live"
    category = None
    bookmaker_name = "FakeLive"

    def __init__(self, records=None, raises: bool = False):
        self._records = records or []
        self._raises = raises
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def get_odds_for_match(self, home_team_name, away_team_name, kickoff_utc_iso):
        self.calls += 1
        if self._raises:
            raise RuntimeError("simulated live odds fetch failure")
        return self._records


def test_run_analysis_fetches_live_odds_for_a_scheduled_fixture(db_session):
    """A not-yet-played match starts with zero Market/OddsQuote rows (unlike
    every match `_seed_matches` creates, which always comes with closing
    odds) — `run_analysis_for_match` must call the given odds provider and
    use what it returns, not just skip the market for lack of any quote."""
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    last_kickoff = matches[-1].kickoff_utc

    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2024/2025")
    home = get_or_create_team(db_session, "Synth A")
    away = get_or_create_team(db_session, "Synth B")
    future_match = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=last_kickoff + timedelta(days=7),
        status=MatchStatus.SCHEDULED,
        external_ref="synth:future:live-odds",
    )
    db_session.add(future_match)
    db_session.flush()
    assert db_session.scalars(select(Market).where(Market.match_id == future_match.id)).all() == []

    now = last_kickoff + timedelta(days=6)
    provider = _FakeLiveOddsProvider(
        [
            OddsQuoteRecord("Betfair", "1X2", "HOME", 2.0, now, is_closing=False),
            OddsQuoteRecord("Betfair", "1X2", "DRAW", 3.3, now, is_closing=False),
            OddsQuoteRecord("Betfair", "1X2", "AWAY", 3.8, now, is_closing=False),
        ]
    )

    result = run_analysis_for_match(db_session, future_match.id, odds_provider=provider)
    db_session.flush()

    assert provider.calls == 1
    assert len(result.risk_levels) > 0
    markets = db_session.scalars(select(Market).where(Market.match_id == future_match.id)).all()
    assert any(m.category.value == "MATCH_RESULT" for m in markets)
    odds = db_session.scalars(
        select(OddsQuote)
        .join(MarketOutcome, OddsQuote.market_outcome_id == MarketOutcome.id)
        .join(Market, MarketOutcome.market_id == Market.id)
        .where(Market.match_id == future_match.id)
    ).all()
    assert {o.bookmaker for o in odds} == {"Betfair"}


def test_run_analysis_shows_nd_for_market_with_no_liquid_quote(db_session):
    """Core "never skip a row" behavior: when the live odds provider has a
    quote for MATCH_RESULT but nothing for TOTAL_GOALS (a very plausible
    real Betfair situation — 1X2 markets open earlier than O/U), TOTAL_GOALS
    must still show up with its model probability/fair-odds — as a
    Prediction with bookmaker_odds=None/value=None (n/d), never silently
    absent and never a fabricated price."""
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    last_kickoff = matches[-1].kickoff_utc

    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2024/2025")
    home = get_or_create_team(db_session, "Synth A")
    away = get_or_create_team(db_session, "Synth B")
    future_match = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=last_kickoff + timedelta(days=7),
        status=MatchStatus.SCHEDULED,
        external_ref="synth:future:partial-odds",
    )
    db_session.add(future_match)
    db_session.flush()

    now = last_kickoff + timedelta(days=6)
    provider = _FakeLiveOddsProvider(
        [
            OddsQuoteRecord("Betfair", "1X2", "HOME", 2.0, now, is_closing=False),
            OddsQuoteRecord("Betfair", "1X2", "DRAW", 3.3, now, is_closing=False),
            OddsQuoteRecord("Betfair", "1X2", "AWAY", 3.8, now, is_closing=False),
            # No OVER/UNDER quotes at all — Betfair has no O/U market yet.
        ]
    )

    result = run_analysis_for_match(db_session, future_match.id, odds_provider=provider)
    db_session.flush()

    # MATCH_RESULT got real candidates — all 10 risk levels still populated.
    assert len(result.risk_levels) == 10

    analysis_version = db_session.scalar(
        select(AnalysisVersion).where(AnalysisVersion.match_id == future_match.id)
    )
    nd_predictions = db_session.scalars(
        select(Prediction).where(
            Prediction.analysis_version_id == analysis_version.id,
            Prediction.bookmaker_odds.is_(None),
        )
    ).all()
    nd_by_outcome = {}
    for pred in nd_predictions:
        outcome = db_session.get(MarketOutcome, pred.market_outcome_id)
        nd_by_outcome[outcome.code] = pred

    assert set(nd_by_outcome) == {"OVER", "UNDER"}
    for pred in nd_by_outcome.values():
        assert pred.bookmaker_odds is None
        assert pred.bookmaker_name is None
        assert pred.value is None
        assert pred.probability is not None  # model estimate still computed
        assert pred.fair_odds == pytest.approx(1.0 / pred.probability)

    # Never enters the risk ladder (no RiskSelection for the n/d predictions).
    nd_prediction_ids = {p.id for p in nd_predictions}
    risk_selection_prediction_ids = {
        rs.prediction_id
        for rs in db_session.scalars(
            select(RiskSelection).where(RiskSelection.analysis_version_id == analysis_version.id)
        ).all()
    }
    assert nd_prediction_ids.isdisjoint(risk_selection_prediction_ids)


def test_run_analysis_survives_live_odds_provider_failure(db_session):
    """A provider raising (network down, bad response) must never abort the
    whole analysis — it degrades to whatever OddsQuote rows already exist
    (none, here), which correctly yields InsufficientDataError rather than a
    crash or fabricated data."""
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    last_kickoff = matches[-1].kickoff_utc

    competition = get_or_create_competition(db_session, "EPL")
    season = get_or_create_season(db_session, competition, "2024/2025")
    home = get_or_create_team(db_session, "Synth C")
    away = get_or_create_team(db_session, "Synth D")
    future_match = Match(
        season_id=season.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_utc=last_kickoff + timedelta(days=7),
        status=MatchStatus.SCHEDULED,
        external_ref="synth:future:failing-provider",
    )
    db_session.add(future_match)
    db_session.flush()

    provider = _FakeLiveOddsProvider(raises=True)

    with pytest.raises(InsufficientDataError):
        run_analysis_for_match(db_session, future_match.id, odds_provider=provider)
    assert provider.calls == 1


def _well_calibrated_full_range_bets() -> list[BetRecord]:
    """40 bets per decile, each decile's win rate == its own predicted
    probability — perfectly calibrated everywhere, and every bin has
    n=40 >= reliability.MIN_BIN_COUNT, so whatever probability a real
    candidate lands on, it finds a trustworthy, well-calibrated bin."""
    bets = []
    for decile in range(10):
        p = decile / 10 + 0.05
        n_won = round(40 * p)
        for i in range(40):
            bets.append(BetRecord(probability=p, bookmaker_odds=1.5, won=(i < n_won)))
    return bets


def test_model_reliability_lowers_risk_once_a_real_backtest_is_persisted(db_session):
    """Before any Backtest row exists for this competition/market, reliability
    falls back to the conservative 0.0 (see reliability.py). Once a real,
    well-calibrated Backtest is persisted, the same candidate's risk score
    should go down — proof the wiring in analysis_runner.py actually reads
    it, not just a unit test of reliability.py in isolation."""
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    target = matches[-1]

    first = run_analysis_for_match(db_session, target.id)
    db_session.flush()
    first_home_risk = _match_result_home_risk_raw(db_session, first.analysis_version_id)
    assert first_home_risk is not None

    competition = get_or_create_competition(db_session, "EPL")
    db_session.flush()
    persist_backtest_run(
        db_session,
        bets=_well_calibrated_full_range_bets(),
        model_family=ModelFamily.DIXON_COLES_POISSON,
        market_category="MATCH_RESULT",
        competition_id=competition.id,
        version_label="test-reliability-wiring",
        window_start=date(2023, 8, 1),
        window_end=date(2024, 5, 1),
    )
    db_session.flush()

    second = run_analysis_for_match(db_session, target.id)
    db_session.flush()
    second_home_risk = _match_result_home_risk_raw(db_session, second.analysis_version_id)
    assert second_home_risk is not None

    assert second_home_risk < first_home_risk


def _match_result_home_risk_raw(db_session, analysis_version_id: int) -> float | None:
    row = db_session.execute(
        select(RiskSelection.risk_score_raw)
        .join(Prediction, RiskSelection.prediction_id == Prediction.id)
        .join(MarketOutcome, Prediction.market_outcome_id == MarketOutcome.id)
        .join(Market, MarketOutcome.market_id == Market.id)
        .where(
            RiskSelection.analysis_version_id == analysis_version_id,
            Market.category == MarketCategory.MATCH_RESULT,
            MarketOutcome.code == "HOME",
        )
        .limit(1)
    ).first()
    return row[0] if row else None


def test_rerunning_analysis_supersedes_previous_version(db_session):
    n_rounds = (MIN_TRAINING_MATCHES // 2) + 6
    matches = _seed_matches(db_session, n_rounds=n_rounds)
    target = matches[-1]

    first = run_analysis_for_match(db_session, target.id)
    db_session.flush()
    second = run_analysis_for_match(db_session, target.id)
    db_session.flush()

    assert first.analysis_version_id != second.analysis_version_id
    first_version = db_session.get(AnalysisVersion, first.analysis_version_id)
    second_version = db_session.get(AnalysisVersion, second.analysis_version_id)
    assert first_version.is_current is False
    assert second_version.is_current is True
