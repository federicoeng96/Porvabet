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
    tests never leak data into each other and never touch the dev database."""
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
