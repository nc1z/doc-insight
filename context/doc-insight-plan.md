# PLAN: doc-insight

This plan builds doc-insight in phases, following [architecture.md](architecture.md) and [PRD.md](PRD.md). The backend comes first: foundations, then the upload and job API, then a worker running a mocked pipeline end to end, then real extraction, guardrails, and LLM steps. Every backend phase is testable through Bruno before any UI exists. The frontend starts only once the backend is complete, and builds against the `GET /jobs/{id}` contract defined in the architecture.

Every external dependency is built behind an interface from the start, with a mock or local adapter as the baseline. Real providers are added later as new adapters, not rewrites. Out of scope for this plan: production AWS infrastructure, authentication, and the optional AI feature (considered only after the final acceptance pass).

Primary services/packages/frameworks:

- **FastAPI**: REST API, request validation, and auto-generated OpenAPI docs that the frontend types are generated from.
- **Postgres + SQLAlchemy 2 + Alembic**: job store, results store, and queue in one database; migrations run automatically at startup.
- **Postgres-backed queue library (Procrastinate or PGQueuer)**: lets the API create and enqueue a job in one transaction, and runs the worker.
- **pydantic and pydantic-settings**: typed config from environment variables, and the schemas every LLM output is validated against.
- **PDF library (PyMuPDF4LLM or Docling)**: validation, per-page text, page images, and font data for hidden-text checks.
- **GLM 4.7 or later through an OpenAI-compatible client**: document summaries and consolidation.
- **Jev**: decision model for prompt-injection detection and document type.
- **Bruno**: manual and CLI API testing for every backend endpoint.
- **React + Vite + TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Playwright**: frontend, styling, components, polling, and end-to-end smoke tests.
- **Docker Compose and GitHub Actions**: one-command local run, and CI.

## Review Model

Each phase is split into sub-phases. A sub-phase should be small enough to review independently and explain with:

- files changed
- small code snippets
- what the code does in plain language
- how the change helps the overall flow
- what can be tested now
- whether any production infrastructure can be tested

No phase touches production infrastructure. Everything runs locally through Docker Compose and in CI.

## Flow Map

This plan follows the main user/system lifecycle directly:

| Flow step | What happens                                                        | Phase    |
| --------- | ------------------------------------------------------------------- | -------- |
| 1         | Client uploads PDFs; the API validates, stores, and creates a job   | Phase 1  |
| 2         | Client reads job status and resolves rejected files through the API | Phase 2  |
| 3         | Worker claims the job and runs the pipeline (mocked)                | Phase 3  |
| 4         | Worker extracts text per page                                       | Phase 4  |
| 5         | Worker runs guardrails and flags suspicious documents               | Phase 5  |
| 6         | Worker summarises each document, then consolidates                  | Phase 6  |
| 7         | Golden and adversarial evals measure pipeline quality               | Phase 7  |
| 8         | Worker understands images and scanned pages                         | Phase 8  |
| 9         | Analyst uploads and resolves rejected files in the UI               | Phase 10 |
| 10        | Analyst watches progress and reads the report in the UI             | Phase 11 |

## 0. Backend Foundations

Goal: a backend skeleton with config, Postgres, migrations, error handling, logging, and adapter interfaces, so later phases only add behaviour.

### 0A. Project Layout and Config

- [ ] Create the layered layout: `app/api/`, `app/domain/`, `app/adapters/`, `app/pipeline/`, `app/schemas/`, `app/core/`, `app/worker/`.
- [ ] Add `pydantic-settings` with a typed `Settings` class in `app/core/config.py` (database URL, storage path, file limits, provider names, model names, API keys, timeouts).
- [ ] Add `.env.example` with every setting, defaulting providers to `mock`, so the stack runs with no API key.
- [ ] Switch `app/main.py` to an app factory that wires settings, routers, and dependencies.
- [ ] Add mypy to the dev dependencies and the `lint` script.

### 0B. Postgres, ORM, and Migrations

- [ ] Add a `postgres` service to `docker-compose.yml` with a named volume and a healthcheck; the backend waits for it.
- [ ] Add SQLAlchemy 2 (async) with psycopg 3, a session factory, and a FastAPI dependency for sessions.
- [ ] Add Alembic with an empty initial migration; run `alembic upgrade head` on container start before the API starts.
- [ ] Extend `/health` to report database connectivity, keeping the response shape Bruno already tests.

### 0C. Errors, Logging, and Request IDs

- [ ] Define one error schema (`code`, `message`, `details`) and exception handlers that map domain errors to HTTP status codes.
- [ ] Add structured JSON logging with a request ID middleware; return the ID in an `X-Request-ID` header.

### 0D. Adapter Interfaces and Mocks

- [ ] Define `Protocol` interfaces in `app/domain/ports.py`: `FileStorage`, `JobRepository` (with a single `create_and_enqueue` operation), `LLMProvider`, `Classifier`.
- [ ] Add a factory that picks each adapter from config, injected through FastAPI dependencies and the worker entry point.
- [ ] Add mock `LLMProvider` and `Classifier` adapters with deterministic outputs.
- [ ] Add the central prompts file `app/pipeline/prompts.yaml` and a loader that validates every entry (ID, version, template, placeholders) at startup; the path comes from config.

### 0E. Tests, CI, and Bruno

- [ ] Add a pytest fixture that runs migrations against a test database, and a test for `/health`.
- [ ] Add a Postgres service container to the CI `ci` job so backend tests run against a real database.
- [ ] Confirm the CI `docker` job still passes with the new Postgres service.

### 0F. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the layout, config, and adapter interfaces let later phases swap providers without rewrites.

Suggested commit message: `feat(backend): add config, postgres, migrations, and adapter interfaces`

## 1. Upload and Job Creation

Goal: `POST /jobs` validates uploads, stores valid files, and creates a job that is queued or waiting for the analyst.

Solves flow step 1: a client (Bruno) uploads PDFs and gets an immediate job ID.

### 1A. Data Model

- [ ] Add `jobs` and `documents` tables with a migration: job status, document status, filename, storage key, SHA-256 hash, page count, rejection reason, and an `excluded` flag.
- [ ] Define job and document status enums matching the job and document states in the architecture.

### 1B. File Validation

- [ ] Add a validator in `app/domain/validation.py` that checks MIME type, `%PDF` magic bytes, size, page count, encryption, and JavaScript or embedded files.
- [ ] Read all limits (file size, page count, file count) from config.
- [ ] Return a typed per-file result with an error code and message for each rejection.
- [ ] Decide `413` versus a per-file `422` for limit errors, and record it in `decision-record.md`.

### 1C. Local File Storage Adapter

- [ ] Implement `LocalFileStorage` writing to a path from config, mounted as a shared Docker volume for the API and worker.
- [ ] Record the file storage baseline decision (shared volume versus MinIO) in `decision-record.md`.

### 1D. Queue Library and Create-and-Enqueue

- [ ] Confirm which library (Procrastinate or PGQueuer) can enqueue on the same connection and transaction that creates the job; pick it and record the decision.
- [ ] Implement `PostgresJobRepository.create_and_enqueue` so the job row and the queue entry commit in one transaction.

### 1E. POST /jobs

- [ ] All files valid: store each file, create and enqueue the job, return `202` with the job ID and status `queued`.
- [ ] Some files rejected: store valid files, create the job as `awaiting_input` without enqueuing, return `201` with accepted and rejected files.
- [ ] No valid files: store nothing, return `422` with the per-file error list.

### 1F. Sample Fixtures

- [ ] Add `samples/` with 2–4 PDFs on one topic and a `samples/README.md` listing source and licence.
- [ ] Include at least two samples that disagree on a fact, so the report must surface a contradiction.
- [ ] Add `samples/invalid/`: corrupt, encrypted, empty, and non-PDF renamed to `.pdf`.
- [ ] Add `samples/adversarial/` with a PDF containing injected instructions.

### 1G. Tests and Manual Verification

- [ ] Unit tests for each validation rule, using small PDFs generated in tests.
- [ ] Integration tests for the three `POST /jobs` outcomes, checking stored files, job rows, and queue entries.
- [ ] Bruno requests for valid, mixed, and all-invalid uploads using files in `samples/`.
- [ ] Expected result: `202`, `201`, and `422` respectively, each with the documented response body.

### 1H. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how atomic create-and-enqueue keeps jobs from being stranded.

