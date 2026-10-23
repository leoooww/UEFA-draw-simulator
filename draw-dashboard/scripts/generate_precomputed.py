#!/usr/bin/env python3
"""Precompute and store UEFA draw simulations with real computing times."""

import json
from pathlib import Path
import sys
import time
import requests

API_URL = "http://127.0.0.1:8080"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "precomputed_draws.json"

def check_backend():
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        return r.ok and r.json().get("ready", False)
    except Exception:
        return False

def compute_draw(league: str, seed: int, order: str = "by_pot", selection: str = "rejection", n_draws: int = 1):
    payload = {
        "league": league,
        "order": order,
        "selection": selection,
        "n_draws": n_draws,
        "seed": seed,
    }
    t0 = time.perf_counter()
    resp = requests.post(f"{API_URL}/api/draw", json=payload, timeout=300)
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    data = resp.json()
    # Ensure seconds accurately reflects the real compute time
    if "seconds" not in data or data["seconds"] <= 0:
        data["seconds"] = round(elapsed, 3)
    return data

def main():
    if not check_backend():
        print(f"Error: Julia service not reachable at {API_URL}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    catalog = {
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "description": "Pre-computed UEFA draw simulations with real JuMP/SCIP computing times.",
        },
        "draws": {},
        "multi_draws": {},
    }

    # Seeds to compute for single draws
    cl_seeds = list(range(1, 26)) + [42, 99, 100, 777, 2024, 2025]
    el_seeds = list(range(1, 16)) + [42, 100, 2024, 2025]

    print(f"Computing {len(cl_seeds)} Champions League draws...")
    for s in cl_seeds:
        key = f"CHAMPIONS_LEAGUE_{s}"
        print(f"  [CL] Seed {s}...", end=" ", flush=True)
        res = compute_draw("CHAMPIONS_LEAGUE", s)
        print(f"done in {res['seconds']:.2f} s ({res['draws'][0]['solver_calls']} solver calls)")
        catalog["draws"][key] = res

    print(f"Computing {len(el_seeds)} Europa League draws...")
    for s in el_seeds:
        key = f"EUROPA_LEAGUE_{s}"
        print(f"  [EL] Seed {s}...", end=" ", flush=True)
        res = compute_draw("EUROPA_LEAGUE", s)
        print(f"done in {res['seconds']:.2f} s ({res['draws'][0]['solver_calls']} solver calls)")
        catalog["draws"][key] = res

    # Also compute 1 multi-draw each for statistical schedule strength tab
    print("Computing Champions League 10-draw sample for Strength Analysis tab...", flush=True)
    res_cl_multi = compute_draw("CHAMPIONS_LEAGUE", seed=2024, n_draws=10)
    catalog["multi_draws"]["CHAMPIONS_LEAGUE_10"] = res_cl_multi

    print("Computing Europa League 10-draw sample for Strength Analysis tab...", flush=True)
    res_el_multi = compute_draw("EUROPA_LEAGUE", seed=2024, n_draws=10)
    catalog["multi_draws"]["EUROPA_LEAGUE_10"] = res_el_multi

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, separators=(",", ":"))

    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"Successfully saved {len(catalog['draws'])} draws to {OUTPUT_FILE} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
