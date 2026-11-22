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

## Database migrations

Schema changes live in [`backend/alembic/versions/`](backend/alembic/versions/). Alembic reads `DATABASE_URL` from the repo-root `.env`.

The API and worker containers apply pending migrations when they start. [`backend/docker-entrypoint.sh`](backend/docker-entrypoint.sh) runs `alembic upgrade head` and then the container command. The API command starts the server. The worker command is `python -m app.worker`. `docker compose up -d` is enough. After adding a migration, rebuild the image so the new file is in it:

```bash
docker compose up -d --build backend
```

`pnpm dev` does not apply migrations. With the repo-root `.env` in place, start Postgres and apply them yourself:

```bash
docker compose up -d postgres
uv run --directory backend alembic upgrade head
```

`upgrade head` applies every migration the database has not recorded yet. Running it again leaves the database as it is. The first revision, `0001_initial`, is empty and only records that Alembic is set up.

To add a migration:

```bash
uv run --directory backend alembic revision -m "describe the change"
```

Fill in `upgrade()` and `downgrade()` in the new file, then apply it with `alembic upgrade head` as above.

## File storage

Uploads go to MinIO. `docker compose up -d` starts it with the API. For `pnpm dev`, start MinIO first so the API can create its bucket:

```bash
docker compose up -d minio
```

The API container uses `http://minio:9000`. A process on the host uses `S3_ENDPOINT` from the repo-root `.env`, which points at `http://localhost:9000`.

## Backend tests

`uv run --directory backend pytest` includes tests that use the `postgres-test` container. That server is separate from the app database on port 5432. Start it with:

```bash
pnpm test:db
```

Those tests connect with `TEST_POSTGRES_USER`, `TEST_POSTGRES_PASSWORD`, and `TEST_POSTGRES_DB` from the repo-root `.env`. They create and drop that database on port 5433, apply migrations, and call `/health`. CI starts the same container. The other tests do not connect.

## Git hooks

- **pre-commit**:
  - `gitleaks` scans staged changes for secrets and blocks the commit if any are found. Config: [`.gitleaks.toml`](.gitleaks.toml).
  - `lint-staged` runs Prettier on staged files, and `actionlint` on staged workflow files. Config: `lint-staged` in [`package.json`](package.json).
- **commit-msg**: `commitlint` enforces [Conventional Commits](https://www.conventionalcommits.org/). Config: `commitlint` in [`package.json`](package.json).
- **pre-push**: `pnpm test`. Turbo caches each package's test run, so a package with no file changes reuses the last result instead of running again. When the backend cache misses, run `pnpm test:db` first.

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
- The `docker` job does not run reliably under act. Check it with `cp .env.example .env` and then `docker compose up -d --build --wait` instead.

Pull requests remain the final check, because act only approximates GitHub's runners.

## Dependency policy

- pnpm only; do not use npm or yarn.
- uv only for the backend; do not use pip or poetry. Add packages with `uv add` in `backend/`.
- Both block package versions published less than 7 days ago: `minimumReleaseAge` in [`pnpm-workspace.yaml`](pnpm-workspace.yaml) and `exclude-newer` in [`backend/pyproject.toml`](backend/pyproject.toml).
- Run `pnpm audit` after dependency changes.
