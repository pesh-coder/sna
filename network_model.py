"""
FundBlock — network model and SNA metrics.

The research question: what happens to a student-funding network when
universities stop being the sole intermediary between donors and students?

Two topologies are compared:
  MEDIATED  Donor -> University -> Student   (the traditional route)
  DIRECT    Donor -> University -> Student
            plus Donor -> Student            (FundBlock adds this edge type)

Node ids encode type: D* donor, U* university, S* student.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Node typing
# --------------------------------------------------------------------------
NODE_TYPES = ("Donor", "University", "Student")

TYPE_COLORS = {
    "Donor": "#C7452F",       # red
    "University": "#2B6CB0",  # blue
    "Student": "#2F855A",     # green
}


def node_type(node: str) -> str:
    """Classify a node from its id prefix."""
    if node.startswith("D"):
        return "Donor"
    if node.startswith("U"):
        return "University"
    return "Student"


# --------------------------------------------------------------------------
# Scenario definitions
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """One network configuration."""

    key: str
    label: str
    n_donors: int
    n_unis: int
    n_students: int
    direct: bool          # do donors link straight to students?
    csv: str | None = None  # load from file if present, else generate
    note: str = ""

    @property
    def topology(self) -> str:
        return "Direct + mediated" if self.direct else "Mediated only"


SCENARIOS: list[Scenario] = [
    # ---- the two primary cases (deep analysis) ----
    Scenario(
        key="small_mediated",
        label="A · Pilot — mediated only",
        n_donors=10, n_unis=5, n_students=100, direct=False,
        csv="data/small_edge_list_with_undirect_links.csv",
        note="Baseline pilot. Every rand reaches a student through a university.",
    ),
    Scenario(
        key="small_direct",
        label="B · Pilot — with direct funding",
        n_donors=10, n_unis=5, n_students=100, direct=True,
        csv="data/small_edge_list_with_direct_links.csv",
        note="Same pilot, but donors may also fund students directly (FundBlock).",
    ),
    # ---- national scale ----
    Scenario(
        key="full_mediated",
        label="C · National — mediated only",
        n_donors=100, n_unis=26, n_students=1000, direct=False,
        csv="data/full_edge_list_with_undirect_links.csv",
        note="26 public universities, national scale, traditional routing.",
    ),
    Scenario(
        key="full_direct",
        label="D · National — with direct funding",
        n_donors=100, n_unis=26, n_students=1000, direct=True,
        csv="data/full_edge_list_with_direct_links.csv",
        note="National scale with direct donor-to-student edges.",
    ),
    # ---- concentrated case: few universities, many students ----
    Scenario(
        key="concentrated_mediated",
        label="E · Concentrated — mediated only",
        n_donors=20, n_unis=3, n_students=100, direct=False,
        note="Few institutions act as gatekeepers for many students.",
    ),
    Scenario(
        key="concentrated_direct",
        label="F · Concentrated — with direct funding",
        n_donors=20, n_unis=3, n_students=100, direct=True,
        note="The same bottleneck, relieved by direct funding.",
    ),
]

SCENARIOS_BY_KEY = {s.key: s for s in SCENARIOS}


# --------------------------------------------------------------------------
# Building the graph
# --------------------------------------------------------------------------
def generate_edges(
    n_donors: int,
    n_unis: int,
    n_students: int,
    direct: bool,
    seed: int = 42,
    min_unis_per_donor: int = 1,
    max_unis_per_donor: int = 5,
    min_direct: int = 1,
    max_direct: int = 10,
) -> pd.DataFrame:
    """
    Build an edge list with the same rules as the original matrix scripts:
      * every student belongs to exactly one university
      * each donor supports between min and max universities
      * if `direct`, each donor also funds a random set of students
    """
    rng = random.Random(seed)

    donors = [f"D{i}" for i in range(n_donors)]
    unis = [f"U{i}" for i in range(n_unis)]
    students = [f"S{i}" for i in range(n_students)]

    edges: list[tuple[str, str]] = []

    # University -> Student (exactly one university per student)
    for s in students:
        edges.append((rng.choice(unis), s))

    # Donor -> University
    for d in donors:
        k = rng.randint(min_unis_per_donor, min(max_unis_per_donor, n_unis))
        for u in rng.sample(unis, k):
            edges.append((d, u))

    # Donor -> Student (only in the direct topology)
    if direct:
        for d in donors:
            k = rng.randint(min_direct, min(max_direct, n_students))
            for s in rng.sample(students, k):
                edges.append((d, s))

    return pd.DataFrame(edges, columns=["source", "target"])


def build_graph(edges: pd.DataFrame) -> nx.DiGraph:
    """Directed graph; funding flows source -> target."""
    g = nx.from_pandas_edgelist(
        edges, source="source", target="target", create_using=nx.DiGraph()
    )
    nx.set_node_attributes(g, {n: node_type(n) for n in g.nodes()}, "type")
    return g


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def node_metrics(g: nx.DiGraph, exact_betweenness: bool = True) -> pd.DataFrame:
    """
    Per-node centrality table.

    Betweenness is the expensive one; on large graphs we sample pivots
    (k=200) which is a standard approximation and keeps the app responsive.
    """
    n = g.number_of_nodes()
    if exact_betweenness or n <= 400:
        betweenness = nx.betweenness_centrality(g, normalized=True)
    else:
        betweenness = nx.betweenness_centrality(
            g, k=min(200, n), normalized=True, seed=42
        )

    in_deg = dict(g.in_degree())
    out_deg = dict(g.out_degree())
    closeness_out = nx.closeness_centrality(g)
    closeness_in = nx.closeness_centrality(g.reverse())
    pagerank = nx.pagerank(g)
    reach = {node: len(nx.descendants(g, node)) for node in g.nodes()}

    return pd.DataFrame(
        {
            "node": list(g.nodes()),
            "type": [node_type(x) for x in g.nodes()],
            "in_degree": [in_deg[x] for x in g.nodes()],
            "out_degree": [out_deg[x] for x in g.nodes()],
            "betweenness": [betweenness[x] for x in g.nodes()],
            "closeness_out": [closeness_out[x] for x in g.nodes()],
            "closeness_in": [closeness_in[x] for x in g.nodes()],
            "pagerank": [pagerank[x] for x in g.nodes()],
            "reachable_nodes": [reach[x] for x in g.nodes()],
        }
    ).set_index("node")


def group_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    """Average each metric within Donor / University / Student."""
    order = [t for t in NODE_TYPES if t in set(metrics["type"])]
    return (
        metrics.groupby("type")
        .mean(numeric_only=True)
        .reindex(order)
        .round(4)
    )


def avg_shortest_path_directed(g: nx.DiGraph) -> float:
    """Mean length over all *reachable* ordered pairs."""
    total, count = 0, 0
    for node in g.nodes():
        lengths = nx.single_source_shortest_path_length(g, node)
        for target, dist in lengths.items():
            if node != target:
                total += dist
                count += 1
    return total / count if count else float("nan")


def network_summary(g: nx.DiGraph) -> pd.DataFrame:
    """Whole-graph structural metrics."""
    reach = [len(nx.descendants(g, n)) for n in g.nodes()]
    rows = {
        "Nodes": g.number_of_nodes(),
        "Edges": g.number_of_edges(),
        "Density": nx.density(g),
        "Avg shortest path (directed)": avg_shortest_path_directed(g),
        "Avg reachability": float(np.mean(reach)) if reach else 0.0,
        "Weak components": nx.number_weakly_connected_components(g),
        "Strong components": nx.number_strongly_connected_components(g),
    }
    return pd.DataFrame({"Value": rows.values()}, index=list(rows.keys()))


# --------------------------------------------------------------------------
# Disintermediation: what happens when universities are removed?
# --------------------------------------------------------------------------
def students_reachable_by_donors(g: nx.DiGraph) -> int:
    """How many distinct students can any donor reach, by any path?"""
    donors = [n for n in g.nodes() if node_type(n) == "Donor"]
    reached: set[str] = set()
    for d in donors:
        reached |= {x for x in nx.descendants(g, d) if node_type(x) == "Student"}
    return len(reached)


def orphaned_students(g: nx.DiGraph) -> int:
    """Students no donor can reach — the ones who lose funding access."""
    students = [n for n in g.nodes() if node_type(n) == "Student"]
    return len(students) - students_reachable_by_donors(g)


def remove_universities(g: nx.DiGraph, unis: list[str]) -> nx.DiGraph:
    """Return a copy with the given universities removed (edges included)."""
    h = g.copy()
    h.remove_nodes_from(unis)
    return h


def failure_curve(g: nx.DiGraph, order: str = "betweenness") -> pd.DataFrame:
    """
    Remove universities one at a time and record how many students remain
    reachable by donors.

    `order`:
      "betweenness" — most central first (targeted failure)
      "random"      — random order (accidental failure)

    This is the core experiment: in a mediated-only network, removing the
    hubs strands students. With direct edges, the drop is far smaller —
    which is the quantitative case for disintermediation.
    """
    unis = [n for n in g.nodes() if node_type(n) == "University"]

    if order == "betweenness":
        bc = nx.betweenness_centrality(g, normalized=True)
        unis = sorted(unis, key=lambda u: bc[u], reverse=True)
    else:
        rng = random.Random(42)
        rng.shuffle(unis)

    total_students = sum(1 for n in g.nodes() if node_type(n) == "Student")

    rows = [
        {
            "universities_removed": 0,
            "students_reachable": students_reachable_by_donors(g),
            "pct_reachable": 100 * students_reachable_by_donors(g) / total_students,
        }
    ]

    working = g.copy()
    for i, u in enumerate(unis, start=1):
        working.remove_node(u)
        reachable = students_reachable_by_donors(working)
        rows.append(
            {
                "universities_removed": i,
                "students_reachable": reachable,
                "pct_reachable": 100 * reachable / total_students,
            }
        )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
def layout_3d(g: nx.DiGraph, mode: str = "layered", seed: int = 42) -> dict:
    """
    3D positions.

    "layered" — donors on top, universities in the middle, students below.
                Makes the intermediary role legible at a glance.
    "spring"  — force-directed in 3D; clusters emerge naturally.
    """
    if mode == "layered":
        pos2d = nx.spring_layout(g, dim=2, seed=seed)
        z_by_type = {"Donor": 1.0, "University": 0.0, "Student": -1.0}
        return {
            n: (float(pos2d[n][0]), float(pos2d[n][1]), z_by_type[node_type(n)])
            for n in g.nodes()
        }

    pos3d = nx.spring_layout(g, dim=3, seed=seed)
    return {n: tuple(float(c) for c in pos3d[n]) for n in g.nodes()}
