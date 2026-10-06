"""Which files the installer writes, and what happens to each one that already exists (decision 100).

Everything is decided here, before anything is written, so `--dry-run` shows exactly what a real
run does and a problem (a broken managed block, a folder or link in the way) stops the install
with nothing half-written.

- Kit-owned (`payload/kit-owned/`): created; replaced only if it matches the hash the manifest
  recorded when the kit wrote it (nobody edited it). Otherwise the owner's file stays and the kit's
  version is offered beside it as `<name>.kit-new`.
- Project-owned (`payload/templates/`, rendered): created once. A file the owner already had gets a
  `.kit-new`; a file an earlier install rendered is never touched again (decision 7).
- A `.kit-new` is offered once per kit version: an existing one is never overwritten (the owner may
  be mid-merge), and one the owner deleted isn't offered again until the kit's version changes.
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

# In .gitattributes later lines win, so a block after the owner's rules would override them (and
# `* text=auto eol=lf` would renormalize a CRLF repo). When the owner has rules, the kit adds only
# what its own scripts need (review round 1; the owner's call, flagged in the PR).
OWNER_GITATTRIBUTES_BODY = """\
# The kit's shell scripts must keep LF line endings, whatever the rest of the repository uses.
.claude/kit/hook text eol=lf
.claude/kit/kit text eol=lf
.githooks/* text eol=lf
"""


class PlanError(ValueError):
    """Something in the target makes a planned write unsafe; nothing has been written."""


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
    notes: list = field(default_factory=list)  # things not written, and why
    files: dict = field(default_factory=dict)  # kit-owned rel -> sha256 of what the kit wrote there
    templates: list = field(default_factory=list)  # project-owned rels the kit has rendered
    offered: dict = field(default_factory=dict)  # rel -> sha256 of the .kit-new last offered for it


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def kit_owned() -> dict:
    """rel -> (bytes, mode) for every kit-owned file."""
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
    """previous: the manifest an earlier install wrote (already checked), or {}."""
    plan = FilePlan()
    recorded = previous.get("files", {})
    offered = previous.get("offered", {})
    owned = kit_owned()
    owned[VERSION_REL] = ((values["kit_version"] + "\n").encode("utf-8"), None)
    for rel, (data, mode) in owned.items():
        current = _read(target, rel)
        if current is None:
            plan.files[rel] = sha256(data)
            plan.writes.append(Write(rel, data, "create", mode))
        elif current == data:
            plan.files[rel] = sha256(data)
            plan.unchanged.append(rel)
        elif rel in recorded and recorded[rel] == sha256(current):
            plan.files[rel] = sha256(data)
            plan.writes.append(Write(rel, data, "replace", mode))
        else:
            # The owner's file (or their edit of the kit's): keep whatever the kit last wrote on
            # record, and never the owner's hash, or a re-run would "replace" their file.
            if rel in recorded:
                plan.files[rel] = recorded[rel]
            why = "edited since install" if rel in recorded else "exists"
            _offer(plan, target, rel, data, mode, offered, f"{why}; yours is kept")

    rendered_before = set(previous.get("templates", []))
    for rel, data in rendered_templates(values).items():
        current = _read(target, rel)
        if rel in BLOCK_FILES:
            plan.templates.append(rel)
            _block(plan, rel, current, data.decode("utf-8"))
        elif current is None:
            plan.templates.append(rel)
            plan.writes.append(Write(rel, data, "create"))
        elif current == data:
            plan.templates.append(rel)
            plan.unchanged.append(rel)
        elif rel in rendered_before:
            plan.templates.append(rel)
            plan.kept.append(rel)  # project-owned: rendered once, then the project's
        else:
            _offer(plan, target, rel, data, None, offered, "exists; yours is kept")
    return plan


def _block(plan: FilePlan, rel: str, current: bytes | None, body: str) -> None:
    try:
        text = "" if current is None else current.decode("utf-8")  # a BOM stays part of the text
        if rel == ".gitattributes" and blocks.outside(text):
            body = OWNER_GITATTRIBUTES_BODY
        merged = blocks.merge(text, body).encode("utf-8")
    except UnicodeDecodeError:
        raise PlanError(f"{rel}: not UTF-8 text, so the kit can't add its lines") from None
    except blocks.BlockError as error:
        raise PlanError(f"{rel}: {error}") from None
    if merged == current:
        plan.unchanged.append(rel)
    else:
        plan.writes.append(Write(rel, merged, "block" if current is not None else "create"))


def _offer(plan: FilePlan, target: Path, rel: str, data: bytes, mode, offered: dict, note: str) -> None:
    new_rel = rel + ".kit-new"
    existing = _read(target, new_rel)
    digest = sha256(data)
    plan.offered[rel] = digest
    if existing == data:
        plan.unchanged.append(new_rel)
    elif existing is not None:
        plan.notes.append(f"{new_rel} kept as it is: it differs from the kit's version (delete it to get a new one)")
    elif offered.get(rel) == digest:
        pass  # offered before and deleted by the owner: not again until the kit's version changes
    else:
        plan.writes.append(Write(new_rel, data, "kit-new", mode, f"{rel} {note}"))


def check_path(target: Path, rel: str) -> None:
    """A planned file must not be a folder, and nothing on its way may be a link: the kit never
    writes outside the project through one."""
    path = target
    for part in Path(rel).parts:
        path = path / part
        if path.is_symlink():
            shown = path.relative_to(target).as_posix()
            raise PlanError(f"{rel}: {shown} is a symbolic link; the installer doesn't write through links")
    if path.is_dir():
        raise PlanError(f"{rel}: a folder is where the kit's file goes; move it, then run the installer again")


def _read(target: Path, rel: str) -> bytes | None:
    check_path(target, rel)
    path = target / rel
    return path.read_bytes() if path.is_file() else None


def apply(target: Path, plan: FilePlan) -> None:
    for write in plan.writes:
        path = target / write.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(write.data)  # bytes: no CRLF conversion on Windows
        if write.mode is not None:
            path.chmod(write.mode)
