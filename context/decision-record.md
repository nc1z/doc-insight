# Decision Record

These are my decision records and thought process throughout planning & development, in chronological order.

## Scaffolding

- `2026-11-21 09:49` **Turborepo**: best fit for managing multiple apps in one repo; global root commands (build, lint, test) plus caching.
- `2026-11-21 09:53` **pnpm** `minimumReleaseAge` **7 days + pinned Node version**: security; defends against supply-chain attacks from malicious newly published packages, and keeps the runtime on a known, patched release.
- `2026-11-21 09:55` **Husky, set up early**: enforces codebase conventions from day one, so both AI agents and humans follow the same rules.
- `2026-11-21 10:21` **Reusable prompts in** `.agents/prompts/`**, before development starts**: streamline the workflow (PRD, plan, execute, explain, commit, docs cleanup) so each step is repeatable; `.agents/` keeps them tool-agnostic rather than tied to one AI tool.
- `2026-11-21 10:48` **React + Vite + TypeScript for the frontend**: simple, agent-native (LLMs write it well), scales as the app grows, and fits a single-page upload-and-report UI.
- `2026-11-21 11:00` **FastAPI + uv for the backend**: simple, agent-native, and scalable; FastAPI's Pydantic models fit structured LLM output, and uv manages Python itself plus a lockfile, so setup is one tool.
- `2026-11-21 11:12` **Bruno for API testing**: collections are plain-text files in the repo (versioned and reviewed with the code), offline, no account needed; the collection lives in `backend/bruno/` and can run in CI through the Bruno CLI later.
- `2026-11-21 11:18` **Dockerize early**: a working baseline before development starts; `docker compose up -d` runs the full stack with only Docker installed, and CI builds and health-checks both images on every push.
- `2026-11-21 11:33` **nginx serves the frontend and proxies** `/api` **to the backend**: `vite preview` is not meant for production; the proxy avoids CORS and baking the backend URL into the build. Vite's dev proxy mirrors it, so frontend code always calls `/api`. Assumes no cloud deployment for this task; a static host (Vercel, Netlify, S3 + CloudFront) would replace nginx.
- `2026-11-21 11:39` **actionlint + act for CI changes**: actionlint catches workflow mistakes in the pre-commit hook and in CI; act runs the `ci` job locally (`pnpm ci:local`) and catches problems actionlint cannot, such as a missing action version.
