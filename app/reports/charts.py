"""Plotly chart builders shared by the dashboard and HTML reports.

Each returns plotly Figure objects (JSON-serializable via to_json) so charts
can be embedded into Jinja2 templates with Plotly.js.
"""
from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _json(fig):
    return fig.to_json()


def line_timeseries(rows, x_key, series: list[tuple[str, str]], title: str = "") -> str:
    """Build a line chart. rows: list of dicts; series: [(label, field), ...]."""
    fig = go.Figure()
    x = [r[x_key] for r in rows]
    for label, field in series:
        fig.add_trace(go.Scatter(x=x, y=[r.get(field) for r in rows],
                                 mode="lines", name=label))
    fig.update_layout(title=title, template="plotly_white")
    return _json(fig)


def bar_ranking(rows, name_key, value_key, title: str = "", top: int = 10) -> str:
    rows = sorted(rows, key=lambda r: r.get(value_key, 0), reverse=True)[:top]
    fig = go.Figure(
        go.Bar(
            x=[r.get(value_key) for r in rows],
            y=[str(r.get(name_key))[:40] for r in rows],
            orientation="h",
        )
    )
    fig.update_layout(title=title, template="plotly_white",
                      yaxis=dict(autorange="reversed"))
    return _json(fig)


def health_gauge(score: int) -> str:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": "steelblue"},
                   "steps": [
                       {"range": [0, 40], "color": "#f8d7da"},
                       {"range": [40, 70], "color": "#fff3cd"},
                       {"range": [70, 100], "color": "#d4edda"},
                   ]},
        )
    )
    fig.update_layout(template="plotly_white")
    return _json(fig)
