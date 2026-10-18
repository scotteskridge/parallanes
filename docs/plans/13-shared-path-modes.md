# 13 — Shared path modes

**Status:** In progress
**Branch / PR:** `plan/13-shared-path-modes` · PR link once open
**Builds on:** backlog `shared-path-modes` (step 3 of the v0.2 build order, decision 110); decisions
41 (the hook fails open), 96 (the boundary check fails closed), 97 (who owns a file two lanes
claim), 111 (repo-wide files were left to this item); ARCHITECTURE §6 "Ownership", §8;
`docs/survey-lanekeeper.md` (`append_only`, `escalate`, steward); two-lane trial F8 and F11

## Goal
A project can say how each shared path is shared: **open** (any lane changes it, today's only
kind), **append** (any lane adds a file; changing or deleting an existing one needs a person) or
**ask** (any change needs a person), each with an optional **steward**, the one lane that changes it
without asking. Repo-wide files like `.gitignore` then have a way through: a lane asks, the owner
says yes, and the commit lands (in the trial, F8, the yes was given and the commit was refused).

## Out of scope
- A command that edits `kit.toml` (`lanes allow`): decision 111 still holds.
- Putting the shared-path notes into the PR body or as GitHub annotations: printed only, here
  (follow-up idea).
- Making `docs/design/decisions-log.md` appendable by fragments: backlog `decision-log-fragments`
  (step 4).
- CODEOWNERS from lanes and stewards (`codeowners-from-lanes`, later).

## Open questions
1. **The `kit.toml` shape.** *Recommendation:* a new `[[shared]]` table per zone, beside the
   existing key:
   ```toml
   [[shared]]
   paths = ["docs/changelog.d/**", "docs/health/**"]
   mode = "append"                # "open", "append" or "ask"

   [[shared]]
   paths = ["/.gitignore", "/package.json"]
   mode = "ask"
   steward = "platform"           # optional: a lane name
   ```
   `shared_paths` stays and means mode `open`, so a v0.1 `kit.toml` behaves exactly as before. If
   the project writes either key, the defaults are replaced (as `shared_paths` does today). A path
   in two zones takes the stricter mode (ask > append > open); a steward that names no lane is a
   load error. *Why:* one table per zone keeps a steward next to the paths it looks after, and
   keeping `shared_paths` means nobody has to migrate. *What would change it:* if you'd rather have
   one way to write it, `shared_paths` becomes an error pointing at `[[shared]]` (a breaking
   change for v0.1 users).
2. **Which mode the default shared paths get.** *Recommendation:* `append` for
   `docs/changelog.d/**` and `docs/health/**` (only ever gain files); `open` for `docs/backlog/**`,
   `docs/plans/**` and `docs/design/decisions-log.md`. *Why:* `/wrap-up` moves the finished backlog
   item to `done/` and plans gain a Status and notes after implementation, so `append` there
   would ask at every task's end; the decisions log is one file every lane appends to, which
   `append` would block until `decision-log-fragments`. No default `ask` zone: which repo-wide files
   a project has depends on its stack, so the `kit.toml` template shows `.gitignore` and
   `package.json` as a commented example. *What would change it:* if a prompt at wrap-up is fine
   with you, plans can be `append` too.
3. **What "needs a person" means when the work lands.** The ownership hook asks at edit time (a
   permission prompt), but the boundary check, which runs at commit, `lanes finish` and CI, can't
   see that yes. *Recommendation:* for shared zones the boundary check **passes and lists** the
   change ("2 shared-path changes a person approved or should look at: …"), instead of refusing.
   Files another lane owns, files no lane owns and `kit.toml` are refused as now. *Why:* these
   paths are fully open today, so listing is still stricter than today; refusing would bring F8
   back (the owner says yes, the commit is refused). The steward lane changes its zone with no
   prompt and no listing. *What would change it:* if you want shared zones to fail closed like the
   rest, an `ask` change would then land only from the steward lane or a branch that isn't a
   lane's, and the steward becomes required in practice.

Settled without a question (say if you disagree): an **existing** file is one present where the
task branch left the integration branch (its merge base), in the hook, pre-commit and `lanes
finish` alike, so a fragment the lane added earlier in the same task can still be edited freely.
In a merge commit, a file present in either parent is existing. A rename is a delete plus an add
(as everywhere in the kit), so renaming another lane's fragment is a change to an existing file.

## Reuse
- `kitlib/lane_owners.py` (`Owners`, `judge`, `Fix`): the one rule the hook and the boundary check
  share (decision 97); modes go in here, so both stay the same by construction.
- `kitlib/config.py` (`_lane_settings`, `_globs`, `lanes_only`, `DEFAULT_SHARED_PATHS`): loading and
  strict validation; `lanes_only` must read `[[shared]]` too, since old `kit.toml`s judge a lane.
- `kitlib/gitfiles.py` (`touched_*`, `deleted_*`, `merge_base`, `show`, `touched_by_merge_commit`):
  add "what existed at base" beside them.
