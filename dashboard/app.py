# dashboard/app.py
"""Entrypoint for the Regional Cost of Living dashboard.

Run locally:
    streamlit run dashboard/app.py

Deploy:
    Push to GitHub → connect to Streamlit Community Cloud → add secrets.
"""

import streamlit as st

from dashboard.data_access import is_database_reachable
from dashboard.styles import inject_css
from dashboard.components import footer, sidebar_filters

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Regional Cost of Living",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ---------------------------------------------------------------------------
# Database health check
# ---------------------------------------------------------------------------

if not is_database_reachable():
    st.error(
        "**Cannot reach the warehouse database.**\n\n"
        "Make sure PostgreSQL is running (`docker compose up -d postgres`) "
        "and that `DATABASE_URL` is set correctly in `.streamlit/secrets.toml` "
        "or your environment."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Global sidebar filters (shared across all pages)
# ---------------------------------------------------------------------------

filters = sidebar_filters()
st.session_state["filters"] = filters

# ---------------------------------------------------------------------------
# Define pages and navigation
# ---------------------------------------------------------------------------

pages = [
    st.Page(
        "views/national_overview.py",
        title="National Overview",
        icon=":material/public:",
        default=True,
    ),
    st.Page(
        "views/regional_comparison.py",
        title="Regional Comparison",
        icon=":material/map:",
    ),
    st.Page(
        "views/affordability.py",
        title="Affordability",
        icon=":material/home:",
    ),
    st.Page(
        "views/inflation_adjuster.py",
        title="Inflation Adjuster",
        icon=":material/trending_up:",
    ),
    st.Page(
        "views/policy_simulator.py",
        title="Policy Simulator",
        icon=":material/policy:",
    ),
]

nav = st.navigation(pages)
nav.run()

footer()
