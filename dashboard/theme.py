# dashboard/theme.py
"""Shared theme constants for Plotly charts and Streamlit layout."""

# Plotly template matching the Streamlit dark theme
PLOTLY_TEMPLATE = "plotly_dark"

# Consistent color palette for multi-series charts
REGION_COLORS = {
    "Canada": "#38BDF8",
    "United States": "#F472B6",
    "Ontario": "#22D3EE",
    "Quebec": "#A78BFA",
    "British Columbia": "#34D399",
    "Alberta": "#FBBF24",
    "California": "#FB7185",
    "New York": "#818CF8",
    "Texas": "#F97316",
    "Florida": "#2DD4BF",
}

# Affordability heatmap color scale (green = affordable, red = unaffordable)
AFFORDABILITY_SCALE = [
    [0.0, "#065F46"],   # deep green
    [0.3, "#10B981"],   # green
    [0.5, "#FBBF24"],   # amber
    [0.7, "#F97316"],   # orange
    [1.0, "#DC2626"],   # red
]

# CPI / inflation color scale
CPI_SCALE = "Plasma"

# Standard chart layout overrides
CHART_LAYOUT = dict(
    template=PLOTLY_TEMPLATE,
    height=480,
    margin=dict(l=40, r=20, t=60, b=40),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

# KPI card accent colors
KPI_ACCENTS = {
    "positive": "#10B981",
    "negative": "#EF4444",
    "neutral": "#38BDF8",
    "warning": "#FBBF24",
}
