# dashboard/charts.py
"""Plotly chart builders for the dashboard.

Each function is pure: takes a DataFrame, returns a Figure.
No Streamlit calls here — this keeps charts testable and reusable.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.theme import (
    AFFORDABILITY_SCALE,
    CHART_LAYOUT,
    CPI_SCALE,
    REGION_COLORS,
)


def _region_color_map(regions: list[str]) -> dict[str, str]:
    """Return a stable color map for a list of region names."""
    return {r: REGION_COLORS.get(r, "#94A3B8") for r in regions}


def time_series_line(
    df: pd.DataFrame,
    value_col: str = "value",
    region_col: str = "province_state",
    title: str = "",
    y_axis_label: str = "",
    show_recessions: bool = True,
) -> go.Figure:
    """Multi-region time-series line chart with unified hover."""
    if df.empty:
        return _empty_figure(title)

    regions = sorted(df[region_col].dropna().unique())
    color_map = _region_color_map(regions)

    fig = px.line(
        df,
        x="full_date",
        y=value_col,
        color=region_col,
        color_discrete_map=color_map,
        title=title,
        labels={value_col: y_axis_label, region_col: "", "full_date": ""},
    )
    fig.update_traces(mode="lines", hovertemplate=None)
    fig.update_layout(**CHART_LAYOUT)

    if show_recessions and "is_recession" in df.columns:
        recession_dates = df.loc[df["is_recession"], "full_date"].drop_duplicates()
        for d in recession_dates:
            fig.add_vrect(
                x0=d, x1=d + pd.Timedelta(days=31),
                fillcolor="#EF4444", opacity=0.08, line_width=0,
            )

    return fig


def regional_bar(
    df: pd.DataFrame,
    x_col: str = "province_state",
    y_col: str = "value",
    title: str = "",
    y_axis_label: str = "",
    color_col: str | None = "country",
) -> go.Figure:
    """Horizontal bar chart comparing a metric across regions."""
    if df.empty:
        return _empty_figure(title)

    df = df.sort_values(y_col, ascending=True)
    fig = px.bar(
        df,
        x=y_col,
        y=x_col,
        orientation="h",
        color=color_col,
        color_discrete_map=REGION_COLORS,
        title=title,
        labels={y_col: y_axis_label, x_col: ""},
        text_auto=".2s",
    )
    fig.update_layout(**{**CHART_LAYOUT, "hovermode": "closest"})
    fig.update_traces(textposition="outside")
    return fig


def affordability_heatmap(
    df: pd.DataFrame,
    title: str = "Rent-to-Income Ratio (%)",
) -> go.Figure:
    """Heatmap of rent-to-income ratio: region (y) × year (x)."""
    if df.empty:
        return _empty_figure(title)

    pivot = df.pivot_table(
        index="province_state",
        columns="year",
        values="rent_to_income_pct",
        aggfunc="mean",
    ).dropna(how="all")

    if pivot.empty:
        return _empty_figure(title)

    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale=AFFORDABILITY_SCALE,
        title=title,
        labels=dict(x="Year", y="", color="Rent / Income (%)"),
    )
    fig.update_layout(**{**CHART_LAYOUT, "hovermode": "closest"})
    return fig


def cpi_comparison_chart(df: pd.DataFrame, base_year: int = 2002) -> go.Figure:
    """CPI comparison indexed to a base year (default 2002 = 100)."""
    if df.empty:
        return _empty_figure("CPI Comparison")

    indexed = []
    for country, group in df.groupby("country"):
        base = group.loc[group["year"] == base_year, "cpi"].mean()
        if pd.isna(base) or base == 0:
            continue
        g = group.copy()
        g["indexed_cpi"] = g["cpi"] / base * 100
        indexed.append(g)

    if not indexed:
        return _empty_figure("CPI Comparison")

    combined = pd.concat(indexed, ignore_index=True)
    combined["date"] = pd.to_datetime(
        combined[["year", "month"]].assign(day=1)
    )

    fig = px.line(
        combined,
        x="date",
        y="indexed_cpi",
        color="country",
        color_discrete_map=REGION_COLORS,
        title=f"Consumer Price Index (base year {base_year} = 100)",
        labels={"indexed_cpi": "Index (base=100)", "date": "", "country": ""},
    )
    fig.update_traces(mode="lines", hovertemplate=None)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def income_vs_rent_scatter(
    df: pd.DataFrame,
    title: str = "Income vs Rent (latest year)",
) -> go.Figure:
    """Bubble scatter: median income (x) vs average rent (y), sized by CPI."""
    if df.empty or "median_income" not in df.columns:
        return _empty_figure(title)

    plot_df = df.dropna(subset=["median_income", "average_rent"]).copy()
    if plot_df.empty:
        return _empty_figure(title)

    fig = px.scatter(
        plot_df,
        x="median_income",
        y="average_rent",
        color="country",
        color_discrete_map=REGION_COLORS,
        text="province_state",
        size="cpi" if "cpi" in plot_df.columns else None,
        title=title,
        labels={
            "median_income": "Median Household Income",
            "average_rent": "Average Monthly Rent",
            "country": "",
        },
    )
    fig.update_traces(textposition="top center", marker=dict(line=dict(width=1, color="#0F172A")))
    fig.update_layout(**{**CHART_LAYOUT, "hovermode": "closest"})
    return fig


def distribution_box(
    df: pd.DataFrame,
    value_col: str = "value",
    group_col: str = "country",
    title: str = "",
    y_axis_label: str = "",
) -> go.Figure:
    """Box plot of a metric's distribution by group."""
    if df.empty:
        return _empty_figure(title)

    fig = px.box(
        df,
        x=group_col,
        y=value_col,
        color=group_col,
        color_discrete_map=REGION_COLORS,
        title=title,
        labels={value_col: y_axis_label, group_col: ""},
        points="outliers",
    )
    fig.update_layout(**{**CHART_LAYOUT, "hovermode": "closest"})
    return fig


def animated_income_rent(
    df: pd.DataFrame,
    title: str = "Income vs Rent Over Time",
) -> go.Figure:
    """Animated scatter showing income-rent trajectory across years.

    Uses animation_frame to let the user scrub through decades.
    Requires a 'year' column and both income and rent pivoted wide.
    """
    if df.empty or "year" not in df.columns:
        return _empty_figure(title)

    fig = px.scatter(
        df,
        x="median_income",
        y="average_rent",
        animation_frame="year",
        animation_group="province_state",
        color="country",
        color_discrete_map=REGION_COLORS,
        hover_name="province_state",
        size="cpi" if "cpi" in df.columns else None,
        range_x=[df["median_income"].min() * 0.9, df["median_income"].max() * 1.1],
        range_y=[df["average_rent"].min() * 0.9, df["average_rent"].max() * 1.1],
        title=title,
        labels={
            "median_income": "Median Household Income",
            "average_rent": "Average Monthly Rent",
            "country": "",
        },
    )
    fig.update_layout(**{**CHART_LAYOUT, "hovermode": "closest"}, height=560)
    return fig


def _empty_figure(title: str) -> go.Figure:
    """Placeholder figure shown when a query returns no rows."""
    fig = go.Figure()
    fig.add_annotation(
        text="No data available for the selected filters",
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=16, color="#64748B"),
    )
    fig.update_layout(**CHART_LAYOUT, title=title)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig
