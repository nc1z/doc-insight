# Architecture

Solution design for doc-insight. Product requirements live in [PRD.md](PRD.md), the architectural rules in [direction.md](direction.md), and the literature behind the pipeline design in [industry-insights.md](industry-insights.md).

## System components (POC)

_This is what we are building._

```mermaid
flowchart LR
    Analyst([Analyst]) --> Browser[Frontend<br/>React]
    Browser -- "page load and /api" --> Nginx[nginx<br/>static files + reverse proxy]
    Nginx --> API

    subgraph Backend
        API[API container<br/>FastAPI] --> DB[(Postgres<br/>jobs, results, queue)]
        API --> Files[(MinIO<br/>S3 API)]
        Worker[Worker container<br/>same image, pipeline] --> DB
        Worker --> Files
    end

    Worker --> LLM{{LLM provider<br/>text and vision models}}
```

The API and the worker are separate containers from the same image. The API container runs the HTTP server. The worker container runs `python -m app.worker` and claims queue tasks. Processing capacity is the worker: it reads files from MinIO and writes status back to Postgres, so a long job stays off the process that serves uploads and polls. Extra worker containers add processing capacity without extra API containers. The two containers meet only through Postgres and MinIO.

## System components (production AWS)

_Envisioned architecture if we were to go to production._ These parts swap in through adapters, with no changes to API or worker logic:

- **Queue**: Postgres queue to SQS, with an outbox behind the same create-and-enqueue operation.
- **File storage**: MinIO to AWS S3, a configuration change (endpoint, bucket, and keys). The adapter stays the same.
- **LLM provider**: mock or hosted model to Bedrock or another provider.
- **Job store**: Postgres to RDS Postgres, a configuration change only.

Hosting (nginx to CloudFront and a load balancer) is an infrastructure change, not a code change. Authentication with Cognito is new work, not a swap.

```mermaid
flowchart LR
    Analyst([Analyst]) --> CF[CloudFront]
    CF -- "static files" --> Static[(S3<br/>frontend build)]
    CF -- "/api" --> ALB[Application Load Balancer]
    Analyst -. "sign in" .-> Cognito[Cognito<br/>auth]

    subgraph Backend
        ALB --> API[API<br/>ECS Fargate]
        API -- "job + outbox row,<br/>one transaction" --> DB[(RDS Postgres<br/>jobs, results, outbox)]
        API --> Files[(S3<br/>uploads)]
        Relay[Outbox relay] -- "read unsent rows" --> DB
        Relay -- "publish document id<br/>or consolidation job id" --> SQS[[SQS<br/>with dead-letter queue]]
        SQS --> Worker[Worker<br/>ECS Fargate, scales on queue depth]
        Worker --> DB
        Worker --> Files
    end

    API -. "verify token" .-> Cognito
    Worker --> LLM{{Bedrock or external LLM provider}}
```

## Upload flow

What happens from the moment the analyst selects files until the job is queued. Processing by the worker is a separate flow.

A job only starts when every file is accepted, or when the analyst explicitly chooses to continue without the rejected ones.

### Happy path: all files valid

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as Frontend
    participant API as API
    participant Files as File storage adapter
    participant Jobs as Job store and queue adapter (Postgres)

    Analyst->>UI: Select one or more PDFs
    UI->>UI: Validate type, size, and file count
    UI->>API: POST /jobs (multipart)
    API->>API: Validate each file
    loop Each file
        API->>Files: Store file
        Files-->>API: Storage key
    end
    API->>Jobs: Create job (queued) and enqueue<br/>one task per document, in one transaction
    Jobs-->>API: Job ID
    API-->>UI: 202 Accepted (job ID, status queued)
    UI-->>Analyst: Show per-document progress
```

- **Validation happens twice.** The client check gives fast feedback. The server check is the one that is enforced, because client checks can be bypassed.
- **Server validation** checks MIME type, `%PDF` magic bytes, size, page count, encryption, and JavaScript or embedded files. A file that fails is a per-file rejection. Size, page, and file-count limits use that same result with `422`, including a whole upload that has too many files.
- **Files rejected on the client** are shown with reasons before upload, so the analyst can replace or remove them first.
- **`202 Accepted`** means the job is queued, not that it has finished. The UI follows progress through the [status flow](#status-flow).

### Negative case: all files rejected

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as Frontend
    participant API as API

    UI->>API: POST /jobs (multipart)
    API->>API: Validate each file, none pass
    API-->>UI: 422 with a per-file error list
    UI-->>Analyst: Show why each file was rejected
```

