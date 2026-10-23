#!/usr/bin/env bash
# Starts the Julia API (background) and the Streamlit frontend (foreground).
# Works locally, in Docker, on Cloud Run ($PORT) and on Hugging Face Spaces.
set -euo pipefail
cd "$(dirname "$0")"

export JULIA_API_HOST="${JULIA_API_HOST:-127.0.0.1}"
export JULIA_API_PORT="${JULIA_API_PORT:-8080}"
export JULIA_API_URL="${JULIA_API_URL:-http://127.0.0.1:${JULIA_API_PORT}}"
STREAMLIT_PORT="${PORT:-${STREAMLIT_PORT:-8501}}"
PY="${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"

julia --project=julia -t "${JULIA_NUM_THREADS:-auto}" julia/server.jl &
JULIA_PID=$!
trap 'kill "$JULIA_PID" 2>/dev/null || true' EXIT INT TERM

echo "Waiting for the Julia API on ${JULIA_API_URL} ..."
for _ in $(seq 1 120); do
  if curl -fs "${JULIA_API_URL}/health" >/dev/null 2>&1; then break; fi
  kill -0 "$JULIA_PID" 2>/dev/null || { echo "Julia API exited early" >&2; exit 1; }
  sleep 1
done

# No `exec`: the shell must stay alive so the trap can stop Julia.
"$PY" -m streamlit run app.py \
  --server.port "${STREAMLIT_PORT}" \
  --server.address 0.0.0.0 \
  --server.headless true
