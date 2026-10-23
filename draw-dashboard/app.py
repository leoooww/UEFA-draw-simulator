"""Streamlit dashboard for the UEFA draw simulator."""

from __future__ import annotations

import os
import random
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

st.set_page_config(page_title="UEFA Draw Simulator", layout="wide")

st.title("UEFA Draw Simulator")
st.caption("League-phase draw simulation for 36 teams across 4 pots using Julia (JuMP and SCIP).")


# ----------------------------------------------------------------------------- API client
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


@st.cache_data(ttl=600, show_spinner=False)
def get_leagues() -> dict[str, dict]:
    return {league["key"]: league for league in _call("GET", "/api/leagues", timeout=30)}


@st.cache_data(max_entries=64, show_spinner=False)
def get_draws(league: str, order: str, selection: str, n_draws: int, seed: int) -> dict:
    """Cached on the full parameter set: identical inputs (incl. seed) never hit Julia twice."""
    payload = {"league": league, "order": order, "selection": selection, "n_draws": n_draws, "seed": seed}
    return _call("POST", "/api/draw", json=payload)


def backend_health() -> dict | None:
    try:
        return requests.get(f"{API_URL}/health", timeout=2).json()
    except (requests.RequestException, ValueError):
        return None


# ----------------------------------------------------------------------------- data shaping
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
                {"Pot": o["pot"], "Venue": venue, "Opponent": opp, "Nationality": m["nationality"],
                 "Elo": m["elo"], "UEFA coeff.": m["uefa"]}
            )
    return pd.DataFrame(rows)


def aggregate_strength(draws: list[dict]) -> pd.DataFrame:
    rows = [
        {"Club": t["club"], "Pot": t["pot"], "elo": t["elo_sum"], "uefa": t["uefa_sum"]}
        for d in draws
        for t in d["teams"]
    ]
    df = pd.DataFrame(rows)
    out = df.groupby(["Club", "Pot"], sort=False).agg(
        elo_mean=("elo", "mean"), elo_std=("elo", "std"),
        uefa_mean=("uefa", "mean"), uefa_std=("uefa", "std"),
    ).reset_index()
    return out.fillna({"elo_std": 0.0, "uefa_std": 0.0})


def strength_chart(agg: pd.DataFrame, metric: str, title: str, show_error: bool) -> go.Figure:
    fig = go.Figure()
    for pot, color in POT_COLORS.items():
        sub = agg[agg["Pot"] == pot]
        fig.add_bar(
            x=sub["Club"], y=sub[f"{metric}_mean"], name=f"Pot {pot}", marker_color=color,
            error_y=dict(type="data", array=sub[f"{metric}_std"], visible=show_error),
            hovertemplate="%{x}<br>%{y:,.1f}<extra>Pot " + pot + "</extra>",
        )
    lo = agg[f"{metric}_mean"].min()
    hi = agg[f"{metric}_mean"].max()
    fig.update_layout(
        title=title, barmode="group", height=420, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=1.1, x=0), xaxis_tickangle=-60,
        yaxis=dict(range=[lo - 0.15 * (hi - lo), hi + 0.08 * (hi - lo)], title=None),
    )
    return fig


# ----------------------------------------------------------------------------- backend gate
health = backend_health()
if health is None:
    st.error(f"Julia service unreachable at `{API_URL}`.")
    st.caption("Start it with `julia --project=julia -t auto julia/server.jl` or `docker compose up`.")
    if st.button("Retry"):
        st.rerun()
    st.stop()

try:
    leagues = get_leagues()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

# ----------------------------------------------------------------------------- sidebar
st.session_state.setdefault("seed", random.randint(1, MAX_SEED))
st.session_state.setdefault("params", None)

with st.sidebar:
    st.header("Draw settings")
    st.caption("Backend ready" if health.get("ready") else "Backend warming up")
    randomize = st.checkbox("New random seed on every run", value=True)
    with st.form("draw_form"):
        league = st.selectbox("League", list(leagues), format_func=lambda k: leagues[k]["label"])
        order = st.radio("Draw order", list(ORDER_LABELS), format_func=ORDER_LABELS.get,
                         help="Pot-by-pot mirrors the official procedure; fully random shuffles teams and opponent pots.")
        selection = st.radio("Selection algorithm", list(SELECTION_LABELS), format_func=SELECTION_LABELS.get,
                             help="Both sample uniformly among admissible couples. Exhaustive solves every candidate "
                                  "(slower, ~20-40s per draw) and reports how many options each step had.")
        n_draws = st.slider("Number of draws", 1, 25, 1,
                            help="Run multiple draws to compare schedule strength across clubs.")
        seed_input = st.number_input("Seed", 1, MAX_SEED, st.session_state["seed"], disabled=randomize)
        submitted = st.form_submit_button("Run draw", type="primary", width="stretch")

if submitted:
    seed = random.randint(1, MAX_SEED) if randomize else int(seed_input)
    st.session_state["seed"] = seed
    st.session_state["params"] = dict(league=league, order=order, selection=selection, n_draws=n_draws, seed=seed)

params = st.session_state["params"]

# ----------------------------------------------------------------------------- main canvas
tab_result, tab_fair, tab_log, tab_pots = st.tabs(["Results", "Strength Analysis", "Draw Log", "Pots"])

with tab_pots:
    for key, lg in leagues.items():
        if params and key != params["league"]:
            continue
        st.subheader(lg["label"])
        cols = st.columns(4)
        for col, pot, label in zip(cols, lg["pots"], "ABCD"):
            with col:
                st.caption(f"Pot {label}")
                st.dataframe(
                    pd.DataFrame(pot)[["club", "nationality", "elo", "uefa"]].rename(
                        columns={"club": "Club", "nationality": "Nation", "elo": "Elo", "uefa": "UEFA"}),
                    hide_index=True, width="stretch")

if params is None:
    with tab_result:
        st.info("Pick settings in the sidebar and click Run draw.")
    for tab in (tab_fair, tab_log):
        with tab:
            st.caption("Run a draw first.")
    st.stop()

try:
    with st.spinner("Running draw simulation..."):
        result = get_draws(**params)
except ApiError as exc:
    for tab in (tab_result, tab_fair, tab_log):
        with tab:
            st.error(str(exc))
    st.stop()

draws = result["draws"]
n = len(draws)
total_calls = sum(d["solver_calls"] for d in draws)
violations = sum(len(d["violations"]) for d in draws)

with tab_result:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Draws", n)
    k2.metric("Total time", f"{result['seconds']:.1f} s")
    k3.metric("Solver calls / draw", f"{total_calls / n:.0f}")
    k4.metric("Rule check", "Passed" if violations == 0 else f"{violations} violations")
    k5.metric("Seed", result["seed"])

    idx = st.slider("Show draw #", 1, n, 1, key="draw_idx") - 1 if n > 1 else 0
    draw = draws[idx]
    if draw["violations"]:
        st.error("Rule violations: " + "; ".join(draw["violations"]))

    df = teams_frame(draw)
    st.dataframe(df, hide_index=True, width="stretch", height=420)
    c1, c2 = st.columns([1, 1])
    c1.download_button("Download fixtures (CSV)", fixtures_frame(draw).to_csv(index=False),
                       file_name=f"fixtures_{result['league']}_{draw['seed']}.csv", mime="text/csv")
    c2.download_button("Download team table (CSV)", df.to_csv(index=False),
                       file_name=f"teams_{result['league']}_{draw['seed']}.csv", mime="text/csv")

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
    st.dataframe(log[log["Origin"] == "drawn"] if only_drawn else log, hide_index=True,
                 width="stretch", height=480)
