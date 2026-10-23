# TDLOG Project - Simulation of the 2024-25 Champions League League Phase Draw

## Project Overview

This project simulates the 2024-25 UEFA Champions League single-league phase draw, solving scheduling and nationality constraints using Mixed-Integer Linear Programming (MILP).

The original draw simulation algorithm is based on: [https://github.com/JulienGuyon/UEFA-league-phase-draw](https://github.com/JulienGuyon/UEFA-league-phase-draw).

---

## Important Solver Information (Original Backend)

The original drawing code in `draw-backend/` uses the **Gurobi** solver by default. If you do not have a Gurobi license, you can switch to the free, open-source **SCIP** solver.

In `draw-backend/draw_matchups_first.jl`, change:
```julia
####################################### CONFIG VARIABLES #######################################
const SOLVER = "Gurobi" # Alternative: "SCIP"
```
to:
```julia
####################################### CONFIG VARIABLES #######################################
const SOLVER = "SCIP"
```
*Note: solving with SCIP may be slower than Gurobi.*

---

## Quick Start: Run the Web Dashboard Locally

The web dashboard is located in `draw-dashboard/` and can run either in lightweight standalone mode (using the precomputed simulation catalog) or with a live Julia solver.

### Option A: Standalone Streamlit App (Fastest, Python only)
No Julia or Docker required. Runs instantly with the verified 50-draw MILP catalog and recorded true compute times:

```bash
# 1. Navigate to the dashboard directory from the project root
cd draw-dashboard

# 2. Activate the virtual environment (or create it if needed)
source .venv/bin/activate
# If the venv does not exist yet: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 3. Launch the dashboard
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

### Option B: Full Stack with Live Julia Solver (Optional)
Requires Julia installed on your machine:

```bash
cd draw-dashboard
julia --project=julia -e 'using Pkg; Pkg.instantiate()'
./start.sh
```

---

### Option C: Docker (Optional)
Requires Docker Desktop installed and running:

```bash
cd draw-dashboard
docker compose up --build
```
Access at `http://localhost:8501`.

---

## Project Structure

### 1. Interactive Streamlit Dashboard (`draw-dashboard/`)
The web simulator featuring animated draw tables, team crests, pot breakdown, and schedule Elo strength analysis. Contains:
- `app.py`: Streamlit frontend application.
- `data/`: League assignments and pre-computed draw catalogs.
- `assets/logos/`: Official UEFA club crests.
- `julia/`: Persistent `Oxygen.jl` microservice for live MILP solving.

### 2. Angular Frontend (`champions-league-draw/`)
Web interface built with Angular.

To start the local development server:
```bash
cd champions-league-draw
npm install
ng serve
```
Once running, navigate to `http://localhost:4200/`.

### 3. Original WebSocket Backend (`draw-backend/`)
FastAPI backend that streams the CLI Julia draw process via WebSockets.

To start:
```bash
cd draw-backend
uvicorn main:app --reload
```
Ensure the URL where the backend runs (e.g., `http://127.0.0.1:8000`) matches the URL configured in `champions-league-draw/src/app/terminal.service.ts`.

---

## Required Packages

### Original Backend (Python)
- `fastapi`
- `websockets`
- `uvicorn`
- `pexpect`

### Original Backend (Julia)
- `JuMP`
- `SCIP`
- `Gurobi` (optional, licensed)
- `CSV`
- `DataFrames`
- `Random`

### Dashboard (`draw-dashboard/`)
- Python: `streamlit`, `requests`, `pandas`, `plotly`
- Julia: `JuMP`, `SCIP`, `Oxygen`, `HTTP`, `JSON3`, `Random`

---

## Authors

- Léo Wang
- Matthieu Mayaud
- Alexandre Tranié

**Supervised by:**
- Étienne Polack
- Julien Guyon