No files are stored and no job is created, so there is nothing to clean up. The analyst selects new files and starts again.

### Negative case: some files rejected

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as Frontend
    participant API as API
    participant Files as File storage adapter
    participant Jobs as Job store and queue adapter (Postgres)

    UI->>API: POST /jobs (multipart)
    API->>API: Validate each file, some fail
    loop Each valid file
        API->>Files: Store file
        Files-->>API: Storage key
    end
    API->>Jobs: Create job (awaiting_input), with accepted and rejected files
    Jobs-->>API: Job ID
    API-->>UI: 201 Created (job ID, status awaiting_input, accepted, rejected)
    UI-->>Analyst: Show rejected files and three choices
```

- **The job is not enqueued.** It waits in `awaiting_input` until the analyst re-uploads the rejected files, continues without them, or cancels.
- **Why**: the consolidated report is only correct if it covers every document the analyst meant to include. Silently dropping a document can change the conclusion, for example a market analysis behind a trade, or identifying suspects from evidence documents. The analyst must know what is missing and accept it.
- **`201 Created`** means the job exists but is waiting for the analyst.
- **Accepted files are stored straight away**, so re-uploading only sends the rejected files again.

#### Choice: re-upload rejected files

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as Frontend
    participant API as API
    participant Files as File storage adapter
    participant Jobs as Job store and queue adapter (Postgres)

    Analyst->>UI: Pick replacement files
    UI->>API: POST /jobs/{id}/documents (multipart)
    API->>API: Validate each file
    API->>Files: Store valid files
    API->>Jobs: Add accepted files, update rejected list
    API-->>UI: Updated job (still awaiting_input)
    UI-->>Analyst: Show remaining rejected files, if any, and the three choices
```

The job stays in `awaiting_input` even when nothing is left rejected, so the analyst confirms the final set of files before processing starts.

#### Choice: continue without rejected files

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as Frontend
    participant API as API
    participant Jobs as Job store and queue adapter (Postgres)

    Analyst->>UI: Continue
    UI->>API: POST /jobs/{id}/confirm
    API->>Jobs: Set status queued, record excluded files,<br/>and enqueue one task per stored document, in one transaction
    API-->>UI: 202 Accepted
    UI-->>Analyst: Show per-document progress
```

Excluded files are recorded on the job and listed in the consolidated report, so anyone reading it can see which documents were left out.

#### Choice: cancel

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as Frontend
    participant API as API
    participant Files as File storage adapter
    participant Jobs as Job store and queue adapter (Postgres)

    Analyst->>UI: Cancel
    UI->>API: POST /jobs/{id}/cancel
    API->>Jobs: Set status cancelled
    API->>Files: Delete stored files
    API-->>UI: 200 OK (updated job, status cancelled)
```

If the analyst never decides, the job expires after 24 hours and its stored files are deleted.

### Job states during upload

```mermaid
stateDiagram-v2
    [*] --> queued: all files valid
    [*] --> awaiting_input: some files rejected
    awaiting_input --> awaiting_input: re-upload
    awaiting_input --> queued: continue
    awaiting_input --> cancelled: cancel
    awaiting_input --> expired: no decision before timeout
    queued --> [*]: document tasks start
    cancelled --> [*]
    expired --> [*]
```

### Notes

- **The API coordinates every step.** Each adapter does one thing and never calls another adapter.
- **State changes use action endpoints**: `POST /jobs/{id}/confirm`, `POST /jobs/{id}/retry`, and `POST /jobs/{id}/cancel`. Confirm accepts the final set of files, or continues without a document that failed during processing. Retry requeues that failed document. Each action is explicit, and the server rejects actions that are invalid for the job's current state with `409 Conflict`. Cancel is a `POST`, not a `DELETE`, because the job record stays with status `cancelled`.
- **Postgres is the job store and the queue.** Procrastinate inserts each queue row on the same connection as the job row, so they commit together and a crash cannot leave a queued job with no document task. This removes the need for an outbox or sweeper. Workers claim ready tasks with `SELECT … FOR UPDATE SKIP LOCKED` and must still be idempotent, because a task can be retried after a worker crash.
- **One operation for create and enqueue.** Creating a queued job and inserting one queue row per stored document is a single operation. The Postgres adapter does it in one transaction; another queue provider would need an outbox behind the same interface.
- **The queue carries ids, not file bytes.** A document task carries the document id. The consolidation task carries the job id. The worker loads the job and reads the file from storage by its storage key.
- **The last finished document starts consolidation.** That task locks the job and marks itself finished. Consolidation starts only when every stored document has succeeded. A failed document shows its error and does not stop the others. The analyst retries it, continues without it, or cancels. Continuing without it excludes the file, and the report lists it. A second finisher finds the job already past `running`, so it does not start another report.
- **Orphaned files are cleaned up, not prevented.** If storing a file succeeds but creating the job fails, the file is left without a job. A retention rule or cleanup job deletes it, in line with the retention assumption in the PRD.
- **Uploads go to MinIO.** The file storage adapter speaks the S3 API and points at a MinIO service in Docker Compose. No cloud account is required. Moving to AWS S3 later changes the endpoint, bucket, and keys.

