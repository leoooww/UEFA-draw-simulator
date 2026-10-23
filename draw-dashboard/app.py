"""Streamlit dashboard for the UEFA draw simulator."""

from __future__ import annotations

import json
import os
from pathlib import Path
import random
import time
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.environ.get("JULIA_API_URL", "http://127.0.0.1:8080").rstrip("/")
POT_COLORS = {"A": "#f5c542", "B": "#4cc9f0", "C": "#b388ff", "D": "#ff7a90"}
ORDER_LABELS = {
    "by_pot": "Pot by pot (A to D)",
    "random": "Fully random order",
}
SELECTION_LABELS = {
    "rejection": "Rejection sampling",
    "enumeration": "Exhaustive enumeration",
}
MAX_SEED = 2**31 - 1

DATA_DIR = Path(__file__).resolve().parent / "data"
LEAGUES_FILE = DATA_DIR / "leagues.json"
PRECOMPUTED_FILE = DATA_DIR / "precomputed_draws.json"

st.set_page_config(page_title="UEFA Draw Simulator", layout="wide")

st.title("UEFA Draw Simulator")
st.caption("League-phase draw simulation for 36 teams across 4 pots using Julia (JuMP and SCIP).")


# ----------------------------------------------------------------------------- Data Catalog & API
class ApiError(Exception):
    """Raised for any failure talking to the Julia service."""


def _call(method: str, path: str, *, timeout: float = 600, **kwargs: Any) -> Any:
    try:
        resp = requests.request(method, f"{API_URL}{path}", timeout=timeout, **kwargs)
    except requests.ConnectionError as exc:
        raise ApiError(f"Cannot reach the Julia service at {API_URL}. Is it running?") from exc
    except requests.Timeout as exc:
        raise ApiError("The Julia service took too long to answer.") from exc
    if not resp.ok:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(f"Julia service error {resp.status_code}: {detail}")
    return resp.json()


