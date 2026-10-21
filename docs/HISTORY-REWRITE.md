# History rewrite, 2026-10-21

Almost every commit SHA in this repository changed on 2026-10-21 (the oldest
commits up to `v1.0.0` were unaffected). If you hold a clone
from before that date, re-sync it (below). Don't push old commits back: that
puts the removed material back in public history.

## Why

The repo is public and the owner wants it to stay public. Older history
contained material that shouldn't be public:

1. Links to private AI coding sessions, carried in `Claude-Session:` trailer
   lines and bare session URLs in commit messages.
2. A real player's in-game name, used in the monthly-streak test fixtures and
   one commit message. It is now the synthetic name `Champ`. The tests and
   their behaviour are unchanged.
3. An internal host name and its on-disk data path, in CHANGELOG and commit
   messages. They now read "the live deployment" and `~/meshquiz-data`.
4. Personal and machine-local author emails on six commits, now mapped to the
   GitHub noreply address. Author names and dates are unchanged.

Everything else was kept. Every commit message keeps its real content (only
the lines above came out or were reworded), and `Co-Authored-By` lines, docs,
authors' names and dates are untouched. The tree of `main` is byte-identical
before and after the rewrite.

## How

- Tool: `git filter-repo` (a40bce548d2c).
- `--message-callback`: drops lines that are only a session link, a
  `Claude-Session:` trailer or a "Generated with" trailer, and collapses the
  blank lines that leaves behind.
- `--replace-text` and `--replace-message`: a short list of literal
  replacements for categories 2 and 3. `--mailmap` for category 4. The lists
  are kept privately with the owner because they name the removed strings.
- Scope: all branches and all tags. Annotated tags were rewritten and their
  releases still attach to the same tag names.
- A full pre-rewrite mirror and bundle are kept privately by the owner, off
  GitHub.
- Before the push, 214 tests passed on the same `main` tree. After the push,
  a fresh clone had 0 matches for any removed string across `git log --all`,
  author metadata, every blob in every commit, and every tag.

## Re-syncing an old clone

```sh
git fetch origin --prune --force '+refs/heads/*:refs/remotes/origin/*' '+refs/tags/*:refs/tags/*'
git reset --keep origin/<your-branch>   # per branch that has no local-only work
```

For a branch with local-only commits, rebase those commits onto the new
branch (`git rebase --onto origin/<branch> <old-base> <branch>`) or re-clone.

## What still holds the old commits

GitHub keeps old commits reachable through the read-only `refs/pull/*` refs
of past pull requests, and through its caches, so an old SHA URL may still
open. A purge request to GitHub Support covers that. The rewrite can't reach
it.

## Branch and tag map (old -> new)

| ref | old | new |
|---|---|---|
| `heads/feat/ambient-mode` | `8e3c681b72dc` | `222674f85481` |
| `heads/main` | `4d1b0747e35a` | `8a24ca4d7650` |
| `tags/v1.0.0` | `4bf296c3bd35` | `4bf296c3bd35` |
| `tags/v1.1.0` | `8e3c681b72dc` | `222674f85481` |
| `tags/v1.2.0` | `36e1b4ba8c1a` | `a1728c0f8db8` |
| `tags/v1.2.1` | `f388ad580daa` | `4475ccbe6945` |
| `tags/v1.2.2` | `da03d0d7c59a` | `2ffe1017cd18` |
| `tags/v1.3.0` | `388045d30983` | `904e0fe300a2` |
| `tags/v1.4.0` | `418101d63ace` | `60edb97edad3` |
| `tags/v1.4.1` | `a6bd5a1d50bf` | `ef9e99a54310` |
