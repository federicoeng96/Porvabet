import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DATABASE_URL = "postgresql+psycopg://porvabet:porvabet_dev@localhost:5432/porvabet_test"


@pytest.fixture(scope="session")
def engine():
    return create_engine(TEST_DATABASE_URL, future=True)


@pytest.fixture()
def db_session(engine):
    """Each test runs inside a transaction that is rolled back afterwards, so
    tests never leak data into each other and never touch the dev database.

    `join_transaction_mode="create_savepoint"` is required, not just tidy: any
    code under test that calls `session.commit()` (e.g. the batch-analyze API
    endpoint, which commits per match) would otherwise commit this fixture's
    own outer `transaction` too — the standard SQLAlchemy footgun of binding a
    Session directly to an already-open Connection/transaction. With this
    mode, an inner `commit()` only releases a SAVEPOINT; the real rollback
    below still discards everything at the end of the test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, future=True, join_transaction_mode="create_savepoint")
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
