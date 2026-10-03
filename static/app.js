// Clef System 1 Pac-Man Benchmark Visualizer

let gameState = null;
let isAutoPlaying = false;
let autoPlayTimer = null;

// DOM Elements
const pacmanGridEl = document.getElementById("pacman-grid");
const moveCounterEl = document.getElementById("move-counter");
const scoreDisplayEl = document.getElementById("score-display");
const sourceBadgeEl = document.getElementById("source-badge");
const gameBannerEl = document.getElementById("game-banner");
const bannerIconEl = document.getElementById("banner-icon");
const bannerTextEl = document.getElementById("banner-text");
const jsonCodeEl = document.getElementById("json-code");
const cacheHitRateEl = document.getElementById("cache-hit-rate");
const cacheSavedEl = document.getElementById("cache-saved");
const btnStep = document.getElementById("btn-step");
const btnAutoPlay = document.getElementById("btn-autoplay");
const btnReset = document.getElementById("btn-reset");
const btnClearCache = document.getElementById("btn-clear-cache");
const backendSelect = document.getElementById("backend-select");
const speedSlider = document.getElementById("speed-slider");
const speedLabel = document.getElementById("speed-label");
const pelletText = document.getElementById("pellet-text");
const latencyBadge = document.getElementById("latency-badge");

// Ghost Colors
const GHOST_COLORS = {
  pinky: "#f472b6",
  blinky: "#ef4444",
  clyde: "#f97316",
};

// Pac-Man Rotation Degrees
const DIR_ROTATION = {
  right: 0,
  down: 90,
  left: 180,
  up: 270,
};

// Initialize
async function init() {
  await fetchState();
  setupEventListeners();
}

async function fetchState() {
  try {
    const res = await fetch("/api/state");
    gameState = await res.json();
    gameState.pelletSet = new Set((gameState.pellets || []).map(([x, y]) => `${x},${y}`));

    if (backendSelect && gameState.active_backend) {
      backendSelect.value = gameState.active_backend;
    }

    renderGrid();
    updateInspector(gameState);
  } catch (err) {
    console.error("Failed to fetch initial Pac-Man state:", err);
  }
}

function renderGrid() {
  if (!gameState) return;

  const { width, height, grid, pacman_pos, pacman_dir, ghosts, pelletSet } = gameState;
  pacmanGridEl.innerHTML = "";

  const ghostMap = {};
  if (ghosts) {
    for (const [name, pos] of Object.entries(ghosts)) {
      ghostMap[`${pos[0]},${pos[1]}`] = name;
    }
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const cell = document.createElement("div");
      cell.classList.add("grid-cell");

      const char = grid[y][x];
      const isPacman = pacman_pos && (x === pacman_pos[0] && y === pacman_pos[1]);
      const ghostName = ghostMap[`${x},${y}`];
      const hasPellet = pelletSet && pelletSet.has(`${x},${y}`);

      if (char === "#") {
        cell.classList.add("cell-wall");
      } else if (char === " ") {
        cell.classList.add("cell-void");
      } else {
        cell.classList.add("cell-floor");

        if (isPacman) {
          cell.innerHTML = getPacmanSVG(pacman_dir);
        } else if (ghostName) {
          cell.innerHTML = getGhostSVG(ghostName);
        } else if (hasPellet) {
          cell.innerHTML = '<div class="pellet-dot"></div>';
        }
      }

      pacmanGridEl.appendChild(cell);
    }
  }

  // Update pellets count
  if (pelletText && gameState.pellets_remaining !== undefined) {
    pelletText.innerText = `${gameState.pellets_remaining} left`;
  }
}

function getPacmanSVG(dir) {
  const rot = DIR_ROTATION[dir] !== undefined ? DIR_ROTATION[dir] : 0;
  return `
    <div class="pacman-wrapper" style="transform: rotate(${rot}deg);">
      <svg class="pacman-svg" viewBox="0 0 32 32">
        <path class="pacman-body" d="M16 16 L29 7 A14 14 0 1 0 29 25 Z" />
      </svg>
    </div>
  `;
}

function getGhostSVG(ghostName) {
  const color = GHOST_COLORS[ghostName] || "#f472b6";
  return `
    <div class="ghost-wrapper">
      <svg class="ghost-svg" viewBox="0 0 32 32">
        <path fill="${color}" d="M4 16 C4 9.37 9.37 4 16 4 C22.63 4 28 9.37 28 16 L28 28 L24 24 L20 28 L16 24 L12 28 L8 24 L4 28 Z" />
        <circle cx="11" cy="13" r="3.2" fill="#ffffff" />
        <circle cx="21" cy="13" r="3.2" fill="#ffffff" />
        <circle cx="12" cy="13" r="1.6" fill="#1e293b" />
        <circle cx="22" cy="13" r="1.6" fill="#1e293b" />
      </svg>
    </div>
  `;
}

