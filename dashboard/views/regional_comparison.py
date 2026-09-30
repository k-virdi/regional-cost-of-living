# dashboard/views/regional_comparison.py
"""Regional comparison: side-by-side bars, scatter, distribution."""

import streamlit as st

from dashboard.charts import income_vs_rent_scatter, regional_bar, distribution_box
from dashboard.components import section_header
from dashboard.data_access import load_regional_snapshot, load_time_series

st.title("🗺️ Regional Comparison")
st.caption("Compare income, rent, and unemployment across provinces and states.")

filters = st.session_state.get("filters", {})
countries = filters.get("countries") or None
year_end = filters.get("year_end", 2024)

# ---------------------------------------------------------------------------
# Latest-year snapshot
# ---------------------------------------------------------------------------

snapshot = load_regional_snapshot(year=year_end, country=None)
if not snapshot.empty and countries:
    snapshot = snapshot[snapshot["country"].isin(countries)]

tab_income, tab_rent, tab_unemployment, tab_scatter = st.tabs(
    ["Median Income", "Average Rent", "Unemployment", "Income vs Rent"]
)

with tab_income:
    section_header("Median household income by region")
    if not snapshot.empty and "median_income" in snapshot.columns:
        st.plotly_chart(
            regional_bar(
                snapshot.dropna(subset=["median_income"]),
                x_col="province_state",
                y_col="median_income",
                title="",
                y_axis_label="Median household income",
            ),
            use_container_width=True,
        )
    else:
        st.info("No median income data for the selected filters.")

with tab_rent:
    section_header("Average monthly rent by region")
    if not snapshot.empty and "average_rent" in snapshot.columns:
        st.plotly_chart(
            regional_bar(
                snapshot.dropna(subset=["average_rent"]),
                x_col="province_state",
                y_col="average_rent",
                title="",
                y_axis_label="Average monthly rent",
            ),
            use_container_width=True,
        )
    else:
        st.info("No rent data for the selected filters.")

with tab_unemployment:
    section_header("Unemployment rate by region")
    if not snapshot.empty and "unemployment_rate" in snapshot.columns:
        st.plotly_chart(
            regional_bar(
                snapshot.dropna(subset=["unemployment_rate"]),
                x_col="province_state",
                y_col="unemployment_rate",
                title="",
                y_axis_label="Unemployment rate (%)",
            ),
            use_container_width=True,
        )
    else:
        st.info("No unemployment data for the selected filters.")

with tab_scatter:
    section_header("Income vs rent: where does your region land?")
    st.plotly_chart(
        income_vs_rent_scatter(snapshot),
        use_container_width=True,
    )
    st.caption(
        "Regions in the upper-left quadrant have high rent relative to income — "
        "the least affordable markets."
    )

# ---------------------------------------------------------------------------
# Distribution across time
# ---------------------------------------------------------------------------

section_header("Distribution of rent across the full period")
rent_ts = load_time_series(
    indicator_type="average_rent",
    start_year=filters.get("year_start", 1975),
)
if not rent_ts.empty:
    st.plotly_chart(
        distribution_box(
            rent_ts,
            value_col="value",
            group_col="country",
            title="",
            y_axis_label="Average monthly rent",
        ),
        use_container_width=True,
    )
