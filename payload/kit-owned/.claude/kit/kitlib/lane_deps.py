"""How to install a lane's dependencies, and whether a Node lane has (decision 103).

A worktree is a fresh checkout without installed packages. Lanes in `.claude/worktrees/` sit inside
the main checkout, and Node looks for packages in parent folders, so a lane that never installs
silently runs the main checkout's `node_modules` (two-lane trial, F4).
"""

import json
from pathlib import Path

YARN = "yarn.lock"
NODE_LOCKFILES = (
    ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
    (YARN, "yarn install --immutable"),  # Yarn 2+; Yarn 1's lockfile is told apart in _command
    ("package-lock.json", "npm ci"),
    # Not in lanekeeper's table; without it a Bun project would be told it has no lockfile.
    ("bun.lock", "bun install --frozen-lockfile"),
    ("bun.lockb", "bun install --frozen-lockfile"),
)
# Per ecosystem: its manifests, then its lockfiles in lanekeeper's order (docs/survey-lanekeeper.md).
# The first lockfile found wins: a project mid-migration keeps the old one around.
ECOSYSTEMS = (
    (("package.json",), NODE_LOCKFILES),
    (
        ("pyproject.toml", "Pipfile", "requirements.txt"),
        (("uv.lock", "uv sync"), ("poetry.lock", "poetry install"), ("Pipfile.lock", "pipenv sync")),
    ),
    (("Gemfile",), (("Gemfile.lock", "bundle install"),)),
    (("composer.json",), (("composer.lock", "composer install"),)),
)

WHY_NESTED = (
    "Why install in each lane: lanes sit inside the main checkout and Node looks for packages in "
    "parent folders, so a Node lane without its own install can silently use the main checkout's "
    "packages and tests their versions, not the lane's."
)
WHY = "Why install in each lane: a lane is a fresh checkout, with no installed packages of its own."

# Files a package manager writes into node_modules on install. A folder holding only dot-entries
# without one of these is a tool's cache (Vite's .vite, babel-loader's .cache), not an install.
INSTALL_MARKERS = (".package-lock.json", ".modules.yaml", ".yarn-state.yml", ".yarn-integrity")
# package.json keys that make an install create node_modules (workspaces are linked into it).
PACKAGE_KEYS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies", "workspaces")


def install_hints(folder) -> list[str]:
    """One line per ecosystem at the lane's root: its install command, or that it is the owner's call.

    Only the root is read: workspace tools install from there, and walking every folder would be
    slow and would guess at subprojects.
    """
    root = Path(folder)
    hints = []
    for manifests, lockfiles in ECOSYSTEMS:
        command = _command(root, lockfiles)
        if command:
            hints.append(command)
            continue
        found = [name for name in manifests if (root / name).is_file()]
        if found:
            hints.append(f"the owner's call ({found[0]} has no lockfile)")
    return hints


def uses_node(folder) -> bool:
    root = Path(folder)
    return (root / "package.json").is_file() or _command(root, NODE_LOCKFILES) is not None


def missing_node_modules(folder, nested: bool) -> str | None:
    """A warning when the lane has package.json but no install of its own; None otherwise.

    Only Node is checked: its install folder is fixed, while Poetry, Pipenv and Bundler often
    install outside the project, so a warning there would be a guess (decision 103). nested: the
    lane sits inside the main checkout, so Node finds that checkout's packages instead of failing.
    """
    root = Path(folder)
    if not _needs_node_install(root):
        return None
    command = _command(root, NODE_LOCKFILES)
    how = f"run `{command}` here" if command else "install here (no lockfile: ask the owner which command)"
    then = (
        "Until then Node looks in parent folders and may silently use the main checkout's packages."
        if nested
        else "Until then imports of its packages fail."
    )
    return f"package.json but no node_modules in this lane: {how}. {then}"


def missing_node_modules_short(folder) -> str | None:
    """The same check, as one part of a `lanes status` line."""
    root = Path(folder)
    if not _needs_node_install(root):
        return None
    return f"no node_modules ({_command(root, NODE_LOCKFILES) or 'no lockfile: the owner picks the command'})"


def _needs_node_install(root: Path) -> bool:
    if not (root / "package.json").is_file():
        return False
    # Yarn Plug'n'Play has no node_modules by design: .pnp.cjs, or .pnp.js before Yarn 2.1.
    if (root / ".pnp.cjs").is_file() or (root / ".pnp.js").is_file():
        return False
    # pnpm lists its workspaces in pnpm-workspace.yaml, so a scripts-only root package.json still installs.
    packages = (root / "pnpm-workspace.yaml").is_file() or _declares_packages(root / "package.json")
    return packages and not _installed(root / "node_modules")


def _declares_packages(manifest: Path) -> bool:
    """False for a scripts-only package.json: npm installs nothing then and makes no node_modules,
    so the warning could never clear. A file that can't be read or parsed still warns."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return True
    if not isinstance(data, dict):
        return True
    return any(data.get(key) for key in PACKAGE_KEYS)


def _installed(modules: Path) -> bool:
    try:
        # Stops at the first package: a real node_modules holds thousands.
        return any(not entry.name.startswith(".") or entry.name in INSTALL_MARKERS for entry in modules.iterdir())
    except OSError:
        return False  # missing (or unreadable: an install the agent can't use either)


def _command(root: Path, lockfiles) -> str | None:
    for name, command in lockfiles:
        if (root / name).is_file():
            return "yarn install --frozen-lockfile" if name == YARN and _yarn_classic(root / name) else command
    return None


def _yarn_classic(lockfile: Path) -> bool:
    """Yarn 1 heads its lockfile with "# yarn lockfile v1"; Yarn 2+ writes YAML with __metadata."""
    try:
        with lockfile.open("rb") as handle:
            return b"yarn lockfile v1" in handle.read(512)
    except OSError:
        return False  # unreadable: the table's command
