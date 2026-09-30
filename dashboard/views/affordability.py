# dashboard/views/affordability.py
"""Affordability deep-dive: rent-to-income heatmap and trajectory."""

import streamlit as st

from dashboard.charts import affordability_heatmap, animated_income_rent, time_series_line
from dashboard.components import kpi_row, section_header
from dashboard.data_access import load_affordability, load_regional_snapshot

st.title("🏠 Affordability")
st.caption(
    "Rent-to-income ratio is the single best summary of housing affordability. "
    "A ratio above 30% is considered 'cost-burdened' by CMHC and HUD."
)

filters = st.session_state.get("filters", {})
start_year = filters.get("year_start", 1975)
year_end = filters.get("year_end", 2024)

afford = load_affordability(start_year=start_year)

# ---------------------------------------------------------------------------
# Headline KPIs
# ---------------------------------------------------------------------------

if not afford.empty:
    latest = afford[afford["year"] == afford["year"].max()]
    most_expensive = latest.loc[latest["rent_to_income_pct"].idxmax()]
    least_expensive = latest.loc[latest["rent_to_income_pct"].idxmin()]
    national_avg = latest["rent_to_income_pct"].mean()

    kpi_row([
        {
            "label": "Most expensive region",
            "value": f"{most_expensive['rent_to_income_pct']:.1f}%",
            "delta": most_expensive["province_state"],
            "accent": "negative",
        },
        {
            "label": "Least expensive region",
            "value": f"{least_expensive['rent_to_income_pct']:.1f}%",
            "delta": least_expensive["province_state"],
            "accent": "positive",
        },
        {
            "label": "Average across regions",
            "value": f"{national_avg:.1f}%",
            "delta": "Latest year",
            "accent": "neutral",
        },
        {
            "label": "Cost-burdened regions",
            "value": f"{(latest['rent_to_income_pct'] > 30).sum()} / {len(latest)}",
            "delta": "> 30% threshold",
            "accent": "warning",
        },
    ])

# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

section_header("Rent-to-income ratio over time")
st.plotly_chart(
    affordability_heatmap(afford),
    use_container_width=True,
)
st.caption(
    "Darker red indicates a higher share of income going to rent. "
    "Look for regions that shifted from green to red over the decades."
)

# ---------------------------------------------------------------------------
# Trajectory line
# ---------------------------------------------------------------------------

section_header("Affordability trajectory by region")
st.plotly_chart(
    time_series_line(
        afford,
        value_col="rent_to_income_pct",
        region_col="province_state",
        title="",
        y_axis_label="Rent as % of income",
        show_recessions=True,
    ),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Animated scatter
# ---------------------------------------------------------------------------

section_header("Income vs rent: an animated history")
snapshot_by_year = load_regional_snapshot(year=year_end)
if not snapshot_by_year.empty and "median_income" in snapshot_by_year.columns:
    # Build an animated frame by re-querying per decade anchor
    import pandas as pd
    from dashboard.data_access import load_affordability

    frames = []
    for yr in range(start_year, year_end + 1, 5):
        snap = load_regional_snapshot(year=yr)
        if not snap.empty and "median_income" in snap.columns:
            snap = snap.dropna(subset=["median_income", "average_rent"]).copy()
            snap["year"] = yr
            frames.append(snap)

    if frames:
        animated_df = pd.concat(frames, ignore_index=True)
        st.plotly_chart(
            animated_income_rent(animated_df),
            use_container_width=True,
        )
