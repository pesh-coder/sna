"""
FundBlock — Social Network Analysis of student funding in South Africa.

Interactive companion to the DDiB 2026 final project. Compares a traditional
donor -> university -> student funding network against one where donors can
also fund students directly, and quantifies what universities' centrality
is actually worth to the system.

Run locally:   streamlit run main.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import network_model as nm
import viz

st.set_page_config(
    page_title="FundBlock · Funding Network Analysis",
    page_icon="🎓",
    layout="wide",
)

DATA_DIR = Path(__file__).parent / "data"


# --------------------------------------------------------------------------
# Data loading (cached — these are the expensive calls)
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_edges(key: str) -> pd.DataFrame:
    """Read a scenario's edge list, or generate it when no CSV is supplied."""
    scenario = nm.SCENARIOS_BY_KEY[key]

    if scenario.csv:
        path = Path(__file__).parent / scenario.csv
        if path.exists():
            return pd.read_csv(path)

    return nm.generate_edges(
        n_donors=scenario.n_donors,
        n_unis=scenario.n_unis,
        n_students=scenario.n_students,
        direct=scenario.direct,
        seed=42,
    )


@st.cache_data(show_spinner=False)
def compute_metrics(key: str) -> pd.DataFrame:
    graph = nm.build_graph(load_edges(key))
    return nm.node_metrics(graph, exact_betweenness=graph.number_of_nodes() <= 400)


@st.cache_data(show_spinner=False)
def compute_network_summary(key: str) -> pd.DataFrame:
    return nm.network_summary(nm.build_graph(load_edges(key)))


@st.cache_data(show_spinner=False)
def compute_failure_curve(key: str, order: str) -> pd.DataFrame:
    return nm.failure_curve(nm.build_graph(load_edges(key)), order=order)


@st.cache_data(show_spinner=False)
def compute_layout(key: str, mode: str) -> dict:
    return nm.layout_3d(nm.build_graph(load_edges(key)), mode=mode)


def graph_for(key: str):
    return nm.build_graph(load_edges(key))


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.title("🎓 FundBlock")
    st.caption("Network analysis of student funding · DDiB 2026")

    st.subheader("Network")
    scenario_key = st.selectbox(
        "Scenario",
        options=[s.key for s in nm.SCENARIOS],
        format_func=lambda k: nm.SCENARIOS_BY_KEY[k].label,
        index=1,
    )
    scenario = nm.SCENARIOS_BY_KEY[scenario_key]
    st.caption(scenario.note)

    st.subheader("3D view")
    layout_mode = st.radio(
        "Layout",
        options=["layered", "spring"],
        format_func=lambda m: "Layered (by role)" if m == "layered" else "Force-directed",
        help="Layered stacks donors above universities above students, which "
             "makes the intermediary layer obvious. Force-directed reveals clusters.",
    )
    node_size = st.slider("Node size", 2, 10, 4)
    show_edges = st.checkbox("Show edges", value=True)

    st.divider()
    st.caption(
        "Node counts follow South African higher education: 26 public "
        "universities nationally. Sources: DBE university register; DHET "
        "register of private colleges."
    )


graph = graph_for(scenario_key)
metrics = compute_metrics(scenario_key)

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("Funding networks: what happens when universities stop being the gatekeeper?")
st.markdown(
    "Donors traditionally reach students **through** universities. FundBlock adds a "
    "direct donor→student edge. This app measures what that structural change does "
    "to reach, resilience, and the centrality of institutions."
)

col1, col2, col3, col4 = st.columns(4)
n_donors = sum(1 for n in graph.nodes() if nm.node_type(n) == "Donor")
n_unis = sum(1 for n in graph.nodes() if nm.node_type(n) == "University")
n_students = sum(1 for n in graph.nodes() if nm.node_type(n) == "Student")
col1.metric("Donors", n_donors)
col2.metric("Universities", n_unis)
col3.metric("Students", n_students)
col4.metric("Funding relationships", graph.number_of_edges())

st.caption(f"**Topology:** {scenario.topology}")

tab_network, tab_removal, tab_metrics, tab_compare, tab_about = st.tabs(
    ["🌐 3D Network", "⚡ Removing universities", "📊 Metrics", "⚖️ Compare", "ℹ️ About"]
)


# --------------------------------------------------------------------------
# Tab 1 — the 3D network
# --------------------------------------------------------------------------
with tab_network:
    left, right = st.columns([3, 1])

    with right:
        st.subheader("Highlight")
        highlight_metric = st.selectbox(
            "Most central nodes by",
            ["betweenness", "out_degree", "in_degree", "pagerank", "closeness_in"],
            help="Highlighted nodes are drawn larger and in gold.",
        )
        highlight_n = st.slider("How many", 0, 25, 5)
        highlight = set(metrics.nlargest(highlight_n, highlight_metric).index) if highlight_n else set()

        if highlight:
            st.caption("Highlighted:")
            st.dataframe(
                metrics.loc[sorted(highlight), ["type", highlight_metric]]
                .sort_values(highlight_metric, ascending=False)
                .round(4),
                use_container_width=True,
            )

    with left:
        pos = compute_layout(scenario_key, layout_mode)
        st.plotly_chart(
            viz.network_3d(
                graph, pos,
                highlight=highlight,
                node_size=node_size,
                show_edges=show_edges,
            ),
            use_container_width=True,
        )
        st.caption(
            "Drag to rotate · scroll to zoom · click legend entries to toggle "
            "node types and edge classes. Turning off *Donor → Student (direct)* "
            "shows the traditional network underneath."
        )


