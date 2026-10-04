"""What a check found, and how it is shown to people and agents."""
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    check: str
    message: str
    rule: str = ""


def format_findings(findings) -> str:
    """One `path:line: [check/rule] message` line per finding, sorted by location."""
    lines = []
    for finding in sorted(findings):
        tag = f"{finding.check}/{finding.rule}" if finding.rule else finding.check
        lines.append(f"{finding.path}:{finding.line}: [{tag}] {finding.message}")
    return "\n".join(lines)
