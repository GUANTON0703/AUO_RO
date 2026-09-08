# ROtxt Feature Update BAT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a Windows batch file that updates the second computer's program files from GitHub while preserving its local player database and settings.

**Architecture:** The batch file runs from the repository root, refuses to overwrite uncommitted tracked code, backs up the local SQLite files, performs a fast-forward-only pull from `origin/main`, and refreshes dependencies with `uv sync` when available. It never copies or deletes `rotxt.db`, `.env`, `.venv`, or SQLite WAL/SHM files.

**Tech Stack:** Windows batch, Git, uv, existing ROtxt SQLite database and migration system.

---

### Task 1: Add the safe updater

**Files:**
- Create: `更新功能.bat`

- [ ] **Step 1: Add the updater with local-data safeguards**

The script must run from its own directory, require Git and the repository metadata, stop when tracked code has local edits, create timestamped backups of `rotxt.db` and its WAL/SHM sidecars when present, pull `origin/main` with `--ff-only`, and run `uv sync` if uv is installed.

- [ ] **Step 2: Verify the script statically**

Check that the script contains the required backup, pull, and dependency-update commands, and that it does not contain `git clean`, `del rotxt.db`, or any command that deletes local data.

### Task 2: Verify the repository change

**Files:**
- Test: no new test file; use the script's static checks and Git diff review.

- [ ] **Step 1: Review the exact diff**

Confirm only the updater and this plan are included, with no database, environment, or virtual-environment files staged.

- [ ] **Step 2: Run the existing test suite**

Run `uv run pytest -q` and record the result before committing.

### Task 3: Commit and schedule the GitHub upload

**Files:**
- Commit: `更新功能.bat` and this plan only.

- [ ] **Step 1: Run the independent code review**

Review the final diff with Claude Code and fix any Critical or High findings before committing.

- [ ] **Step 2: Commit with a Codex trailer**

Stage only the two explicit files after checking the staged list for secrets, then commit with a `Co-Authored-By: Codex <noreply@openai.com>` trailer.

- [ ] **Step 3: Schedule the upload**

Create a one-time local automation for 2026-09-09 08:30 Asia/Taipei that pushes the committed change to `origin/main`, reports success or failure, and does not alter unrelated work.
