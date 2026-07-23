# FundBlock — Funding Network Analysis

Interactive 3D social-network analysis of student funding in South Africa, built for the
UZH *Deep Dive into Blockchain 2026* final project.

**The question:** donors traditionally reach students *through* universities. FundBlock adds a
direct donor→student edge. What does that structural change do to reach, resilience, and the
centrality of institutions?

---

## The headline finding

Universities are removed one at a time, most central first, and we measure how many students
**any donor can still reach**:

| Network | All universities removed |
|---|---|
| National · mediated only | **0%** of students reachable |
| National · with direct funding | **84%** of students reachable |
| Pilot · mediated only | **0%** |
| Pilot · with direct funding | **42%** |

In a mediated-only topology, funding access collapses completely when intermediaries fail.
Direct edges keep most students reachable. That gap is the structural argument for
disintermediation — not that universities fail, but that a single-intermediary topology is
fragile by construction.

## Run locally

```bash
pip install -r requirements.txt
streamlit run main.py
```

## Deploy to Streamlit Cloud (free, public URL)

1. Push this folder to a **public** GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **Create app** → select your repository.
4. Set **Main file path** to `main.py`.
5. **Deploy.** First build takes 1–2 minutes.

Streamlit reads `requirements.txt` automatically. Keep the `data/` folder — the app loads
your real edge lists from it.

## What's in here

```
main.py               the Streamlit app (UI, tabs, layout)
network_model.py      graph construction, SNA metrics, failure experiment
viz.py                Plotly 3D network and chart builders
data/                 the four uploaded edge lists
requirements.txt      dependencies for Streamlit Cloud
.streamlit/config.toml  theme
```

The logic is deliberately separate from the UI so the metrics can be cited in the report
independently of the app.

## The six networks

| # | Scenario | Donors | Universities | Students | Topology | Source |
|---|---|---|---|---|---|---|
| A | Pilot — mediated | 10 | 5 | 100 | D→U→S | uploaded CSV |
| B | Pilot — direct | 10 | 5 | 100 | + D→S | uploaded CSV |
| C | National — mediated | 100 | 26 | 1000 | D→U→S | uploaded CSV |
| D | National — direct | 100 | 26 | 1000 | + D→S | uploaded CSV |
| E | Concentrated — mediated | 20 | 3 | 100 | D→U→S | generated |
| F | Concentrated — direct | 20 | 3 | 100 | + D→S | generated |

A–D come from the uploaded edge lists. E–F are generated at runtime with the same rules
(every student belongs to exactly one university; donors link to 1–5 universities; in the
direct topology donors also fund a random set of students).

## Metrics

* **Degree centrality** (in/out) — direct connection counts.
* **Betweenness centrality** — how often a node bridges others; the gatekeeping measure.
* **Closeness centrality** — computed both directions, since funding is directional.
* **PageRank** — influence weighted by the influence of one's connections.
* **Density** — realised share of possible ties. Low density concentrates flow through few
  paths, so a weak fundraiser at one institution strands the students behind it.
* **Reachability** — how many nodes a node can reach by any path. For a donor, their true
  funding footprint.

Betweenness on networks above 400 nodes uses 200 sampled pivots (standard approximation) to
keep the app responsive.

## Data sources and honest limits

Node counts reflect South African higher education — 26 public universities nationally.

* Department of Basic Education — university register:
  <https://www.education.gov.za/FurtherStudies/Universities.aspx>
* DHET — register of private colleges (15 July 2026):
  <https://www.dhet.gov.za/Registers_DocLib/Register%20of%20Private%20Colleges%20%2015%20July%202026.pdf>

**Limitation worth stating in the report:** the network *structure* is calibrated to the real
sector, but individual donor and student links are synthetic — no real funding-relationship
data was available. The results therefore describe how networks of this *shape* behave, not
observed South African funding flows. The comparison between topologies is the finding; the
absolute numbers are illustrative.

---

DDiB 2026 · UZH Blockchain Center · FundBlock
