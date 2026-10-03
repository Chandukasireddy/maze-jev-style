"""Pac-Man maze simulation and System 1 decision engine for agent navigation."""

from __future__ import annotations

import random
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

# Resolve sibling agent-decision-router if present
_PARENT = Path(__file__).resolve().parent.parent
if (_PARENT / "agent-decision-router").exists() and str(_PARENT / "agent-decision-router") not in sys.path:
    sys.path.insert(0, str(_PARENT / "agent-decision-router"))

try:
    from agent_decision_router.config import get_settings
    from agent_decision_router.models import DecisionPayload, QuestionDefinition, DecisionResult, DecisionStatus
    from agent_decision_router.cache import FastPathCache
    from agent_decision_router.backend.cloudflare import CloudflareBackend
    from agent_decision_router.backend.mock import MockBackend
except ImportError:
    # Minimal 15-line shim if agent_decision_router is not in environment
    class FastPathCache:
        def __init__(self, **_kw): self._c, self.stats = {}, SimpleNamespace(hits=0, misses=0, evictions=0, total_requests=0, hit_rate=0.0, total_latency_saved_ms=0.0)
        @staticmethod
        def compute_state_hash(s, c): import hashlib, json; return hashlib.sha256(f"{s}::{json.dumps(c, sort_keys=True)}".encode()).hexdigest()[:16]
        def get(self, k):
            r = self._c.get(k)
            self.stats.hits += bool(r); self.stats.misses += not r; self.stats.total_requests += 1
            self.stats.hit_rate = round(self.stats.hits / self.stats.total_requests, 4); return r
        def set(self, k, v): self._c[k] = v
        def clear(self): self._c.clear()

    class MockBackend:
        def query_decision_sync(self, payload):
            c = payload.questions.get("move").criteria or {}
            scored = {k: 3.0 if "eat pellet" in v.lower() else (0.1 if "danger" in v.lower() else 1.0) for k, v in c.items()}
            tot = sum(scored.values()) or 1.0
            probs = {k: round(v / tot, 2) for k, v in scored.items()}
            act = max(probs, key=probs.get) if probs else "right"
            return SimpleNamespace(selected_action=act, confidence=probs.get(act, 0.8), probabilities=probs)

    CloudflareBackend = MockBackend
    DecisionPayload = SimpleNamespace
    QuestionDefinition = SimpleNamespace
    DecisionResult = SimpleNamespace
    DecisionStatus = SimpleNamespace(EXECUTABLE="executable", LOOKAHEAD_RESOLVED="lookahead_resolved")
    get_settings = lambda: SimpleNamespace(is_cloudflare_configured=False)


# Direction vectors: (dx, dy)
DIRECTIONS: Dict[str, Tuple[int, int]] = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
DIR_OPPOSITES: Dict[str, str] = {"up": "down", "down": "up", "left": "right", "right": "left"}

PACMAN_MAP: List[str] = [
    "###################",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    ".......#   #.......",
    "####.# ##### #.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#..#...........#..#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################",
]


