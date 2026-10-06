"""Managed blocks in files the project owns, such as `.gitignore` (decision 100).

The kit's lines sit between two marker lines and only that text is ever rewritten, so the owner's
own lines stay theirs. A lone, doubled or reversed marker means someone edited the block by hand:
that is an error to show, never something to repair silently (the pattern from lanekeeper's
CODEOWNERS handling, `docs/survey-lanekeeper.md`).
"""

BEGIN = "# >>> claude-code-lanes-starter (managed: the installer rewrites the lines between these markers)"
END = "# <<< claude-code-lanes-starter"
_BEGIN_KEY = "# >>> claude-code-lanes-starter"


class BlockError(ValueError):
    """The markers are broken; the file is left untouched."""


def merge(existing: str, body: str) -> str:
    """existing with the block holding body added at the end, or replaced where it already is."""
    newline = "\r\n" if "\r\n" in existing else "\n"
    lines = existing.replace("\r\n", "\n").split("\n")
    begins = [number for number, line in enumerate(lines) if line.startswith(_BEGIN_KEY)]
    ends = [number for number, line in enumerate(lines) if line.rstrip() == END]
    block = [BEGIN, *body.replace("\r\n", "\n").rstrip("\n").split("\n"), END]

    if not begins and not ends:
        kept = "\n".join(lines).rstrip("\n")
        merged = (kept + "\n\n" if kept else "") + "\n".join(block) + "\n"
    elif len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
        merged = "\n".join(lines[: begins[0]] + block + lines[ends[0] + 1 :])
    else:
        raise BlockError(
            f"its claude-code-lanes-starter markers are broken ({len(begins)} start, {len(ends)} end): "
            "fix or remove them by hand, then run the installer again"
        )
    return merged.replace("\n", newline)