## Status flow

How the UI learns a job's progress and gets its results.

```mermaid
sequenceDiagram
    participant UI as Frontend (TanStack Query)
    participant API as API
    participant Jobs as Job store (Postgres)

    loop Every 1–2 seconds while queued, running, or consolidating
        UI->>API: GET /jobs/{id}
        API->>Jobs: Load job, documents, and results
        API-->>UI: 200 OK (status, progress, documents, report)
    end
    UI->>UI: Stop polling at a final state
```

- **Polling, not server-sent events.** Refresh and shared links work for free, because the URL holds the job ID and every poll fetches the current state. The API stays stateless, with no pub/sub layer or nginx buffering changes.
- **One endpoint returns everything** the UI needs. An unknown ID returns `404`.
- **Polling stops at a final state**: `succeeded`, `failed`, `cancelled`, or `expired`. The UI does not poll while a job is `awaiting_input`, because only the analyst can change it.

### Response

```json
{
  "id": "…",
  "status": "running",
  "progress": { "completed_steps": 7, "total_steps": 12 },
  "documents": [
    {
      "id": "…",
      "filename": "a.pdf",
      "status": "summarising",
      "flagged": false,
      "flag_reasons": [],
      "error": null,
      "summary": null
    },
    {
      "id": "…",
      "filename": "b.pdf",
      "status": "succeeded",
      "flagged": true,
      "flag_reasons": ["hidden_text"],
      "error": null,
      "summary": {}
    }
  ],
  "rejected_files": [],
  "excluded_files": [],
  "report": null,
  "error": null
}
```

- `summary` is filled in for each document as it finishes, and `report` once consolidation is done.
- **Progress counts finished pipeline steps.** Each stored document has extract, check, and summarise. `total_steps` is three per stored document. A step counts once the document status has moved past it.
- `error` uses the same error schema as the rest of the API.

### Job states

```mermaid
stateDiagram-v2
    [*] --> awaiting_input: some files rejected
    [*] --> queued: all files valid
    awaiting_input --> queued: confirm, or retry a failed document
    awaiting_input --> consolidating: continue without a failed document
    awaiting_input --> cancelled: cancel
    awaiting_input --> expired: timeout
    queued --> running: first document starts
    running --> consolidating: every stored document succeeded
    running --> awaiting_input: a document failed and the others have finished
    running --> cancelled: cancel
    consolidating --> succeeded
```

### Document states

- `pending`, then `extracting`, `checking` (guardrails), `summarising`, and finally `succeeded` or `failed`.
- A failed document keeps its error. The other documents keep processing. The analyst retries that document, continues without it, or cancels the job.
- Transient step failures retry 3 times with exponential backoff and jitter. A permanent failure, such as a corrupt file, fails that document on the first attempt.
- `flagged` is a separate true-or-false field, because a document can be flagged and still succeed. `flag_reasons` lists the rules that set it: `classifier`, `hidden_text`, `invisible_characters`, or `encoded_blob`. The job keeps going. The flag and the reasons are the warning.

### What the UI shows

| Job status                           | Screen                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------- |
| `awaiting_input`                     | Rejected files, or a failed document, with retry, continue, or cancel   |
| `queued`, `running`, `consolidating` | Progress. A failed document shows its error while the others keep going |
| `succeeded`                          | Transition into the report                                              |
| `failed`, `cancelled`, `expired`     | Message with the reason, and a link back to upload                      |

While a job runs, each file shows its state. The overview and the document tabs appear together when the job succeeds.

