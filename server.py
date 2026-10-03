"""FastAPI application serving the Pac-Man Decision Visualizer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from maze_test.maze_engine import PacmanEnvironment, PacmanDecisionController

app = FastAPI(title="Clef System 1 Pac-Man Benchmark")

# Initialize global environment and controller
env = PacmanEnvironment()
controller = PacmanDecisionController(env)

STATIC_DIR = BASE_DIR / "static"


@app.get("/api/state")
def get_state() -> Dict[str, Any]:
    """Retrieve full Pac-Man board and agent status."""
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
        "move_num": env.move_count,
        "max_moves": env.max_moves,
        "is_game_over": env.is_game_over,
        "is_win": len(env.pellets) == 0,
        "answers": controller.get_current_response(
            action=env.pacman_dir,
            confidence=0.77,
            probabilities={"left": 0.04, "right": 0.96},
            source="initial",
            execution_time=0.0,
        )["answers"],
    }


@app.post("/api/step")
def step_agent() -> Dict[str, Any]:
    """Trigger one decision step using Clef / System 1 engine."""
    try:
        step_result = controller.step()
        return step_result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/reset")
def reset_maze() -> Dict[str, Any]:
    """Reset Pac-Man back to initial state."""
    env.reset()
    controller.cache.clear()
    return get_state()


# Mount static directory for HTML, CSS, JS
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


def main():
    print("Starting Clef Pac-Man Visualizer on http://localhost:8080 ...")
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
