# Requirements Analysis

## Scenario: what problem they actually care about

- User: an **analyst** with **multiple documents on one topic** who needs to understand them **quickly**.
- Implications:
  - Cross-document synthesis (the consolidated report) is the core value, not just per-file summaries.
  - Output must be **skimmable and trustworthy**: structured sections, with sources traceable to their documents and pages.
  - "PDFs may contain text and images": they will check whether you handle images or scanned PDFs, or at least acknowledge the gap.
  - "Harmful documents (adversarial content)": they will check whether you know about **prompt injection** in RAG/LLM pipelines.

### Key insights from the wording

- **"Regularly"**: this happens often, so optimise for a repeatable workflow (fast re-runs, consistent output, caching by file hash), not a one-off tool.
- **"Multiple documents"**: assume a reasonable number per upload (for example up to 10 PDFs of moderate length), and enforce it with configurable limits.
- **"A quick way"**: speed matters to the user. Async processing (see [direction.md](direction.md)) can seem to contradict this, so async must feel fast:
  - Return immediately and show live per-document progress.
  - Process documents in parallel and show each result as soon as it is ready, before the consolidated report finishes.
  - Keep total time low; async exists to avoid timeouts and scale, not to make the user wait.
- **"Simple web application"**: keep what the user sees simple. Upload, watch progress, read results. Complexity belongs in the backend, not the UI.
- **"PDFs may contain text and images"**: PDF is the only input format for the MVP. Images mean extracting embedded images and charts, and OCR or a multimodal LLM for scanned pages.
- **"Analyses and understands content"**: an LLM interprets the parsed content. Break processing into explicit pipeline stages (validate, extract, chunk, analyse, validate output) rather than one prompt.
- **"Generates key details… and a consolidated summary report"**: a transform step that turns raw content into two structured outputs, per document and across documents.
- **"Displays the generated results through a web interface"**: results must be readable and well presented, not raw JSON.

### Overall shape: an ETL pipeline

- **Extract**: validate uploads, then parse PDF text, images, and scanned pages (OCR) per page.
- **Transform**: LLM analysis per document, then consolidation across documents, each validated against a schema.
- **Load**: store results and job state, then serve them to the UI.

Treating it as ETL keeps each stage separate, testable, and swappable, and maps directly onto queues and background workers.

## Baseline (must have)

### Backend (`backend/`)

- Python + FastAPI, with RESTful resource-oriented endpoints, e.g.:
  - `POST /jobs` (multipart, multiple files)
  - `GET /jobs/{id}` (status + results)
  - `GET /health`
- PDF text extraction (e.g. PyMuPDF/pdfplumber).
- LLM pipeline using a hosted API (no training or fine-tuning needed).
- **Per-document key details** in a documented structured schema:
  - title / inferred type, short summary, main topics, key entities (people, orgs, locations, dates), notable points.
- **Consolidated report** across all docs:
  - overall summary, common themes, differences/contradictions, combined entities, takeaways.
- Structured LLM output (JSON schema / Pydantic validation, retry on invalid output).
- Error handling:
  - Unsupported type: check MIME and magic bytes (`%PDF`), not just the extension.
  - Invalid/corrupt or encrypted PDFs, empty/no-text PDFs.
  - Size, page-count, and file-count limits.
  - LLM failures/timeouts, returned as clear error responses (consistent error schema, correct HTTP codes).
  - Adversarial content: basic prompt-injection mitigation (see below).
- Dockerfile (slim image, non-root user).

### Frontend (`frontend/`)

- React/Vue/Angular. React + Vite + TypeScript is the safe choice.
- Multi-file upload (drag-and-drop plus file picker), with client-side type/size validation.
- Per-document key-details view (cards/tabs) and a consolidated report view.
- **Processing states** (uploading, processing per document, done) and **error states** (per file and global).
- Partial-failure handling: if one bad file is rejected, the others still process.
- Dockerfile (multi-stage build, served by nginx).
- Stated focus: **usability, clarity, correct backend interaction**. Clean beats flashy.

### CI + local run

- GitHub Actions: lint, test (backend + frontend), and Docker builds for both images.
- Backend tests: API endpoints, validation/error cases, pipeline with a **mocked LLM** (deterministic, no key needed in CI).
- Frontend tests: component tests for upload, states, and rendering results.
- `docker-compose.yml` runs the full stack with a single command.

### README (all 6 required)

- Overview, architecture diagram (Mermaid renders natively on GitHub), setup, screenshots, assumptions, limitations.
- **Design decisions**: output schema, model choice, chunking strategy, sync vs async processing.
- Sample PDFs committed or linked. Pick 2–4 PDFs on **one topic** so the consolidation is meaningful, including at least one with images/charts.

## Good to have (shows seniority)

- **Async processing**: a background task plus status polling or SSE/WebSocket for progress. Avoids HTTP timeouts on big files.
- **Long-document handling**: chunking with map-reduce summarisation and a token-budget awareness strategy.
- **Image handling**: send page images or embedded images to a multimodal LLM, plus OCR fallback for scanned pages.
- **Source attribution**: notable points cite the document and page number, which builds analyst trust.
- **Provider abstraction**: an LLM interface that makes swapping OpenAI/Anthropic/Gemini/local (Ollama) config-only, plus a mock provider.
- Typed config via env vars (pydantic-settings), structured logging, request IDs.
- Linting/formatting/type-checking in CI (ruff, mypy, eslint, tsc).
- Container healthchecks, pinned dependencies, `.dockerignore`.
- Export the report (Markdown/PDF download).
- Clean layering: `api/`, `services/`, `pipeline/`, `schemas/`, `tests/`.

## Prompt-injection and harmful-content handling (likely a key differentiator)

- Treat document text as **untrusted data**. Use clear delimiters and system-prompt instructions to never follow instructions found inside documents.
- Pre-scan with heuristics for injection patterns (e.g. "ignore previous instructions"), and optionally an LLM/moderation classifier.
- Validate output against the schema. Reject or flag anomalies.
- Flag suspicious docs in the UI ("possible adversarial content detected") instead of silently failing.
- File-level safety: size limits, page limits, reject encrypted files and JavaScript/embedded-file PDFs, no execution of embedded content.
- Include an **adversarial sample PDF** plus a test that demonstrates the defence.

## Wow factors (pick a few, do them well)

- **Optional AI feature (choose one)**, ideally one that directly serves the analyst:
  - **Q&A / chat over uploaded docs with citations** (RAG): the most natural fit and the highest perceived value.
  - Cross-document contradiction/agreement detection.
  - Entity relationship graph or timeline visualisation.
- Live per-document progress streaming (SSE).
- Evaluation harness: a small golden set plus checks (schema validity, entity recall, injection resistance) run in CI.
- Cost/latency telemetry per job (tokens used, time taken) shown in the UI or logs.
- Caching by file hash, so re-uploads are instant and free.
- Works offline with a local model (Ollama) or mock mode, so the reviewer can run it without an API key.
- Short demo GIF/video in the README.
- A thoughtful "Known limitations and future work" section (scaling, auth, persistence, multi-tenant, better OCR) that shows you understand production gaps.

## Avoid

- Overengineering (Kubernetes, microservices, auth systems) at the cost of a polished core.
- A single giant prompt with no structure, validation, or length handling.
- Silent failures or a spinner that hangs forever.
- Requiring a paid key with no fallback and no clear instructions.
- Undocumented choices or anything you can't defend in the follow-up interview.