class PacmanEnvironment:
    """Pac-Man arcade environment with pellets, wrap-around tunnels, and ghosts."""

    def __init__(self) -> None:
        self.height = len(PACMAN_MAP)
        self.width = len(PACMAN_MAP[0])
        self.grid: List[List[str]] = [list(row) for row in PACMAN_MAP]
        self.reset()

    def reset(self) -> None:
        """Reset simulation state."""
        self.pacman_pos: Tuple[int, int] = (2, 19)
        self.pacman_dir: str = "right"
        self.move_count: int = 1
        self.max_moves: int = 187
        self.is_game_over: bool = False
        self.game_over_reason: Optional[str] = None
        self.score: int = 0

        self.ghosts: Dict[str, Tuple[int, int]] = {"pinky": (3, 3), "blinky": (15, 3), "clyde": (3, 13)}
        self.ghost_dirs: Dict[str, str] = {"pinky": "left", "blinky": "right", "clyde": "down"}

        self.pellets: Set[Tuple[int, int]] = {
            (x, y) for y in range(self.height) for x in range(self.width) if self.grid[y][x] == "."
        }
        if self.pacman_pos in self.pellets:
            self.pellets.discard(self.pacman_pos)
            self.score += 10

        self.total_pellets = len(self.pellets) + 1
        self.path_history: List[Tuple[int, int]] = [self.pacman_pos]

    def is_valid_tile(self, x: int, y: int) -> bool:
        """Check if (x, y) is walkable corridor, considering tunnel wrap-around."""
        x = (x % self.width) if y == 9 else x
        if x < 0 or x >= self.width or y < 0 or y >= self.height or (7 <= x <= 11 and 8 <= y <= 10):
            return False
        return self.grid[y][x] not in ("#", " ")

    def get_valid_moves(self, pos: Optional[Tuple[int, int]] = None) -> Dict[str, Tuple[int, int]]:
        """Return valid adjacent moves."""
        cx, cy = pos or self.pacman_pos
        moves = {}
        for d, (dx, dy) in DIRECTIONS.items():
            nx = (cx + dx) % self.width if cy + dy == 9 else cx + dx
            ny = cy + dy
            if self.is_valid_tile(nx, ny):
                moves[d] = (nx, ny)
        return moves

    def get_decision_moves(self) -> Dict[str, Tuple[int, int]]:
        """Return valid moves filtering out immediate 180-deg reversal when forward path exists."""
        valid = self.get_valid_moves()
        if len(self.path_history) > 1:
            prev = self.path_history[-2]
            forward = {k: v for k, v in valid.items() if v != prev}
            if forward:
                return forward
        return valid

    def _bfs(self, start_pos: Tuple[int, int], target: Optional[Tuple[int, int]] = None) -> Any:
        """Single BFS for shortest distance to target tile or nearest pellet."""
        if target is not None and start_pos == target:
            return 0
        q, visited = deque([(start_pos, 0)]), {start_pos}
        while q:
            curr, dist = q.popleft()
            if target is not None:
                if curr == target:
                    return dist
            elif curr in self.pellets:
                return curr, dist
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx = (curr[0] + dx) % self.width if curr[1] + dy == 9 else curr[0] + dx
                ny = curr[1] + dy
                if self.is_valid_tile(nx, ny) and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append(((nx, ny), dist + 1))
        return 999 if target is not None else None

    def find_nearest_pellet(self, start_pos: Tuple[int, int]) -> Optional[Tuple[Tuple[int, int], int]]:
        """Return nearest remaining pellet and step count."""
        return self._bfs(start_pos)

    def shortest_path_distance(self, start_pos: Tuple[int, int], target: Tuple[int, int]) -> int:
        """Return BFS distance between any two walkable tiles."""
        return self._bfs(start_pos, target)

    def build_clef_state_and_questions(self) -> Tuple[str, Dict[str, Any], str]:
        """Construct System 1 prompt, typed choice question, and cache key."""
        px, py = self.pacman_pos
        decision_moves = self.get_decision_moves()
        nearest_info = self.find_nearest_pellet(self.pacman_pos)
        nearest_pellet = nearest_info[0] if nearest_info else None

        state_parts = [
            f"Pac-Man position: ({px}, {py}), facing: {self.pacman_dir}.",
            f"Move number: {self.move_count} of {self.max_moves}. Pellets remaining: {len(self.pellets)}.",
        ]

        for g_name, g_pos in self.ghosts.items():
            dist = self.shortest_path_distance(self.pacman_pos, g_pos)
            if dist <= 4:
                state_parts.append(f"WARNING: Ghost {g_name} is nearby at {g_pos} (dist {dist})!")

        criteria: Dict[str, str] = {}
        for d_name, (tx, ty) in decision_moves.items():
            parts = [f"Step {d_name} to ({tx}, {ty})"]
            if (tx, ty) in self.pellets:
                parts.append("EAT PELLET immediately on this tile")
            elif nearest_pellet:
                dist = self.shortest_path_distance((tx, ty), nearest_pellet)
                parts.append(f"advance towards nearest pellet ({dist} steps away)")

            if any(self.shortest_path_distance((tx, ty), gp) <= 1 for gp in self.ghosts.values()):
                parts.append("DANGER: ghost on adjacent tile!")
            elif d_name == self.pacman_dir:
                parts.append("continue forward in current corridor momentum")
            criteria[d_name] = "; ".join(parts)

        if len(criteria) == 1:
            criteria["wait"] = "Pause in place (delays progress, prefer forward move)"
        elif not criteria:
            criteria["wait"], criteria["right"] = "Wait in place", "Try moving right"

        questions = {
            "move": QuestionDefinition(
                type="choice",
                instructions="Which direction (up, down, left, right) should Pac-Man move to eat pellets and avoid ghosts?",
                criteria=criteria,
            )
        }

        cache_key = f"pos:({px},{py})|dir:{self.pacman_dir}|pellets:{len(self.pellets)}|nearest:{nearest_pellet}|ghosts:{tuple(sorted(self.ghosts.items()))}"
        return "\n".join(state_parts), questions, cache_key

    def move_ghosts(self) -> None:
        """Patrol ghosts smoothly with anti-reversal corridor momentum."""
        for g_name, g_pos in list(self.ghosts.items()):
            moves = self.get_valid_moves(g_pos)
            if not moves:
                continue
            cur_dir = self.ghost_dirs.get(g_name, "up")
            opp_dir = DIR_OPPOSITES.get(cur_dir, "")
            non_rev = {k: v for k, v in moves.items() if k != opp_dir}
            candidates = non_rev or moves

            chosen_dir = cur_dir if (cur_dir in candidates and random.random() < 0.70) else random.choice(list(candidates.keys()))
            self.ghosts[g_name] = candidates[chosen_dir]
            self.ghost_dirs[g_name] = chosen_dir


