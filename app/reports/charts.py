"""Plotly chart builders shared by the dashboard and HTML reports.

Each returns plotly Figure objects (JSON-serializable via to_json) so charts
can be embedded into Jinja2 templates with Plotly.js.
"""
from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _json(fig):
    return fig.to_json()


_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e5e7eb"),
    margin=dict(l=40, r=20, t=40, b=40),
)


def line_timeseries(rows, x_key, series: list[tuple[str, str]], title: str = "") -> str:
    """Build a line chart. rows: list of dicts; series: [(label, field), ...]."""
    fig = go.Figure()
    x = [r[x_key] for r in rows]
    for label, field in series:
        fig.add_trace(go.Scatter(x=x, y=[r.get(field) for r in rows],
                                 mode="lines", name=label))
    fig.update_layout(title=title, **_DARK)
    return _json(fig)


def bar_ranking(rows, name_key, value_key, title: str = "", top: int = 10) -> str:
    rows = sorted(rows, key=lambda r: r.get(value_key, 0), reverse=True)[:top]
    fig = go.Figure(
        go.Bar(
            x=[r.get(value_key) for r in rows],
            y=[str(r.get(name_key))[:40] for r in rows],
            orientation="h",
            marker_color="#6366f1",
        )
    )
    fig.update_layout(title=title, yaxis=dict(autorange="reversed"), **_DARK)
    return _json(fig)


def health_gauge(score: int) -> str:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"font": {"color": "#e5e7eb"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#e5e7eb"},
                "bar": {"color": "#6366f1"},
                "bgcolor": "#1f2937",
                "steps": [
                    {"range": [0, 40], "color": "#7f1d1d"},
                    {"range": [40, 70], "color": "#78350f"},
                    {"range": [70, 100], "color": "#14532d"},
                ],
            },
        )
    )
    fig.update_layout(**_DARK)
    return _json(fig)
