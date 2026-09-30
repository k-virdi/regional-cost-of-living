# dashboard/components.py
"""Reusable UI components: KPI cards, sidebar filters, section headers."""

from datetime import date

import pandas as pd
import streamlit as st

from dashboard.data_access import (
    clear_all_caches,
    load_available_regions,
    load_indicator_coverage,
)
from dashboard.theme import KPI_ACCENTS


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

def kpi_card(label: str, value: str, delta: str | None = None, accent: str = "neutral") -> None:
    """Render a styled KPI card using custom CSS."""
    color = KPI_ACCENTS.get(accent, KPI_ACCENTS["neutral"])
    delta_html = ""
    if delta:
        delta_class = (
            "kpi-delta-positive" if not delta.strip().startswith("-")
            else "kpi-delta-negative"
        )
        delta_html = f'<div class="{delta_class}">{delta}</div>'

    st.markdown(
        f"""
        <div class="kpi-card" style="border-left: 4px solid {color};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(cards: list[dict]) -> None:
    """Render a row of KPI cards evenly spaced."""
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            kpi_card(**card)


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def section_header(text: str) -> None:
    """Render a styled section header."""
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

def sidebar_filters() -> dict:
    """Render the global sidebar filters and return the selected values.

    Uses st.session_state so selections persist across page navigation.
    """
    with st.sidebar:
        st.markdown("## Filters")

        regions = load_available_regions()
        countries = sorted(regions["country"].dropna().unique().tolist())

        selected_countries = st.multiselect(
            "Country",
            options=countries,
            default=countries,
            key="filter_countries",
        )

        if selected_countries:
            province_options = sorted(
                regions.loc[
                    regions["country"].isin(selected_countries), "province_state"
                ].dropna().unique().tolist()
            )
        else:
            province_options = []

        selected_provinces = st.multiselect(
            "Province / State",
            options=province_options,
            default=province_options[:5] if len(province_options) > 5 else province_options,
            key="filter_provinces",
        )

        year_range = st.slider(
            "Year range",
            min_value=1975,
            max_value=date.today().year,
            value=(1975, date.today().year),
            step=1,
            key="filter_year_range",
        )

        st.markdown("---")
        st.markdown("### Data Coverage")
        with st.expander("Indicator coverage", expanded=False):
            coverage = load_indicator_coverage()
            if not coverage.empty:
                st.dataframe(
                    coverage,
                    use_container_width=True,
                    hide_index=True,
                    height=220,
                )

        st.markdown("---")
        if st.button("🔄 Refresh data", use_container_width=True):
            clear_all_caches()
            st.rerun()

        st.caption(
            "Sources: Statistics Canada, US Census Bureau, BLS, CMHC. "
            "Data covers 1975–present."
        )

    return {
        "countries": selected_countries,
        "provinces": selected_provinces,
        "year_start": year_range[0],
        "year_end": year_range[1],
    }


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def footer() -> None:
    """Render the app footer."""
    st.markdown(
        """
        <div class="app-footer">
            Regional Cost of Living · Data platform & policy simulator<br>
            Built with Python, PostgreSQL, dbt, Streamlit, and Plotly
        </div>
        """,
        unsafe_allow_html=True,
    )
