"""A first guess at a project's lanes, from its tracked folders (plan 16, decision 122).

Only a draft: the installer shows it and writes it on a yes, and `lanes suggest` prints it. Each
lane owns one code folder: a top-level folder such as `server/`, or a folder inside a source root
(`src/core/`), with its `tests/<name>/` folder when there is one. Fewer than two or more than five
folders give no guess, with the reason, since a split that size needs the owner's judgement.
"""

import re

from .lane_owners import toml_string
from .records import record

MIN_LANES, MAX_LANES = 2, 5
# Folders whose subfolders are the code areas (a single package inside one is opened too).
_SOURCE_ROOTS = {"src", "lib", "app", "apps", "packages", "services"}
_TEST_ROOTS = ("tests", "test")
# Not a lane's code: docs, tests (they follow their lane), build output and other people's code.
_SKIP = {"docs", "doc", "tests", "test", "spec", "specs", "build", "dist", "out", "target", "vendor"}
_SKIP |= {"third_party", "node_modules", "venv", "env", "__pycache__"}


@record
class Suggestion:
    name: str
    owns: list
    scope: str


def suggest(paths) -> tuple[list, str]:
    """(lanes, "") for a guess; ([], why) when there's none. paths: tracked files, `/`-separated."""
    tree = _tree(paths)
    folders = []
    for top in sorted(tree):
        if _skipped(top):
            continue
        if top in _SOURCE_ROOTS:
            folders += _inside(tree, top)
        else:
            folders.append(top)
    if len(folders) < MIN_LANES:
        found = f"only one code folder ({folders[0]}/)" if folders else "no code folders"
        return [], f"{found}: lanes need at least two areas to split the work between"
    if len(folders) > MAX_LANES:
        return [], f"{len(folders)} code folders: too many to guess; pick two to five in .claude/kit.toml"
    names = _names(folders)
    tracked = set(paths)
    lanes = []
    for folder, name in zip(folders, names, strict=True):
        owns = [f"{folder}/**"]
        leaf = folder.rsplit("/", 1)[-1]
        owns += [f"{root}/{leaf}/**" for root in _TEST_ROOTS if any(p.startswith(f"{root}/{leaf}/") for p in tracked)]
        lanes.append(Suggestion(name, owns, f"Everything under {folder}/"))
    return lanes, ""


def to_toml(lanes) -> str:
    """The `[[lanes]]` tables for kit.toml, each owned path as a TOML string."""
    blocks = []
    for lane in lanes:
        owns = ", ".join(toml_string(path) for path in lane.owns)
        blocks.append(
            f"[[lanes]]\nname = {toml_string(lane.name)}\nscope = {toml_string(lane.scope)}\nowns = [{owns}]\n"
        )
    return "\n".join(blocks)


def _tree(paths) -> dict:
    """folder -> {subfolder -> {...}}, for every folder holding a tracked file."""
    tree = {}
    for path in paths:
        node = tree
        for part in path.split("/")[:-1]:
            node = node.setdefault(part, {})
    return tree


def _skipped(name: str) -> bool:
    return name.startswith((".", "_")) or name.lower() in _SKIP


def _inside(tree: dict, top: str) -> list:
    """The code folders inside a source root: its subfolders, or a single package's subfolders."""
    prefix, node = top, tree[top]
    subfolders = [name for name in sorted(node) if not _skipped(name)]
    if len(subfolders) == 1:
        prefix, node = f"{top}/{subfolders[0]}", node[subfolders[0]]
        inner = [name for name in sorted(node) if not _skipped(name)]
        if len(inner) >= MIN_LANES:
            subfolders = inner
        else:
            return [prefix]
    elif not subfolders:
        return [top]
    return [f"{prefix}/{name}" for name in subfolders]


def _names(folders) -> list:
    """A valid lane name per folder (config's rule); two folders with one name get their parent's too."""
    leaves = [_slug(folder.rsplit("/", 1)[-1]) for folder in folders]
    full = [_slug(folder.replace("/", "-")) for folder in folders]
    return [
        full[i] if leaves.count(leaf) > 1 else leaf  # e.g. apps/web and packages/web
        for i, leaf in enumerate(leaves)
    ]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "lane"
