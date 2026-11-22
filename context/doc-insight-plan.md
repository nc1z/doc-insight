# PLAN: doc-insight

This plan builds doc-insight in phases, following [architecture.md](architecture.md) and [PRD.md](PRD.md). The backend comes first: foundations, then the upload and job API, then a worker running a mocked pipeline end to end, then real extraction, guardrails, and LLM steps. Every backend phase is testable through Bruno before any UI exists. The frontend starts only once the backend is complete, and builds against the `GET /jobs/{id}` contract defined in the architecture.

Every external dependency is built behind an interface, with a mock or local adapter as the baseline. The interface and its first adapter are added in the phase that first uses that dependency. Real providers are added later as new adapters, not rewrites. Add a package only in the phase that first puts a file in it; do not scaffold empty directories ahead of that work. Out of scope for this plan: production AWS infrastructure, authentication, and the optional AI feature (considered only after the final acceptance pass).

Primary services/packages/frameworks:

- **FastAPI**: REST API, request validation, and auto-generated OpenAPI docs that the frontend types are generated from.
- **Postgres + SQLAlchemy 2 + Alembic**: job store, results store, and queue in one database; migrations run automatically at startup.
- **Postgres-backed queue library (Procrastinate or PGQueuer)**: lets the API create and enqueue a job in one transaction, and runs the worker.
- **pydantic and pydantic-settings**: typed config from environment variables, and the schemas every LLM output is validated against.
- **PyMuPDF4LLM**: per-page text. A page is marked for image handling in Phase 8 when `get_image_info()` shows an image on that page.
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

Goal: config, Postgres, migrations, error handling, and logging. Later phases add their own packages with the feature that needs them.

### 0A. Config

- [x] Add `app/core/` with `pydantic-settings` and a typed `Settings` class in `config.py` (database URL, MinIO endpoint, bucket, and keys, file limits, provider names, model names, API keys, timeouts).
- [x] Add `.env.example` with every setting, defaulting providers to `mock`, so the stack runs with no API key.
- [x] Switch `app/main.py` to an app factory that wires settings, routers, and dependencies.
- [x] Add mypy to the dev dependencies and the `lint` script.

Defaults in `Settings` and `.env.example`: mock providers, 20 MiB / 100 pages / 10 files, 60s LLM timeout, 30s classifier timeout. A hosted provider refuses to start without its key (and, for the LLM, its base URL). `app = create_app()` stays at module level so `fastapi run app/main.py` keeps working. Job-expiry and step timeouts wait for the phases that use them.

### 0B. Postgres, ORM, and Migrations

- [x] Add a `postgres` service to `docker-compose.yml` with a named volume and a healthcheck; the backend waits for it.
- [x] Add SQLAlchemy 2 (async) with psycopg 3, a session factory, and a FastAPI dependency for sessions.
- [x] Add Alembic with an empty initial migration; run `alembic upgrade head` on container start before the API starts.
- [x] Extend `/health` to report database connectivity, keeping the response shape Bruno already tests.

A healthy database still returns `{ "status": "ok" }`. If the check fails, the route returns `503`. Compose sets `DATABASE_URL` to the `postgres` service. The container runs `alembic upgrade head` before the API starts. The empty revision is `0001_initial`.

### 0C. Errors, Logging, and Request IDs

- [x] Define one error schema (`code`, `message`, `details`) and the exception handlers that map domain errors to HTTP status codes, both in `app/core/`.
- [x] Add structured JSON logging with a request ID middleware; return the ID in an `X-Request-ID` header.

Errors use one body: `code`, `message`, and `details`. `DomainError` carries the status code. Validation errors, HTTP errors, and unhandled errors use that same body; an unhandled error is logged and the response stays generic. Every response includes `X-Request-ID`. A valid incoming ID is echoed, and any other value is replaced. Request logs are one JSON line and include that ID.

### 0D. Tests, CI, and Bruno

