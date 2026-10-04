from helpers import make_repo, run_cli, write

CHANGELOG = """# Changelog

Notable changes, newest first.

## [Unreleased]

## [0.1.0] - 2026-01-01
### Added
- First release.
"""


def setup(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "docs/CHANGELOG.md", CHANGELOG)
    write(repo, "docs/changelog.d/README.md", "# How fragments work\n### Added\n- not a fragment\n")
    write(repo, "docs/changelog.d/core-export.md", "### Added\n- CSV export.\n\n### Fixed\n- Totals.\n")
    write(repo, "docs/changelog.d/api-auth.md", "### Fixed\n- Login timeout\n  on slow networks.\n### Security\n- Tokens expire.\n")
    return repo


def test_build_merges_fragments_in_keep_a_changelog_order(tmp_path):
    repo = setup(tmp_path)
    result = run_cli(repo, "changelog", "build", "--version", "0.2.0", "--date", "2026-10-04")
    assert result.returncode == 0, result.stderr
    text = (repo / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    expected = (
        "## [Unreleased]\n\n"
        "## [0.2.0] - 2026-10-04\n"
        "### Added\n- CSV export.\n\n"
        "### Fixed\n- Login timeout\n  on slow networks.\n- Totals.\n\n"
        "### Security\n- Tokens expire.\n\n"
        "## [0.1.0] - 2026-01-01\n"
    )
    assert expected in text


def test_build_deletes_fragments_but_keeps_the_readme(tmp_path):
    repo = setup(tmp_path)
    run_cli(repo, "changelog", "build", "--version", "0.2.0", "--date", "2026-10-04")
    assert sorted(p.name for p in (repo / "docs/changelog.d").iterdir()) == ["README.md"]


def test_dry_run_prints_and_writes_nothing(tmp_path):
    repo = setup(tmp_path)
    result = run_cli(repo, "changelog", "build", "--version", "0.2.0", "--dry-run")
    assert result.returncode == 0
    assert "## [0.2.0]" in result.stdout
    assert (repo / "docs/CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG
    assert (repo / "docs/changelog.d/core-export.md").exists()


def test_unknown_heading_is_rejected_and_nothing_changes(tmp_path):
    repo = setup(tmp_path)
    write(repo, "docs/changelog.d/x-y.md", "### Improved\n- Things.\n")
    result = run_cli(repo, "changelog", "build", "--version", "0.2.0")
    assert result.returncode == 2
    assert "x-y.md" in result.stderr and "Improved" in result.stderr
    assert (repo / "docs/CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG


def test_text_before_the_first_heading_is_rejected(tmp_path):
    repo = setup(tmp_path)
    write(repo, "docs/changelog.d/x-y.md", "- orphan bullet\n")
    assert run_cli(repo, "changelog", "build", "--version", "0.2.0").returncode == 2


def test_no_fragments_is_an_error(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "docs/CHANGELOG.md", CHANGELOG)
    result = run_cli(repo, "changelog", "build", "--version", "0.2.0")
    assert result.returncode == 2
    assert "no fragments" in result.stderr.lower()


def test_entries_already_under_unreleased_are_refused(tmp_path):
    repo = setup(tmp_path)
    write(repo, "docs/CHANGELOG.md", CHANGELOG.replace("## [Unreleased]\n", "## [Unreleased]\n### Fixed\n- Hand-written.\n"))
    result = run_cli(repo, "changelog", "build", "--version", "0.2.0")
    assert result.returncode == 2
    assert "fragment" in result.stderr


def test_fragment_with_byte_order_mark_is_accepted(tmp_path):
    repo = setup(tmp_path)
    (repo / "docs/changelog.d/core-export.md").write_bytes(b"\xef\xbb\xbf### Added\n- CSV export.\n")
    assert run_cli(repo, "changelog", "build", "--version", "0.2.0").returncode == 0


def test_changelog_without_unreleased_heading_is_an_error(tmp_path):
    repo = setup(tmp_path)
    write(repo, "docs/CHANGELOG.md", "# Changelog\n")
    assert run_cli(repo, "changelog", "build", "--version", "0.2.0").returncode == 2
