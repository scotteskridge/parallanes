"""Managed blocks in files the project owns, such as `.gitignore` (decision 100).

The kit's lines sit between two marker lines and only that text is ever rewritten: the owner's
lines keep their bytes, line endings and BOM. A lone, doubled or reversed marker means someone
edited the block by hand: that is an error to show, never something to repair silently (the
pattern from lanekeeper's CODEOWNERS handling, `docs/survey-lanekeeper.md`).
"""

BEGIN = "# >>> worklanes (managed: the installer rewrites the lines between these markers)"
END = "# <<< worklanes"
# The kit's name before decision 108: a block written then is found under it and rewritten with
# the new markers. A pair must use one name, so a half-renamed block is broken like any other.
_NAMES = ("worklanes", "claude-code-lanes-starter")
_BOM = "﻿"


class BlockError(ValueError):
    """The markers are broken; the file is left untouched."""


def _bare(line: str) -> str:
    return line.rstrip("\r\n").removeprefix(_BOM)


def _markers(lines: list) -> tuple[list, list]:
    found = {}
    for name in _NAMES:
        begins = [number for number, line in enumerate(lines) if _bare(line).startswith(f"# >>> {name}")]
        ends = [number for number, line in enumerate(lines) if _bare(line).rstrip() == f"# <<< {name}"]
        if begins or ends:
            found[name] = (begins, ends)
    if not found:
        return [], []
    begins, ends = next(iter(found.values()))
    if len(found) > 1 or not (len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]):
        counts = ", ".join(f"{len(b)} start and {len(e)} end named {name}" for name, (b, e) in found.items())
        raise BlockError(
            f"its worklanes markers are broken ({counts}): fix or remove them by hand, then run the installer again"
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


def inside(existing: str) -> list | None:
    """The block's own lines, or None if there is no block."""
    lines = existing.splitlines(keepends=True)
    begins, ends = _markers(lines)
    if not begins:
        return None
    return [_bare(line).strip() for line in lines[begins[0] + 1 : ends[0]]]


def outside(existing: str) -> list:
    """The owner's non-blank lines: everything not inside the block."""
    lines = existing.splitlines(keepends=True)
    begins, ends = _markers(lines)
    if begins:
        lines = lines[: begins[0]] + lines[ends[0] + 1 :]
    return [_bare(line).strip() for line in lines if _bare(line).strip()]