## LLM processing pipeline

What the worker does with a queued job, from extracted text to a stored consolidated report.

```mermaid
flowchart TD
    Enqueue[Create or confirm<br/>one queue task per stored document] --> Extract

    subgraph PerDoc[Document task, one per file, in parallel]
        Extract[Extract<br/>text per page, then read picture<br/>pages with a vision model] --> Checks[Programmatic guardrails<br/>injection patterns, hidden text,<br/>invisible characters]
        Checks --> Classifier[Decision-model guardrail<br/>injection classifier]
        Classifier --> Summarise[Document summary<br/>chunk, summarise, combine]
        Summarise --> ValidateDoc[Output validation<br/>schema, citations]
    end

    ValidateDoc --> FanIn{Job locked: every stored<br/>document succeeded?}
    FanIn -- yes --> Consolidate[Consolidation task<br/>payload is the job id]
    FanIn -- "a document failed" --> Decide[Analyst retries it,<br/>continues without it, or cancels]
    Consolidate --> ValidateReport[Output validation<br/>schema, citations]

    Extract -. store .-> DB[(Postgres)]
    Classifier -. store flags .-> DB
    ValidateDoc -. store .-> DB
    ValidateReport -. store .-> DB
```

### Agent or pipeline

- **A fixed pipeline, not an agent.** The steps are known in advance and always run in the same order, so an agent deciding what to do next adds cost, latency, and unpredictability without adding value.
- A fixed pipeline is easier to evaluate, because each step has a defined input, output, and eval set.
- An agent may make sense for the optional feature, for example Q&A over the documents, where the next step depends on the question.

### Guardrails

Document text is untrusted data. Guardrails run in layers, cheapest first.

- **Programmatic checks**: patterns such as "ignore previous instructions" or fake role markers, hidden text (white or tiny font), invisible Unicode characters, and long encoded blobs.
- **Decision-model classifier**: a fast, cheap decision model returns the probability that each chunk contains instructions aimed at the model, and a document type from the fixed list. It sits behind its own classifier interface (`injection_probability`, `document_type`), not the LLM adapter, because decision models do not take prompts or generate text.
- **Datamarking (spotlighting)**: document text in prompts has a special marker character interleaved through it, and the system prompt explains that marked text is data and must never be followed as instructions. Delimiters alone can be faked by an attacker; datamarking is far more resistant.
- **No tools for the LLM**: the pipeline's model only returns JSON and cannot take actions, so a successful injection can distort output but cannot trigger anything.
- **Output validation**: every LLM response is checked against its schema and retried on invalid output. Citations are checked programmatically: the cited page must contain the quoted text.
- **Text read from images is untrusted too.** It joins the page text before the checks run, so the classifier checks it and prompts datamark it like any other text. A vision model is told to treat everything in the picture as data. Its output only becomes page text and is never used as an instruction.
- **Flagged documents** are marked on the job and shown in the UI with a warning, never dropped silently. Flags carry forward into consolidation and appear in the report, because injected content can still travel through a document's summary.

### Document summary

- Each document is summarised separately, in parallel, as its own queue task. The payload is the document id.
- Long documents are split into chunks. Each chunk returns structured fields: topics, entities, and notable points with a page and a quote. The last call reads those fields and writes the document summary (map-reduce), within a configurable token budget. A prose summary of a chunk drops facts the last call never sees.
- The combine step also receives relevant source excerpts alongside those structured fields, which improves faithfulness and reduces hallucination.
- The output follows the per-document schema, written to be read quickly and to stay short:
  - `title`: the document's name in at most six words, and `inferred_type`.
  - `summary`: one sentence of at most 12 words, the most important idea. The UI shows it as the headline.
  - `key_points`: exactly three one-line points of at most 14 words, each with a fact or a number.
  - `sections`: two or three sections, each with a heading of at most four words, two or three short paragraphs of one or two sentences, and at most one pull quote.
  - `topics`: up to five tags of one or two words.
  - `entities`: people, organisations, locations, and dates. Each entity has a name and optional aliases.
  - `notable_points`: each with a page number and a supporting quote.
- The schema limits are a guard a little above what the prompt asks for. A longer answer goes back to the model to shorten.
- A pull quote on a section is kept only when it appears on the page it cites. A quote that fails the check is dropped and the section still shows.

### Images and scanned pages

Extraction marks a page `needs_image` when it displays a picture. A scan is one picture and a chart sits next to text, so a text extractor alone misses them.

