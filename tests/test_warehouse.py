# tests/test_warehouse.py
"""Tests for the Layer 2 warehouse models, loader, and queries."""

import os

import pytest
from sqlalchemy import inspect

from src.warehouse.models import Base, DimDate, DimRegion, FctIndicator
from src.warehouse.session import create_engine_with_pool


@pytest.fixture(scope="module")
def engine():
    """Create a test engine against a scratch schema."""
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://rcol:rcol_dev_password@localhost:5432/regional_cost_of_living_test",
    )
    eng = create_engine_with_pool(url)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


def test_tables_created(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"dim_regions", "dim_dates", "fct_indicators"}.issubset(tables)


def test_dim_region_unique_constraint(engine):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(DimRegion(country="CA", province_state="Ontario"))
        session.commit()

        session.add(DimRegion(country="CA", province_state="Ontario"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_indicator_value_check_constraint(engine):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        region = DimRegion(country="US", province_state="California")
        d = DimDate(full_date="2023-01-01", year=2023, month=1, quarter=1)
        session.add_all([region, d])
        session.flush()

        session.add(
            FctIndicator(
                region_id=region.region_id,
                date_id=d.date_id,
                indicator_type="cpi",
                value=-5,  # invalid: must be > 0
                source_table="test",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
