---
status: next
lane: any
size: M
---
# Measure and cut the time each hook adds to a tool call

Users feel the kit's hooks on every tool call, not its test suite. Measured on 2026-10-06 (Windows,
Python 3.12): `kit hook protected` takes about 320 ms per call, of which Python start-up is about
90 ms; the rest is importing and running the kit. Every Bash, Edit and Write call pays it, plus the
ownership hook in a lane, so a long session adds minutes. Do this before the two-lane trial
(`prove-it-on-a-real-project`), so the trial measures the experience users will get.

Likely causes to check first: modules each hook imports but doesn't need (load them only on the
path that uses them), reading and validating all of `kit.toml` on every call, and the `sh` launcher
in front of Python.

**Done when:** each hook's time per call is measured on Windows and Linux and recorded; the
protected and ownership hooks take under about 150 ms on Windows, or the decisions log says why
not; and a test fails if a hook's import time grows past a set limit.