def backend_health() -> dict | None:
    try:
        resp = requests.get(f"{API_URL}/health", timeout=1.5)
        if resp.ok:
            return resp.json()
    except (requests.RequestException, ValueError):
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_leagues() -> dict[str, dict]:
    """Load league configuration from pre-saved data file or live API."""
    if LEAGUES_FILE.exists():
        try:
            with open(LEAGUES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {league["key"]: league for league in data}
        except Exception:
            pass
    return {league["key"]: league for league in _call("GET", "/api/leagues", timeout=10)}


@st.cache_data(show_spinner=False)
def get_precomputed_catalog() -> dict:
    """Load pre-computed simulations with true recorded JuMP/SCIP execution times."""
    if PRECOMPUTED_FILE.exists():
        try:
            with open(PRECOMPUTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"draws": {}, "multi_draws": {}}


@st.cache_data(max_entries=64, show_spinner=False)
def fetch_live_draw(league: str, order: str, selection: str, n_draws: int, seed: int) -> dict:
    """Cached on parameter set: identical live inputs never hit Julia twice."""
    payload = {"league": league, "order": order, "selection": selection, "n_draws": n_draws, "seed": seed}
    return _call("POST", "/api/draw", json=payload)


# ----------------------------------------------------------------------------- Data Shaping
def teams_frame(draw: dict) -> pd.DataFrame:
    rows = []
    for t in draw["teams"]:
        row = {"Club": t["club"], "Pot": t["pot"], "Nationality": t["nationality"]}
        for o in t["opponents"]:
            row[f"Home vs {o['pot']}"] = o["home_vs"]
            row[f"Away at {o['pot']}"] = o["away_vs"]
        row["Total Opponent Elo"] = t["elo_sum"]
        row["Total Opponent UEFA"] = round(t["uefa_sum"], 3)
        rows.append(row)
    return pd.DataFrame(rows)


def fixtures_frame(draw: dict) -> pd.DataFrame:
    rows = [
        {"Home": t["club"], "Away": o["home_vs"], "Pot of away team": o["pot"]}
        for t in draw["teams"]
        for o in t["opponents"]
    ]
    return pd.DataFrame(rows)


def team_schedule(draw: dict, club: str) -> pd.DataFrame:
    meta = {t["club"]: t for t in draw["teams"]}
    rows = []
    for o in next(t for t in draw["teams"] if t["club"] == club)["opponents"]:
        for venue, opp in (("Home", o["home_vs"]), ("Away", o["away_vs"])):
            m = meta[opp]
            rows.append(
                {
                    "Pot": o["pot"],
                    "Venue": venue,
                    "Opponent": opp,
                    "Nationality": m["nationality"],
                    "Elo": m["elo"],
                    "UEFA coeff.": m["uefa"],
                }
            )
    return pd.DataFrame(rows)


def render_animated_results_table(df: pd.DataFrame, nonce: int = 0, animate: bool = True) -> str:
    """Render the results table with a top-left to bottom-right fading green wave animation covering the whole cell."""
    cols = list(df.columns)
    team_cols = {
        "Club",
        "Home vs A", "Away at A",
        "Home vs B", "Away at B",
        "Home vs C", "Away at C",
        "Home vs D", "Away at D",
    }

    style_block = ""
    if animate:
        style_block = f"""<style>
@keyframes cellFadeGreenSweep_{nonce} {{
  0% {{
    opacity: 0;
    transform: scale(0.96) translateY(2px);
    background-color: rgba(34, 197, 94, 0.55);
    box-shadow: inset 0 0 12px rgba(34, 197, 94, 0.45);
    color: #ffffff;
  }}
  30% {{
    opacity: 1;
    transform: scale(1) translateY(0);
    background-color: rgba(34, 197, 94, 0.35);
    box-shadow: inset 0 0 8px rgba(34, 197, 94, 0.3);
    color: #15803d;
  }}
  100% {{
    opacity: 1;
    transform: scale(1) translateY(0);
    background-color: transparent;
    box-shadow: none;
    color: inherit;
  }}
}}

.draw-table-{nonce} td.anim-cell-{nonce} {{
  will-change: transform, opacity, background-color;
  animation-name: cellFadeGreenSweep_{nonce};
  animation-duration: 0.85s;
  animation-timing-function: cubic-bezier(0.16, 1, 0.3, 1);
  animation-fill-mode: both;
}}
</style>
"""

    html = [
        f"""{style_block}<style>
.table-wrap-{nonce} {{
  overflow-x: auto;
  overflow-y: auto;
  max-height: 480px;
  border: 1px solid rgba(128, 128, 128, 0.2);
  border-radius: 8px;
  margin-top: 0.5rem;
  margin-bottom: 1rem;
}}

.draw-table-{nonce} {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.85rem;
  font-family: inherit;
  text-align: left;
}}

.draw-table-{nonce} th {{
  position: sticky;
  top: 0;
  z-index: 2;
  background-color: #1e293b;
  color: #f8fafc;
  padding: 8px 10px;
  font-weight: 600;
  border-bottom: 2px solid rgba(128, 128, 128, 0.3);
  white-space: nowrap;
}}

.draw-table-{nonce} td {{
  padding: 6px 10px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  white-space: nowrap;
}}

.draw-table-{nonce} tr:hover td {{
  background-color: rgba(128, 128, 128, 0.08);
}}

.team-name {{
  font-weight: 600;
}}

.pot-pill {{
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #111827;
}}
</style>
<div class="table-wrap-{nonce}">
<table class="draw-table-{nonce}">
  <thead>
    <tr>
"""
    ]
    for col in cols:
        html.append(f"      <th>{col}</th>\n")
    html.append("    </tr>\n  </thead>\n  <tbody>\n")

    for r, (_, row) in enumerate(df.iterrows()):
        html.append("    <tr>\n")
        for c, col in enumerate(cols):
            val = row[col]
            delay = round(r * 0.035 + c * 0.025, 3)
            if col in team_cols:
                content = f'<span class="team-name">{val}</span>'
            elif col == "Pot":
                pot_color = POT_COLORS.get(str(val), "#e2e8f0")
                content = f'<span class="pot-pill" style="background-color: {pot_color};">Pot {val}</span>'
            else:
                content = f"{val}"

            if animate:
                html.append(f'      <td class="anim-cell-{nonce}" style="animation-delay: {delay}s;">{content}</td>\n')
            else:
                html.append(f'      <td>{content}</td>\n')
        html.append("    </tr>\n")

    html.append("  </tbody>\n</table>\n</div>\n")
    return "".join(html)



def aggregate_strength(draws: list[dict]) -> pd.DataFrame:
    rows = [
        {"Club": t["club"], "Pot": t["pot"], "elo": t["elo_sum"], "uefa": t["uefa_sum"]}
        for d in draws
        for t in d["teams"]
    ]
    df = pd.DataFrame(rows)
    out = df.groupby(["Club", "Pot"], sort=False).agg(
        elo_mean=("elo", "mean"),
        elo_std=("elo", "std"),
        uefa_mean=("uefa", "mean"),
        uefa_std=("uefa", "std"),
    ).reset_index()
    return out.fillna({"elo_std": 0.0, "uefa_std": 0.0})


def strength_chart(agg: pd.DataFrame, metric: str, title: str, show_error: bool) -> go.Figure:
    fig = go.Figure()
    for pot, color in POT_COLORS.items():
        sub = agg[agg["Pot"] == pot]
        fig.add_bar(
            x=sub["Club"],
            y=sub[f"{metric}_mean"],
            name=f"Pot {pot}",
            marker_color=color,
            error_y=dict(type="data", array=sub[f"{metric}_std"], visible=show_error),
            hovertemplate="%{x}<br>%{y:,.1f}<extra>Pot " + pot + "</extra>",
        )
    lo = agg[f"{metric}_mean"].min()
    hi = agg[f"{metric}_mean"].max()
    fig.update_layout(
        title=title,
        barmode="group",
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=1.1, x=0),
        xaxis_tickangle=-60,
        yaxis=dict(range=[lo - 0.15 * (hi - lo), hi + 0.08 * (hi - lo)], title=None),
    )
    return fig


