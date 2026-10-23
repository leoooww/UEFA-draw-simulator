# UEFA League-Phase Draw Dashboard

Streamlit frontend for the Julia draw simulator in [`../draw-backend/draw_matchups_first.jl`](../draw-backend/draw_matchups_first.jl).

Architecture:
```
Streamlit (app.py, :8501) ---> Pre-computed library (data/precomputed_draws.json)
                         \---> Live Oxygen.jl service (julia/server.jl, :8080) [optional]
```

The application runs in two complementary modes:
1. Pre-computed library (default, offline-ready): Instant browsing of 50 verified MILP draws across Champions League and Europa League, showing exact true JuMP/SCIP computing times recorded during simulation. Runs standalone with pure Python (ready for Streamlit Community Cloud).
2. Live solver mode: When the local or containerized Julia service is running on port 8080, allows dynamic draws with arbitrary seeds and multi-draw parameters.

## Run

### Streamlit only (instant offline mode)

```bash
cd draw-dashboard
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

### Full stack (Docker)

```bash
docker compose up --build
```

Access at `http://localhost:8501`.

### Local

```bash
julia --project=julia -e 'using Pkg; Pkg.instantiate()'
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./start.sh
```

## Parameters

| Streamlit control | API field | Original script variable |
|---|---|---|
| League | `league` | `LEAGUE` |
| Draw order | `order` | `uefa_draw*` vs `uefa_draw_randomized` |
| Selection method | `selection` | `uefa_draw_with_rejection` vs `true_admissible_matches` |
| Number of draws | `n_draws` (<= `MAX_DRAWS`, default 25) | `NB_DRAWS` |
| Seed | `seed` | Random seed for reproducibility |

### API endpoints

```
GET  /health          -> {"status": "ok", "ready": bool, "threads": int}
GET  /api/leagues     -> pot assignments, Elo ratings, UEFA coefficients
POST /api/draw        -> payload: {"league", "order", "selection", "n_draws", "seed"}
```

Status codes:
- 200: success
- 400: malformed JSON request
- 422: validation error
- 500: solver error

## Changes from original script

- Encapsulated logic in `julia/src/DrawService.jl` without global state, terminal prompts, or file writes.
- Uses SCIP instead of Gurobi to run without external license keys.
- Uses a 2D formulation (`x[i, j]`) since matchday index `t` was unconstrained in the original 3D formulation.
- Computes opponent Elo and UEFA metrics across all 8 assigned opponents.
- Includes independent post-draw validation function (`validate_draw`).

## Tests

```bash
julia --project=julia julia/test/runtests.jl
.venv/bin/pip install pytest && .venv/bin/python -m pytest tests
```