class PacmanDecisionController:
    """Controller running Clef-Flash inference with Fast-Path Cache."""

    def __init__(self, environment: PacmanEnvironment) -> None:
        self.env = environment
        self.settings = get_settings()
        self.cache = FastPathCache(max_size=512, ttl_seconds=3600)
        self.active_backend: str = "cloudflare" if getattr(self.settings, "is_cloudflare_configured", False) else "mock"
        self.backend = CloudflareBackend() if getattr(self.settings, "is_cloudflare_configured", False) else MockBackend()
        self.mock_backend = MockBackend()

    def set_backend(self, backend_name: str) -> None:
        """Set active decision backend ('cloudflare' or 'mock')."""
        if backend_name == "cloudflare" and getattr(self.settings, "is_cloudflare_configured", False):
            self.active_backend = "cloudflare"
            self.backend = CloudflareBackend()
        else:
            self.active_backend = "mock"
            self.backend = self.mock_backend

    def step(self, backend_override: Optional[str] = None) -> Dict[str, Any]:
        """Execute one decision step."""
        if backend_override:
            self.set_backend(backend_override)
        start = time.perf_counter()
        if self.env.is_game_over or len(self.env.pellets) == 0:
            return self.get_current_response(self.env.pacman_dir, 1.0, {}, "environment", 0.05)

        state_str, questions, cache_key = self.env.build_clef_state_and_questions()
        criteria = questions["move"].criteria or {}
        state_hash = FastPathCache.compute_state_hash(cache_key, criteria)
        cached = self.cache.get(state_hash)

        if cached is not None:
            chosen_dir, conf, probs, source = cached.action, cached.confidence, cached.probabilities, "cache"
        else:
            payload = DecisionPayload(state=state_str, questions=questions)
            try:
                parsed = self.backend.query_decision_sync(payload) if self.active_backend == "cloudflare" else self.mock_backend.query_decision_sync(payload)
                source = "cloudflare_clef" if self.active_backend == "cloudflare" else "mock_engine"
            except Exception:
                parsed = self.mock_backend.query_decision_sync(payload)
                source = "mock_engine_fallback"

            chosen_dir, conf, probs = parsed.selected_action, parsed.confidence, parsed.probabilities
            self.cache.set(state_hash, DecisionResult(action=chosen_dir, confidence=conf, probabilities=probs, status=DecisionStatus.EXECUTABLE))

        # Anti-oscillation move execution
        old_pos = self.env.pacman_pos
        dec_moves = self.env.get_decision_moves()
        val_moves = self.env.get_valid_moves()

        if chosen_dir in dec_moves:
            exec_dir = chosen_dir
        elif self.env.pacman_dir in dec_moves:
            exec_dir = self.env.pacman_dir
        elif dec_moves:
            exec_dir = next(iter(dec_moves))
        else:
            exec_dir = next(iter(val_moves)) if val_moves else self.env.pacman_dir

        next_pos = val_moves.get(exec_dir, self.env.pacman_pos)
        self.env.pacman_pos = next_pos
        self.env.pacman_dir = exec_dir
        self.env.path_history.append(next_pos)
        self.env.move_count += 1

        if next_pos in self.env.pellets:
            self.env.pellets.discard(next_pos)
            self.env.score += 10

        prev_ghosts = dict(self.env.ghosts)
        if self.env.move_count % 2 == 0:
            self.env.move_ghosts()

        for g_name, g_pos in self.env.ghosts.items():
            if g_pos == self.env.pacman_pos or (prev_ghosts.get(g_name) == self.env.pacman_pos and g_pos == old_pos):
                self.env.is_game_over = True
                self.env.game_over_reason = f"caught_by_{g_name}"
                break

        if not self.env.is_game_over:
            if len(self.env.pellets) == 0:
                self.env.is_game_over, self.env.game_over_reason = True, "victory"
            elif self.env.move_count >= self.env.max_moves:
                self.env.is_game_over, self.env.game_over_reason = True, "moves_exhausted"

        return self.get_current_response(exec_dir, conf, probs, source, (time.perf_counter() - start) * 1000.0)

    def get_current_response(self, action: str, confidence: float, probabilities: Dict[str, float], source: str, execution_time: float) -> Dict[str, Any]:
        """Construct response layout matching benchmark specification."""
        stats = self.cache.stats.to_dict() if hasattr(self.cache.stats, "to_dict") else vars(self.cache.stats)
        return {
            "answers": {"move": {"type": "choice", "choice": action, "probabilities": {k: round(float(v), 2) for k, v in probabilities.items()}, "confidence": round(confidence, 2)}},
            "move_num": self.env.move_count,
            "max_moves": self.env.max_moves,
            "pacman_pos": self.env.pacman_pos,
            "pacman_dir": self.env.pacman_dir,
            "ghosts": self.env.ghosts,
            "pellets": list(self.env.pellets),
            "pellets_remaining": len(self.env.pellets),
            "pellets_total": self.env.total_pellets,
            "score": self.env.score,
            "is_game_over": self.env.is_game_over,
            "is_win": len(self.env.pellets) == 0,
            "game_over_reason": self.env.game_over_reason,
            "source": source,
            "execution_time_ms": round(execution_time, 2),
            "cache_stats": stats,
        }
