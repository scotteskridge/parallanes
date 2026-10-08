---
status: next
lane: any
size: S
---
# Say up front what local merge mode needs

With `merge_mode = "local"` the main checkout must be detached (`git switch --detach main`), or the
first `lanes finish` can't fast-forward `main`. In the two-lane trial (F2, F9) only `lanes status`
said so: the installer's next steps and `lanes create` didn't. And `lanes status` still printed
`PR: unknown` for every lane, though local mode never opens one.

**Done when:** `lanes create` in local mode ends with the detach command when the main checkout has
the integration branch checked out, and `lanes status` leaves out the PR field in local mode.
