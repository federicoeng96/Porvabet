"""DB-backed tests for aggregating resolved backtest predictions into the
`backtests`/`model_versions` tables (see ROADMAP.md item 1)."""

import json
from datetime import date

import pytest
from sqlalchemy import select

from app.backtest.metrics import BetRecord
from app.backtest.persistence import persist_backtest_run
from app.ingestion.match_ingestion import get_or_create_competition
from app.models.backtest import Backtest
from app.models.enums import ModelFamily
from app.models.prediction import ModelVersion


def _sample_bets() -> list[BetRecord]:
    return [
        BetRecord(probability=0.6, bookmaker_odds=1.8, won=True, market_category="MATCH_RESULT"),
        BetRecord(probability=0.6, bookmaker_odds=1.8, won=False, market_category="MATCH_RESULT"),
        BetRecord(probability=0.9, bookmaker_odds=1.2, won=True, market_category="MATCH_RESULT"),
    ]


def test_persist_backtest_run_writes_model_version_and_backtest_row(db_session):
    competition = get_or_create_competition(db_session, "EPL")
    db_session.flush()
    bets = _sample_bets()

    backtest = persist_backtest_run(
        db_session,
        bets=bets,
        model_family=ModelFamily.DIXON_COLES_POISSON,
        market_category="MATCH_RESULT",
        competition_id=competition.id,
        version_label="test-run-1",
        window_start=date(2023, 8, 1),
        window_end=date(2024, 5, 1),
        hyperparameters={"refit_batch_days": 21},
        notes="test",
    )
    db_session.flush()

    assert backtest.id is not None
    model_version = db_session.get(ModelVersion, backtest.model_version_id)
    assert model_version is not None
    assert model_version.family == ModelFamily.DIXON_COLES_POISSON
    assert model_version.competition_id == competition.id
    assert model_version.market_category == "MATCH_RESULT"
    assert json.loads(model_version.hyperparameters_json) == {"refit_batch_days": 21}

    assert backtest.n_predictions == 3
    assert backtest.hit_rate == pytest.approx(2 / 3)
    assert backtest.brier_score is not None
    assert backtest.log_loss is not None
    # Priced bets here (bookmaker_odds set on every BetRecord), so ROI is a real number.
    assert backtest.roi is not None

    metrics = json.loads(backtest.metrics_json)
    assert "calibration_curve" in metrics


def test_persist_backtest_run_leaves_pricing_metrics_none_without_odds(db_session):
    competition = get_or_create_competition(db_session, "SERIE_A")
    db_session.flush()
    bets = [
        BetRecord(probability=0.55, bookmaker_odds=None, won=True),
        BetRecord(probability=0.55, bookmaker_odds=None, won=False),
    ]

    backtest = persist_backtest_run(
        db_session,
        bets=bets,
        model_family=ModelFamily.POISSON_COUNT_MODEL,
        market_category="CORNERS",
        competition_id=competition.id,
        version_label="test-run-2",
        window_start=date(2023, 8, 1),
        window_end=date(2024, 5, 1),
    )

    assert backtest.roi is None
    assert backtest.profit_units is None
    assert backtest.yield_pct is None
    assert backtest.hit_rate == pytest.approx(0.5)


def test_persist_backtest_run_rejects_empty_bets(db_session):
    competition = get_or_create_competition(db_session, "EPL")
    db_session.flush()
    with pytest.raises(ValueError):
        persist_backtest_run(
            db_session,
            bets=[],
            model_family=ModelFamily.DIXON_COLES_POISSON,
            market_category="MATCH_RESULT",
            competition_id=competition.id,
            version_label="test-run-3",
            window_start=date(2023, 8, 1),
            window_end=date(2024, 5, 1),
        )


def test_persisted_backtest_is_queryable_by_model_version(db_session):
    competition = get_or_create_competition(db_session, "EPL")
    db_session.flush()
    persist_backtest_run(
        db_session,
        bets=_sample_bets(),
        model_family=ModelFamily.DIXON_COLES_POISSON,
        market_category="MATCH_RESULT",
        competition_id=competition.id,
        version_label="test-run-4",
        window_start=date(2023, 8, 1),
        window_end=date(2024, 5, 1),
    )
    db_session.flush()

    rows = db_session.scalars(
        select(Backtest).join(ModelVersion, Backtest.model_version_id == ModelVersion.id).where(
            ModelVersion.version_label == "test-run-4"
        )
    ).all()
    assert len(rows) == 1
