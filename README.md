# Clef System 1 Pac-Man Benchmark

An interactive, high-fidelity visual benchmark demonstration showcasing the **Clef / Jev System One decision architecture** navigating Pac-Man through a classic 19×21 arcade maze in real time.

```
       Stage 1                                     Stage 2
 ┌─────────────────┐    Cache Hit (<1ms)     ┌─────────────────┐
 │   Grid State    │ ──────────────────────► │ Executed Action │
 └────────┬────────┘                         └─────────────────┘
          │                                           ▲
          │ Cache Miss                                │
          ▼                                           │
 ┌─────────────────┐      Inference (~400ms)          │
 │ Fast-Path Hash  │ ─────────────────────────────────┘
 └────────┬────────┘
          ▼
 ┌──────────────────────────────────────────┐
 │ Cloudflare Workers AI: Clef-Flash (9B)  │
 └──────────────────────────────────────────┘
```

---

## Architecture Overview

At each tick, Pac-Man evaluates candidate moves through a two-stage decision pipeline:

1. **Environmental State & Criteria Formulation:**
   - Evaluates open neighboring corridor tiles (North, South, East, West) and tunnel wrap-arounds (Row 9).
   - Enforces anti-oscillation forward progress so Pac-Man does not vibrate between two cells.
   - Computes BFS shortest-path distance to the nearest remaining pellet and scans for ghost hazards.
   - Builds typed choice criteria:
     - `right`: *"Step right to (3, 19); advance towards nearest pellet (5 steps away); continue forward in current corridor momentum"*
     - `left`: *"Step left to (1, 19); advance towards nearest pellet (7 steps away)"*

2. **Stage 1: Fast-Path Cache ($< 1\text{ ms}$):**
   - Hashes the semantic local board state (agent position, direction, remaining pellets, ghost relative coordinates).
   - If an identical situation has been resolved before, the cached choice and confidence are returned instantly ($< 0.1\text{ ms}$), completely bypassing neural inference.

3. **Stage 2: Live Clef-Flash Inference ($\sim 400\text{ ms}$):**
   - On a cache miss, queries `@cf/cloudflare/clef-flash` (or `@cf/cloudflare/clef`) via Cloudflare Workers AI REST API.
   - Returns candidate probabilities and confidence metrics (`confidence >= 0.70`).
   - Automatically stores the decision into the Fast-Path Cache for subsequent visits.

---

## Features

- 🎮 **19×21 Arcade Simulation:** Authentic grid layout with horizontal wrap-around tunnel, 160+ pellets, and patrol ghosts (*Pinky*, *Blinky*, *Clyde*).
- ⚡ **Dual Decision Backends:**
  - **Cloudflare Clef-Flash:** Live neural inference via Cloudflare Workers AI.
  - **Local Heuristic Engine:** Offline, ultra-fast simulated decision model (no API keys required).
- 🧠 **Stage 1 Fast-Path Cache Telemetry:** Live tracking of cache hits, misses, hit rate percentage, and avoided neural latency.
- 🔍 **Real-Time JSON Inspector:** Live syntax-highlighted display of `answers: { move: { choice, probabilities, confidence } }` matching benchmark specifications.
- ⌨️ **Keyboard & Interactive Controls:**
  - <kbd>Space</kbd> : Toggle Auto-Play / Pause
  - <kbd>S</kbd> : Execute single step
  - <kbd>R</kbd> : Reset board to starting position (retains learned cache)
  - <kbd>C</kbd> : Clear Fast-Path Cache

---

## Quick Start

### 1. Prerequisites

- Python 3.9+ installed.

### 2. Installation

Clone or open the repository directory:

```powershell
pip install -r requirements.txt
```

### 3. (Optional) Cloudflare Workers AI Configuration

To run live inference with `@cf/cloudflare/clef-flash`:

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Fill in your `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (Workers AI Read permissions).
3. If no Cloudflare credentials are provided, the benchmark automatically falls back to the high-speed local heuristic engine.

### 4. Launch the Server

Run with Python:

```powershell
python server.py
```

Or using `uvicorn`:

```powershell
uvicorn server:app --port 8080 --reload
```

Open your browser at:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the interactive visualizer HTML application |
| `GET` | `/api/state` | Returns complete grid state, positions, pellets, score, and cache telemetry |
| `POST` | `/api/step` | Executes a single decision step (supports `?backend=cloudflare` or `?backend=mock`) |
| `POST` | `/api/reset` | Resets Pac-Man and pellets to start; preserves learned Fast-Path Cache |
| `POST` | `/api/cache/clear` | Flushes the Fast-Path Cache and resets telemetry counters |
| `GET` | `/api/cache/stats` | Retrieves cache performance statistics (hits, misses, hit rate, latency saved) |
| `GET` | `/api/backend` | Retrieves the currently active decision backend |
| `POST` | `/api/backend` | Sets active backend (`{"backend": "cloudflare"}` or `{"backend": "mock"}`) |

---

## Running the Test Suite

The project includes unit and integration tests covering the simulation environment, movement constraints, collision rules, Fast-Path Cache, and REST endpoints:

```powershell
pytest -v
```

---

## Project Structure

```
maze-jev-style/
├── .env.example         # Template configuration for Cloudflare Workers AI
├── .gitignore           # Git ignore file for Python, secrets, and caches
├── pyproject.toml       # PEP 621 package metadata and pytest settings
├── requirements.txt     # Python runtime dependencies
├── README.md            # Benchmark documentation and setup instructions
├── maze_engine.py       # Pac-Man environment, BFS pathing, and decision controller
├── server.py            # FastAPI web server and REST endpoints
├── static/
│   ├── index.html       # Visualizer interface layout
│   ├── app.js           # Client-side simulation loop, keyboard events, syntax highlighter
│   └── style.css        # Minimalist white/light benchmark styling and animations
└── tests/
    ├── conftest.py      # Pytest setup and path configuration
    ├── test_maze_engine.py # Environment, ghost patrol, and cache tests
    └── test_server.py   # FastAPI endpoint tests
```
