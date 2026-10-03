"""Unit tests for Pac-Man maze simulation and System 1 decision engine."""

import pytest
from maze_engine import (
    PACMAN_MAP,
    DIRECTIONS,
    PacmanEnvironment,
    PacmanDecisionController,
    FastPathCache,
    DecisionResult,
    DecisionStatus,
)


class TestPacmanEnvironment:
    """Test environment simulation logic, movement constraints, and collision rules."""

    def test_init_state(self):
        env = PacmanEnvironment()
        assert env.width == 19
        assert env.height == 21
        assert env.pacman_pos == (2, 19)
        assert env.pacman_dir == "right"
        assert env.move_count == 1
        assert env.max_moves == 187
        assert not env.is_game_over
        assert env.game_over_reason is None
        assert env.score == 10  # Starting tile pellet consumed
        assert len(env.ghosts) == 3
        assert "pinky" in env.ghosts
        assert "blinky" in env.ghosts
        assert "clyde" in env.ghosts
        assert len(env.pellets) > 150

    def test_tile_validity(self):
        env = PacmanEnvironment()
        # Wall tile
        assert not env.is_valid_tile(0, 0)
        assert not env.is_valid_tile(9, 0)
        # Corridors
        assert env.is_valid_tile(1, 1)
        assert env.is_valid_tile(2, 19)
        # Ghost house interior (restricted)
        assert not env.is_valid_tile(8, 9)
        assert not env.is_valid_tile(9, 9)
        assert not env.is_valid_tile(10, 9)

    def test_tunnel_wrap_around(self):
        env = PacmanEnvironment()
        # Row 9 is the tunnel
        moves_left_edge = env.get_valid_moves((0, 9))
        assert "left" in moves_left_edge
        assert moves_left_edge["left"] == (18, 9)

        moves_right_edge = env.get_valid_moves((18, 9))
        assert "right" in moves_right_edge
        assert moves_right_edge["right"] == (0, 9)

    def test_anti_reversal_decision_moves(self):
        env = PacmanEnvironment()
        # Move from (2, 19) to (3, 19)
        env.pacman_pos = (3, 19)
        env.path_history.append((3, 19))

        decision_moves = env.get_decision_moves()
        # Moving back to (2, 19) should be filtered out when forward options exist
        assert "left" not in decision_moves
        assert "right" in decision_moves

    def test_bfs_nearest_pellet(self):
        env = PacmanEnvironment()
        result = env.find_nearest_pellet(env.pacman_pos)
        assert result is not None
        pellet_pos, steps = result
        assert pellet_pos in env.pellets
        assert steps >= 1

    def test_shortest_path_distance(self):
        env = PacmanEnvironment()
        dist_same = env.shortest_path_distance((1, 1), (1, 1))
        assert dist_same == 0

        dist_adjacent = env.shortest_path_distance((1, 1), (2, 1))
        assert dist_adjacent == 1

    def test_ghost_patrol_movement(self):
        env = PacmanEnvironment()
        initial_pinky_pos = env.ghosts["pinky"]
        # Ghosts move every 2 steps in simulation
        env.move_ghosts()
        new_pinky_pos = env.ghosts["pinky"]
        # Pinky should either move to an adjacent valid tile or stay valid
        assert env.is_valid_tile(new_pinky_pos[0], new_pinky_pos[1])

    def test_direct_collision(self):
        env = PacmanEnvironment()
        controller = PacmanDecisionController(env)
        # Place ghost on Pac-Man's tile
        env.ghosts["pinky"] = env.pacman_pos
        # Step controller
        result = controller.step(backend_override="mock")
        assert result["is_game_over"]
        assert result["game_over_reason"] == "caught_by_pinky"

    def test_swap_collision(self):
        env = PacmanEnvironment()
        controller = PacmanDecisionController(env)
        # Set up head-on collision scenario:
        # Pacman at (2, 19) facing right, moves to (3, 19)
        # Ghost at (3, 19), moves to (2, 19)
        env.pacman_pos = (2, 19)
        env.ghosts["pinky"] = (3, 19)
        # Force move count to be odd so next step will move ghosts
        env.move_count = 1
        # Mock ghost to head left into (2, 19)
        env.ghost_dirs["pinky"] = "left"

        result = controller.step(backend_override="mock")
        # Check that swap collision is detected
        if env.pacman_pos == (3, 19) and env.ghosts["pinky"] == (2, 19):
            assert result["is_game_over"]
            assert "caught_by_pinky" in result["game_over_reason"]

    def test_max_moves_exhaustion(self):
        env = PacmanEnvironment()
        controller = PacmanDecisionController(env)
        env.move_count = 186
        result = controller.step(backend_override="mock")
        assert result["is_game_over"]
        assert result["game_over_reason"] == "moves_exhausted"


class TestFastPathCache:
    """Test Fast-Path content-addressable caching mechanism and telemetry."""

    def test_cache_miss_and_set(self):
        cache = FastPathCache(max_size=10, ttl_seconds=60)
        res = cache.get("test_key")
        assert res is None
        assert cache.stats.misses == 1

        val = DecisionResult(action="right", confidence=0.92, status=DecisionStatus.EXECUTABLE)
        cache.set("test_key", val)
        cached_res = cache.get("test_key")
        assert cached_res is not None
        assert cached_res.action == "right"
        assert cache.stats.hits == 1
        assert cache.stats.hit_rate == 0.5  # 1 hit out of 2 requests

    def test_cache_clear(self):
        cache = FastPathCache()
        val = DecisionResult(action="up", confidence=0.88, status=DecisionStatus.EXECUTABLE)
        cache.set("key1", val)
        cache.clear()
        assert cache.get("key1") is None


class TestPacmanDecisionController:
    """Test end-to-end decision controller and mock backend."""

    def test_controller_mock_step(self):
        env = PacmanEnvironment()
        controller = PacmanDecisionController(env)
        controller.set_backend("mock")

        step_res = controller.step(backend_override="mock")
        assert "answers" in step_res
        assert "move" in step_res["answers"]
        assert step_res["answers"]["move"]["choice"] in ["left", "right", "up", "down"]
        assert step_res["source"] in ["mock_engine", "cache"]
        assert step_res["move_num"] == 2
        assert step_res["score"] >= 10
        assert step_res["execution_time_ms"] >= 0.0

    def test_controller_cache_hit_on_replay(self):
        env = PacmanEnvironment()
        controller = PacmanDecisionController(env)
        controller.set_backend("mock")

        # Step 1: Populates cache
        res1 = controller.step(backend_override="mock")
        assert res1["source"] == "mock_engine"

        # Reset environment back to starting point
        env.reset()

        # Step 2: Identical spatial state should retrieve from FastPathCache
        res2 = controller.step(backend_override="mock")
        assert res2["source"] == "cache"
        assert controller.cache.stats.hits >= 1
