# Suggest commit message

Suggest a commit message for the current changes. Do not commit.

## Gather context

1. Run `git diff --staged`. If nothing is staged, run `git status` and `git diff` and say that the suggestion covers unstaged changes.
2. Run `git log --oneline -15` to match the repo's existing scope names and phrasing.
3. Read the commit conventions in [CONTRIBUTING.md](../../CONTRIBUTING.md) and the `commitlint` config in [package.json](../../package.json). These take precedence over the rules below.

## Format

```
type(scope): subject

optional body

optional footer
```

- **type**: one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **scope**: optional. Use the affected package or area (e.g. `backend`, `frontend`, `deps`). Reuse scopes already in the log. Omit it if the change spans the whole repo.
- **subject**: imperative mood ("add", not "added" or "adds"), lowercase start, no trailing period. Keep the whole header under 72 characters.
- **body**: only when the subject cannot convey why. Explain the motivation or a non-obvious consequence, not a file-by-file list of what changed. Wrap at 100 characters.
- **footer**: `BREAKING CHANGE: <description>` for breaking changes (also add `!` after the type/scope), or issue references.

## Choosing the type

- Pick the type by the change's effect on users of the code, not by the file touched. A bug fix in a test helper is `test`; a new user-facing feature that also adds tests is `feat`.
- Formatting-only changes are `style`. Dependency or build tooling changes are `build`. Repo housekeeping that fits nothing else is `chore`.

## Splitting

If the changes contain unrelated concerns, say so and suggest a separate message for each group, listing the files that belong to each. Suggest `git add <files>` commands to stage them separately.

## Output

1. The recommended message in a code block, ready to paste.
2. Up to two alternatives only if the type or scope is genuinely ambiguous, each with one line on why.