Suggested commit message: `feat(backend): add job creation with file validation and storage`

## 2. Job Status and Actions

Goal: the full job API: read status, re-upload, confirm, cancel, and expiry.

Solves flow step 2: a client (Bruno) reads any job's state and resolves rejected files through the API.

### 2A. GET /jobs/{id}

- [ ] Add the response schema exactly as in the architecture status flow: status, progress, documents (status, flagged, error, summary), rejected and excluded files, report, error.
- [ ] Return `404` with the error schema for an unknown ID.
- [ ] Check the generated OpenAPI schema at `/docs` matches the response.

### 2B. Job State Machine

- [ ] Add a state machine in `app/domain/job_state.py` listing allowed transitions; invalid transitions raise a domain error mapped to `409 Conflict`.

### 2C. Re-upload, Confirm, and Cancel

- [ ] `POST /jobs/{id}/documents`: validate and store new files, add accepted ones, update the rejected list; job stays `awaiting_input`.
- [ ] `POST /jobs/{id}/confirm`: mark remaining rejected files as excluded, set `queued`, and enqueue in one transaction; return `202`.
- [ ] `POST /jobs/{id}/cancel`: set `cancelled`, delete stored files, return `200` with the updated job.

### 2D. Expiry and Cleanup

- [ ] Add a periodic task that expires `awaiting_input` jobs past a configurable timeout and deletes their files.
- [ ] Add a periodic task that deletes stored files with no job (orphans) older than a configurable age.
- [ ] Record the `awaiting_input` timeout default in `decision-record.md`.

### 2E. Tests and Manual Verification

- [ ] Integration tests for each action, including `409` for confirming a cancelled job and re-uploading to a queued job.
- [ ] Test expiry and orphan cleanup with a short configured timeout.
- [ ] Bruno requests for get, re-upload, confirm, and cancel, chained through a collection variable holding the job ID.
- [ ] Expected result: a mixed upload can be resolved three ways through Bruno alone.

### 2F. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the state machine keeps the API and worker in agreement.

Suggested commit message: `feat(backend): add job status, actions, and expiry`

## 3. Worker and Mocked Pipeline

Goal: a first working backend end to end: upload, process asynchronously with mock steps, poll to `succeeded`.

Solves flow step 3: the worker claims the job and moves it through every state.

### 3A. Queue Model Decision

- [ ] Decide between one task per job and one task per document plus a consolidation task triggered when the last document finishes.
- [ ] Update the architecture to remove the contradiction between "only the job ID goes on the queue" and "each document is its own queue task", and record the decision.

### 3B. Worker Process

- [ ] Add a worker entry point in `app/worker/` using the queue library, running from the same image with a different command.
- [ ] Add a `worker` service to `docker-compose.yml` sharing the storage volume and database.
- [ ] Make every step idempotent: store each step's status, and skip steps already completed on retry.

### 3C. Pipeline Skeleton

- [ ] Define pipeline steps in `app/pipeline/` as functions with typed inputs and outputs: extract, check, summarise, consolidate.
- [ ] Wire each step to the mock adapters, with configurable delays so mock mode shows realistic progress.
- [ ] Update job and document statuses and progress counts as steps complete.

### 3D. Processing Failures

- [ ] Decide what happens when a document fails during processing (fail the job, continue without it, or pause for the analyst), and record it.
- [ ] Implement the decision, plus a timeout on each step that marks the document failed with a clear reason.

### 3E. Tests and Manual Verification

- [ ] Integration test: create a job, run the worker in-process, assert the job reaches `succeeded` with mock summaries and report.
- [ ] Integration test: a forced step failure produces the decided failure behaviour.
- [ ] Bruno: upload, then poll `GET /jobs/{id}` until `succeeded`.
- [ ] Run the Bruno collection with the Bruno CLI in the CI `docker` job against the Compose stack in mock mode.

### 3F. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the API and worker cooperate through Postgres alone.

Suggested commit message: `feat(backend): add worker and mocked processing pipeline`

## 4. Text Extraction

Goal: real per-page text extraction replaces the mock extract step.

Solves flow step 4: the worker reads each document's text, keeping page numbers.

### 4A. Per-Page Extraction