# --------------------------------------------------------------------------
# Tab 2 — the disintermediation experiment
# --------------------------------------------------------------------------
with tab_removal:
    st.subheader("What if universities disappear?")
    st.markdown(
        "Universities are removed one at a time, most central first. The line "
        "tracks how many students **any donor can still reach**. This is the "
        "central experiment: it prices the risk of routing all funding through "
        "a small number of intermediaries."
    )

    removal_order = st.radio(
        "Removal order",
        ["betweenness", "random"],
        format_func=lambda o: "Targeted (most central first)" if o == "betweenness" else "Random (accidental failure)",
        horizontal=True,
    )

    curves = {
        "Mediated only": compute_failure_curve(
            "small_mediated" if scenario.n_students <= 100 and scenario.n_unis == 5 else "full_mediated",
            removal_order,
        ),
        "Direct + mediated": compute_failure_curve(
            "small_direct" if scenario.n_students <= 100 and scenario.n_unis == 5 else "full_direct",
            removal_order,
        ),
    }

    st.plotly_chart(viz.failure_curve_chart(curves), use_container_width=True)

    med_final = curves["Mediated only"]["pct_reachable"].iloc[-1]
    dir_final = curves["Direct + mediated"]["pct_reachable"].iloc[-1]

    a, b, c = st.columns(3)
    a.metric("Mediated: students reachable after full collapse", f"{med_final:.0f}%")
    b.metric("Direct: students reachable after full collapse", f"{dir_final:.0f}%")
    c.metric("Resilience gained", f"+{dir_final - med_final:.0f} pts")

    st.info(
        f"With every university removed, the mediated network leaves "
        f"**{med_final:.0f}%** of students reachable — funding access collapses. "
        f"With direct donor→student edges, **{dir_final:.0f}%** remain reachable. "
        "That gap is the structural value FundBlock adds: it is not a claim about "
        "universities failing, but about what a single-intermediary topology costs "
        "when any part of it is disrupted."
    )

    with st.expander("Why this matters for the three stakeholders"):
        st.markdown(
            """
**Universities** — the model does not remove their role, it removes their
*obligation*. They keep verification (which is what they are trusted for) while
no longer being the sole funding conduit, so they carry less fundraising burden.

**Students** — in a mediated-only network, a student's access to funding is
bounded by how well their institution attracts donors. Direct edges decouple
those two things, so students at less well-resourced institutions are no longer
structurally disadvantaged.

**Companies and donors** — direct edges let a donor reach a specific field or
cohort without negotiating with each institution separately, which is the
talent-pipeline argument.
            """
        )

    with st.expander("Underlying numbers"):
        merged = curves["Mediated only"][["universities_removed", "pct_reachable"]].rename(
            columns={"pct_reachable": "Mediated (%)"}
        ).merge(
            curves["Direct + mediated"][["universities_removed", "pct_reachable"]].rename(
                columns={"pct_reachable": "Direct (%)"}
            ),
            on="universities_removed",
        )
        st.dataframe(merged.round(1), use_container_width=True)


