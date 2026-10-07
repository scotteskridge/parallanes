"""Lane logic on canned git and gh output: no repos, so these stay in the fast set.

The slow tests prove the same commands end to end on real repos; these keep each lane module covered
by the fast set (`-m "not slow"`, AGENTS.md) while working.
"""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from kitlib import lane_cli, lane_cycle, lane_merged, lane_status, lanes
from kitlib.lane_pr import compare_url

A, B, C = "a" * 40, "b" * 40, "c" * 40


def config(mode="pr"):
    return SimpleNamespace(lane_settings=SimpleNamespace(merge_mode=mode, integration_branch="main"))


# ---- lane_cycle._clean and lanes.changes: one `git status --porcelain -z` ----------------------


def clean(monkeypatch, status_output):
    # The parser is lanes.changes, shared with `parallanes next`; it reads git through lanes.git.
    monkeypatch.setattr(lanes, "git", lambda top, *args, **kwargs: status_output)
    return lane_cycle._clean(Path("."))


@pytest.mark.parametrize(
    "output, changes",
    [
        (" M src/a.py\0", 1),
        ("R  new.py\0old.py\0", 1),  # staged rename: the old name is a second entry with no status
        (" R new.py\0old.py\0", 1),  # worktree rename (`add -N`, then rename)
        ("C  copy.py\0orig.py\0M  b.py\0", 2),
        ("UU both.py\0", 1),
    ],
)
def test_clean_counts_tracked_changes_once_each(monkeypatch, output, changes):
    with pytest.raises(lanes.LaneError, match=rf"^{changes} uncommitted change\(s\) to tracked files"):
        clean(monkeypatch, output)


def test_clean_lists_untracked_names_as_they_are(monkeypatch):
    note = clean(monkeypatch, "?? junit.xml\0?? my reports/\0?? résumé report.xml\0")
    assert len(note) == 1
    assert "junit.xml, my reports/, résumé report.xml" in note[0] and "won't land" in note[0]


def test_clean_with_nothing_says_nothing(monkeypatch):
    assert clean(monkeypatch, "") == []


def test_clean_shortens_a_long_untracked_list(monkeypatch):
    note = clean(monkeypatch, "".join(f"?? f{i}.txt\0" for i in range(8)))
    assert "and 3 more" in note[0]


# ---- lane_merged: the merge proof ----------------------------------------------------------------


def merged(monkeypatch, prs, mode="pr", in_tip=False, error=None):
    monkeypatch.setattr(lanes, "git", lambda *args, **kwargs: A + "\n")  # the branch tip is A
    monkeypatch.setattr(lanes, "is_ancestor", lambda folder, commit, of: in_tip)
    monkeypatch.setattr(lane_merged, "pull_requests", lambda *args, **kwargs: (prs, error))
    return lane_merged.merged(Path("."), config(mode), "core/x", "origin/main")


def pr(number, state, head=A, base="main"):
    return {"number": number, "state": state, "headRefOid": head, "baseRefName": base, "url": f"u{number}"}


def test_in_the_tip_is_merged_without_asking(monkeypatch):
    assert merged(monkeypatch, [], in_tip=True)[0] is True


@pytest.mark.parametrize(
    "prs, done, words",
    [
        ([pr(1, "MERGED")], True, "merged by PR #1"),
        ([pr(1, "OPEN")], False, "still open"),
        ([pr(1, "CLOSED")], False, "closed without merging"),
        ([pr(1, "MERGED", base="core/parent")], False, "into core/parent, not main"),
        ([pr(2, "MERGED", base="core/parent"), pr(1, "MERGED")], True, "merged by PR #1"),
        ([pr(1, "MERGED", head=B)], False, "other commit"),  # B unknown locally: no claim
        ([], False, "no PR for core/x"),
    ],
)
def test_pr_decides(monkeypatch, prs, done, words):
    fetched = []
    monkeypatch.setattr(lane_merged, "_have", lambda folder, commit: False)
    monkeypatch.setattr(lanes, "run_git", lambda *args, **kwargs: fetched.append(args))  # never the network
    result = merged(monkeypatch, prs)
    assert result[0] is done and words in result[1]
    assert all("refs/pull/1/head" in call for call in fetched)  # only a merged PR with an unknown head


def test_without_gh_nothing_is_claimed(monkeypatch):
    done, why = merged(monkeypatch, [], error="gh is not installed")
    assert done is False and "gh is not installed" in why


def test_local_mode_never_asks_gh(monkeypatch):
    done, why = merged(monkeypatch, [pr(1, "MERGED")], mode="local")
    assert done is False and "lanes finish" in why