- **A vision model called through Cloudflare reads the page.** The page is rendered to a PNG and sent, with instructions, to a vision-capable chat model on the same Cloudflare account and key as the LLM. We run no model ourselves, and one path serves scans and charts. OCR such as Tesseract would need a system package and still could not read a chart.
- **It sits behind a port.** `PageReader` takes a request and a page image and returns text. `GatewayPageReader` is the Cloudflare adapter and `MockPageReader` needs no model. `VISION_PROVIDER` selects one (`off`, `mock`, or `cloudflare`) through the factory, and another reader can be registered without touching the pipeline. `off` is the default and keeps the earlier text-only behaviour.
- **Where it runs.** Inside the extract step, after the text layer is read and before pages and chunks are stored. The reader's text is added to the page, so chunking, the safety check, summaries, and quote checks run unchanged. A scan with no text gets the transcript as its text. A page with text gets the image content appended under a short label, and the model is given the page's own text so it does not repeat it.
- **Which pages.** A page is read only when its pictures cover at least `VISION_MIN_IMAGE_FRACTION` of it, which skips logos and icons. At most `VISION_MAX_PAGES` pages are read per file, scans with no text first, `VISION_CONCURRENCY` at a time. A long scan beyond the cap is left partly unread and a warning is logged.
- **Failures are not hidden.** A reader error is not swallowed. The step retries, then the file fails, because a summary that ignores a chart is worse than a failed file. A request the service rejects as invalid, such as a retired model, fails at once and the log names `VISION_MODEL`.
- **Model.** `VISION_MODEL` defaults to `@cf/google/gemma-4-26b-a4b-it`. Providers retire models from time to time, so it is configuration and never fixed in code. The model read the sample chart and the scanned slip correctly. A page costs about $0.0002 and takes 5 to 13 seconds.
- **Limit.** The quote check proves a quote is in the transcript, not that the model read the picture correctly. A misread digit in a chart would pass it.

### Consolidated summary

- Runs once, as its own queue task, when every stored document has succeeded. A failed document blocks that task until the analyst retries it or continues without it. The document task that finds this, while holding the job row lock, inserts the consolidation task, whose payload is the job id, in the same transaction.
- Its input is the validated document summaries, not the raw text. This keeps the prompt small and limits how far injected content can travel.
- The output follows the report schema, with the same limits on length:
  - `summary`: one sentence of at most 12 words, the headline.
  - `takeaways`: exactly five one-line points that read in order like a short story: what the documents cover, what they agree on, what matters most, where they differ, what to watch.
  - `sections`: three to five sections of further reading, one per theme, shaped like a document section. Disagreements stay out of the sections and go in `contradictions`.
  - `themes`: up to five tags, then `entities`, `flagged_documents`, and `excluded_files`.
- A pull quote on a report section is kept only when a document summary already holds it as a checked quote.
- **Contradictions are surfaced, not merged.** LLMs tend to collapse conflicting facts into one consensus value. The prompt asks for disagreements explicitly, and each contradiction holds exactly two claims. Each claim has its text, the document, the page, and a quote.

### Evaluation

- **Source of truth**: `backend/evals/golden.json` (expected outputs) and `backend/evals/adversarial.json` (expected safe behaviour), with source documents in `backend/evals/fixtures.json`. Each file sets its pass thresholds; each case lists API steps, expected statuses, and content expectations, and says whether it runs in CI on the mock (`ci_mock`) or against real models (`real`).
- **Fictional topic**: the eval documents describe an invented project, so the model cannot pass by recalling facts it already knows.
- **Canary**: every system prompt contains a canary string; any output containing it fails, catching system-prompt leaks.
- **Flagging rule**: phrase or role-marker matches alone do not flag a document, so benign documents about prompt injection or with speaker labels are not flagged; the classifier decides. Hidden text, invisible characters, and encoded blobs flag on their own.
- **Programmatic checks first**: schema validity, quotes found on their cited pages, entity recall, and topic coverage against the golden set.
- **LLM judge for coverage and conciseness**, averaged over several runs, because single LLM-judge scores are inconsistent and overestimate faithfulness.
- **Human spot-check** of the sample outputs, for what automated scoring misses.
- **Contradiction case**: the golden set includes a pair of documents that disagree on purpose; the report must surface both sides.
- **Reasoning modes** are compared through evals before being enabled, since more reasoning does not reliably improve summaries.

