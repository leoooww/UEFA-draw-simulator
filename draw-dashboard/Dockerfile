# syntax=docker/dockerfile:1.7
# Multi-stage build: Julia deps are instantiated + precompiled in a throw-away stage,
# then Julia (binary + depot) is copied next to Python in a slim runtime image.

ARG JULIA_VERSION=1.11
ARG PYTHON_VERSION=3.12

# ---------- stage 1: Julia packages, precompiled ----------
FROM julia:${JULIA_VERSION}-bookworm AS julia-build
ENV JULIA_DEPOT_PATH=/opt/julia-depot \
    JULIA_PKG_PRECOMPILE_AUTO=0
WORKDIR /app/julia
COPY julia/Project.toml julia/Manifest.toml ./
# dependencies first (cached layer) ...
RUN julia --project=. -e 'using Pkg; Pkg.instantiate()'
COPY julia/src ./src
# ... then compile our package + exercise the solver once so artifacts/JIT caches exist
RUN julia --project=. -e 'using Pkg; Pkg.precompile(); using DrawService, SCIP; println("precompiled OK")'

# ---------- stage 2: Python deps ----------
FROM python:${PYTHON_VERSION}-slim-bookworm AS py-build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- stage 3: runtime ----------
# julia:*-bookworm and python:*-slim-bookworm share the same glibc, so the Julia tree is portable.
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=julia-build /usr/local/julia /usr/local/julia
COPY --from=julia-build --chown=1000:1000 /opt/julia-depot /opt/julia-depot
COPY --from=py-build /install /usr/local

ENV PATH="/usr/local/julia/bin:${PATH}" \
    JULIA_DEPOT_PATH=/opt/julia-depot \
    JULIA_PKG_PRECOMPILE_AUTO=0 \
    JULIA_API_HOST=127.0.0.1 \
    JULIA_API_PORT=8080 \
    JULIA_API_URL=http://127.0.0.1:8080 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --chown=app:app julia ./julia
COPY --chown=app:app app.py start.sh ./
RUN chmod +x start.sh

USER app
# Cloud Run injects $PORT, Hugging Face Spaces uses 7860, local default is 8501.
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD curl -fs "http://127.0.0.1:${PORT:-8501}/_stcore/health" || exit 1
CMD ["./start.sh"]