- [ ] Choose the PDF library: PyMuPDF4LLM (fastest, AGPL, needs Tesseract for scans) or Docling (MIT, slower, built-in OCR); time both on `samples/` and record the decision.
- [ ] Extract text per page and store it in a `pages` table for citation checks and re-runs.
- [ ] Mark pages with little or no text as needing image handling (done in Phase 8).

### 4B. Chunking

- [ ] Split page text into chunks within a configurable token budget, keeping page numbers on every chunk.

### 4C. Tests and Manual Verification

- [ ] Tests against `samples/`: page counts, non-empty text, page numbers on chunks.
- [ ] Bruno: upload a sample and confirm the job still reaches `succeeded`.

### 4D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how page-tagged chunks make citations possible.

Suggested commit message: `feat(backend): extract text per page and chunk documents`

## 5. Guardrails

Goal: detect adversarial content in layers and flag documents instead of following injected instructions.

Solves flow step 5: suspicious documents are flagged in the job response.

### 5A. Programmatic Checks

- [ ] Detect injection phrases and fake role markers, invisible Unicode characters, long encoded blobs, and hidden text (white or tiny font).
- [ ] Store each finding with its page and rule in a `guardrail_results` table.

### 5B. Jev Classifier Adapter

- [ ] Implement a `JevClassifier` behind the `Classifier` interface, returning the probability that a chunk contains instructions aimed at the model.
- [ ] Add a configurable flag threshold; keep the mock classifier as the default.
- [ ] Use Jev for inferred document type (a choice from a fixed list).
- [ ] Keep the Jev questions and option descriptions in `prompts.yaml`, not in code.

### 5C. Flagging

- [ ] Set `flagged` on the document when any check fires, and include the reasons in `GET /jobs/{id}`.
- [ ] Decide whether flagged documents continue with a warning or pause the job for the analyst, and record it.

### 5D. Tests and Manual Verification

- [ ] Tests: the adversarial sample is flagged; a benign document that discusses prompt injection is not.
- [ ] Bruno: upload the adversarial sample and see `flagged: true` with reasons.

### 5E. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and why cheap checks run before the model-based one.

Suggested commit message: `feat(backend): add layered guardrails and document flagging`

## 6. Document Summaries and Consolidation

Goal: real LLM summaries per document and a consolidated report, validated against schemas.

Solves flow step 6: the job's results contain real key details and a report.

### 6A. Output Schemas

- [ ] Define the per-document schema: title, inferred type, short summary, main topics, key entities, notable points with page number and supporting quote.
- [ ] Define the report schema: overall summary, common themes, contradictions, combined entities, takeaways, flagged documents, excluded files.
- [ ] Each contradiction holds both claims, each with its document, page, and quote.

### 6B. GLM Adapter

- [ ] Implement an OpenAI-compatible `LLMProvider` adapter, with base URL, model, and key from config, so GLM or any compatible provider is a config change.
- [ ] Request JSON output, validate against the Pydantic schema, and retry up to a configured limit on invalid output.
- [ ] Add a per-call timeout.

### 6C. Prompts

- [ ] Write every system prompt and user template for chunk summary, document combine, and consolidation in `prompts.yaml`, each with an ID and version.
- [ ] Record the prompt ID and version with every LLM call, and run the evals in CI whenever `prompts.yaml` changes.
- [ ] Apply datamarking to document text: interleave a marker character through it, and explain in the system prompt that marked text is data, never instructions.
- [ ] Ask the consolidation prompt to list disagreements explicitly instead of a single consensus.

### 6D. Summarise and Consolidate

- [ ] Summarise each chunk, then combine chunk summaries into the document schema (map-reduce), passing relevant source excerpts into the combine step.
- [ ] Consolidate from validated document summaries only, listing flagged and excluded files.

### 6E. Citation Checks and Telemetry

- [ ] Verify each notable point's quote appears on its cited page; drop or mark points that fail.
- [ ] Store model, prompt version, tokens, and latency per LLM call; include totals per job in `GET /jobs/{id}`.

### 6F. Tests and Manual Verification

- [ ] Tests with the mock provider: valid output passes, invalid output retries then fails cleanly, citation checks catch a wrong page.
- [ ] Manual: set a real GLM key in `.env`, upload `samples/`, and inspect the report through Bruno.