### Prompts in one file

- Every prompt the pipeline uses lives in one file, `backend/app/pipeline/prompts.yaml`: system prompts, user prompt templates, and classifier questions with their option descriptions.
- Maintainers tune behaviour by editing that file only; no prompt text lives in code.
- Each entry has an ID, a version, and a template with named placeholders (for example `{document_text}`).
- `load_system_prompts` validates the file at startup: a missing system prompt or an unknown placeholder fails fast instead of failing mid-job.
- The prompt ID and version are recorded with every LLM call, used in the cache key, and changing the file triggers the evals.
- The file path is configurable, so a different prompt set can be swapped in without code changes.

### Model choice per step

Each step picks its model through configuration (strategy pattern). The pipeline has few judgement calls: control flow is fixed, and most work is generating structured summaries. So the steps split into two kinds, each with a model suited to it.

- **Decisions: [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)** (TypeSafe AI). A non-generative decision model: it takes text plus typed questions and returns a fixed option, a rubric score, or a yes/no probability, with calibrated confidence. Outputs are type-safe by construction, it is very fast, and input costs about $0.04 per million tokens with free output. Used for:
  - Prompt-injection detection per chunk (yes/no probability). A chunk above `CLASSIFIER_FLAG_THRESHOLD` (default 0.7) marks the document flagged.
  - Inferred document type (choice from a fixed list).
- **Generation: DeepSeek V4.1 Flash**, set by `LLM_MODEL` (currently `@cf/deepseek-ai/deepseek-v4.1-flash-1017`). Used for document summaries and consolidation, where the output is free text inside a schema (summaries, entities, themes, contradictions).
  - The schema goes in the prompt. Pydantic AI checks the reply and asks again, up to `LLM_OUTPUT_RETRIES`, when it does not match.
  - A model call stops at `LLM_TIMEOUT_SECONDS` (180). A whole document step stops at `STEP_TIMEOUT_SECONDS` (300). Chunk calls for one file still run one after another inside that step.
- **Vision: a vision model called through Cloudflare**, set by `VISION_MODEL` (see Images and scanned pages). It only transcribes pages. It does not summarise.
- **Limits**: Jev cannot write summaries or extract free-text entities, and its input is capped at 32k tokens per request, which fits chunk-level checks. A valid typed answer can still be wrong, so its thresholds are tuned on the adversarial eval set.
- **Swappable**: Jev sits behind the classifier interface, the summary model behind the LLM adapter, and the vision model behind the page reader, so each can be replaced through configuration. The mock adapters remain the default for tests and CI.

### Stored in Postgres

- Extracted text per page in `pages`, kept for citation checks and re-runs. `needs_image` is set when `page.get_image_info()` lists an image displayed on the page. A short page of text stays unmarked, and so does a blank page. For a marked page that the vision step read, the stored text includes what the model found in the pictures.
- Chunks of that page text in `chunks`. Each chunk carries its page number and does not cross a page. `CHUNK_TOKEN_BUDGET` defaults to 2048 cl100k tokens, enough for a full page of text. A denser page splits inside that page.
- Programmatic guardrail findings in `guardrail_results`. Each row is the page, the rule, and a short excerpt. The rules are an injection phrase, a fake role marker, invisible characters, a long encoded blob, and text drawn in white or at a tiny size. A classifier row is added when a chunk's probability is above the threshold. A phrase or a role marker is recorded and does not, by itself, mark the document flagged.
- Document summaries and the consolidated report, as validated JSON.
- Telemetry per LLM call in `llm_calls`: model, prompt id and version, input tokens, output tokens, and latency. Each page read by the vision model is a call under the `page_image` prompt. `GET /admin/usage` returns those calls. `GET /jobs/{id}` stays the status and the results the frontend polls.
- Status of each step, so a retried job resumes from the last completed step.

## UI/UX

```mermaid
flowchart LR
    Landing[Landing page<br/>title, instruction, upload,<br/>past summaries] -- upload --> Check{Any files<br/>rejected?}
    Check -- yes --> Review[Rejected files<br/>re-upload, continue, or cancel]
    Review -- continue --> Progress
    Review -- cancel --> Landing
    Check -- no --> Progress[Progress]
    Progress -- "job done" --> Report[Report<br/>overview tab, one tab per document,<br/>download]
    Landing -- "open past summary" --> Report
```

### Landing page