# ----------------------------------------------------------------------------- Setup State
leagues = get_leagues()
catalog = get_precomputed_catalog()
precomputed_draws = catalog.get("draws", {})
precomputed_multi = catalog.get("multi_draws", {})

health = backend_health()
backend_ready = bool(health and health.get("ready"))

st.session_state.setdefault("result", None)
st.session_state.setdefault("source_label", "")
st.session_state.setdefault("draw_nonce", 0)
st.session_state.setdefault("just_drawn", False)

# ----------------------------------------------------------------------------- Sidebar
with st.sidebar:
    st.header("Draw settings")

    # Mode selection
    mode_options = ["Pre-computed library"]
    if backend_ready:
        mode_options.append("Live Julia solver")

    selected_mode = st.radio(
        "Simulation mode",
        mode_options,
        index=0,
        help="Pre-computed library provides verified draw results with true JuMP/SCIP computing times.",
    )

    if not backend_ready:
        st.caption("Offline mode: using pre-computed draws library.")

    if selected_mode == "Pre-computed library":
        league_key = st.selectbox(
            "League",
            list(leagues),
            format_func=lambda k: leagues[k]["label"],
            key="pre_league",
        )

        sample_type = st.radio(
            "Sample type",
            ["Single draw", "10-draw sample (Strength Analysis)"],
            index=0,
            help="Single draw shows full fixtures and logs. 10-draw sample aggregates opponent strength distributions.",
        )

        if sample_type == "Single draw":
            available_seeds = sorted(
                [
                    v["seed"]
                    for k, v in precomputed_draws.items()
                    if v.get("league") == league_key
                ]
            )
            if not available_seeds:
                available_seeds = [1]

            col_seed, col_rnd = st.columns([2, 1])
            with col_seed:
                selected_seed = st.selectbox(
                    "Seed",
                    available_seeds,
                    index=0,
                    key="pre_seed_select",
                    help="Select a seed from the pre-computed catalog.",
                )
            with col_rnd:
                st.write("")
                st.write("")
                if st.button("Random", help="Select a random pre-computed seed"):
                    selected_seed = random.choice(available_seeds)
                    st.session_state["pre_seed_select"] = selected_seed

            draw_btn = st.button("Draw", type="primary", width="stretch")
            if draw_btn:
                key = f"{league_key}_{selected_seed}"
                if key in precomputed_draws:
                    st.session_state["result"] = precomputed_draws[key]
                    st.session_state["draw_nonce"] = st.session_state.get("draw_nonce", 0) + 1
                    st.session_state["just_drawn"] = True
                    st.session_state["source_label"] = (
                        f"Pre-computed draw (seed {selected_seed}, true compute time: "
                        f"{precomputed_draws[key]['seconds']:.2f} s)"
                    )
        else:
            multi_key = f"{league_key}_10"
            draw_multi_btn = st.button("Draw", type="primary", width="stretch")
            if draw_multi_btn:
                if multi_key in precomputed_multi:
                    st.session_state["result"] = precomputed_multi[multi_key]
                    st.session_state["draw_nonce"] = st.session_state.get("draw_nonce", 0) + 1
                    st.session_state["just_drawn"] = True
                    st.session_state["source_label"] = (
                        f"Pre-computed 10-draw sample (seed 2024, true compute time: "
                        f"{precomputed_multi[multi_key]['seconds']:.2f} s)"
                    )

    else:
        # Live Julia Solver Form
        st.caption("Backend ready: Julia runtime running JuMP and SCIP.")
        randomize = st.checkbox("New random seed on every run", value=True)
        with st.form("live_draw_form"):
            live_league = st.selectbox(
                "League",
                list(leagues),
                format_func=lambda k: leagues[k]["label"],
            )
            live_order = st.radio(
                "Draw order",
                list(ORDER_LABELS),
                format_func=ORDER_LABELS.get,
                help="Pot-by-pot mirrors the official procedure; fully random shuffles teams and opponent pots.",
            )
            live_selection = st.radio(
                "Selection algorithm",
                list(SELECTION_LABELS),
                format_func=SELECTION_LABELS.get,
                help="Rejection sampling draws rapidly (~1.8s). Exhaustive solves every candidate (~20-40s).",
            )
            live_n = st.slider("Number of draws", 1, 25, 1)
            live_seed_input = st.number_input(
                "Seed",
                1,
                MAX_SEED,
                random.randint(1, MAX_SEED),
                disabled=randomize,
            )
            run_live = st.form_submit_button("Draw", type="primary", width="stretch")

        if run_live:
            actual_seed = random.randint(1, MAX_SEED) if randomize else int(live_seed_input)
            try:
                with st.spinner("Solving draw with JuMP and SCIP..."):
                    res = fetch_live_draw(live_league, live_order, live_selection, live_n, actual_seed)
                st.session_state["result"] = res
                st.session_state["draw_nonce"] = st.session_state.get("draw_nonce", 0) + 1
                st.session_state["just_drawn"] = True
                st.session_state["source_label"] = (
                    f"Live solver result (seed {actual_seed}, compute time: {res['seconds']:.2f} s)"
                )
            except ApiError as exc:
                st.error(str(exc))


