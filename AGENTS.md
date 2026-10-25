# AGENTS.md

<!-- cursor-prime-cloud:begin -->
## cursor-prime-cloud

Follow these rules for every task in this repo. Rule text is [cursor-prime](https://github.com/xnoahwang/cursor-prime) v0.3.3 (`256dd8bdd2b2`) plus the cloud overlay. Where the overlay and the rules disagree about waiting for a human, the overlay wins.

Installed default mode: `autonomous`.
At runtime, `CURSOR_PRIME_CLOUD_MODE` (`autonomous`, `plan-only`, or `interactive`) overrides `.cursor/cursor-prime-cloud-mode`.

Do not edit this marked section by hand. Re-run cursor-prime-cloud `install.sh` to refresh it.

Slash commands from cursor-prime are in `.cursor/commands/` (`/plan`, `/verify`, `/loop`, `/debug`, `/grill`, `/handoff`, `/delta`, `/submission-init`).

### Cloud overlay

# Cloud mode (cursor-prime-cloud)

This rule is layered on top of `behavior.mdc` and `maintainability.mdc`. Those files are the cursor-prime originals. Do not edit them to "fix" the gate.

When this overlay conflicts with `behavior.mdc` or a slash command **only** about waiting for a human (`GO`, design-check approval, or a clarifying-question reply), **this overlay wins**. Task class, surgical changes, simplicity, verify receipts, delta reports, and maintainability tiers still apply.

## Which mode

1. If `CURSOR_PRIME_CLOUD_MODE` is `autonomous`, `plan-only`, or `interactive`, use that.
2. Otherwise read `.cursor/cursor-prime-cloud-mode` (one word).
3. If neither is set, use `autonomous`.

A later message that is exactly `GO` approves the plan already written: implement it (unless it is already done) and produce the Verify Receipt and Delta Report. Do not ask for `GO` again.

## autonomous (default)

No human is waiting in this session. Do not block on `GO`, clarifying questions, or design-check approval.

1. Still classify the task. On non-trivial work, still write a full `<plan>` block (Goal, Out of scope, Done when, Scale, pre-flight file list, verify) **before** the first edit to project source.
2. Recording that plan is allowed before other edits. Put it in the pull request description under `## Plan`. If this run is not opening a pull request, write the same section to `PLAN.md` at the repo root.
3. State assumptions in the plan instead of asking. If the request cannot be interpreted without guessing into a destructive or out-of-scope change, stop after the plan and say what is missing.
4. Then implement. Do not wait for `GO`.
5. When you open or update a pull request after implementation, put a **Verify Receipt** (exact command and exact output) and a **Delta Report** in the PR body under `## Verify`. A chat-only "done" does not replace that section when a PR exists.
6. If you must touch a file that was not on the pre-flight list, add it to `## Plan` and continue. Do not wait for approval.

## plan-only

Do steps 1–3 of autonomous, write the plan to the PR `## Plan` section or to `PLAN.md`, then **stop**.

Do not implement, and do not edit source files other than the plan record. Do not claim a Verify Receipt for work you did not run. A later `GO`, or a switch of mode to `autonomous`, is the approval to implement.

## interactive

A human is in the session. Follow `behavior.mdc` Plan Gate: output `<plan>` and wait for literal `GO` before state-changing tools. Still produce a Verify Receipt and a Delta Report. When a pull request is part of the task, also put those under `## Verify` in the PR body.

## Do not

- Do not skip the `<plan>` block on non-trivial work because nobody will type `GO`.
- Do not skip the Verify Receipt or the Delta Report in `autonomous` mode.
- Do not fork `behavior.mdc` or `maintainability.mdc`. Mode lives here and in `.cursor/cursor-prime-cloud-mode`.

### Coding Behavior

# Coding Behavior

Karpathy-derived discipline rules. Always on for this project.

## Task Class

Classify every request **before any state-changing tool** (Write, StrReplace, Delete, Shell that modifies files, etc.):

- **Trivial** (Plan Gate **off**) — **only** these:
  - Q&A, explanation, or read-only exploration (no file edits).
  - A **single-line** literal or typo fix in **one** file at a **known** location (e.g. fix a typo in one string). Multi-line edits are **never** trivial.
  - User reply is literally `GO` continuing an **already approved** plan from this session.
- **Non-trivial** (Plan Gate **on**) — **everything else**, including:
  - **Any** file create, modify, or delete — code, tests, configs, **README, docs, markdown, AGENTS.md**, comments (if more than one line changes), scripts, rules.
  - New sections, paragraphs, or tables in documentation (even one file).
  - New logic, refactors, new commands/endpoints, or multiple files.
- **Workflow-scale** — 20+ files, multi-module migration, or parallel independent workstreams. Plan Gate **on**; the plan must include phased steps and warn that full completion may need multiple sessions or subagents.

**Hard rule:** If the task would use Write, StrReplace, Delete, or a shell command that changes files, it is **non-trivial** unless it matches the trivial whitelist exactly. "Simple" or "just docs" does **not** exempt you. When in doubt, plan first.

## ⚠️ MANDATORY: Plan Gate
**On every non-trivial task, before the first state-changing tool call, you MUST:**
1. Output a `<plan>` block describing the intended changes (include **Out of scope**, **Done when**, and **Scale** — see `/plan`).
2. STOP and wait for the user to reply with the literal word `GO`.
3. Do NOT call Write, StrReplace, Delete, or any state-changing tool until the user has sent `GO`.

Reading files and answering questions does NOT require a plan. Exploration reads during the plan phase (before `GO`) are allowed.

If you already started editing without a plan, STOP immediately, output the plan, and wait for `GO` before further edits.

## Design check (optional)

Before the implementation `<plan>`, when the request is **ambiguous**, **greenfield**, or clearly **workflow-scale**, briefly refine intent:

1. Ask short clarifying questions only if needed (prefer one focused question). Prefer a short **grill** when branches matter: chase open decisions until the important forks are resolved (or the user says skip).
2. Present the design in **short chunks** the human can accept or correct.
3. Then output the implementation `<plan>` and wait for `GO`.

Skip when the user already gave a concrete approach, a file-level brief, or says to skip design/grill. Note `Design notes: skipped` | `grilled: <one-line>` inside the `<plan>` when useful. This does **not** replace Plan Gate. User-invoked deep alignment: `/grill`.

## Shared language (optional)

For longer-lived product repos, an optional root **`CONTEXT.md`** may hold the project’s shared language: glossary of domain terms, and pointers to hard decisions (short ADR links or bullets). Prefer those terms in chat and code names so the agent does not use twenty words where one will do.

Doc split (do not merge into one blob):

| Doc | Role |
|-----|------|
| `CONTEXT.md` | Domain jargon / ubiquitous language |
| `AGENTS.md` | Layout, conventions, verify, forbidden zones |
| `@project` / `project.mdc` | Stack, entry points, commands |

If `CONTEXT.md` is absent, do **not** invent a mandatory one for tiny or assessment tasks. Create/update it only when the user asks, after a `/grill` that produced new terms, or when greenfield domain language would otherwise stay undocumented.

## Explore Cheap

Before editing, minimize context cost:

- **Search first** — use grep or semantic search before reading whole files.
- **Read minimally** — use offset/limit on large files; do not read files outside the pre-flight list unless you state why and get approval (or include them in an updated plan before editing).
- **Pre-flight applies to reads** — the file list in the plan is the boundary for both reads and writes unless exploration-only reads are listed separately.

## Simplicity
- Build only what was asked. No speculative abstractions, no unrequested "flexibility".
- If 200 lines could be 50, rewrite.
- **Exception (new surfaces):** module headers, public API docs, and entry docs required by `maintainability.mdc` are part of a shippable deliverable — not speculative extras. See intensity tiers there.

## Surgical Changes
- Don't touch adjacent code, comments, or formatting.
- Remove only imports/symbols your change made unused. Mention unrelated dead code; don't delete it.
- Every changed line must trace to the request.
- Respect **Protected paths** in `@project` if defined — do not edit them unless listed in the pre-flight file list.
- **New files** you create should still meet `maintainability.mdc` (headers, public API docs, layout).

## Pre-flight File List
Inside the `<plan>` block, include an explicit list of every file you intend to create, modify, or delete.
If during execution you discover you need to touch a file not on that list, **STOP** and explain before continuing.

## Goal-Driven
- Restate the task as a verifiable goal before coding.
- Each completed block needs a verify step proving PASS/FAIL.
- For new modules or public APIs, **Done when** must include the maintainability checklist in `maintainability.mdc` (tier C), or the full `/handoff` bar (tier D) when the user asked for handoff-quality delivery.

## Bite-sized steps (workflow-scale)

When **Scale** is `workflow-scale`, the `<plan>` must include a **Task breakdown**: an ordered list of small steps, each with target file paths and a verify / Done-when check. Prefer steps small enough to finish and check in one pass.

During execution, after completing a breakdown step, do a quick two-stage self-check before the next step: (1) matches that step’s plan/spec, (2) no obvious regression or quality miss. Do not start a separate review ceremony unless the user asks. Stay inside the credit guard — no multi-hour unattended subagent runs.

## Systematic debugging

When hunting a bug (or the user runs `/debug`), before broad edits:

1. **Reproduce** — exact failing command/symptom (or state what blocks repro).
2. **Minimise** — shrink the failing case when cheap (smaller input, single path).
3. **Hypothesize** — one primary cause (and optional secondary).
4. **Instrument / evidence** — smallest check that would confirm/reject (log, test, bisect read).
5. **Fix** — only then change code.
6. **Regression check** — re-run the failing verify; add or extend a test when the project already has a harness and the bug could return.

Do not spray unrelated changes hoping the bug disappears. `/loop` still applies after a fix if verify fails.

## Verify Receipt
When claiming verification, paste the exact command you ran and its exact output (or relevant tail).
"Tested and works" without a transcript is not acceptable for non-trivial tasks.
Prefer verify commands documented in `@project` when available.

**Hard verifier:** For non-trivial tasks, you must **run** the plan's verify command(s) before declaring done. Inspection-only or self-graded passes are not valid when a hard gate exists (test, lint, build, typecheck). No transcript = not done.

## Loop Discipline (light loop)

Session-only fix-and-retry after Plan Gate `GO` — not unattended cron or overnight automation.

### Iterate until pass or cap
When verify FAILs and the user wants another pass (or sent `/loop`):
1. Pick the **single highest-impact** failure.
2. Make the **smallest** change that addresses it.
3. Re-run **all** verify commands from the plan.
4. Repeat until all PASS or **max iterations** reached (default **8**; plan or user may set lower).

On cap: STOP, summarize what changed and what still fails, update `progress.md` Loop State if pausing. Do not silently continue.

### Loop worthiness
Before proposing iterate-until-green on `workflow-scale` tasks, all four must be true:
- Task repeats at least weekly
- Hard gate exists (test, lint, build, typecheck)
- Agent can finish end-to-end without mid-task human steps
- Done is objective, not taste

If any is false: one plan + GO + single execution pass unless the user explicitly sends `/loop`.

### Loop state
During multi-iteration work, update `progress.md` **Loop State** when stopping at iteration cap or before pausing mid-task.

### Credit guard
Each iteration re-sends growing context. Fix one failure per pass; no parallel fix attempts unless the plan says so.

## Edge Case Checklist
Before declaring a non-trivial task done, for each new public function, CLI command, or HTTP endpoint, briefly note (one line each):
- Empty / missing input behavior
- Malformed / wrong-type input behavior
- Large or unusual scale behavior
- Which error paths exist and how they're handled

If a case is intentionally not covered, say so explicitly so the user knows.

## Self-Review (Delta Report)
Before declaring done on any non-trivial task, output a **Delta Report**, then the final summary:

  Delta Report
  - Files changed: <path>  (+N / -M)   one line per file
  - Outside plan: ⚠️ <path> — <one-line reason>   (omit section if none)
  - Signatures changed: <old> → <new>              (omit section if none)
  - Symbols deleted: <name> — <one-line reason>    (omit section if none)
  - Verify: <command>  →  <pass/fail + key output>

If everything matches the plan, the report can be a single line: "Delta: matches plan; verify passed."
This is non-negotiable. Skip only for trivial tasks.
If the user ran `/verify`, reference its outcome in the Delta Report when relevant.

## Session Continuity

After a long session or if context was compacted, **before making further edits** restate the pre-flight file list and out-of-scope boundaries in one sentence — do not silently expand scope.

When pausing a non-trivial task, update `progress.md` **Handoff** (plan status, files touched, next verify command) so the next session can resume without re-exploring the repo.

## Exploration First
- Read relevant files and check current API docs before acting. State assumptions explicitly.
- If multiple interpretations exist, list them — don't pick silently.
- If genuinely unclear after extracting intent, ask one focused question.

## Output Format
- After a task: what changed, any decision worth noting, watch-outs — 2–3 lines max (after the Delta Report).
- No "Great!", no restating the request, no "I hope this helps".
- Diffs over full-file rewrites unless creating a new file.

## Code
- Standard naming. No `var1`, `tmp2`. Isolate Logic / IO / Action.
- Prefer conventions already in the repo; if none exist (greenfield), establish them and write them into `AGENTS.md` (and `@project` when the stack is fixed) — do not leave an undocumented one-off style.

## Persistence (global settings package — no per-project install)
- **Global User Rules** (from `install.ps1`) include **Coding Behavior + Maintainability** so every project gets Plan Gate, Karpathy discipline, and handoff comment/layout standards after one paste into Cursor Settings.
- `progress.md` is the working log. If it does not exist, create it at the project root the first time you complete a milestone, using this structure: Current Focus / Completed / Next Steps / Known Issues / Handoff. Update it after each milestone or before pausing a task.
- `.cursor/rules/project.mdc` holds project context (tech stack, key paths, commands, verify commands, optional protected paths). Create or update it once stack decisions are finalized — don't create an empty placeholder preemptively.
- `AGENTS.md` / `README.md` are the successor entry points; keep them truthful when you add run paths, layout, or verify steps.
- Do NOT auto-create `.gitignore`; the user's global gitignore already covers common noise (node_modules, .venv, __pycache__, Cursor caches). Add project-specific ignores only when asked.

## Submission docs (opt-in only)

**Default: off.** Do **not** create, detect, or update `submission/` on ordinary non-trivial work. Prefer **inline why-comments** (and Maintainability tiers for public APIs / file headers) unless the user explicitly wants write-up docs.

Enable `submission/` **only** when one of these is true:

1. User ran **`/submission-init`**, or
2. User explicitly asked for handover / reflection / appendix / assessment write-up docs (or named the `submission/` trio).

When enabled:

1. Scaffold from the local cursor-prime clone if missing:
   - Prefer `$env:USERPROFILE\cursor-prime\payload\submission\*.md` (Windows) or the user’s known clone path (e.g. `C:\XW\cursor-prime\payload\submission\`).
   - If the clone cannot be found, create the three Title Case files (Handover / Reflection / Appendix) rather than skipping.
2. Grow the three docs during the task; English body; Title Case headings.
3. List `submission/*` on the pre-flight file list when creating or editing them.

If submission is not enabled for the task, note that in plan **Out of scope** when relevant (e.g. interview pad with docs optional).

### Maintainability

# Maintainability (handoff-ready)

Code must run **and** be readable by the next human and the next AI. These standards ship in **global User Rules** (via `install.ps1`, merged after Coding Behavior). Intensity is **tiered** so small fixes stay cheap.

## Intensity tiers

Apply the matching tier; do not over-document trivial work.

| Tier | When | Required |
|------|------|----------|
| **A — Trivial** | Read-only Q&A, or single-line typo in one known place | No extra docs |
| **B — Edit existing** | Change files that already exist; no new public API | Surgical only; update docs **only** if behavior/layout/conventions changed and that update is on the pre-flight list |
| **C — New surface** | New file, new module, or new public function/CLI/endpoint | Full checklist below for everything you add |
| **D — Milestone / `/handoff` / assessment** | User ran `/handoff`, interview/CoderPad deliverable, or explicit ship/hand off | Full checklist + refresh `README.md` / `AGENTS.md` / `@project` as needed. **`submission/` trio only if** the user explicitly asked for those docs or ran `/submission-init` |

**Not scope creep:** For tier C/D, module headers, public API docs, and entry docs (`README.md`, `AGENTS.md`) are part of the deliverable — even if the user only named the feature.

## Public API documentation

Every new **public** function, class, CLI command, or HTTP endpoint must have the language-idiomatic docstring / doc comment covering:

- **Why / responsibility** (not a line-by-line restatement of the body)
- **Parameters and return** when non-obvious
- **Errors / failure modes** the caller must handle
- **Invariants** or important constraints (auth, ordering, idempotency, units)

Private helpers: document only non-obvious rules. Prefer clear names over noise comments.

## Module / file headers

Every **new** source file that owns a concern gets a short file-level comment (about 2–5 lines):

- What this file is responsible for
- What it deliberately does **not** own (if helpful)

## Comments (quality bar)

- Default explanation for judgment is **inline why-comments** (and public API / file headers per tiers above) — not a separate `submission/` folder.
- Write comments for **why**, tradeoffs, and non-obvious business rules.
- Do **not** write comments that only restate the next line of code.
- Do **not** leave commented-out dead code in the deliverable.

## Layout and naming

- Follow the language’s common layout (`src/`, `lib/`, `tests/` / `__tests__`, etc.). Do not dump unrelated modules in the repo root without a reason stated in `AGENTS.md`.
- Names: clear and conventional. No `var1`, `tmp2`, `data2`, `helper`.
- Keep **Logic / IO / Action** separable where the codebase already does (or when starting greenfield).

## Repository entry docs (minimum)

Projects scaffolded by cursor-prime should keep these truthful:

- **`README.md`** — what the project is, how to install/run, how to test/verify.
- **`AGENTS.md`** — map for humans and AIs: layout, conventions, verify commands, forbidden zones.
- **`.cursor/rules/project.mdc`** — fill tech stack, entry points, and verify commands once the stack is known (do not leave forever as `[TBD]` after the first real milestone).

If this task creates the first real code in a greenfield repo and those files are still stubs, update them in the same task (list them on the pre-flight file list).

## Greenfield / no prior convention

When `/plan` pattern grounding finds **no** existing convention:

1. **Establish** naming, error handling, test location, and layout for this repo.
2. **Write them down** in `AGENTS.md` (and `@project` when stack is fixed).
3. Follow that convention for the rest of the task.

Do **not** invent a one-off style and leave it undocumented.

## Done when (maintainability)

For tier C/D non-trivial tasks, the task is incomplete until:

- [ ] New public APIs have proper docstrings / doc comments
- [ ] New modules have file headers
- [ ] Layout matches stated conventions (or conventions were written in `AGENTS.md`)
- [ ] `README.md` / `AGENTS.md` / `@project` reflect any new entry points, commands, or verify steps you added
- [ ] `submission/` trio updated **only if** submission was explicitly enabled for this task (`/submission-init` or user request)
- [ ] A successor could find “where to start” and “how to verify” without chatting with you

Tier A/B: skip the checklist unless docs became wrong because of your change.

## Relationship to Plan Gate / Surgical Changes

- Plan Gate, pre-flight lists, and verify receipts still apply (Coding Behavior / `behavior.mdc`).
- Surgical Changes still apply to **existing** code you were not asked to reformat.
- Maintainability requirements for **new** surfaces override “only what was asked” when “what was asked” implies shippable code.
- Global User Rules may already include this entire Maintainability section — do not wait for an in-repo `maintainability.mdc` to apply these standards.

### Reminder

Mode from `CURSOR_PRIME_CLOUD_MODE` or `.cursor/cursor-prime-cloud-mode` overrides any "stop and wait for GO" line above and in `/plan`. `autonomous` writes the plan, records it, and continues. `plan-only` writes the plan and stops. `interactive` waits for `GO`.
<!-- cursor-prime-cloud:end -->
## Project: Calgary school ranking (by PAT)

Start with `README.md` (what it is, how to run it, data definitions, limitations). `PLAN.md` holds the current plan and verify record. The page that opens is the ranking list and school map.

### Layout
- `scripts/build_data.py`: official community data is downloaded, joined, and scored. Cache is `data/raw/build/`. Output goes to `web/data/`.
- `scripts/build_zones.py`: CBE attendance areas and walk zones for each published program, from the public finder KMZ files. The ranking map draws a zone when a school is clicked. Community lists on a zone are stored for the regular program. Run it after `build_data.py`.
- `scripts/fetch_cbe_directory.py`: CBE school directory (name, phone, address, website, grades, programs) from the public fragment API. Output is `web/data/cbe_directory.json`. The page uses it for program and grade filters.
- `scripts/fetch_ab_contacts.py`: Alberta's public school directory (phone and website). Cache is `data/raw/ab_contacts/`. Output is `web/data/ab_contacts.json`. The page fills a phone or website only when the school does not already have one.
- `scripts/fetch_community_profiles.py`: 2021 census fields from the City's community-profile PDFs. Output is `web/data/community_profiles.json`. The HTML profile pages do not contain the tables. Not part of the weekly school update.
- `scripts/fetch_assurance.py`: the six Assurance survey measures from each CBE School Improvement Results PDF. Output is `web/data/assurance.json`. The summary table is an image. Not part of the weekly school update, and not mixed into the PAT score.
- `scripts/update_schools.py`: refreshes the CBE directory, Alberta contacts, and CBE zones. Writes a file only when the text changed. Does not download home values. `--install-task` registers a weekly Sunday 09:00 run. Its log is `data/raw/logs/update_schools.log`.
- `scripts/store.py`: writes a generated file only when the text changed. The fetch scripts use it. It does not download.
- `scripts/verify.py`: data sanity checks (exit 1 on failure). It reads `web/data/` and does not download.
- `tests/`: pytest for school-name folding and Assurance row grouping. `requirements-dev.txt` adds pytest. It does not download.
- `web/`: static front end with no build step. `rank.js` decides who is listed and how rows sort. `zone.js` chooses the attendance zone and fills the panel. `map.js` draws points and polygons. `app.js` loads JSON and connects those three. `zones.geojson` is fetched the first time a school is selected. `index.html` sets `ASSET_VERSION` for CSS, scripts, and `web/data/`. All UI strings live in `i18n.js` (en, zh, zh-Hant, fr, ja, ko), and any new key must be added to every language. The header pill is Prototype while the page covers Calgary. Ranking rules are checked with `node --test web/rank.test.mjs`.
- `data/raw/`: download cache. **Do not commit.** One directory per script: `build/`, `ab_contacts/`, `cbe_directory/`, `cbe_kmz/`, `community_profiles/`, `assurance/`, `logs/`. `web/data/` is generated but committed.

### Conventions
- Python 3.12 in `.venv`. `rapidocr-onnxruntime` 1.4.4 does not run on 3.13. Dependencies are pinned in `requirements.txt`. Names are snake_case. Every file has a module docstring header, and public functions have docstrings.
- Missing or suppressed values are `None`/`null` and appear as "no data". Never coerce them to 0. Do not invent data (for example rent).
- Error handling: a failure in a required source (boundaries, schools, PAT) exits non-zero. A failure in an optional source sets its fields to null and adds the source to `meta.json → sources_failed`.
- Code and comments are in English.

### Verify
```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/verify.py
node --test web/rank.test.mjs
```

`.github/workflows/ci.yml` runs those three on a push or pull request to `main`.

A rebuild that also refreshes zones is `build_data.py`, then `fetch_cbe_directory.py`, `fetch_ab_contacts.py`, `build_zones.py`, then `verify.py`. `fetch_community_profiles.py` and `fetch_assurance.py` stay out of that weekly path.

### Forbidden zones
- Do not edit the `cursor-prime-cloud` marked section above, or `.cursor/rules/behavior.mdc`, `maintainability.mdc`, or `cloud-overlay.mdc`. Re-run the installer instead.
- Do not commit `.cursor/cursor-prime-cloud-backups/`, `data/raw/`, or `scripts/_probe_*.py` / `scripts/_repair_*.py`.
- Rule text matches cursor-prime v0.3.3 (`256dd8b`). `.cursor/cursor-prime-cloud-mode` is `interactive`.
