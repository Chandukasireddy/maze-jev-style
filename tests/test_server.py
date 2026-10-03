"""Integration tests for FastAPI application serving the Pac-Man benchmark."""

import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Clef System 1 Pac-Man Benchmark" in response.text
    assert "pacman-grid" in response.text


def test_api_state(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert data["width"] == 19
    assert data["height"] == 21
    assert "pacman_pos" in data
    assert "ghosts" in data
    assert "pellets" in data
    assert "score" in data
    assert "answers" in data
    assert "cache_stats" in data


def test_api_step(client):
    response = client.post("/api/step")
    assert response.status_code == 200
    data = response.json()
    assert "answers" in data
    assert "move" in data["answers"]
    assert "execution_time_ms" in data
    assert "score" in data


def test_api_reset(client):
    client.post("/api/step")
    response = client.post("/api/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["pacman_pos"] == [2, 19]
    assert data["move_num"] == 1


def test_api_cache_clear(client):
    response = client.post("/api/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"
    assert data["cache_stats"]["hits"] == 0


def test_api_backend_toggle(client):
    res = client.post("/api/backend", json={"backend": "mock"})
    assert res.status_code == 200
    assert res.json()["active_backend"] == "mock"
