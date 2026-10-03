"""FastAPI application serving the Clef System 1 Pac-Man Benchmark."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from maze_engine import PacmanEnvironment, PacmanDecisionController

app = FastAPI(title="Clef System 1 Pac-Man Benchmark")

env = PacmanEnvironment()
controller = PacmanDecisionController(env)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/api/state")
def get_state() -> Dict[str, Any]:
    """Retrieve full Pac-Man board, agent status, and cache telemetry."""
    _, questions, _ = env.build_clef_state_and_questions()
    criteria = questions["move"].criteria or {}
    candidates = [k for k in criteria if k != "wait"]
    probs = {k: round(1.0 / len(candidates), 2) for k in candidates} if candidates else {"right": 1.0}

    stats = controller.cache.stats.to_dict() if hasattr(controller.cache.stats, "to_dict") else vars(controller.cache.stats)
    return {
        "width": env.width,
        "height": env.height,
        "grid": env.grid,
        "pacman_pos": env.pacman_pos,
        "pacman_dir": env.pacman_dir,
        "ghosts": env.ghosts,
        "pellets": list(env.pellets),
        "pellets_remaining": len(env.pellets),
        "pellets_total": env.total_pellets,
        "score": env.score,
        "move_num": env.move_count,
        "max_moves": env.max_moves,
        "is_game_over": env.is_game_over,
        "is_win": len(env.pellets) == 0,
        "game_over_reason": env.game_over_reason,
        "active_backend": controller.active_backend,
        "answers": {"move": {"type": "choice", "choice": env.pacman_dir, "probabilities": probs, "confidence": 0.85}},
        "cache_stats": stats,
    }


@app.post("/api/step")
def step_agent() -> Dict[str, Any]:
    """Trigger one decision step."""
    try:
        return controller.step()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reset")
def reset_maze() -> Dict[str, Any]:
    """Reset simulation back to initial state, keeping learned Fast-Path Cache."""
    env.reset()
    return get_state()


@app.post("/api/cache/clear")
def clear_cache() -> Dict[str, Any]:
    """Flush Stage 1 Fast-Path Cache entries and reset counters."""
    if hasattr(controller.cache, "clear"):
        controller.cache.clear()
    if hasattr(controller.cache, "stats"):
        controller.cache.stats.hits = 0
        controller.cache.stats.misses = 0
        controller.cache.stats.evictions = 0
        controller.cache.stats.total_latency_saved_ms = 0.0
    stats = controller.cache.stats.to_dict() if hasattr(controller.cache.stats, "to_dict") else vars(controller.cache.stats)
    return {"status": "cleared", "cache_stats": stats}


@app.post("/api/backend")
def set_backend(backend: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Switch active decision backend between 'cloudflare' and 'mock'."""
    controller.set_backend(backend)
    return {"active_backend": controller.active_backend}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
