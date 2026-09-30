# dashboard/styles.py
"""Inject custom CSS for KPI cards, metric styling, and layout polish."""

import streamlit as st

CUSTOM_CSS = """
<style>
    /* KPI card */
    .kpi-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .kpi-label {
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #F1F5F9;
        line-height: 1.1;
    }
    .kpi-delta-positive {
        font-size: 0.85rem;
        color: #10B981;
        margin-top: 4px;
    }
    .kpi-delta-negative {
        font-size: 0.85rem;
        color: #EF4444;
        margin-top: 4px;
    }

    /* Section headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 600;
        color: #E2E8F0;
        margin: 24px 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 1px solid #334155;
    }

    /* Sidebar polish */
    section[data-testid="stSidebar"] {
        background-color: #0B1220;
        border-right: 1px solid #1E293B;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1E293B;
        border-radius: 8px 8px 0 0;
        padding: 8px 18px;
    }

    /* Footer */
    .app-footer {
        text-align: center;
        color: #64748B;
        font-size: 0.8rem;
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #1E293B;
    }
</style>
"""


def inject_css() -> None:
    """Inject the custom CSS into the current Streamlit page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
