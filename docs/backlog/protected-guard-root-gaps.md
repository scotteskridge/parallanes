---
status: idea
lane: any
size: M
---
# Close the protected guard's gaps around the project root

Plan 15's reviewers found three ways past the protected-paths hook that `main` already had (decision
120 kept them as they were). The deny rules in settings.json still cover the file tools; the hook is
the backstop, and these get past it:
- A hook cwd inside a real nested repository (`git init sub`, then work in `sub`): the root becomes
  `sub`, which has no kit.toml, so the guard allows everything. A home-folder dotfiles repo above a
  project that isn't a git repo does the same.
- From a lane's cwd, an Edit to the main checkout's own `vendor/lib.py` is allowed: the target is
  outside the lane's root, so it is never matched against `[protected]`.
- A Bash `rm "C:\...\project\vendor\lib.py"` with a backslash absolute path is allowed; the
  forward-slash spelling is blocked.

Each needs a design call: fail closed, or search upward for kit.toml, when the root has none; judge
a path in another checkout of the same repository against that checkout's kit.toml; normalize
backslash absolute paths in shell commands.

**Done when:** each of the three is blocked (or the decisions log says why it isn't), with a test.
