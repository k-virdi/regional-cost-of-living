# tests/test_pipeline.py
"""Unit tests for Layer 1 extractors and transformers."""

import pandas as pd
import pytest

from src.transformers import normalize
from src.transformers.schema import Country, IndicatorRecord, IndicatorType


def test_indicator_record_validates_and_coerces():
    rec = IndicatorRecord(
        country="CA",
        province_state="Ontario",
        indicator_type="cpi",
        reference_date="2023-06",
        value="137.4",
        source_table="statcan:18100004",
    )
    assert rec.country == Country.CANADA
    assert rec.indicator_type == IndicatorType.CPI
    assert rec.value == pytest.approx(137.4)
    assert rec.reference_date.year == 2023


def test_indicator_record_rejects_negative_value():
    with pytest.raises(Exception):
        IndicatorRecord(
            country="US",
            province_state="California",
            indicator_type="median_income",
            reference_date="2023",
            value="-100",
            source_table="census:acs5",
        )


def test_normalize_bls_produces_records():
    df = pd.DataFrame(
        {
            "series_id": ["CUUR0000SA0"],
            "year": ["2023"],
            "period": ["M01"],
            "period_name": ["January"],
            "value": [299.17],
            "date": [pd.Timestamp("2023-01-01")],
        }
    )
    records, report = normalize.normalize_bls(df, "cpi_all_items")
    assert report.valid == 1
    assert records[0].country == Country.UNITED_STATES
    assert records[0].indicator_type == IndicatorType.CPI
