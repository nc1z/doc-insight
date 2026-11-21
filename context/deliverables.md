# Deliverables Analysis

## The single deliverable
- **One public repo link.** It's the only thing they see, so the repo has to explain itself.
- Assume the reviewer will: open the README, clone, run one command, upload a PDF, read the code, check CI.
- If any step fails, expect a fast rejection. "Executable without errors" is stated as a **hard gate** ("considered incomplete").

## Hard gates (fail any one and you're likely out)
- Repo is public. Check this from a logged-out/incognito browser.
- `backend/` and `frontend/` directories use **exactly** those names.
- `docker compose up` works on a clean machine with no manual steps beyond setting an API key.
- Python env setup script is included (e.g. `setup.sh` / `Makefile`, plus `pyproject.toml` with a lockfile or `requirements.txt`).
- CI pipeline is green on the latest commit, with a visible badge in the README.
- All 6 README sections exist: overview, architecture diagram, setup, screenshots, assumptions, limitations.
- Sample PDFs are committed or linked.
- Assumptions are stated **per task**, as the instruction explicitly says.

## What the reviewer is really assessing
- The stated focus is "**design, implement, explain, and justify**". Using AI tools is allowed, so the code alone won't differentiate you. **Reasoning and judgement will.**
- Can you ship a complete, working vertical slice end to end, rather than a polished fragment?
- Do you make sensible trade-offs and **write them down** (the "why", not just the "what")?
- Production instincts: containers, CI, tests, error handling, security around untrusted input.
- AI engineering maturity: structured outputs, handling long/multimodal docs, prompt-injection awareness, cost/latency awareness.
- Likely follow-up: a **walkthrough/defence interview**. Every choice must be explainable, and nothing in the repo should be something you can't justify.

## Interpreting the instructions
- "Follow closely to the Test Instruction": they're checking for attention to detail. Use the exact directory names and README headings, and complete every numbered sub-task.
- "You can make assumptions": they want to see you scope things deliberately. Document the assumptions instead of asking about everything.
- "Reach out with queries": optionally send one sharp, sensible clarifying email. This shows communication skills. Don't block on the reply.
- "Document and comment your code properly": add docstrings, type hints, and module-level intent. Avoid noisy comments.
- "Optional feature… only after core is done": a broken core plus a fancy extra is worse than a solid core alone. Only add the extra if everything else is green.
- "Up to one" additional feature: pick **one** and do it well. Don't add several.

## Reviewer experience checklist
- README top section: a one-paragraph pitch, a screenshot/GIF, and a 3-line quickstart.
- `.env.example` with clear instructions for the LLM API key. Optionally add a mock/offline LLM mode so the app and CI run without a key.
- Pinned versions (Python, Node, base images, dependencies).
- Clean commit history with meaningful messages spread over the week, which shows your process.
- No secrets committed. No `node_modules`, build artefacts, or `.env` files.
- Healthcheck endpoint plus auto-generated OpenAPI docs (`/docs`).
- `Makefile` or scripts: `make up`, `make test`, `make lint`.

## Time plan (7 days, solo)
- Day 1: scaffold the repo, compose, CI skeleton, and a hello-world front-to-back.
- Days 2–3: backend pipeline (extraction, LLM, structured output, consolidation) and error handling.
- Day 4: frontend (upload, progress, results, errors).
- Day 5: tests, CI hardening, security/adversarial handling.
- Day 6: README, diagram, screenshots, assumptions/limitations; optional feature if everything is green.
- Day 7: fresh-clone test on a clean machine, polish, buffer.

## Final pre-submit check
- Fresh `git clone` into a new folder, then `cp .env.example .env`, then `docker compose up`, then upload the samples. Everything should work.
- CI green, repo public, README renders correctly on the hosting platform, images load.
- Re-read the original instructions line by line and tick off every item.
