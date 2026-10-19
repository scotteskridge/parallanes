---
status: idea
lane: any
size: S
---
# Split installer/main.py

`installer/main.py` passed ~300 lines with plan 16 (308). The settings and hook planning
(`_plan_settings`) and the manifest reading are each self-contained and could move to their own
modules, leaving `main()` as the readable order of steps. The installer also has its own
`toml_string` beside `kitlib.lane_owners.toml_string`; one can go.

**Done when:** `main.py` is under ~250 lines with the same tests passing, and the kit has one TOML
string helper.
