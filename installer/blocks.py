"""Managed blocks in files the project owns, such as `.gitignore` (decision 100).

The kit's lines sit between two marker lines and only that text is ever rewritten: the owner's
lines keep their bytes, line endings and BOM. A lone, doubled or reversed marker means someone
edited the block by hand: that is an error to show, never something to repair silently (the
pattern from lanekeeper's CODEOWNERS handling, `docs/survey-lanekeeper.md`).
"""

BEGIN = "# >>> claude-code-lanes-starter (managed: the installer rewrites the lines between these markers)"
END = "# <<< claude-code-lanes-starter"
_BEGIN_KEY = "# >>> claude-code-lanes-starter"
_BOM = "﻿"


class BlockError(ValueError):
    """The markers are broken; the file is left untouched."""


def _bare(line: str) -> str:
    return line.rstrip("\r\n").removeprefix(_BOM)


def _markers(lines: list) -> tuple[list, list]:
    begins = [number for number, line in enumerate(lines) if _bare(line).startswith(_BEGIN_KEY)]
    ends = [number for number, line in enumerate(lines) if _bare(line).rstrip() == END]
    if (begins or ends) and not (len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]):
        raise BlockError(
            f"its claude-code-lanes-starter markers are broken ({len(begins)} start, {len(ends)} end): "
            "fix or remove them by hand, then run the installer again"
        )
    return begins, ends


def merge(existing: str, body: str) -> str:
    """existing with the block holding body added at the end, or replaced where it already is."""
    lines = existing.splitlines(keepends=True)
    begins, ends = _markers(lines)
    newline = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    block = "".join(line + newline for line in [BEGIN, *body.replace("\r\n", "\n").rstrip("\n").split("\n"), END])
    if begins:
        return "".join(lines[: begins[0]]) + block + "".join(lines[ends[0] + 1 :])
    kept = "".join(lines)
    if not _bare(kept).strip():
        return kept + block  # empty, or just a BOM
    if not kept.endswith("\n"):
        kept += newline
    gap = "" if _bare(lines[-1]).strip() == "" or kept.endswith(newline * 2) else newline
    return kept + gap + block


def outside(existing: str) -> list:
    """The owner's non-blank lines: everything not inside the block."""
    lines = existing.splitlines(keepends=True)
    begins, ends = _markers(lines)
    if begins:
        lines = lines[: begins[0]] + lines[ends[0] + 1 :]
    return [_bare(line).strip() for line in lines if _bare(line).strip()]
