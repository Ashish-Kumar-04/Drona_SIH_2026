"""
Shared pytest setup.

The test suite runs against the same SQLite database the app uses, and several test
modules create the schema with `Base.metadata.create_all()` in their own `setup_module`.
`create_all()` only creates *missing* tables — it never adds columns to a table that
already exists on disk. Since Phase 5 added `flexibility_score` / `body_composition_score`
to `performances`, an older DB file would be missing those columns and every test that
registers an athlete (which upserts a Performance row) would fail.

Running the app's real startup path — `init_db()`, which applies the idempotent
lightweight column migrations — once per session keeps tests aligned with production
startup and self-heals a stale schema.
"""

import pytest

from app.database.session import init_db


@pytest.fixture(scope="session", autouse=True)
def _initialise_database():
    init_db()
    yield
