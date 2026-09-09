# Combat Progression Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Boss, drop-rate GM controls, staged skills UI, dual-mode refining, hunt-status synchronization, and experience-percentage display changes.

**Architecture:** Preserve the existing content JSON and FastAPI boundaries. Add persisted override/settings layers only where runtime GM changes require them, keep combat events as the shared contract, and make the web client consume explicit state rather than inferring combat from a hunting id. Each feature gets focused regression tests before implementation.

**Tech Stack:** Python 3, FastAPI, SQLite, Pydantic, pytest, vanilla JavaScript/CSS, JSON content data.

---

### Task 1: Boss scaling, roster expansion, and slow live combat playback

**Files:**
- Modify: `server/content/monster_stats.py`, `server/mvp/challenge.py`, `server/settlement/engine.py`
- Modify: `data/mvps.json`, `data/cards.json`, and any required content drop files
- Modify: `web/js/screen-more.js`, `web/js/screens.js`, `web/js/app.js`
- Test: `tests/test_monster_stats.py`, `tests/test_mvp_challenge.py`, `tests/test_data_files_valid.py`, `tests/test_api_mvp.py`, `tests/test_api_hunt.py`

- [ ] Add failing tests for stronger Boss stats, expanded MVP content validity, 30–80 round same-level geared fights, and a live playback floor that does not compress a 30-round Boss fight into a few seconds.
- [ ] Run the focused tests and confirm they fail for the new behavior.
- [ ] Add/adjust Boss data and scaling, preserving content references and making weak characters able to lose or flee.
- [ ] Implement a shared client event queue with slower Boss pacing for manual MVP and live hunt events; keep offline or oversized batches fast-forwarded.
- [ ] Run focused combat, MVP, hunt, and data tests; then run the full suite.
- [ ] Commit only the task files with a `Co-Authored-By` trailer.

### Task 2: Global and source-specific GM drop-rate overrides

**Files:**
- Modify: `server/db/schema.sql`, `server/settlement/drops.py`, `server/mvp/challenge.py`, `server/api/admin.py`, `server/api/content.py`
- Modify: `web/js/screen-more.js`, `web/js/api.js`
- Test: `tests/test_settlement_drops.py`, `tests/test_mvp_challenge.py`, `tests/test_api_admin.py`, `tests/test_admin_gm.py`

- [ ] Add failing tests proving precedence `source+item override > global item override > content rate`, validation in `[0, 1]`, and application to normal plus MVP drops.
- [ ] Add SQLite persistence for global item overrides and source/item overrides, with backward-compatible empty defaults.
- [ ] Centralize effective-rate lookup and make all drop rollers use it without changing pity or quantity behavior.
- [ ] Add GM-only read/update endpoints and a compact GM panel for searching/editing equipment and card rates.
- [ ] Run focused drop/admin tests and the full suite.
- [ ] Commit only the task files with a `Co-Authored-By` trailer.

### Task 3: Staged skill display and prerequisite locking

**Files:**
- Modify: `web/js/screen-build.js`, `web/style.css`
- Test: `tests/test_api_progression.py`, `tests/test_progression_skills.py`, and existing client/web tests if available

- [ ] Add a frontend-testable grouping helper or deterministic fixture for novice/first/second skill sections and prerequisite lock state.
- [ ] Confirm the test fails before the new grouped UI exists.
- [ ] Render three collapsible tier sections, show every skill, retain existing `requires` text, use dark-red styling for unmet prerequisites, and disable the learn button until the prerequisite is met.
- [ ] Keep the backend `can_learn` checks authoritative and ensure inherited skills remain visible but follow the approved interaction behavior.
- [ ] Run progression and client regression tests.
- [ ] Commit only the task files with a `Co-Authored-By` trailer.

### Task 4: Normal and random refining

**Files:**
- Modify: `server/loot/refine.py`, `server/api/inventory.py`, `web/js/screen-bag.js`, `web/js/api.js`
- Test: `tests/test_loot_refine.py`, `tests/test_api_inventory.py`

- [ ] Add failing unit tests for weighted random increments `0:10%`, `1:50%`, `2:35%`, `3:5%`, +10 cap, and unchanged normal refining.
- [ ] Add a mode-aware refine function with injectable RNG and extend the request model with a backward-compatible `normal` default.
- [ ] Return the chosen mode/increment/result in the API response and render a player choice between normal and random refine.
- [ ] Run focused refining tests and full API regression tests.
- [ ] Commit only the task files with a `Co-Authored-By` trailer.

### Task 5: Hunt status correctness, event cursors, and loading performance

**Files:**
- Modify: `server/api/hunt.py`, `server/settlement/engine.py`, `server/repositories/characters.py`
- Modify: `web/js/app.js`, `web/js/screens.js`, `web/js/api.js`
- Test: `tests/test_api_hunt.py`, `tests/test_settlement_engine.py`, `tests/test_hunt_strategy_api.py`, client tests as needed

- [ ] Add failing API tests for repeated status polling, warm start, no-time-advance, event-batch deduplication, and explicit combat state when no events exist.
- [ ] Trace and measure the status request path before changing it; keep settlement idempotent under concurrent requests.
- [ ] Add explicit state/cursor semantics and reduce redundant initial requests; make the client display “in combat” only when the server state or event stream supports it.
- [ ] Preserve offline settlement and existing potion, loot, and retreat behavior.
- [ ] Run focused hunt tests, client tests, and the full suite.
- [ ] Commit only the task files with a `Co-Authored-By` trailer.

### Task 6: Base and Job experience percentages

**Files:**
- Modify: `web/js/screens.js`, `web/js/screen-build.js` if needed, `web/js/app.js` if needed
- Test: existing client render tests and a new focused frontend calculation test or deterministic JS fixture

- [ ] Add failing tests for normal levels, zero/edge requirements, level-up boundaries, and novice/first/second Job curves.
- [ ] Add one shared percentage calculation using the existing level curve and render both current/next XP and percentage for Base and Job.
- [ ] Run focused client tests and the full suite.
- [ ] Commit only the task files with a `Co-Authored-By` trailer.

### Task 7: Integration verification and final review

**Files:**
- No new production files unless a prior review identifies a required fix.

- [ ] Run content validation and the complete pytest suite.
- [ ] Exercise the key API paths for MVP, GM drop settings, skill learning, refining, hunt status, and character progress.
- [ ] Inspect the final diff for unintended files and sensitive paths.
- [ ] Run the required independent Claude Code review; resolve Critical/High findings and repeat up to three rounds.
- [ ] Commit any review fixes and report tests, review rounds, and remaining observations.
