# dashboard/views/national_overview.py
"""National overview: headline KPIs and long-run time series."""

import streamlit as st

from dashboard.charts import cpi_comparison_chart, time_series_line
from dashboard.components import kpi_row, section_header
from dashboard.data_access import load_cpi_comparison, load_time_series

st.title("🏙️ Regional Cost of Living")
st.caption(
    "Fifty years of economic indicators for Canada and the United States. "
    "Data from Statistics Canada, US Census Bureau, BLS, and CMHC."
)

filters = st.session_state.get("filters", {})
countries = filters.get("countries") or None
start_year = filters.get("year_start", 1975)

# ---------------------------------------------------------------------------
# Headline KPIs
# ---------------------------------------------------------------------------

cpi_df = load_cpi_comparison(start_year=start_year)
if not cpi_df.empty:
    latest_year = int(cpi_df["year"].max())
    latest = cpi_df[cpi_df["year"] == latest_year]
    prior = cpi_df[cpi_df["year"] == latest_year - 1]

    ca_latest = latest.loc[latest["country"] == "CA", "cpi"].mean()
    us_latest = latest.loc[latest["country"] == "US", "cpi"].mean()
    ca_prior = prior.loc[prior["country"] == "CA", "cpi"].mean()
    us_prior = prior.loc[prior["country"] == "US", "cpi"].mean()

    ca_yoy = ((ca_latest - ca_prior) / ca_prior * 100) if ca_prior else 0
    us_yoy = ((us_latest - us_prior) / us_prior * 100) if us_prior else 0

    kpi_row([
        {
            "label": "Canada CPI (latest)",
            "value": f"{ca_latest:.1f}",
            "delta": f"{ca_yoy:+.1f}% YoY",
            "accent": "negative" if ca_yoy > 3 else "positive",
        },
        {
            "label": "US CPI (latest)",
            "value": f"{us_latest:.1f}",
            "delta": f"{us_yoy:+.1f}% YoY",
            "accent": "negative" if us_yoy > 3 else "positive",
        },
        {
            "label": "Years of data",
            "value": f"{latest_year - 1975}",
            "delta": f"1975–{latest_year}",
            "accent": "neutral",
        },
        {
            "label": "Regions tracked",
            "value": "10+",
            "delta": "CA + US",
            "accent": "neutral",
        },
    ])

# ---------------------------------------------------------------------------
# CPI comparison
# ---------------------------------------------------------------------------

section_header("Long-run inflation: Canada vs United States")
st.plotly_chart(
    cpi_comparison_chart(cpi_df, base_year=2002),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Median income time series
# ---------------------------------------------------------------------------

section_header("Median household income")
income_df = load_time_series(
    indicator_type="median_income",
    country=None,
    start_year=start_year,
)
st.plotly_chart(
    time_series_line(
        income_df,
        value_col="value",
        region_col="province_state",
        title="",
        y_axis_label="Median household income",
    ),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Rent time series
# ---------------------------------------------------------------------------

section_header("Average monthly rent")
rent_df = load_time_series(
    indicator_type="average_rent",
    country=None,
    start_year=start_year,
)
st.plotly_chart(
    time_series_line(
        rent_df,
        value_col="value",
        region_col="province_state",
        title="",
        y_axis_label="Average monthly rent",
    ),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Data table
# ---------------------------------------------------------------------------

with st.expander("View raw data"):
    st.markdown("**CPI (monthly)**")
    st.dataframe(cpi_df.tail(50), use_container_width=True, hide_index=True)