# --------------------------------------------------------------------------
# Tab 3 — metrics
# --------------------------------------------------------------------------
with tab_metrics:
    st.subheader("Network-level metrics")
    st.dataframe(compute_network_summary(scenario_key).round(4), use_container_width=True)

    st.caption(
        "**Density** is the share of possible connections that exist. Low density "
        "means information and money must travel through few paths — so a weak "
        "fundraiser at one institution strands the students behind it. "
        "**Strong components** counts mutually-reachable groups; funding flows one "
        "way, so this stays near the node count and is reported for completeness."
    )

    st.subheader("Average metrics by node type")
    st.dataframe(nm.group_summary(metrics), use_container_width=True)

    st.markdown(
        """
Reading the table:

* **Betweenness** — how often a node sits on the shortest path between two
  others. In a mediated network this is concentrated almost entirely in
  universities: they are the bridge. Direct edges reduce it.
* **Out-degree** for donors is how many parties they fund; for universities,
  how many students they serve.
* **Reachable nodes** for a donor is the size of their funding footprint —
  the clearest single measure of what direct funding unlocks.
        """
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Degree distribution")
        degree_col = st.selectbox("Measure", ["out_degree", "in_degree"], key="degree_dist")
        st.plotly_chart(viz.degree_distribution(metrics, degree_col), use_container_width=True)

    with right:
        st.subheader("Most central nodes")
        central_col = st.selectbox(
            "Centrality",
            ["betweenness", "pagerank", "out_degree", "in_degree", "closeness_in"],
            key="central_bar",
        )
        st.plotly_chart(viz.centrality_bar(metrics, central_col), use_container_width=True)

    st.subheader("Per-node table")
    type_filter = st.multiselect(
        "Node types", nm.NODE_TYPES, default=list(nm.NODE_TYPES)
    )
    filtered = metrics[metrics["type"].isin(type_filter)]
    st.dataframe(filtered.round(4), use_container_width=True, height=340)
    st.download_button(
        "Download metrics (CSV)",
        filtered.to_csv().encode("utf-8"),
        file_name=f"fundblock_metrics_{scenario_key}.csv",
        mime="text/csv",
    )


# --------------------------------------------------------------------------
# Tab 4 — side-by-side comparison
# --------------------------------------------------------------------------
with tab_compare:
    st.subheader("Compare any two networks")

    left_key, right_key = st.columns(2)
    with left_key:
        key_a = st.selectbox(
            "Left",
            [s.key for s in nm.SCENARIOS],
            format_func=lambda k: nm.SCENARIOS_BY_KEY[k].label,
            index=0,
            key="cmp_a",
        )
    with right_key:
        key_b = st.selectbox(
            "Right",
            [s.key for s in nm.SCENARIOS],
            format_func=lambda k: nm.SCENARIOS_BY_KEY[k].label,
            index=1,
            key="cmp_b",
        )

    summary_a = compute_network_summary(key_a)
    summary_b = compute_network_summary(key_b)
    side_by_side = summary_a.join(summary_b, lsuffix=" · left", rsuffix=" · right")
    side_by_side.columns = [
        nm.SCENARIOS_BY_KEY[key_a].label,
        nm.SCENARIOS_BY_KEY[key_b].label,
    ]
    st.dataframe(side_by_side.round(4), use_container_width=True)

    ca, cb = st.columns(2)
    for col, key in ((ca, key_a), (cb, key_b)):
        with col:
            st.markdown(f"**{nm.SCENARIOS_BY_KEY[key].label}**")
            g = graph_for(key)
            st.plotly_chart(
                viz.network_3d(
                    g,
                    compute_layout(key, layout_mode),
                    node_size=max(2, node_size - 1),
                    show_edges=show_edges,
                ),
                use_container_width=True,
                key=f"cmp_plot_{key}",
            )
            st.dataframe(nm.group_summary(compute_metrics(key)), use_container_width=True)


# --------------------------------------------------------------------------
# Tab 5 — about
# --------------------------------------------------------------------------
with tab_about:
    st.subheader("What this models")
    st.markdown(
        """
FundBlock is a blockchain-backed marketplace connecting donors with
university-verified students. This analysis asks a structural question that
sits underneath the product: **what does it change when donors can reach
students directly, instead of only through institutions?**

Three node types, three edge types:

| Edge | Meaning |
|---|---|
| Donor → University | Traditional institutional giving |
| University → Student | Institutional allocation to a student |
| Donor → Student | Direct funding — the edge FundBlock adds |

Every student belongs to exactly one university, which mirrors enrolment and
makes the intermediary's role unambiguous.
        """
    )

    st.subheader("The six networks")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Scenario": s.label,
                    "Donors": s.n_donors,
                    "Universities": s.n_unis,
                    "Students": s.n_students,
                    "Topology": s.topology,
                    "Source": "Uploaded edge list" if s.csv else "Generated",
                }
                for s in nm.SCENARIOS
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Metrics used")
    st.markdown(
        """
* **Degree centrality** (in / out) — direct connection counts.
* **Betweenness centrality** — how often a node bridges others. The measure
  that captures gatekeeping.
* **Closeness centrality** — computed both ways, since funding is directional:
  *closeness-out* is how quickly a node reaches others, *closeness-in* how
  quickly it is reached.
* **PageRank** — influence weighted by the influence of one's connections.
* **Density** — realised share of possible ties. Low density concentrates flow
  through few paths, so disruption propagates.
* **Reachability** — how many nodes a given node can reach by any path. For a
  donor, this is their true funding footprint.

On networks above 400 nodes, betweenness is estimated with 200 sampled pivots
(a standard approximation) to keep the app responsive.
        """
    )

    st.subheader("Data sources")
    st.markdown(
        """
Node counts reflect South African higher education — 26 public universities
nationally.

* Department of Basic Education — university register:
  <https://www.education.gov.za/FurtherStudies/Universities.aspx>
* DHET — register of private colleges (15 July 2026):
  <https://www.dhet.gov.za/Registers_DocLib/Register%20of%20Private%20Colleges%20%2015%20July%202026.pdf>

**A note on interpretation.** The *structure* is calibrated to the real sector,
but the individual donor and student links are synthetic — no real funding
relationships were available. So the results describe how networks of this
*shape* behave, not observed South African funding flows. The comparison
between topologies is the finding; the absolute numbers are illustrative.
        """
    )

    st.subheader("Reproducing this")
    st.code(
        "pip install -r requirements.txt\nstreamlit run main.py",
        language="bash",
    )
    st.caption("DDiB 2026 · UZH Blockchain Center · FundBlock")
