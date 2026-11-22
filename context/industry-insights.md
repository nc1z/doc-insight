# Industry Insights

Findings from technical literature and industry guidance that shape the doc-insight design, and what each one means for [architecture.md](architecture.md).

## Pipeline design

### Workflows over agents

- [Anthropic, "Building effective agents"](https://www.anthropic.com/research/building-effective-agents) separates **workflows** (LLMs orchestrated through predefined code paths) from **agents** (LLMs that direct their own steps). It recommends the simplest solution that works, and workflows for well-defined tasks.
- Two of its workflow patterns match our pipeline:
  - **Prompt chaining**: fixed, dependent steps with programmatic checks between them (extract, check, summarise, consolidate).
  - **Parallelisation (sectioning)**: independent subtasks run at once (one task per document). It names guardrails on a separate model as a good use.

**For us**: confirms the fixed-pipeline decision.

### Long documents: map-reduce

- [BooookScore (ICLR 2024)](https://arxiv.org/html/2310.00785) compared two ways to summarise documents longer than the context window:
  - **Hierarchical merging** (map-reduce): summarise chunks, then merge the summaries. More coherent.
  - **Incremental updating** (refine): update a running summary chunk by chunk. More detail, less coherent.
- [Context-aware hierarchical merging (ACL 2025)](https://doi.org/10.18653/v1/2025.findings-acl.289) found that adding relevant source excerpts during the merge step improves faithfulness and reduces hallucination.

**For us**: keep map-reduce, and pass source excerpts alongside chunk summaries in the combine step.

### Multi-document contradictions

- A [2026 survey of multi-document summarisation](https://link.springer.com/article/10.1007/s10462-026-11580-z) lists handling conflicting information as a core challenge: remove duplication while keeping divergent viewpoints.
- [Claim-anchored attribution (2026)](https://arxiv.org/html/2606.23989v3) found that LLMs usually collapse conflicting facts into one consensus value. An end-to-end model surfaced only 18% of conflicts; their claim-level pipeline surfaced 61%, attributing each side to its source.
- [ConflictScore (EMNLP 2026)](https://aclanthology.org/2026.emnlp-main.2589.pdf) measures how well a response acknowledges conflicting evidence.

**For us**:

- The report schema lists each contradiction with both claims, each with its document and page.
- The consolidation prompt asks for disagreements explicitly, rather than a single consensus.
- The golden set includes a pair of documents that disagree on purpose.

## Prompt-injection defence

- [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) states there is no foolproof prevention. It recommends combining constrained instructions, input and output filtering, and least privilege.
- [Spotlighting (Microsoft, 2024)](https://arxiv.org/html/2403.14720) tested three ways to mark untrusted text:
  - **Delimiting** roughly halves attack success, and an attacker who knows the delimiters can fake them.
  - **Datamarking** (interleaving a special character through the untrusted text, explained in the system prompt) cut attack success from about 50% to under 3%, with minimal impact on task quality.
  - **Encoding** (for example base64) works on capable models but can hurt task quality.
- [The instruction hierarchy (OpenAI, 2024)](https://arxiv.org/abs/2404.13208) trains models to rank system instructions above content from untrusted inputs.
- The **dual-LLM pattern**, described in [CaMeL (Google DeepMind, 2025)](https://arxiv.org/html/2503.18813v2), keeps the model that reads untrusted data free of tools. CaMeL notes that injected content can still change the data that flows on to later steps.

**For us**:

- Use datamarking, not delimiters alone, for document text in prompts.
- The pipeline's LLM has no tools, so an injection can distort output but cannot trigger actions.
- Injected content can still travel from a document summary into consolidation, so flags are carried forward and shown in the report.

## PDF parsing

Benchmarks below come from interested parties: the [docling.org comparison](https://docling.org/compare/) is run by Docling, and the [Parsebridge benchmark](https://parsebridge.com/pdf-parsing-benchmark/) is published by a company that sells a hosted Docling API.

| Tool         | Speed per page (CPU, docling.org) | Licence    | Notes                                                                   |
| ------------ | --------------------------------- | ---------- | ----------------------------------------------------------------------- |
| PyMuPDF4LLM  | about 0.7 s                       | AGPL       | Fast for born-digital PDFs; needs Tesseract installed for scanned pages |
| Docling      | about 1.8 s (OCR off), 6.6 s (on) | MIT        | Layout, tables, and OCR built in                                        |
| Unstructured | about 0.4 s (fast mode)           | Apache 2.0 | Fast mode returned empty text on one chart-heavy report (Parsebridge)   |
| Marker       | about 90 s                        | —          | Built for GPUs; too slow on CPU                                         |

**For us**: PyMuPDF4LLM. The sample memos are born-digital and each page extracts in well under a second. A page is marked for Phase 8 when `page.get_image_info()` lists an image displayed on that page, so a short page of text stays unmarked. Phase 8 can render a marked page for Tesseract or a vision model. PyMuPDF is AGPL, which is acceptable for this local assignment. Shipping it inside a closed product needs Artifex's commercial licence.

## Evaluating summaries

- [Reasoning for abstractive summarisation (ACL 2026)](https://aclanthology.org/2026.findings-acl.859.pdf): G-Eval, an LLM-as-judge method, gave near-perfect faithfulness scores (4.96–4.99) where humans gave 3.98–4.42. The authors conclude faithfulness evaluation cannot rely on an LLM alone. They also found more reasoning does not reliably improve summaries and can reduce faithfulness.
- [Rating Roulette (EMNLP 2025)](https://aclanthology.org/2025.findings-emnlp.1361.pdf): LLM judges score inconsistently across repeated runs.
- [Do automatic factuality metrics measure factuality? (2024)](https://arxiv.org/html/2411.16638): all metrics tested drop on hard cases, and most can be gamed by appending harmless, content-free sentences.
- [UniSumEval (2024)](https://arxiv.org/abs/2409.19898): LLM-based evaluators agree with humans more than NLI- or QA-based ones, but still fall short in some domains.

**For us**:

- Golden-set scoring leans on programmatic checks: schema validity, quotes found on the cited pages, and entity recall.
- An LLM judge scores coverage and conciseness, averaged over several runs.
- A small human spot-check on the samples covers what automated scoring misses.
- Reasoning modes are not assumed to help; compare them through evals before enabling them.
