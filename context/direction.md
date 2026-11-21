# Direction

Architectural directions to enforce across the app. These are set before any system or solution design, and every task, plan, and requirement should follow them.

## Architecture

### Async

The app must scale, so long-running or heavy work does not run inside the request.

- Use queues and background workers for slow work (for example LLM calls, file processing, report generation).
- An API request accepts the work, enqueues it, and returns right away with a job ID.
- Users are told when their action is complete through an async mechanism (for example polling a job status endpoint, server-sent events, or WebSockets), not by holding the request open.
- Job state (queued, running, succeeded, failed) is stored and can be queried.

### Agnostic

Build features so that providers and implementations can be swapped.

- Do not hardcode providers, models, or vendor-specific details, except as a baseline default.
- Put external dependencies (LLM providers and models, storage, queues, databases) behind interfaces, with adapters for each concrete provider.
- Swapping a provider or model should be a configuration change, or at most a new adapter, with minimal changes elsewhere.
- Keep settings in configuration files and environment variables, not in code.

### Scalability

A monolith is fine, but it must be modular.

- Separate the code into domains and services with clear boundaries.
- Modules talk to each other through defined interfaces, not each other's internals.
- Any module should be extractable into its own service later (distributed cloud or microservices) without rewriting the others.
- Components should be plug and play: changeable at any time without ripple effects.

### Design patterns

Use established patterns where they fit:

- **Adapter**: wrap external providers (LLMs, storage, queues) behind a common interface.
- **Strategy**: select interchangeable behaviour (for example which model or processing approach) at runtime or through configuration.
- Others as needed (for example factory, repository, dependency injection), as long as they keep the code swappable and the boundaries clear.

### Evals

Every agent and LLM pipeline we build needs evals.

- Each agent or pipeline ships with two eval sets, each with expected outputs or scoring criteria:
  - **Golden set**: representative, known-good inputs that check the agent or pipeline does the expected job correctly.
  - **Adversarial set**: edge cases and hostile inputs (for example malformed or ambiguous data, prompt injection, off-topic requests) that check it fails safely and stays on task.
- Evals run whenever a prompt, model, or provider changes, so swaps (see Agnostic) are judged on measured quality, not guesswork.
- Results are recorded so quality can be compared across versions.

## Frontend

- **Verification over unit tests**: prioritize end-to-end smoke tests and agentic verification (an agent driving the real UI) over unit tests.
- **shadcn/ui and similar libraries**: prefer component libraries that are plug and play yet fully customizable.
- **Tailwind CSS**: for styling, since shadcn/ui is built on it.
- **TanStack Query (React Query) or SWR**: for API calls and client-side caching, including polling job status for async actions.
