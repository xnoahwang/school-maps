# PLAN.md

Older plans and verify receipts are in git history. This file keeps the current record only.

The page is the Calgary school ranking. The header pill says Prototype while coverage is Calgary. Community colouring, value for money, amenity counts, and the 2025-to-2026 assessed-value change are gone. Diploma placeholders, market rent, crime, class size, and the equity index are gone. Catholic schools with a PAT stay on the list.

## Plan (2026-10-24, align the repo)

Mode: `interactive` after this change. Design notes: skipped. Rule files already match cursor-prime v0.3.3 (`256dd8b`). The mode file is what still said `autonomous`.

**Goal.** Docs match the ranking page. Each download script keeps its own cache directory. Probe scripts and unused cache files are gone. Paths that must not be published are in `.gitignore`.

**Out of scope.** Rewriting the pipeline, re-downloading, changing `web/data/`, a git commit, and editing the protected cursor-prime rule files by hand.

**Done when.** `data/raw/` has no loose files. `scripts/verify.py` passes. `README.md`, `AGENTS.md`, and `.cursor/rules/project.mdc` name the same cache directories and the same verify command.

**Scale.** single-context

**Pre-flight.** `.cursor/cursor-prime-cloud-mode`, `.cursor/rules/project.mdc`, `.gitignore`, `scripts/build_data.py`, `scripts/fetch_ab_contacts.py`, `scripts/fetch_community_profiles.py`, `scripts/update_schools.py`, `scripts/_probe_acadia.py`, `scripts/_probe_ocr.py`, `scripts/_probe_sir.py`, `scripts/_repair_assurance.py`, `data/raw/`, `README.md`, `AGENTS.md`, `progress.md`, `PLAN.md`.

**Verify.** `.venv\Scripts\python -m py_compile` on the changed scripts, then `.venv\Scripts\python scripts\verify.py`.

## Verify (2026-10-24, align the repo)

`.venv\Scripts\python -m py_compile` on `build_data.py`, `fetch_ab_contacts.py`, `update_schools.py`, `fetch_community_profiles.py`, and `verify.py` exited 0. `.venv\Scripts\python scripts\verify.py` exited 0. Every check PASS, including `communities are boundaries and census figures (0 with map fields)` and `high schools are not ranked (111)`. `data/raw/` now has only `build/`, `ab_contacts/`, `cbe_directory/`, `cbe_kmz/`, `community_profiles/`, `assurance/`, and `logs/`. `git check-ignore` matches `data/raw/build/schools.json` and `scripts/_probe_*.py`. `web/data/` was not rewritten.