- [x] Add a pytest fixture that runs migrations against a test database, and a test for `/health`.
- [x] Add a Postgres service container to the CI `ci` job so backend tests run against a real database.
- [x] Confirm the CI `docker` job still passes with the new Postgres service.

The migration fixture uses the `postgres-test` Compose service on port 5433. That service reads `TEST_POSTGRES_USER`, `TEST_POSTGRES_PASSWORD`, and `TEST_POSTGRES_DB`. The fixture creates that database there and runs `alembic upgrade head`. It does not connect to the app database. One test reads `alembic_version`; another calls `/health` against that database. The CI `ci` job starts that same service. `docker compose up` leaves it stopped. The `docker` job is unchanged: it still builds the stack and curls `/api/health`. Bruno's health request also expects `X-Request-ID`.

### 0E. Learning Checkpoint

- [x] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how config, the database session, and error handling give later phases a base to build on. Packages for domain, adapters, API, pipeline, and worker are not created here.

A config loader reads variables from `.env`. Postgres is accessed through the SQLAlchemy ORM, with Alembic migrations. Logging is structured JSON. Integration tests talk to a separate test database.

Suggested commit message: `feat(backend): add config, postgres, and migrations`

## 1. Upload and Job Creation

Goal: `POST /jobs` validates uploads, stores valid files, and creates a job that is queued or waiting for the analyst.

Solves flow step 1: a client (Bruno) uploads PDFs and gets an immediate job ID.

### 1A. Data Model

- [x] Add `app/domain/` with SQLAlchemy models for the `jobs` and `documents` tables: job status, document status, filename, storage key, SHA-256 hash, page count, rejection reason, and an `excluded` flag. Point Alembic `target_metadata` at those models and generate the migration with `alembic revision --autogenerate`.
- [x] Define job and document status enums in that package, matching the job and document states in the architecture.

`JobStatus` and `DocumentStatus` use the architecture's state names. A document also has `flagged`, because a flagged document can still succeed. Storage key, hash, page count, and rejection reason are optional so a rejected file can be recorded before it is stored. Migration `0002_jobs_documents` was generated from the models.

### 1B. File Validation

- [x] Add a validator in `app/domain/validation.py` that checks MIME type, `%PDF` magic bytes, size, page count, encryption, and JavaScript or embedded files.
- [x] Read all limits (file size, page count, file count) from config.
- [x] Return a typed per-file result with an error code and message for each rejection.
- [x] Decide `413` versus a per-file `422` for limit errors, and record it in `decision-record.md`.

`validate_files` runs a list of strategies in order and stops at the first rejection. The default list is `FileValidation` (file count, file size, allowed media types) then `PdfValidation` (`%PDF` header, parse, encryption, JavaScript, embedded files, page limit). A later format is another strategy in that list. Each rejected file has one code and the message from the eval set. Too many files rejects the upload with `file_count_exceeded` and does not inspect the files. Limit failures are `422`, recorded on `2026-11-21`. The endpoint that returns that status arrives in 1E.

### 1C. MinIO File Storage

- [x] Add a `minio` service to `docker-compose.yml` with a named volume and a healthcheck. The API and worker use it. No cloud account.
- [x] Add `app/adapters/` with an S3 `FileStorage` implementation in `app/domain/ports.py`, pointed at the endpoint, bucket, and keys from config. Create the bucket on startup if it is missing.
- [x] Add a factory that picks the storage adapter from config and is injected through FastAPI dependencies. Later adapters register on the same factory.

MinIO runs in Compose with the `minio_data` volume. The image is `alpine/minio`, a community mirror, because `minio/minio` no longer pulls. The API container uses `http://minio:9000` and creates the bucket on startup. `FileStorage` is the port. `S3FileStorage` is the adapter, and `build_file_storage` selects it from `storage_provider`. `get_file_storage` injects that instance. The worker service arrives later and uses the same bucket.

