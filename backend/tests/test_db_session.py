"""Tests for app.db.session.get_db().

The rest of the test suite always overrides this FastAPI dependency with a
test-database session (see conftest.py), so the real generator body never
runs there. This test exercises it directly against the real dev/test
database so the yield/close lifecycle itself is covered.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.db.session import get_db


def test_get_db_yields_a_working_session():
    gen = get_db()
    db = next(gen)

    assert db.execute(text("SELECT 1")).scalar() == 1

    gen.close()


def test_get_db_closes_session_even_if_caller_raises():
    gen = get_db()
    db = next(gen)

    with patch.object(db, "close") as mock_close, pytest.raises(ValueError):
        gen.throw(ValueError("simulated request failure"))

    mock_close.assert_called_once()