def gh_says(monkeypatch, stdout, returncode=0):
    monkeypatch.setattr(lane_merged.shutil, "which", lambda name: "gh")
    monkeypatch.setattr(
        lane_merged.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, returncode, stdout, "boom"),
    )
    return lane_merged.pull_requests(Path("."), "core/x", "all")


def test_pull_requests_reads_gh_json(monkeypatch):
    prs, error = gh_says(monkeypatch, f'[{{"number": 1, "state": "OPEN", "headRefOid": "{A}", "baseRefName": "main"}}]')
    assert error is None and prs[0]["number"] == 1


@pytest.mark.parametrize(
    "stdout, returncode, words",
    [
        ("not json", 0, "isn't JSON"),
        ('[{"number": "1"}]', 0, "unexpected shape"),
        ('{"number": 1}', 0, "unexpected shape"),
        ("", 1, "gh pr list failed: boom"),
    ],
)
def test_pull_requests_never_guesses(monkeypatch, stdout, returncode, words):
    prs, error = gh_says(monkeypatch, stdout, returncode)
    assert prs == [] and words in error


def test_shares_work_ignores_a_pr_already_in_the_tip(monkeypatch):
    """After a merge-commit merge, a reused slug's new branch contains the old PR's head."""
    monkeypatch.setattr(lane_merged, "_have", lambda folder, commit: True)
    monkeypatch.setattr(lanes, "is_ancestor", lambda folder, commit, of: (commit, of) in {(B, "origin/main"), (B, A)})
    assert lane_merged.shares_work(Path("."), B, A, "origin/main") is False
    assert lane_merged.shares_work(Path("."), A, A, "origin/main") is True
    monkeypatch.setattr(lane_merged, "_have", lambda folder, commit: False)
    assert lane_merged.shares_work(Path("."), C, A, "origin/main") is None  # not fetched: can't tell


# ---- lane_status.format_status, lane_pr.compare_url, lane_cli --------------------------------------


def test_status_text(tmp_path):
    lane = lane_status.LaneStatus(
        "core",
        tmp_path / ".claude/worktrees/core",
        "ok",
        branch="core/x",
        ahead=2,
        behind=1,
        changed=1,
        untracked=2,
        gone=True,
        pr="PR #4 MERGED",
    )
    text = lane_status.format_status(
        lane_status.Status(
            tmp_path,
            None,
            "origin/main",
            lanes=[lane, lane_status.LaneStatus("api", tmp_path / ".claude/worktrees/api", "not created")],
            warnings=["careful"],
            notes=["overlap"],
        )
    )
    assert "detached HEAD" in text and "! careful" in text and "Note: overlap" in text
    assert "core .claude/worktrees/core · core/x · 2 ahead, 1 behind origin/main · 1 changed · 2 untracked" in text
    assert "pushed branch gone from origin · PR #4 MERGED" in text
    assert "api .claude/worktrees/api · not created (parallanes lanes create api)" in text


def test_github_remote_gets_a_compare_url():
    assert (
        compare_url("git@github.com:o/r.git", "main", "core/t")
        == "https://github.com/o/r/compare/main...core/t?expand=1"
    )
    assert (
        compare_url("https://github.com/o/r", "main", "core/t")
        == "https://github.com/o/r/compare/main...core/t?expand=1"
    )
    assert compare_url("D:/repos/origin.git", "main", "core/t") is None


def test_lanes_cli_reports_a_missing_config_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # no .claude/kit.toml anywhere up from here
    args = SimpleNamespace(lanes_command="sync")
    assert lane_cli.run(args) == lane_cli.USAGE
    err = capsys.readouterr().err
    assert err.startswith("parallanes: ") and "Traceback" not in err


def test_lanes_cli_catches_unfinished_from_where_it_is_defined(tmp_path, monkeypatch, capsys):
    # Unfinished lives in lanes and is raised from lane_pr too; lane_cycle importing it is an accident
    # that a refactor (or ruff --fix) can remove, so the CLI must not depend on it.
    monkeypatch.delattr(lane_cycle, "Unfinished", raising=False)  # still passes once the import is gone
    monkeypatch.setattr(lane_cli, "find_root", lambda here: tmp_path)
    monkeypatch.setattr(lane_cli, "load", lambda root: config())

    def finish(*args):
        raise lanes.Unfinished("core/t is pushed, but gh pr create failed")

    monkeypatch.setattr(lane_cycle, "finish", finish)
    args = SimpleNamespace(lanes_command="finish", title=None, body_file=None)
    assert lane_cli.run(args) == lane_cli.UNFINISHED
    assert capsys.readouterr().err == "parallanes: core/t is pushed, but gh pr create failed\n"