### 1D. Queue Library and Create-and-Enqueue

- [x] Confirm which library (Procrastinate or PGQueuer) can enqueue on the same connection and transaction that creates the job; pick it and record the decision.
- [x] Add a `JobRepository` protocol with a single `create_and_enqueue` operation, and implement `PostgresJobRepository` in `app/adapters/` so the job row and the queue entry commit in one transaction. Register it on the adapter factory.

Procrastinate is the queue, recorded on `2026-11-22`. `PostgresJobRepository.create_and_enqueue` inserts the job and defers `process_job` on the same connection. The payload is the job id. Migration `0003_procrastinate` applies the queue schema. `build_job_repository` selects it from `queue_provider`.

### 1E. POST /jobs

- [x] Add `app/api/` with the jobs router and `app/schemas/` with the upload response models.
- [x] All files valid: store each file, create and enqueue the job, return `202` with the job ID and status `queued`.
- [x] Some files rejected: store valid files, create the job as `awaiting_input` without enqueuing, return `201` with accepted and rejected files.
- [x] No valid files: store nothing, return `422` with the per-file error list.

`POST /jobs` validates with the strategy list, then stores only accepted files. Every file valid returns `202` and `create_and_enqueue`. A mix returns `201` and `create_awaiting_input`, which records rejected files on the job and does not defer `process_job`. When every file is rejected, or the file count is over the limit, nothing is stored and the error body uses the existing `code` / `message` / `details` shape. Per-file reasons are in `details.rejected`.

### 1F. Sample Fixtures

- [x] Add a fixture builder that generates the eval PDFs from `backend/evals/fixtures.json` (text, scanned, chart, hidden-text, and invalid binary variants); generated PDFs are not committed.
- [x] Turn the `ci_mock` file-validation cases in `backend/evals/adversarial.json` (A14–A22) into integration tests.
- [x] Add `samples/` with 2–4 real PDFs on one topic for the demo and a `samples/README.md` listing source and licence.
- [x] Include at least two samples that disagree on a fact, so the report must surface a contradiction.
- [x] Add `samples/invalid/`: corrupt, encrypted, empty, and non-PDF renamed to `.pdf`.
- [x] Add `samples/adversarial/` with a PDF containing injected instructions.

`backend/evals/builder.py` renders `fixtures.json` when a test asks for a document. Text keeps a text layer, scanned pages and charts are images, hidden text is white 1pt type, and invisible text is Unicode tag characters. `python -m evals.builder` writes the files under `backend/evals/generated/`, which is gitignored. A14–A22 upload those files and check the status, the error code, and that no job is stored. `samples/` is a fictional Cedar Ridge Capital packet on Northline Semiconductor (NTLN), released as CC0. Short notes sit next to a few longer memos. The desk and the broker disagree on FY26 revenue, gross margin, and the price target, and the channel check disagrees with the desk on the order book. `samples/invalid/` is unchanged.

### 1G. Tests and Manual Verification

- [x] Unit tests for each validation rule, using small PDFs generated in tests.
- [x] Integration tests for the three `POST /jobs` outcomes, checking stored files, job rows, and queue entries.
- [x] Bruno requests for valid, mixed, and all-invalid uploads using files in `samples/`.
- [x] Expected result: `202`, `201`, and `422` respectively, each with the documented response body.

`backend/tests/test_validation.py` generates a small PDF per rule. `backend/tests/test_create_job.py` checks the three outcomes against stored bytes, job rows, and queue rows. Bruno's `upload-valid`, `upload-mixed`, and `upload-invalid` requests send `samples/desk-note.pdf` and the files in `samples/invalid/`.

### 1H. Learning Checkpoint

- [x] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how atomic create-and-enqueue keeps jobs from being stranded. The domain, adapter, API, and schema packages arrive with this feature.

