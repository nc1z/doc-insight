# Contributing

Development tooling for working on this repo. Not required to run the app (see [README](README.md)).

## Prerequisites

- [nvm](https://github.com/nvm-sh/nvm#installing-and-updating) — installs the Node.js version pinned in [`.nvmrc`](.nvmrc)
- [pnpm](https://pnpm.io/installation) — install it standalone (macOS: `brew install pnpm`), not through a Node version, so it survives Node upgrades. The exact version is pinned in `packageManager` in [`package.json`](package.json) and pnpm switches to it automatically.
- [gitleaks](https://github.com/gitleaks/gitleaks#installing) — only needed to **commit** (the pre-commit hook runs it). Not needed to install or run anything (macOS: `brew install gitleaks`).

## Setup

Run from the repo root:

```bash
nvm install    # installs and switches to the version in .nvmrc
pnpm install   # also installs git hooks via husky
```

A different Node version only produces a warning, but use the pinned one to match CI and Docker.

## Git hooks

- **pre-commit**:
  - `gitleaks` scans staged changes for secrets and blocks the commit if any are found. Config: [`.gitleaks.toml`](.gitleaks.toml).
  - `lint-staged` runs Prettier on staged files. Config: `lint-staged` in [`package.json`](package.json).
- **commit-msg**: `commitlint` enforces [Conventional Commits](https://www.conventionalcommits.org/). Config: `commitlint` in [`package.json`](package.json).

## Commit messages

Format: `type(optional-scope): subject`, e.g. `feat(backend): add PDF upload endpoint`.

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

## Formatting

- `pnpm format` formats the whole repo with Prettier.
- `pnpm format:check` checks formatting without writing changes (used in CI).

## Dependency policy

- pnpm only; do not use npm or yarn.
- `minimumReleaseAge` in [`pnpm-workspace.yaml`](pnpm-workspace.yaml) blocks package versions published less than 7 days ago.
- Run `pnpm audit` after dependency changes.
