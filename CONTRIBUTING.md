# Contributing

Development tooling for working on this repo. Not required to run the app (see [README](README.md)).

## Prerequisites

- [nvm](https://github.com/nvm-sh/nvm#installing-and-updating) — installs the Node.js version pinned in [`.nvmrc`](.nvmrc)
- [pnpm](https://pnpm.io/installation) — install it standalone (macOS: `brew install pnpm`), not through a Node version, so it survives Node upgrades. The exact version is pinned in `packageManager` in [`package.json`](package.json) and pnpm switches to it automatically.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — manages Python and the backend's dependencies (macOS: `brew install uv`). Python does not need to be installed separately: uv downloads the version pinned in [`backend/.python-version`](backend/.python-version) automatically.
- [gitleaks](https://github.com/gitleaks/gitleaks#installing) — only needed to **commit** (the pre-commit hook runs it). Not needed to install or run anything (macOS: `brew install gitleaks`).
- [actionlint](https://github.com/rhysd/actionlint) — only needed to **commit** changes to `.github/workflows/` (the pre-commit hook runs it). Also install [ShellCheck](https://www.shellcheck.net/) so it checks `run:` scripts (macOS: `brew install actionlint shellcheck`).
- [Bruno](https://www.usebruno.com/downloads) — optional, for manual API testing (macOS: `brew install --cask bruno`).
- [act](https://nektos.github.io/act/) — optional, for running CI locally. Requires Docker (macOS: `brew install act`).

## Setup

Run from the repo root:

```bash
nvm install    # installs and switches to the version in .nvmrc
pnpm install   # also installs git hooks via husky
uv sync --directory backend   # installs Python and the backend's dependencies
```

A different Node version only produces a warning, but use the pinned one to match CI and Docker.

## Git hooks

- **pre-commit**:
  - `gitleaks` scans staged changes for secrets and blocks the commit if any are found. Config: [`.gitleaks.toml`](.gitleaks.toml).
  - `lint-staged` runs Prettier on staged files, and `actionlint` on staged workflow files. Config: `lint-staged` in [`package.json`](package.json).
- **commit-msg**: `commitlint` enforces [Conventional Commits](https://www.conventionalcommits.org/). Config: `commitlint` in [`package.json`](package.json).

## Commit messages

Format: `type(optional-scope): subject`, e.g. `feat(backend): add PDF upload endpoint`.

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

## Formatting

- `pnpm format` formats the whole repo with Prettier.
- `pnpm format:check` checks formatting without writing changes.
- Backend Python code uses Ruff: run `uv run ruff format` in `backend/`. `pnpm lint` checks it.
- `backend/bruno/` is excluded from Prettier because the Bruno app writes those files.

## API testing

The Bruno collection is in [`backend/bruno/`](backend/bruno/).

1. Start the backend: `pnpm dev`.
2. In Bruno, choose **Open Collection** and select `backend/bruno/`.
3. Select the `local` environment, which points to `http://localhost:8000`.

To run the whole collection from the terminal instead, run `pnpm dlx @usebruno/cli run --env local` in `backend/bruno/`.

Add a request for each new endpoint, with tests or assertions for the expected response.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pushes to `main` and on pull requests:

- `ci` job: actionlint, then `pnpm build`, `pnpm lint`, and `pnpm test`.
- `docker` job: builds and starts both containers, then checks `/api/health` through nginx.

To run the `ci` job locally before pushing, start Docker and run `pnpm ci:local`. It uses act with the runner image set in [`.actrc`](.actrc).

- It runs your working copy, including uncommitted changes.
- The first run downloads a large runner image.
- The `docker` job does not run reliably under act. Check it with `docker compose up -d --build --wait` instead.

Pull requests remain the final check, because act only approximates GitHub's runners.

## Dependency policy

- pnpm only; do not use npm or yarn.
- uv only for the backend; do not use pip or poetry. Add packages with `uv add` in `backend/`.
- Both block package versions published less than 7 days ago: `minimumReleaseAge` in [`pnpm-workspace.yaml`](pnpm-workspace.yaml) and `exclude-newer` in [`backend/pyproject.toml`](backend/pyproject.toml).
- Run `pnpm audit` after dependency changes.
