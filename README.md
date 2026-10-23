# UEFA Draw Simulator

A simulation platform for the UEFA 36-team single-league phase draw, solving complex scheduling and nationality constraints using Mixed-Integer Linear Programming (MILP).

## Repository Structure

- **`draw-dashboard/`**: Container-ready Streamlit web application powered by a persistent Julia microservice (`Oxygen.jl` + `JuMP` / `SCIP`). Includes complete Docker configuration for deployment on Cloud Run, Hugging Face Spaces, or local machines.
- **`draw-backend/`**: Original Julia algorithmic logic (`draw_matchups_first.jl`) and FastAPI WebSocket streaming server.
- **`champions-league-draw/`**: Angular frontend application interface.

## Quick Start (Dashboard)

Run locally with Docker:
```bash
cd draw-dashboard
docker compose up --build
```
Access the application at `http://localhost:8501`.
