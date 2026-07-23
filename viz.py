"""Plotly figures for the FundBlock network app."""

from __future__ import annotations

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from network_model import TYPE_COLORS, node_type

# Edge colours by the kind of relationship they represent.
EDGE_COLORS = {
    "D->U": "rgba(199,69,47,0.30)",    # donor funds a university
    "U->S": "rgba(43,108,176,0.28)",   # university allocates to a student
    "D->S": "rgba(47,133,90,0.55)",    # donor funds a student directly
}


def _edge_class(u: str, v: str) -> str:
    return f"{node_type(u)[0]}->{node_type(v)[0]}"


def network_3d(
    g: nx.DiGraph,
    pos: dict,
    highlight: set[str] | None = None,
    node_size: int = 4,
    show_edges: bool = True,
    title: str = "",
) -> go.Figure:
    """
    Interactive 3D network. Edges are drawn as separate traces per class so
    the legend can toggle donor->student links on and off — the single most
    useful interaction for seeing what direct funding adds.
    """
    highlight = highlight or set()
    traces: list[go.Scatter3d] = []

    if show_edges:
        by_class: dict[str, list[tuple[str, str]]] = {}
        for u, v in g.edges():
            by_class.setdefault(_edge_class(u, v), []).append((u, v))

        readable = {
            "D->U": "Donor → University",
            "U->S": "University → Student",
            "D->S": "Donor → Student (direct)",
        }

        for cls, pairs in sorted(by_class.items()):
            ex, ey, ez = [], [], []
            for u, v in pairs:
                x0, y0, z0 = pos[u]
                x1, y1, z1 = pos[v]
                ex += [x0, x1, None]
                ey += [y0, y1, None]
                ez += [z0, z1, None]
            traces.append(
                go.Scatter3d(
                    x=ex, y=ey, z=ez,
                    mode="lines",
                    line=dict(width=1.4, color=EDGE_COLORS.get(cls, "rgba(120,120,120,0.3)")),
                    hoverinfo="none",
                    name=readable.get(cls, cls),
                    legendgroup=cls,
                )
            )

    # One node trace per type, so each can be toggled in the legend.
    for ntype in ("Student", "University", "Donor"):
        members = [n for n in g.nodes() if node_type(n) == ntype]
        if not members:
            continue

        xs = [pos[n][0] for n in members]
        ys = [pos[n][1] for n in members]
        zs = [pos[n][2] for n in members]

        # Scatter3d takes a single scalar for marker.line.width (unlike 2D),
        # so highlighting is expressed through size and colour only.
        sizes, colors = [], []
        for n in members:
            hit = n in highlight
            base = node_size + (3 if ntype == "University" else 0)
            sizes.append(base + 5 if hit else base)
            colors.append("#E8C56A" if hit else TYPE_COLORS[ntype])

        hover = [
            f"<b>{n}</b><br>{ntype}"
            f"<br>in-degree: {g.in_degree(n)}"
            f"<br>out-degree: {g.out_degree(n)}"
            for n in members
        ]

        traces.append(
            go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode="markers",
                marker=dict(
                    size=sizes,
                    color=colors,
                    opacity=0.92,
                    line=dict(width=0.5, color="#1C1917"),
                ),
                text=hover,
                hoverinfo="text",
                name=ntype,
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title or None,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=0.005, x=0.0),
        margin=dict(l=0, r=0, b=0, t=30 if title else 0),
        height=680,
        scene=dict(
            xaxis=dict(showticklabels=False, title="", showbackground=False),
            yaxis=dict(showticklabels=False, title="", showbackground=False),
            zaxis=dict(showticklabels=False, title="", showbackground=False),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def failure_curve_chart(curves: dict[str, pd.DataFrame]) -> go.Figure:
    """
    Students still reachable by donors as universities are removed.
    One line per topology, so the divergence is the headline.
    """
    palette = {
        "Mediated only": "#C7452F",
        "Direct + mediated": "#2F855A",
    }

    fig = go.Figure()
    for label, df in curves.items():
        fig.add_trace(
            go.Scatter(
                x=df["universities_removed"],
                y=df["pct_reachable"],
                mode="lines+markers",
                name=label,
                line=dict(width=3, color=palette.get(label)),
                marker=dict(size=7),
                hovertemplate=(
                    "%{y:.1f}% of students reachable<br>"
                    "after removing %{x} universities<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        xaxis_title="Universities removed (most central first)",
        yaxis_title="Students still reachable by donors (%)",
        yaxis=dict(range=[0, 105]),
        height=430,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        hovermode="x unified",
    )
    return fig


def degree_distribution(metrics: pd.DataFrame, column: str = "out_degree") -> go.Figure:
    """Distribution of a degree measure, split by node type."""
    fig = go.Figure()
    for ntype in ("Donor", "University", "Student"):
        subset = metrics[metrics["type"] == ntype][column]
        if subset.empty:
            continue
        fig.add_trace(
            go.Histogram(
                x=subset,
                name=ntype,
                marker_color=TYPE_COLORS[ntype],
                opacity=0.75,
                nbinsx=25,
            )
        )
    fig.update_layout(
        barmode="overlay",
        xaxis_title=column.replace("_", " "),
        yaxis_title="Number of nodes",
        height=340,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
    )
    return fig


def centrality_bar(metrics: pd.DataFrame, column: str, top_n: int = 15) -> go.Figure:
    """Top-N nodes by a centrality measure."""
    top = metrics.nlargest(top_n, column).iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=top[column],
            y=top.index,
            orientation="h",
            marker_color=[TYPE_COLORS[t] for t in top["type"]],
            hovertemplate="%{y}: %{x:.4f}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title=column.replace("_", " "),
        height=max(300, 22 * len(top)),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    return fig