An upload is validated, stored in MinIO, then written as a job. A fully valid upload inserts the job row and the Procrastinate queue row in one transaction, so a queued job cannot be left without a worker task. A mixed upload is saved as `awaiting_input` and is not queued.

Suggested commit message: `feat(backend): add job creation with file validation and storage`

## 2. Job Status and Actions

Goal: the full job API: read status, re-upload, confirm, cancel, and expiry.

Solves flow step 2: a client (Bruno) reads any job's state and resolves rejected files through the API.

### 2A. GET /jobs/{id}

- [x] Add the `GET /jobs/{id}` response schema in `app/schemas/`, exactly as in the architecture status flow: status, progress, documents (status, flagged, error, summary), rejected and excluded files, report, error.
- [x] Return `404` with the error schema for an unknown ID.
- [x] Check the generated OpenAPI schema at `/docs` matches the response.

`GET /jobs/{id}` returns `JobView`. Stored files are `documents`. Files that were never stored are `rejected_files`, and files the analyst dropped are `excluded_files`. `summary`, `report`, and the job `error` are null until later phases fill them. Progress counts finished documents against the documents still in the job. An unknown id returns `404` with code `not_found`.

### 2B. Job State Machine

- [x] Add a state machine in `app/domain/job_state.py` listing allowed transitions; invalid transitions raise a domain error mapped to `409 Conflict`.

`transition` lists the allowed status changes. A waiting job can stay waiting, be confirmed into `queued`, be cancelled, or expire. The worker moves `queued` to `running`, then `consolidating`, then `succeeded`, or to `failed` from either active state. Any other change raises `invalid_job_state` with status `409`.

### 2C. Re-upload, Confirm, and Cancel

- [x] `POST /jobs/{id}/documents`: validate and store new files, add accepted ones, update the rejected list; job stays `awaiting_input`.
- [x] `POST /jobs/{id}/confirm`: mark remaining rejected files as excluded, set `queued`, and enqueue in one transaction; return `202`.
- [x] `POST /jobs/{id}/cancel`: set `cancelled`, delete stored files, return `200` with the updated job.

`POST /jobs/{id}/documents` returns the updated job and stays `awaiting_input`. A valid file whose name matches a rejection replaces that rejection; other rejections stay. `POST /jobs/{id}/confirm` marks the remaining rejections excluded, sets `queued`, and enqueues in one transaction, returning `202`. `POST /jobs/{id}/cancel` sets `cancelled` and deletes the stored files. An action the current status does not allow returns `409` with code `invalid_job_state`.

### 2D. Expiry and Cleanup

- [x] Add a periodic task that expires `awaiting_input` jobs past a configurable timeout and deletes their files.
- [x] Add a periodic task that deletes stored files with no job (orphans) older than a configurable age.
- [x] Record the `awaiting_input` timeout default in `decision-record.md`.

`expire_awaiting_jobs` and `delete_orphan_files` are Procrastinate tasks. `MAINTENANCE_CRON` sets how often they run, and the default is every 15 minutes. They run when the worker process starts. A job left in `awaiting_input` expires after `AWAITING_INPUT_TIMEOUT_SECONDS` (default 24 hours) and its files are deleted. A re-upload refreshes that clock. A bucket object that no document references is deleted after `ORPHAN_MAX_AGE_SECONDS` (default 1 hour).

### 2E. Tests and Manual Verification

- [x] Integration tests for each action, including `409` for confirming a cancelled job and re-uploading to a queued job.
- [x] Test expiry and orphan cleanup with a short configured timeout.
- [x] Bruno requests for get, re-upload, confirm, and cancel, chained through a collection variable holding the job ID.
- [x] Expected result: a mixed upload can be resolved three ways through Bruno alone.

The action tests cover re-upload, confirm, and cancel, including `409` for confirming a cancelled job and re-uploading to a queued job. Expiry and orphan cleanup also run with a 1-second configured timeout. Bruno keeps each scenario in its own folder. Happy flow uploads two valid files and reads the queued job. Mixed re-upload and confirm saves `jobId`, reads the waiting job, adds a replacement, and confirms. All fail uploads three invalid files and expects `422` with no job.