- A title, a one- or two-line instruction, and a file upload input (drag-and-drop and file picker).
- Past summaries are listed in a left sidebar. A button opens and closes it, and the browser remembers that choice. Each entry is labelled with the start of that report's headline, falls back to the first file name while the job runs, and has a three-dot menu to delete it. A footer button clears all.

### Progress

- A progress bar for the whole job, a step indicator (read, check, summarise, consolidate), and the state of each document. The consolidating step has its own screen when the bar reaches 100 percent, because writing the report is one more step.
- An elapsed-time counter runs beside the file count while the job works. The browser keeps it, because the API sends no timestamps, and it disappears when the report shows.
- Warnings on flagged documents appear as soon as they are detected.

### Report

- While the job is queued, running, or consolidating, the page shows progress. When the job succeeds, that progress is replaced by the report.
- The report is concise and split into tabs, and each tab reads like a short slide deck:
  - **Overview**: a large one-line headline, five numbered points, then "Further reading" with a heading per topic and short paragraphs, with pull quotes between them. Where documents disagree, both claims sit under the topic as indented quotes with the file and page. Then theme tags, and last a plain bullet list of metadata: documents, people, organisations, locations, dates, flagged files, and files left out.
  - **One tab per document**: a one-line headline, three points, reading with pull quotes, topic tags, and metadata bullets. The metadata has no cards or tables.
- The UI draws the report from structured fields, not markdown. A report saved before the structured fields shows through a fallback that splits its long summary into a headline and short paragraphs.
- A Download PDF button above the tabs saves the report as a PDF with one page for the overview and one page for each document, in tab order. The API draws it (`GET /jobs/{id}/report.pdf`) from the stored results with PyMuPDF, which the pipeline already uses. A page whose content runs long is scaled down so the page count stays at one per tab. The endpoint answers `409` until the job has succeeded. Markdown, if wanted later, would be another renderer beside the PDF one in `backend/app/export/`.

### One page

- Upload, rejected files, progress, and the report replace one another in one shell. Once a job starts the address is `/jobs/<id>`, so a refresh keeps the analyst on that job's progress or report. The server already falls back to the app for that path, and the browser history handles back and forward.

### Past summaries

- There is no authentication and no endpoint that lists jobs (see the PRD assumptions). The browser keeps the IDs of jobs it created in local storage and fetches each one by ID.
- Analysts only see their own past jobs on that browser. Jobs that have expired or been deleted are dropped from the list.

## Enhancements

Good to have for scaling the system.

### Document caching

- Hash each uploaded file's bytes (for example SHA-256). If a document with the same hash was already processed, reuse its stored summary and skip the whole per-document pipeline.
- The cache key also includes the pipeline version (model, prompt version, and schema version), so changing any of them produces fresh summaries instead of stale ones.
- Consolidation can be cached the same way, keyed by the set of document hashes plus the pipeline version.
- Guardrail results are cached with the summary, so a flagged document stays flagged on re-upload.
- In production with multiple tenants, the cache is scoped per tenant, so one tenant's upload never reveals or reuses another's results.

### Server-sent events

- Replace polling with server-sent events for instant updates and fewer requests.
- Needs a pub/sub layer (for example Postgres `LISTEN/NOTIFY`), so any API instance can push the worker's updates, and nginx buffering turned off for that route.
- The event payload keeps the same shape as the `GET /jobs/{id}` response, so the UI changes only how it receives updates.

### Retries

Built: the worker retries a step up to 3 times with full-jitter backoff, treats a timeout as transient, and fails a document at once on a permanent error. Not built: honouring `Retry-After`, and telling retryable HTTP statuses from other `4xx` answers in the LLM and classifier adapters (the vision adapter does this already). The points below are the target.

- **Exponential backoff with jitter** on transient failures: timeouts, rate limits (`429`), and provider `5xx` errors. Each step is limited by `STEP_TIMEOUT_SECONDS`. Jitter spreads retries out so workers do not all retry at the same moment.
- Honour the provider's `Retry-After` header when it is present.
- **Do not retry permanent failures**, such as a corrupt file or a request the provider rejects as invalid. Invalid LLM output has its own capped schema retry.
- **Cap the attempts at 3**, then mark that document as failed with a clear reason. The other documents keep processing. The analyst retries the failed document, continues without it, or cancels. In production, failed messages move to the dead-letter queue.
- Retries are safe because workers are idempotent and each step's status is stored, so a retry resumes from the last completed step.