# ----------------------------------------------------------------------------- Main Canvas
result = st.session_state.get("result")

tab_result, tab_fair, tab_log, tab_pots = st.tabs(["Results", "Strength Analysis", "Draw Log", "Pots"])

with tab_pots:
    for key, lg in leagues.items():
        if result and key != result.get("league"):
            continue
        st.subheader(lg["label"])
        cols = st.columns(4)
        for col, pot, label in zip(cols, lg["pots"], "ABCD"):
            with col:
                st.caption(f"Pot {label}")
                st.dataframe(
                    pd.DataFrame(pot)[["club", "nationality", "elo", "uefa"]].rename(
                        columns={"club": "Club", "nationality": "Nation", "elo": "Elo", "uefa": "UEFA"}
                    ),
                    hide_index=True,
                    width="stretch",
                )

if result is None:
    with tab_result:
        st.info("Pick settings in the sidebar and click Draw to simulate.")
    for tab in (tab_fair, tab_log):
        with tab:
            st.caption("No draw conducted yet. Click Draw in the sidebar.")
    st.stop()

draws = result["draws"]
n = len(draws)
total_calls = sum(d["solver_calls"] for d in draws)
violations = sum(len(d["violations"]) for d in draws)

with tab_result:
    if st.session_state.get("source_label"):
        st.caption(st.session_state["source_label"])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Draws", n)
    k2.metric("True compute time", f"{result['seconds']:.2f} s")
    k3.metric("Solver calls / draw", f"{total_calls / n:.0f}")
    k4.metric("Rule check", "Passed" if violations == 0 else f"{violations} violations")
    k5.metric("Seed", result["seed"])

    idx = st.slider("Show draw #", 1, n, 1, key="draw_idx") - 1 if n > 1 else 0
    draw = draws[idx]
    if draw["violations"]:
        st.error("Rule violations: " + "; ".join(draw["violations"]))

    df = teams_frame(draw)
    should_animate = st.session_state.get("just_drawn", False)
    nonce = st.session_state.get("draw_nonce", 0)
    st.markdown(render_animated_results_table(df, nonce=nonce, animate=should_animate), unsafe_allow_html=True)
    st.session_state["just_drawn"] = False
    c1, c2 = st.columns([1, 1])
    c1.download_button(
        "Download fixtures (CSV)",
        fixtures_frame(draw).to_csv(index=False),
        file_name=f"fixtures_{result['league']}_{draw['seed']}.csv",
        mime="text/csv",
    )
    c2.download_button(
        "Download team table (CSV)",
        df.to_csv(index=False),
        file_name=f"teams_{result['league']}_{draw['seed']}.csv",
        mime="text/csv",
    )

    st.subheader("Club schedule")
    club = st.selectbox("Club", [t["club"] for t in draw["teams"]], key="club")
    st.dataframe(team_schedule(draw, club), hide_index=True, width="stretch")