async function performStep() {
  if (gameState && gameState.is_game_over) {
    stopAutoPlay();
    return;
  }

  btnStep.disabled = true;

  try {
    const res = await fetch("/api/step", { method: "POST" });
    const data = await res.json();

    gameState.pacman_pos = data.pacman_pos;
    gameState.pacman_dir = data.pacman_dir;
    gameState.ghosts = data.ghosts;
    gameState.move_num = data.move_num;
    gameState.max_moves = data.max_moves;
    gameState.pellets_remaining = data.pellets_remaining;
    gameState.score = data.score;
    gameState.is_game_over = data.is_game_over;
    gameState.is_win = data.is_win;
    gameState.game_over_reason = data.game_over_reason;
    gameState.answers = data.answers;
    gameState.source = data.source;
    gameState.execution_time_ms = data.execution_time_ms;
    gameState.cache_stats = data.cache_stats;

    // Remove eaten pellet
    const key = `${data.pacman_pos[0]},${data.pacman_pos[1]}`;
    if (gameState.pelletSet && gameState.pelletSet.has(key)) {
      gameState.pelletSet.delete(key);
    }

    renderGrid();
    updateInspector(data);

    if (data.is_game_over || data.is_win) {
      stopAutoPlay();
    }
  } catch (err) {
    console.error("Step execution failed:", err);
  } finally {
    btnStep.disabled = false;
  }
}

function updateInspector(data) {
  // Update Move counter: "Move X of 187"
  if (moveCounterEl && data.move_num !== undefined) {
    moveCounterEl.innerText = `Move ${data.move_num} of ${data.max_moves || 187}`;
  }

  // Update Score
  if (scoreDisplayEl && data.score !== undefined) {
    scoreDisplayEl.innerText = `Score: ${data.score}`;
  }

  // Update Source Badge
  if (sourceBadgeEl) {
    sourceBadgeEl.className = "source-badge";
    const src = data.source || "initial";
    if (src === "cache") {
      sourceBadgeEl.classList.add("badge-cache");
      sourceBadgeEl.innerText = "⚡ Stage 1 Cache";
    } else if (src === "cloudflare_clef") {
      sourceBadgeEl.classList.add("badge-clef");
      sourceBadgeEl.innerText = "☁️ Clef-Flash";
    } else if (src === "mock_engine") {
      sourceBadgeEl.classList.add("badge-mock");
      sourceBadgeEl.innerText = "🤖 Heuristic";
    } else if (src === "mock_engine_fallback") {
      sourceBadgeEl.classList.add("badge-fallback");
      sourceBadgeEl.innerText = "⚠️ Fallback Heuristic";
    } else {
      sourceBadgeEl.classList.add("badge-clef");
      sourceBadgeEl.innerText = "⚡ System 1 Ready";
    }
  }

  // Status Banner (Victory / Defeat)
  if (gameBannerEl) {
    if (data.is_game_over) {
      gameBannerEl.classList.remove("hidden");
      if (data.is_win) {
        gameBannerEl.className = "game-banner banner-victory";
        if (bannerIconEl) bannerIconEl.innerText = "🏆";
        if (bannerTextEl) bannerTextEl.innerText = `Victory! All pellets consumed in ${data.move_num} moves!`;
      } else if (data.game_over_reason && data.game_over_reason.startsWith("caught_by")) {
        const gName = data.game_over_reason.replace("caught_by_", "");
        const capName = gName.charAt(0).toUpperCase() + gName.slice(1);
        gameBannerEl.className = "game-banner banner-defeat";
        if (bannerIconEl) bannerIconEl.innerText = "💀";
        if (bannerTextEl) bannerTextEl.innerText = `Game Over! Caught by ${capName} at move ${data.move_num}.`;
      } else if (data.game_over_reason === "moves_exhausted") {
        gameBannerEl.className = "game-banner banner-defeat";
        if (bannerIconEl) bannerIconEl.innerText = "⏳";
        if (bannerTextEl) bannerTextEl.innerText = `Game Over! Maximum moves (${data.max_moves}) exhausted.`;
      }
    } else {
      gameBannerEl.classList.add("hidden");
    }
  }

  // Syntax highlight JSON output
  if (jsonCodeEl && data.answers) {
    const highlightedHTML = highlightJSON({ answers: data.answers });
    jsonCodeEl.innerHTML = highlightedHTML;
  }

  // Latency
  if (latencyBadge && data.execution_time_ms !== undefined) {
    const ms = data.execution_time_ms;
    latencyBadge.innerText = ms < 1 ? "< 1 ms" : `${Math.round(ms)} ms`;
  }

  // Cache Telemetry
  if (data.cache_stats) {
    const stats = data.cache_stats;
    if (cacheHitRateEl && stats.total_requests !== undefined) {
      const pct = (stats.hit_rate * 100).toFixed(1);
      cacheHitRateEl.innerText = `${pct}% (${stats.hits}/${stats.total_requests})`;
    }
    if (cacheSavedEl && stats.total_latency_saved_ms !== undefined) {
      cacheSavedEl.innerText = `${Math.round(stats.total_latency_saved_ms)} ms`;
    }
  }
}

