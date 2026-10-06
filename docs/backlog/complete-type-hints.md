---
status: next
lane: any
size: M
---
# Complete the type hints in kitlib

Hints are partial: dataclass fields use bare `list`/`dict` (`Rule.paths: list`, `Lane.owns: list`
in `kitlib/config.py`), and many functions take an untyped `config` (e.g. `lane_cycle.start`).
Full hints make the code easier to read and let a type checker do real work.

**Done when:** every function in `payload/kit-owned/.claude/kit/` has typed parameters and return
values, collections say what they hold (`list[str]`, `dict[str, str]`), and `config` parameters
are typed as `Config`.
