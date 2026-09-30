# dashboard/views/inflation_adjuster.py
"""Inflation adjuster: convert nominal values to real (CPI-adjusted) terms."""

import streamlit as st
import pandas as pd

from dashboard.charts import cpi_comparison_chart
from dashboard.components import kpi_card, section_header
from dashboard.data_access import load_cpi_comparison

st.title("📈 Inflation Adjuster")
st.caption(
    "Convert nominal dollars to real purchasing power. "
    "A $50,000 salary in 1990 buys far more than $50,000 today."
)

filters = st.session_state.get("filters", {})
start_year = filters.get("year_start", 1975)

cpi_df = load_cpi_comparison(start_year=start_year)

if cpi_df.empty:
    st.warning("No CPI data available.")
    st.stop()

# ---------------------------------------------------------------------------
# Interactive adjuster
# ---------------------------------------------------------------------------

section_header("Purchasing power calculator")

col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    country = st.selectbox(
        "Country",
        options=["CA", "US"],
        format_func=lambda x: "Canada" if x == "CA" else "United States",
    )

with col2:
    amount = st.number_input(
        "Amount",
        min_value=1.0,
        max_value=10_000_000.0,
        value=50_000.0,
        step=1_000.0,
    )

country_cpi = cpi_df[cpi_df["country"] == country].copy()
country_cpi["date"] = pd.to_datetime(
    country_cpi[["year", "month"]].assign(day=1)
)

with col3:
    years_available = sorted(country_cpi["year"].unique())
    from_year, to_year = st.select_slider(
        "Convert from → to",
        options=years_available,
        value=(years_available[0], years_available[-1]),
    )

from_cpi = country_cpi.loc[
    country_cpi["year"] == from_year, "cpi"
].mean()
to_cpi = country_cpi.loc[
    country_cpi["year"] == to_year, "cpi"
].mean()

if from_cpi and to_cpi and from_cpi > 0:
    adjusted = amount * (to_cpi / from_cpi)
    change_pct = (to_cpi / from_cpi - 1) * 100
    currency_symbol = "$" if country == "CA" else "$"
    currency_code = "CAD" if country == "CA" else "USD"

    kpi_card(
        label=f"{currency_symbol}{amount:,.0f} in {from_year} is worth",
        value=f"{currency_symbol}{adjusted:,.0f}",
        delta=f"{change_pct:+.1f}% cumulative inflation → {to_year}",
        accent="negative" if change_pct > 0 else "positive",
    )
    st.caption(f"Denominated in {currency_code}. Based on annual average CPI.")

# ---------------------------------------------------------------------------
# CPI comparison chart
# ---------------------------------------------------------------------------

section_header("CPI comparison (base year = 2002)")
st.plotly_chart(
    cpi_comparison_chart(cpi_df, base_year=2002),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Raw CPI table
# ---------------------------------------------------------------------------

with st.expander("View raw CPI data"):
    st.dataframe(
        country_cpi[["year", "month", "cpi"]].sort_values(
            ["year", "month"], ascending=False
        ).head(60),
        use_container_width=True,
        hide_index=True,
    )