// Pretty print and syntax highlight JSON
function highlightJSON(obj) {
  const jsonStr = JSON.stringify(obj, null, 2);

  return jsonStr
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      function (match) {
        let cls = "json-number";
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = "json-key";
            const keyContent = match.slice(0, -1);
            return `<span class="${cls}">${keyContent}</span><span class="json-punc">:</span>`;
          } else {
            cls = "json-string";
          }
        } else if (/true|false/.test(match)) {
          cls = "json-boolean";
        } else if (/null/.test(match)) {
          cls = "json-null";
        }
        return `<span class="${cls}">${match}</span>`;
      }
    )
    .replace(/([{}[\],])/g, '<span class="json-punc">$1</span>');
}

async function resetGame() {
  stopAutoPlay();
  try {
    const res = await fetch("/api/reset", { method: "POST" });
    gameState = await res.json();
    gameState.pelletSet = new Set((gameState.pellets || []).map(([x, y]) => `${x},${y}`));
    renderGrid();
    updateInspector(gameState);
  } catch (err) {
    console.error("Reset failed:", err);
  }
}

async function clearCache() {
  try {
    const res = await fetch("/api/cache/clear", { method: "POST" });
    const data = await res.json();
    if (data.cache_stats && gameState) {
      gameState.cache_stats = data.cache_stats;
      updateInspector(gameState);
    }
  } catch (err) {
    console.error("Cache clear failed:", err);
  }
}

async function handleBackendChange(e) {
  const newBackend = e.target.value;
  try {
    await fetch("/api/backend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend: newBackend }),
    });
  } catch (err) {
    console.error("Backend switch failed:", err);
  }
}

function toggleAutoPlay() {
  if (isAutoPlaying) {
    stopAutoPlay();
  } else {
    startAutoPlay();
  }
}

function startAutoPlay() {
  if (gameState && gameState.is_game_over) return;
  isAutoPlaying = true;
  btnAutoPlay.innerHTML = '<span class="btn-icon">⏸</span> Pause';
  btnAutoPlay.classList.add("btn-primary");
  btnAutoPlay.classList.remove("btn-secondary");

  const speed = parseInt(speedSlider.value, 10);
  performStep();
  autoPlayTimer = setInterval(performStep, speed);
}

function stopAutoPlay() {
  isAutoPlaying = false;
  clearInterval(autoPlayTimer);
  btnAutoPlay.innerHTML = '<span class="btn-icon">▶</span> Auto-Play';
  btnAutoPlay.classList.add("btn-secondary");
  btnAutoPlay.classList.remove("btn-primary");
}

function setupEventListeners() {
  btnStep.addEventListener("click", performStep);
  btnAutoPlay.addEventListener("click", toggleAutoPlay);
  btnReset.addEventListener("click", resetGame);
  if (btnClearCache) {
    btnClearCache.addEventListener("click", clearCache);
  }
  if (backendSelect) {
    backendSelect.addEventListener("change", handleBackendChange);
  }

  speedSlider.addEventListener("input", (e) => {
    const val = e.target.value;
    speedLabel.innerText = `${(val / 1000).toFixed(1)}s`;
    if (isAutoPlaying) {
      clearInterval(autoPlayTimer);
      autoPlayTimer = setInterval(performStep, parseInt(val, 10));
    }
  });

  // Keyboard controls
  document.addEventListener("keydown", (e) => {
    // Avoid interfering if typing in an input
    if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;

    if (e.code === "Space") {
      e.preventDefault();
      toggleAutoPlay();
    } else if (e.key === "s" || e.key === "S") {
      e.preventDefault();
      performStep();
    } else if (e.key === "r" || e.key === "R") {
      e.preventDefault();
      resetGame();
    } else if (e.key === "c" || e.key === "C") {
      e.preventDefault();
      clearCache();
    }
  });
}

// Boot
document.addEventListener("DOMContentLoaded", init);
