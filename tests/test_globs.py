import pytest

from kitlib.globs import matches, matches_any, normalize


@pytest.mark.parametrize(
    "pattern, path, expected",
    [
        # A pattern without a slash matches the file name at any depth (gitignore rule).
        ("*.py", "app.py", True),
        ("*.py", "src/deep/app.py", True),
        ("*.py", "src/app.pyc", False),
        # A pattern with a slash is anchored at the project root.
        ("src/*.py", "src/app.py", True),
        ("src/*.py", "src/sub/app.py", False),
        ("src/*.py", "lib/src/app.py", False),
        ("/src/*.py", "src/app.py", True),
        # ** crosses folders; * and ? don't.
        ("src/**/*.py", "src/app.py", True),
        ("src/**/*.py", "src/a/b/app.py", True),
        ("src/**", "src/a/b/c.txt", True),
        ("src/**", "srcx/a.txt", False),
        ("**/test_*.py", "test_x.py", True),
        ("**/test_*.py", "a/b/test_x.py", True),
        ("src/?.py", "src/a.py", True),
        ("src/?.py", "src/ab.py", False),
        ("src/*", "src/a/b.py", False),
        # Character classes, including negation.
        ("data/[ab].csv", "data/a.csv", True),
        ("data/[!ab].csv", "data/a.csv", False),
        ("data/[!ab].csv", "data/c.csv", True),
        # A trailing slash means "everything inside this folder".
        ("vendor/", "vendor/lib/x.js", True),
        ("vendor/", "src/vendor.js", False),
        ("build/", "src/build/x.py", True),  # like gitignore: a lone trailing slash isn't an anchor
        ("src/build/", "lib/src/build/x.py", False),
        # Regex characters in patterns are literal.
        ("docs/a+b.md", "docs/a+b.md", True),
        ("docs/a+b.md", "docs/aab.md", False),
    ],
)
def test_matches(pattern, path, expected):
    assert matches(path, pattern) is expected


def test_windows_separators_are_normalized():
    assert normalize("src\\core\\app.py") == "src/core/app.py"
    assert matches("src\\core\\app.py", "src/**/*.py")


def test_leading_dot_slash_is_ignored():
    assert matches("./src/app.py", "src/*.py")


@pytest.mark.parametrize("pattern", ["", "  ", "src/a[]b"])
def test_validate_rejects_empty_and_uncompilable_globs(pattern):
    from kitlib.globs import validate

    with pytest.raises(ValueError):
        validate(pattern)


def test_matches_any():
    assert matches_any("src/a.py", ["*.md", "src/*.py"])
    assert not matches_any("src/a.py", [])
