---
status: idea
lane: any
size: M
---
# Decide how an owner opts out of one of the kit's hooks

The installer merges four hook groups into `.claude/settings.json` (protected, ownership,
rules-check, lane-router) and records them in `.claude/kit/manifest.json` (decision 100,
`installer/settings_hooks.py`). If the owner deletes one, the next run finds it missing and adds it
back. Rules have an opt-out (`[protected] guard_kit = false`); hooks have none, so an owner who
doesn't want, say, the rules-check hook has to fight every re-run. Found in plan 08's review
(PR #28).

The protected hook is different from the other three: it is the backstop behind the deny rules,
the only guard on shell writes to the kit's config in `bypassPermissions` (decision 92), and what
stops the agent switching the local checks off (decision 34). Losing it silently weakens the
security story; losing rules-check or lane-router only loses a convenience.

Options:

1. **Respect a deletion recorded in the manifest.** A group the manifest says the kit wrote, now
   missing from `settings.json`, stays removed and the record is dropped. Matches how a deleted
   `.kit-new` isn't offered again. But the opt-out is invisible in review, can't be told apart from
   a group lost in a merge conflict or a tool rewriting the file, and works the same for the
   protected hook as for the others.
2. **A `[hooks]` table in `kit.toml`** (`rules_check = false`, …), read by the installer and by
   `kit check settings`. The choice is explicit, shows in a diff, and `kit.toml` is already guarded
   by the `guard_kit` ask rules, so an agent can't flip it quietly. Costs a config key, validation
   and tests.
3. **Keep re-adding and document it.** State in the installer's docs that the four hooks are part
   of the kit and the protected hook must not be removed; the run reports when it re-adds one. No
   new mechanism, but no way out for the three hooks that aren't safety checks.

**Recommendation:** option 2 for ownership, rules-check and lane-router only. The protected hook
gets no switch: re-adding it is the safe failure for a backstop, and its checks can already be
narrowed through `[protected]` (`paths`, `commands`, `secrets`, `guard_kit`). The installer prints a
line whenever it re-adds a group, so a deletion that comes back is never a surprise, and the docs
say why the protected hook always returns.

**Done when:** the owner has picked an option, recorded in the decisions log; the installer and its
tests (switched-off hook not re-added, protected hook always re-added with a notice) match it; and
the installer's docs describe the opt-out.

**Outcome:** option 2, decision 102. `[hooks]` has `rules_check` and `lane_router` only: ownership
already had `[project] ownership = "off"`. `kit check settings` doesn't check hooks at all, so only
the installer applies `[hooks]`.
