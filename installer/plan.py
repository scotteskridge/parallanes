"""Which files the installer writes, and what happens to each one that already exists (decision 100).

Everything is decided here, before anything is written, so `--dry-run` shows exactly what a real
run does and a problem (a broken managed block) stops the install with nothing half-written.

- Kit-owned (`payload/kit-owned/`): created; replaced only if it still matches the manifest's hash
  (nobody edited it); otherwise the new version goes beside it as `<name>.kit-new`.
- Project-owned (`payload/templates/`, rendered): created once. A file the owner already had gets a
  `.kit-new` beside it; a file an earlier install rendered is never touched again (decision 7).
- `.gitignore`, `.gitattributes`, `.worktreeinclude`: the kit's lines live in a managed block.
"""

import hashlib
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from kitlib import render

from . import blocks
from .values import toml_string

PAYLOAD = Path(__file__).resolve().parent.parent / "payload"
KIT_OWNED = PAYLOAD / "kit-owned"
TEMPLATES = PAYLOAD / "templates"
REGISTRY = PAYLOAD / "placeholders.toml"

BLOCK_FILES = {".gitignore", ".gitattributes", ".worktreeinclude"}
VERSION_REL = ".claude/kit/VERSION"
# Never shipped: bytecode, and this machine's interpreter (python-path is written per install).
_SKIP_PARTS = {"__pycache__"}
_SKIP_NAMES = {"python-path"}


@dataclass
class Write:
    rel: str  # where the bytes land; ends in .kit-new when the original is kept
    data: bytes
    kind: str  # create | replace | kit-new | block
    mode: int | None = None  # a kit-owned file's permission bits (the launchers, the pre-commit hook)
    note: str = ""


@dataclass
class FilePlan:
    writes: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    kept: list = field(default_factory=list)  # project-owned files an earlier install rendered
    files: dict = field(default_factory=dict)  # kit-owned rel -> sha256, for the manifest
    templates: list = field(default_factory=list)  # project-owned rels the kit has rendered


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def kit_owned() -> dict:
    """rel -> (bytes, mode) for every kit-owned file, plus VERSION."""
    found = {}
    for path in sorted(KIT_OWNED.rglob("*")):
        rel = path.relative_to(KIT_OWNED)
        if path.is_file() and not _SKIP_PARTS & set(rel.parts) and path.name not in _SKIP_NAMES:
            if path.suffix != ".pyc":
                found[rel.as_posix()] = (path.read_bytes(), path.stat().st_mode & 0o777)
    return found


def rendered_templates(values: dict) -> dict:
    """rel (without .tmpl) -> rendered bytes."""
    registry = set(tomllib.loads(REGISTRY.read_text(encoding="utf-8")))
    # kit.toml puts values inside "...": escape them there (ARCHITECTURE §15), nowhere else.
    in_toml = {key: toml_string(value)[1:-1] for key, value in values.items()}
    found = {}
    for path in sorted(TEMPLATES.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(TEMPLATES).as_posix()
        if rel.endswith(".tmpl"):
            rel = rel.removesuffix(".tmpl")
            text = path.read_text(encoding="utf-8")
            text = render.render(text, in_toml if rel.endswith(".toml") else values, registry)
            found[rel] = text.encode("utf-8")
        else:
            found[rel] = path.read_bytes()
    return found


def build(target: Path, values: dict, previous: dict) -> FilePlan:
    """previous: the manifest an earlier install wrote, or {}."""
    plan = FilePlan()
    recorded = previous.get("files", {})
    owned = kit_owned()
    owned[VERSION_REL] = ((values["kit_version"] + "\n").encode("utf-8"), None)
    for rel, (data, mode) in owned.items():
        current = _read(target / rel)
        plan.files[rel] = sha256(data)
        if current is None:
            plan.writes.append(Write(rel, data, "create", mode))
        elif current == data:
            plan.unchanged.append(rel)
        elif recorded.get(rel) == sha256(current):
            plan.writes.append(Write(rel, data, "replace", mode))
        else:
            plan.files[rel] = recorded.get(rel, sha256(current))  # still the edited one's record
            plan.writes.append(_kit_new(target, rel, data, mode, "edited since install; yours is kept"))

    rendered_before = set(previous.get("templates", []))
    for rel, data in rendered_templates(values).items():
        plan.templates.append(rel)
        current = _read(target / rel)
        if rel in BLOCK_FILES:
            try:
                merged = blocks.merge(_text(current, rel), data.decode("utf-8"))
            except blocks.BlockError as error:
                raise blocks.BlockError(f"{rel}: {error}") from None
            if current is not None and merged.encode("utf-8") == current:
                plan.unchanged.append(rel)
            else:
                plan.writes.append(Write(rel, merged.encode("utf-8"), "block" if current else "create"))
        elif current is None:
            plan.writes.append(Write(rel, data, "create"))
        elif current == data:
            plan.unchanged.append(rel)
        elif rel in rendered_before:
            plan.kept.append(rel)  # project-owned: rendered once, then the project's
        else:
            plan.templates.remove(rel)  # the owner's file, not one the kit rendered
            plan.writes.append(_kit_new(target, rel, data, None, "exists; yours is kept"))
    return plan


def _kit_new(target: Path, rel: str, data: bytes, mode, note: str) -> Write:
    return Write(rel + ".kit-new", data, "kit-new", mode, note)


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _text(data: bytes | None, rel: str) -> str:
    if data is None:
        return ""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise blocks.BlockError("not UTF-8 text, so the kit can't add its lines") from None


def apply(target: Path, plan: FilePlan) -> None:
    for write in plan.writes:
        path = target / write.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(write.data)  # bytes: no CRLF conversion on Windows
        if write.mode is not None:
            path.chmod(write.mode)