### 6G. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how schemas, retries, and citation checks make LLM output trustworthy.

Suggested commit message: `feat(backend): add LLM document summaries and consolidated report`

## 7. Evals

Goal: measure pipeline quality with golden and adversarial sets, so later prompt or model changes are judged on numbers.

Solves flow step 7: every prompt, model, or provider change can be compared against a baseline.

### 7A. Eval Sets

- [ ] Add `backend/evals/golden/` with expected topics, entities, and themes for each sample, plus the expected contradiction between the disagreeing samples.
- [ ] Add `backend/evals/adversarial/` with injection cases, false-positive traps, and expected safe behaviour.

### 7B. Eval Runner

- [ ] Add a runner with programmatic scores first: schema validity, entity recall, topic coverage, citation accuracy (quote on cited page), contradiction surfaced, injection resistance, and unsupported claims.
- [ ] Add an LLM judge for coverage and conciseness, averaged over several runs.
- [ ] Add a short human spot-check checklist for the sample outputs.
- [ ] Compare reasoning modes on and off through the evals before enabling them.
- [ ] Save results with the model and prompt versions, so runs can be compared.

### 7C. CI and Manual Runs

- [ ] Run the evals in CI with the mock provider, checking the harness and the adversarial handling.
- [ ] Run the evals manually against real models and commit the results file.

### 7D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how evals turn model and prompt choices into measured decisions.

Suggested commit message: `feat(backend): add golden and adversarial evals`

## 8. Images and Scanned Pages

Goal: understand content that is not extractable text.

Solves flow step 8: charts and scanned pages contribute to summaries.

### 8A. Approach Decision

- [ ] Decide between OCR, a multimodal model, or OCR for scanned text plus a multimodal model for charts; record it.
- [ ] If Docling was chosen in Phase 4, use its built-in OCR for scanned pages before adding another tool.

### 8B. Implementation

- [ ] Render flagged low-text pages to images and process them with the chosen approach behind an adapter.
- [ ] Feed the resulting text into chunking with the same page numbers.
- [ ] If OCR needs a system package, add it to the backend image and confirm the Compose stack still starts with one command.

### 8C. Tests and Manual Verification

- [ ] Test with the scanned and image-heavy samples; rerun the evals and compare against Phase 7.

### 8D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and the cost and accuracy trade-offs of the chosen approach.

Suggested commit message: `feat(backend): handle images and scanned pages`

## 9. Frontend Foundations

Goal: frontend tooling and a typed API client, ready to build screens.

### 9A. Tooling

- [ ] Add Tailwind CSS and shadcn/ui; add the components needed later (button, card, tabs, progress, alert, dialog).
- [ ] Add TanStack Query with a query client provider, and a router with routes `/` and `/jobs/:id`.

### 9B. Typed API Client

- [ ] Generate TypeScript types from the backend's OpenAPI schema, with a script to regenerate them.
- [ ] Add API functions for every job endpoint, mapping the backend error schema to one client error type.

### 9C. Verification Setup

- [ ] Add Playwright with a smoke test that loads `/` against the Compose stack in mock mode.
- [ ] Run the smoke test in the CI `docker` job.

### 9D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how generated types keep the frontend in step with the backend.

Suggested commit message: `feat(frontend): add tailwind, shadcn, tanstack query, and typed api client`

## 10. Frontend Upload Flow

Goal: the analyst uploads files and resolves any rejected ones.

Solves flow step 9: landing page, upload, and the three choices for rejected files.

### 10A. Landing Page and Upload

- [ ] Build the landing page: title, a one- or two-line instruction, and a drag-and-drop file input with a file picker.
- [ ] Validate type, size, and count on the client; let the analyst replace or remove rejected files before upload.
- [ ] Submit to `POST /jobs` and navigate to `/jobs/{id}`.

### 10B. Rejected Files Screen

- [ ] Show rejected files with reasons, and the three choices: re-upload, continue without them, cancel.
- [ ] Wire each choice to its endpoint and refresh the job.

### 10C. Tests and Manual Verification

- [ ] Playwright smoke tests: valid upload reaches the progress screen; mixed upload shows the rejected screen; each choice works.
- [ ] Agentic verification: an agent drives the running UI through each upload case and reports what it sees.