- `kitlib/lane_hooks.py` (`ownership_reason`), `kitlib/lane_boundary.py` (`check`, `advice`),
  `cli.py` (`check_lanes`), `kitlib/lane_cycle.py` (`_within_lane`): the callers.
- `lane_hooks.py` briefing ("Shared with every lane: …") and `lanes status`: show the modes.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `kitlib/shared_zones.py` | New | `Zone(paths, mode, steward)`, loading `[[shared]]` + `shared_paths`, defaults, stricter-mode lookup (keeps `config.py`, already 446 lines, from growing) |
| `kitlib/config.py` | Edit | `[[shared]]` top-level key; `LaneSettings.shared` zones; steward checked against lane names; `lanes_only` reads it |
| `kitlib/lane_owners.py` | Edit | `judge` takes whether the file existed at base; returns "allowed", "listed" or a refusal |
| `kitlib/gitfiles.py` | Edit | `existed_at(root, ref, paths)` in one `git ls-tree` call |
| `kitlib/lane_boundary.py`, `cli.py`, `lane_cycle.py` | Edit | Listed changes printed as notes, exit code unchanged |
| `kitlib/lane_hooks.py` | Edit | Hook asks for append/ask zones (naming the steward); briefing shows modes |
| `templates/.claude/kit.toml.tmpl`, `templates/docs/ai/parallel-lanes.md.tmpl` | Edit | `[[shared]]` defaults and the commented repo-wide example; the guide's shared-paths section |
| `docs/ARCHITECTURE.md` §6, §8; `docs/decisions-log.md`; CHANGELOG fragment | Edit | The design and the answers |

## Steps
1. Failing tests first: config loading (shape, defaults, errors), `judge` per mode × steward ×
   existing, the boundary check's notes, the hook's prompt text.
2. `shared_zones.py` and the config changes.
3. `existed_at` in `gitfiles`, then `judge` and its callers (hook, `check lanes`, `lanes finish`).
4. Briefing and `lanes status` lines; templates and the guide.
5. Live check: a scratch two-lane repo, `claude -p` in a lane edits another lane's changelog
   fragment (asks) and adds its own (doesn't); pre-commit lists the approved one.
6. Docs, decisions, CHANGELOG; reviews (repo `reviewer` + a general-purpose reviewer in round 1).

## Tests
| Test | Proves |
| --- | --- |
| `test_shared_zones.py` (new) | Shape, `shared_paths` = open, defaults replaced when either key is written, stricter mode wins, unknown mode/steward errors name the key |
| `test_lane_owners.py` (extended) | Each mode × steward × added/existing gives the right outcome; `kit.toml` in a zone is still no lane's |
| `test_lane_boundary.py` (extended) | Append: an add passes silently, an edit or delete is listed, exit 0; ask: listed; steward: silent; a rename of an existing fragment is listed; merge commit uses either parent; paths with spaces |
| `test_hook_ownership.py` (extended) | Asks for an existing file in an append zone, not a new one or one added earlier in the task; names the steward; v0.1 `kit.toml` unchanged |
| `test_lane_cycle.py` (extended) | `lanes finish` prints the notes and still finishes |
| `test_templates.py` (extended) | Template defaults load and equal `DEFAULT_*` |
| `tests/live/` | The live check in step 5 |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] Live check in `tests/live/` run with `--live`
- [ ] CHANGELOG, ROADMAP, backlog item (to `done/`) and decisions log updated

## Notes after implementation
- **Existed, in a merge:** at the merge base, or in `MERGE_HEAD`, rather than "in either parent".
  HEAD holds the lane's own earlier additions, which the general rule treats as free; `MERGE_HEAD`
  holds what other lanes brought in.
- **`LaneSettings.shared_paths` stays**, now the flat list of every zone's paths (all modes are
  shared for the owner rule). The defaults keep v0.1's order, so `test_lane_defaults` passes
  unchanged. `LaneSettings` built by hand from a list alone gets an `open` zone (the defaults get
  their modes), so code and tests that build it the v0.1 way behave as before.
- **A steward on an `open` zone is an error:** every lane already changes an open zone freely.
- **`lanes status` unchanged:** it never listed shared paths; only the session briefing shows them,
  now by mode with each steward.
- **Template test:** the `# shared_paths =` line left the `kit.toml` template (the `[[shared]]`
  examples replace it), so `test_rendered_kit_toml_lane_example_loads_when_uncommented` no longer
  uncomments a line by that key; two new tests check the `[[shared]]` examples load and equal the
  defaults.
- **Hook cost:** only an edit to an existing-looking file in an `append` zone, by a lane that isn't
  its steward, pays for git calls (merge base, then `ls-tree`). When git fails, the edit counts as
  an addition: the hook fails open (decision 41).
- **Live check** (`tests/live/test_shared_path_modes.py`) passed on its first run: in
  `bypassPermissions`, the hook's `ask` stopped the edit to another lane's fragment, as decision
  92's live check found for ask rules.
