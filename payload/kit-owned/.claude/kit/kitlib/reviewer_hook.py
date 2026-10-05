"""`kit hook reviewer-bash`: the reviewer agent may run read-only git commands and nothing else (57).

An allowlist, unlike the protected-paths guard's denylist: every simple command in the text must
be git with a read-only subcommand. Like `commands.py`, it guards against mistakes, not adversaries;
it refuses anything it can't read plainly (substitutions, redirects, environment overrides).
"""
from .commands import program_name, tokenize

READ_ONLY = {
    "diff", "log", "show", "status", "merge-base", "rev-parse", "rev-list", "ls-files", "blame",
    "grep", "cat-file",
}
_GLOBAL_FLAGS = {"--no-pager", "-P", "--no-optional-locks", "--literal-pathspecs"}
# Characters that would run or write something the words don't show: substitution, redirects.
_UNREADABLE = set("`$<>")

ALLOWED_TEXT = "git with one of " + ", ".join(sorted(READ_ONLY))


def reason(text: str) -> str | None:
    """Why text isn't a read-only git command (or a chain of them), or None if it is."""
    if found := _UNREADABLE & set(text):
        return f"`{''.join(sorted(found))}` (substitution or redirect) is not allowed"
    segments = tokenize(text, "bash")
    if not segments:
        return "empty command"
    for words in segments:
        why = _git_reason(words)
        if why:
            return f"`{' '.join(words)}`: {why}"
    return None


def _git_reason(words: list[str]) -> str | None:
    if program_name(words[0]) != "git":
        return "only git commands are allowed"
    args = words[1:]
    while args and args[0].startswith("-"):
        option = args.pop(0)
        if option == "-C" and args:
            args.pop(0)  # another folder: reading it is still reading
        elif option not in _GLOBAL_FLAGS:
            return f"git option {option} is not allowed"
    if not args:
        return "no git subcommand"
    subcommand, rest = args[0], args[1:]
    if subcommand not in READ_ONLY:
        return f"git {subcommand} is not a read-only command"
    for arg in rest:
        if arg == "--":
            break
        name = arg.split("=", 1)[0]
        # git accepts unambiguous abbreviations of long options (`--outp=x` is `--output=x`).
        if name == "--output" or (len(name) >= 4 and "--output".startswith(name)):
            return "--output writes a file"
        if len(name) >= 5 and "--ext-diff".startswith(name):
            return "--ext-diff runs an external program"
        if subcommand == "grep" and (name == "-O" or (len(name) >= 4 and "--open-files-in-pager".startswith(name))):
            return "git grep -O runs a program"
    return None