### 2F. Learning Checkpoint

- [x] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the state machine keeps the API and worker in agreement.

`transition` is the only list of legal status changes. The API calls it for re-upload, confirm, and cancel. Expiry calls it to move a stale waiting job to `expired`. The worker will call the same function for `queued` → `running` → `consolidating` → `succeeded` or `failed`, so neither side can invent a status the other does not allow.

Suggested commit message: `feat(backend): add job status, actions, and expiry`

## 3. Worker and Mocked Pipeline

Goal: a first working backend end to end: upload, process asynchronously with mock steps, poll to `succeeded`.

Solves flow step 3: the worker claims the job and moves it through every state.

### 3A. Queue Model Decision

- [x] Decide between one task per job and one task per document plus a consolidation task triggered when the last document finishes.
- [x] Update the architecture to remove the contradiction between "only the job ID goes on the queue" and "each document is its own queue task", and record the decision.

Creating or confirming a job enqueues one task per stored document in the same transaction. The payload is the document id. The document task that locks the job and finds every stored document `succeeded` or `failed` moves the job to `consolidating` and inserts the consolidation task, whose payload is the job id, on that same connection. The queue never carries file bytes.

### 3B. Worker Process

- [x] Add `app/worker/` with the worker entry point, using the queue library and the same adapter factory as the API. It runs from the same image with a different command.
- [x] Add a `worker` service to `docker-compose.yml` using the same MinIO service and database.
- [x] Make every step idempotent: store each step's status, and skip steps already completed on retry.

`python -m app.worker` runs in the same image as the API. Create and confirm insert one `process_document` task per stored document. The task stores the document status after each step, and a retry continues from that status. The task that finds every stored document finished inserts `consolidate_job` on the same connection. Consolidation marks the job `succeeded`. The work inside each step is still empty.

### 3C. Pipeline Skeleton

- [x] Add `app/pipeline/` with step functions that have typed inputs and outputs: extract, check, summarise, consolidate.
- [x] Add `LLMProvider` and `Classifier` protocols in `app/domain/ports.py`, and mock adapters in `app/adapters/` with deterministic outputs. Register them on the factory.
- [x] Wire each step to the mock adapters, with configurable delays so mock mode shows realistic progress.
- [x] Update job and document statuses and progress counts as steps complete.

Extract, check, summarise, and consolidate are typed step functions. The factory selects the mock LLM and classifier, which return the same output for the same input. `MOCK_STEP_DELAY_SECONDS` defaults to 1 second and pauses the current step, so a poll can see `extracting`, `checking`, and `summarising`. The status is stored before that step runs, and a retry repeats it. A finished document stores its summary. Consolidation stores the report and marks the job `succeeded`. Progress counts those three finished steps per stored document.

### 3D. Processing Failures

- [x] Decide what happens when a document fails during processing (fail the job, continue without it, or pause for the analyst), and record it.
- [x] Implement the decision, plus a timeout on each step that marks the document failed with a clear reason. Each step waits at most `STEP_TIMEOUT_SECONDS` (default 60). A timeout or other transient error retries 3 times with full jitter, then that document is `failed`. `POST /jobs/{id}/retry` requeues it. Confirm excludes it and continues.

A transient step failure retries 3 times with exponential backoff and jitter. After that, only that document is `failed` and shows the error. The other documents keep processing. Consolidation waits until the analyst retries the failed document, continues without it, or cancels.

### 3E. Tests and Manual Verification

