# Contributing

Development tooling for working on this repo. Not required to run the app (see [README](README.md)).

## Prerequisites

- [nvm](https://github.com/nvm-sh/nvm#installing-and-updating) — installs the Node.js version pinned in [`.nvmrc`](.nvmrc)
- [pnpm](https://pnpm.io/installation) — version pinned in `packageManager` in [`package.json`](package.json); pnpm switches to it automatically (macOS: `brew install pnpm`)
- [gitleaks](https://github.com/gitleaks/gitleaks#installing) — required by the pre-commit hook (macOS: `brew install gitleaks`)

## Setup

```bash
nvm install    # installs and switches to the version in .nvmrc
pnpm install   # also installs git hooks via husky
```

## Git hooks

- **pre-commit**: `gitleaks` scans staged changes for secrets and blocks the commit if any are found. Config: [`.gitleaks.toml`](.gitleaks.toml).

## Dependency policy

- pnpm only; do not use npm or yarn.
- `minimumReleaseAge` in [`pnpm-workspace.yaml`](pnpm-workspace.yaml) blocks package versions published less than 7 days ago.
- Run `pnpm audit` after dependency changes.