### 10D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the UI mirrors the job state machine.

Suggested commit message: `feat(frontend): add upload and rejected-files flow`

## 11. Frontend Progress and Report

Goal: the analyst watches progress and reads the report, and the URL survives refresh.

Solves flow step 10: progress, report, and error states.

### 11A. Progress

- [ ] Poll `GET /jobs/{id}` every 1–2 seconds only while the job is `queued`, `running`, or `consolidating`.
- [ ] Show a progress bar, each document's state, and flag warnings as soon as they appear.
- [ ] Decide whether document tabs fill in during progress or the report appears at the end, and record it.

### 11B. Report

- [ ] Transition smoothly from progress into the report.
- [ ] Overview tab with the consolidated report and excluded files; one tab per document with key details and citations.

### 11C. States and URL

- [ ] Show `failed`, `cancelled`, and `expired` with the reason and a link back to upload; show `404` as "job not found".
- [ ] Show a global error when the backend is unreachable.
- [ ] Load any job state directly from `/jobs/{id}` on refresh.

### 11D. Past Summaries

- [ ] Store created job IDs in local storage and list them on the landing page; drop jobs that return `404` or `expired`.
- [ ] Decide placement (left sidebar or below the upload) and record it.

### 11E. Tests and Manual Verification

- [ ] Playwright smoke tests: upload samples in mock mode, reach the report, refresh on `/jobs/{id}`, open a past summary.
- [ ] Agentic verification of progress, report tabs, flags, and failure states, with screenshots for the README.

### 11F. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how polling and URL state make the async flow feel fast.

Suggested commit message: `feat(frontend): add progress, report, and past summaries`

## 12. Enhancements

Goal: good-to-have improvements from the architecture, built only once the core is green.

### 12A. Retries

- [ ] Exponential backoff with jitter for timeouts, `429`, and `5xx`; honour `Retry-After`; cap attempts; never retry permanent failures.

### 12B. Document Caching

- [ ] Cache document results by file hash plus pipeline version (model, prompt, schema); cache consolidation by the set of hashes.

### 12C. Download

- [ ] Add a download button exporting the summaries; decide Markdown, PDF, or both.

### 12D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how each enhancement helps the system scale.

Suggested commit message: `feat: add retries, caching, and report download`

## 13. README and Submission Docs

Goal: the repo explains itself to a reviewer.

### 13A. README

- [ ] Solution overview, architecture diagram, setup instructions, screenshots of generated outputs, assumptions, and known limitations.
- [ ] Design decisions: output schema, model choice, chunking strategy, and async processing.
- [ ] Assumptions grouped by task, one section per task.
- [ ] CI badge and a link to `samples/`.

### 13B. Clean-Machine Check

- [ ] Fresh clone, `cp .env.example .env`, `docker compose up`, upload the samples; everything works in mock mode and with a real key.

### 13C. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the docs map to each required deliverable.

Suggested commit message: `docs: complete readme with design decisions and assumptions`

## Final Acceptance Pass

Goal: Prove the whole feature is correct, usable, observable, and safe enough to keep.

### Final A. Full Test Pass

- [ ] Backend unit and integration tests pass against Postgres.
- [ ] Bruno collection passes through the Bruno CLI against the Compose stack.
- [ ] Playwright smoke tests pass.
- [ ] Lint, format, and type checks pass (ruff, mypy, oxlint, tsc); both Docker images build; CI is green.

### Final B. User Flow Pass

- [ ] Upload the samples, watch progress, and read the report in the UI.
- [ ] Failure case: invalid and adversarial samples are rejected or flagged with clear reasons.
- [ ] Recovery case: resolve a mixed upload by re-uploading, continuing, and cancelling; refresh mid-job and see the same state.

### Final C. Docs and Decision Pass

- [ ] `architecture.md` and `PRD.md` match what was built.
- [ ] Every decision made during the phases is in `decision-record.md`.
- [ ] Open decisions in `architecture.md` are resolved or listed as known limitations.
- [ ] Decide whether to build the optional AI feature.

### Final D. Learning Checkpoint

- [ ] Learning: explain the full feature end to end with final code paths, diagrams when helpful, manual test commands, infrastructure involved, and tradeoffs learned.

Suggested commit message: `chore: complete acceptance pass`
