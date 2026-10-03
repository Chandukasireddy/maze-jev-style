# Clef System 1 Maze Navigator

An interactive visual demonstration showing how the **Clef / Jev System One decision architecture** navigates an agent from Start (`S`) to Goal (`G`) through a complex obstacle grid.

---

## How Clef Decision-Making Works in the Maze

At every tile position `(x, y)`:
1. **Sensory Scan & Environmental State:** The engine scans adjacent coordinates (North, South, East, West), detects open paths vs walls, checks Manhattan distance to `G`, and accounts for prior step history.
2. **System 1 Typed Questions:**
   - **`next_tool` (Choice Question):** Each valid open direction is converted into criteria:
     - `move_east`: *"Step East to (x+1, y). Optimal forward progression towards final goal G."*
     - `move_south`: *"Step South to (x, y+1). Alternative exploration path."*
   - **`is_destructive` (Noul Question):** Checks if the direction steps into a dead-end or repeated cycle.
   - **`task_completion` (Noul Question):** Checks if the agent has reached the final destination `G`.
3. **Fast-Path Cache:** When the agent steps into an already calculated state or symmetrical corridor, it fetches the decision in **$<0.1\text{ ms}$** via Stage 1 Fast-Path Cache.

---

## How to Run

From the root project directory:

```powershell
python -m maze_test.server
```

Or with `uvicorn`:

```powershell
uvicorn maze_test.server:app --port 8080 --reload
```

Then open your browser at:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## Interactive Controls

- **Next Step (Clef Call):** Sends the current grid state to `@cf/cloudflare/clef-flash` and steps the agent forward.
- **Auto-Play:** Continuously steps the agent automatically until the goal is reached.
- **Speed Slider:** Adjust auto-play transition speed from `0.3s` to `2.0s`.
- **Layout Presets:**
  - `Classic Maze (8x7)`
  - `Forks & Turns (8x6)`
  - `Chambers & Corridors (8x7)`
- **Decision Inspector:** Live display of candidate probabilities, confidence gauge, dead-end detection, and raw JSON prompt sent to Cloudflare.
