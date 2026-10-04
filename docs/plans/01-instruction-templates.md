# 01 — Instruction templates

**Status:** Draft
**Branch / PR:** `plan/01-instruction-templates`
**Builds on:** ARCHITECTURE §4 (installed project), §5 (where instructions live), §8 (shared docs);
decisions 4, 7, 13

## Goal
The project-owned files an installed project starts with exist as tested templates: the instructions
agents read (`AGENTS.md`, `CLAUDE.md`, path-scoped rules), the human guides, and the docs scaffolding
(plans, conflict-free changelog fragments and backlog, design docs, code standards). Every template
renders cleanly from a known set of placeholders and stays inside its size budget.

## Out of scope
- Copying templates into a project, asking questions, overwrite handling: the installer (plan 08).
- `.claude/kit.toml` and its loader: plan 02, where the first code that reads it is written.
- `kit changelog build` (compiling fragments into `CHANGELOG.md`): plan 02, with the `kit` CLI.
- `settings.json` and permission rules: plan 03. Skills, reviewer: plans 06–07.
- Stack-specific content (Unity, Python): packs, plan 10. Project-specific rules: `/onboard`, plan 07.

## Open questions
1. **`BUILD-STATE.md` in MVP?** It's only useful if something keeps it true, and the skill that
   regenerates it (`/sync-state`) is a Later item. A stale status doc misleads agents.
   *Recommendation:* leave it out of the MVP templates; add it together with `/sync-state`.
2. **Design docs for every project?** `docs/design/` (VISION, DESIGN, decisions-log) fits
   product and game work; a small library may never use VISION.
   *Recommendation:* always ship `decisions-log.md` (every project makes decisions), and ship
   VISION and DESIGN as short stubs that say "delete if you don't need this".

## Reuse
- `docs/plans/_TEMPLATE.md` (this repo): becomes the project plan template, minus kit-specific lines.
- `docs/survey-hoem.md`: CLAUDE.md shape, universal hard rules, design-doc policy, the reviewer's
  severity scale, budgets, WORKFLOW.md section outline. Reference, not spec (decision 10).
- This repo's `AGENTS.md` / `CLAUDE.md`: the pattern of `CLAUDE.md` importing `@AGENTS.md`.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/templates/AGENTS.md` | New | Universal rules for any agent: project brief, stack, checking your work, hard rules (search before you create; never hide errors; never weaken, skip or delete tests; one task per session; flag undecided design questions; stay in scope; no `cd` prefixes; no secrets), how work flows (plans → branch per task → PR) |
| `payload/templates/CLAUDE.md` | New | `@AGENTS.md`, then Claude-specific parts: skills list, lane pointer (hook tells you your lane), edits to instruction files need approval, compaction notes |
| `payload/templates/.claude/rules/tests.md` | New | Path-scoped (`tests/**`): test-first for bugs, assert behaviour not "doesn't throw", never loosen a test to pass |
| `payload/templates/.claude/rules/design-docs.md` | New | Path-scoped (`docs/design/**`, `docs/plans/**`): what each design doc is for, grep a section rather than reading whole, log decisions |
| `payload/templates/.claude/rules/README.md` | New | How to write a rules file (`paths:` frontmatter, ≤200 lines); `/onboard` proposes project ones |
| `payload/templates/docs/ai/WORKFLOW.md` | New | Human guide: the daily loop, why each rule exists, context hygiene, warning signs |
| `payload/templates/docs/ai/parallel-lanes.md` | New | Human guide to lanes: concepts, the task cycle (`start` → work → `finish`), conflicts, removing a lane |
| `payload/templates/docs/plans/` | New | `_TEMPLATE.md`, `README.md` (index), `finished/.gitkeep` |
| `payload/templates/docs/backlog/` | New | `README.md` (one file per item, header fields), `_TEMPLATE.md`, `done/.gitkeep` |
| `payload/templates/docs/changelog.d/README.md` | New | Fragment naming (`<lane>-<task>.md`) and format |
| `payload/templates/docs/CHANGELOG.md` | New | Keep a Changelog skeleton, note that it's compiled from fragments |
| `payload/templates/docs/CODE-STANDARDS.md` | New | Universal standards: structure, errors, tests, "don't over-engineer", review severities |
| `payload/templates/docs/design/` | New | `decisions-log.md`; `VISION.md` and `DESIGN.md` stubs (per question 2) |
| `payload/templates/.gitignore`, `.gitattributes`, `.worktreeinclude` | New | Base ignores (secrets, `settings.local.json`, `.claude/worktrees/`), LF endings, worktree copy list |
| `payload/templates/PLACEHOLDERS.md` | New | The placeholder registry: name, meaning, example, which templates use it |
| `payload/kit-owned/.claude/kit/kitlib/render.py` | New | `render(text, values)`: replaces `{{name}}`; raises on an unknown or missing placeholder |
| `tests/test_render.py`, `tests/test_templates.py` | New | See Tests |

Placeholders (initial set): `project_name`, `project_description`, `stack`, `test_command`,
`integration_branch`, `kit_version`, `install_date`.

## Steps
1. Failing tests for `render()` (substitution, unknown placeholder, missing value, literal `{{` escaping).
2. Implement `kitlib/render.py` (stdlib only), writing nothing to disk.
3. Write `PLACEHOLDERS.md` and the template-wide tests (registry, budgets, frontmatter, links).
4. Write the instruction templates: `AGENTS.md`, `CLAUDE.md`, rules files.
5. Write the docs scaffolding: plans, backlog, changelog fragments, design docs, code standards.
6. Write the two human guides: `WORKFLOW.md`, `parallel-lanes.md`.
7. Write the git templates: `.gitignore`, `.gitattributes`, `.worktreeinclude`.
8. Review in a fresh context, fix the findings, open the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_render.py::test_substitutes_known_placeholders` | Values land where `{{name}}` was |
| `test_render.py::test_unknown_placeholder_raises` | A typo in a template fails loudly, never ships as `{{projct_name}}` |
| `test_render.py::test_missing_value_raises` | The installer can't render with a value left out |
| `test_render.py::test_escaped_braces_survive` | Templates can show literal `{{` (e.g. in docs about templates) |
| `test_templates.py::test_every_placeholder_is_registered` | Templates use only placeholders listed in `PLACEHOLDERS.md` |
| `test_templates.py::test_every_template_renders_with_sample_values` | No template leaves `{{` behind or fails to render |
| `test_templates.py::test_instruction_budgets` | `AGENTS.md` ≤ 80 lines; `CLAUDE.md` ≤ 40 lines; each rules file ≤ 200 lines |
| `test_templates.py::test_claude_md_imports_agents_md` | `CLAUDE.md` starts with `@AGENTS.md` |
| `test_templates.py::test_rules_files_have_paths_frontmatter` | Every rules file (except README) is path-scoped |
| `test_templates.py::test_relative_links_resolve` | Links between templates point at files that exist in the template set |
| `test_templates.py::test_templates_are_lf` | No CRLF in any template |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] CHANGELOG, ROADMAP and plans index updated; open questions 1–2 answered and logged

## Notes after implementation
<!-- Filled in at wrap-up. -->