with tab_fair:
    agg = aggregate_strength(draws)
    show_err = n > 1
    st.caption(
        f"Sum of opponents strength per club{f' (mean and std over {n} draws)' if show_err else ''}."
    )
    toughest = agg.loc[agg["elo_mean"].idxmax()]
    easiest = agg.loc[agg["elo_mean"].idxmin()]
    m1, m2, m3 = st.columns(3)
    m1.metric("Highest schedule Elo", toughest["Club"], f"{toughest['elo_mean']:,.0f}", delta_color="off")
    m2.metric("Lowest schedule Elo", easiest["Club"], f"{easiest['elo_mean']:,.0f}", delta_color="off")
    m3.metric("Elo difference", f"{toughest['elo_mean'] - easiest['elo_mean']:,.0f}")
    st.plotly_chart(strength_chart(agg, "elo", "Opponent Elo Sum", show_err), width="stretch")
    st.plotly_chart(strength_chart(agg, "uefa", "Opponent UEFA Coefficient Sum", show_err), width="stretch")

with tab_log:
    d = draws[st.session_state.get("draw_idx", 1) - 1] if n > 1 else draws[0]
    st.caption("Step-by-step assignments for each team and pot.")
    log = pd.DataFrame(
        {
            "Step": range(1, len(d["steps"]) + 1),
            "Club": [s["team"] for s in d["steps"]],
            "Opponent pot": [s["pot"] for s in d["steps"]],
            "Home vs": [s["home_vs"] for s in d["steps"]],
            "Away at": [s["away_vs"] for s in d["steps"]],
            "Admissible couples": [s["options"] for s in d["steps"]],
            "Origin": ["forced by earlier step" if s["fixed"] else "drawn" for s in d["steps"]],
        }
    )
    only_drawn = st.toggle("Hide steps forced by earlier draws", value=False)
    st.dataframe(
        log[log["Origin"] == "drawn"] if only_drawn else log,
        hide_index=True,
        width="stretch",
        height=480,
    )