- [x] Integration test: create a job, run the worker in-process, assert the job reaches `succeeded` with mock summaries and report.
- [x] Integration test: a forced step failure produces the decided failure behaviour.
- [x] Bruno: upload, then poll `GET /jobs/{id}` until `succeeded`. Happy flow uploads the two samples and polls for up to 30 seconds. Processing failure is a manual folder: `unreadable.pdf` is a blank page, so the note on its upload request says to throw `StepFailure("unreadable_document", permanent=True)` from `extract_text` and restart the worker before running `pnpm bruno:manual`. `pnpm bruno` skips that folder.
- [x] Run the Bruno collection with the Bruno CLI in the CI `docker` job against the Compose stack in mock mode. `pnpm bruno` runs `@usebruno/cli` after the stack is healthy.

### 3F. Learning Checkpoint

- [x] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how the API and worker cooperate through Postgres alone.

The API writes the job and one queue row per document. The worker, a second process from the same image, claims those rows and runs extract, check, and summarise. A failed document keeps its error while the others continue. The analyst retries it or continues without it. Consolidation runs once every remaining document has succeeded. The two processes share Postgres and MinIO and do not call each other.

Suggested commit message: `feat(backend): add worker and mocked processing pipeline`

## 4. Text Extraction

Goal: real per-page text extraction replaces the mock extract step.

Solves flow step 4: the worker reads each document's text, keeping page numbers.

### 4A. Per-Page Extraction

- [x] Choose the PDF library: PyMuPDF4LLM (fastest, AGPL, needs Tesseract for scans) or Docling (MIT, slower, built-in OCR); time both on `samples/` and record the decision.
- [x] Extract text per page and store it in a `pages` table for citation checks and re-runs.
- [x] Mark a page for image handling when `get_image_info()` shows an image on that page (done in Phase 8).

PyMuPDF4LLM reads each page of these born-digital memos in well under a second. The text is stored in `pages`. `needs_image` is set when `page.get_image_info()` lists an image displayed on the page. A short page of text stays unmarked, and so does a blank page. The scanned expert call and the chart page are marked because each displays an image. Phase 8 can render those pages for Tesseract or a vision model. PyMuPDF is AGPL, which is acceptable for this local assignment; a commercial Artifex licence is required if it ships inside a closed product.

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
- [ ] Add `prompts.yaml` in `app/pipeline/` and a loader that validates every entry (ID, version, template, placeholders) at startup; the path comes from config. Keep the Jev questions and option descriptions in that file, not in code.

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

- [ ] Use `backend/evals/golden.json` and `backend/evals/adversarial.json` as the source of truth; extend them rather than replacing them, and bump `version` when an expectation changes.
- [ ] Put the canary from `adversarial.json` in every system prompt in `prompts.yaml`.
- [ ] Load the eval files with Pydantic models, so a malformed case fails before any run.

### 7B. Eval Runner

- [ ] Add a runner with programmatic scores first: schema validity, entity recall, topic coverage, citation accuracy (quote on cited page), contradiction surfaced, injection resistance, and unsupported claims.
- [ ] Add an LLM judge for coverage and conciseness, averaged over several runs.
- [ ] Add a short human spot-check checklist for the sample outputs.
- [ ] Compare reasoning modes on and off through the evals before enabling them.
- [ ] Save results with the model and prompt versions, so runs can be compared.

### 7C. CI and Manual Runs

- [ ] Run the `ci_mock` cases in CI with the mock provider, checking API behaviour, statuses, schema shape, and programmatic flags.
- [ ] Run the `real` cases manually; a run passes only if every threshold in both files is met.
- [ ] Run the evals manually against real models and commit the results file.

### 7D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how evals turn model and prompt choices into measured decisions.

Suggested commit message: `feat(backend): add golden and adversarial evals`

## 8. Images and Scanned Pages

Goal: understand content that is not extractable text.

Solves flow step 8: charts and scanned pages contribute to summaries.

### 8A. Approach Decision

- [ ] Decide between OCR, a multimodal model, or OCR for scanned text plus a multimodal model for charts; record it.
- [ ] Render each page stored with `needs_image` and pass the image to Tesseract or a vision model.

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
