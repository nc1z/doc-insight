Create a development plan file from the context provided by the user.

The user will provide:

- what they want to build
- any product or technical context
- any preferred architecture, services, tools, or constraints
- optionally, the desired output file path

If the user does not provide an output path, create the plan as:

```text
context/[short-kebab-case-topic]-plan.md
```

Do not implement the feature. Only create or update the plan document.

## Required Output Style

The generated plan must be structured like a detailed implementation roadmap with:

- a title
- a short explanation of what the plan is for
- primary services, packages, frameworks, or infrastructure involved
- a review model
- a flow map
- numbered phases
- lettered sub-phases inside every phase
- checklist tasks
- a learning checkpoint at the end of every phase
- a suggested commit message at the end of every phase
- a final acceptance pass

The plan must be generic to the requested topic. Do not mention unrelated prior projects, RAG, vector search, Cloudflare, or any specific technology unless the user provided that context.

## Required Structure

Use this exact document pattern:

```md
# PLAN: [Name Of Thing Being Built]

[One or two paragraphs explaining what this plan covers and what it intentionally does not cover.]

Primary services/packages/frameworks:

- [Service/package/framework 1 and why it matters]
- [Service/package/framework 2 and why it matters]
- [Service/package/framework 3 and why it matters]

## Review Model

Each phase is split into sub-phases. A sub-phase should be small enough to review independently and explain with:

- files changed
- small code snippets
- what the code does in plain language
- how the change helps the overall flow
- what can be tested now
- whether any production infrastructure can be tested

## Flow Map

This plan follows the main user/system lifecycle directly:

| Flow step | What happens                | Phase   |
| --------- | --------------------------- | ------- |
| 1         | [First user/system action]  | Phase 1 |
| 2         | [Second user/system action] | Phase 2 |
| 3         | [Third user/system action]  | Phase 3 |

## 0. [Foundation Phase Name]

Goal: [One sentence explaining the goal.]

### 0A. [Sub-phase Name]

- [ ] [Concrete task]
- [ ] [Concrete task]
- [ ] [Concrete task]

### 0B. [Sub-phase Name]

- [ ] [Concrete task]
- [ ] [Concrete task]

### 0C. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how this phase benefits the overall system.

Suggested commit message: `[type(scope): concise commit message]`

## 1. [Phase Name]

Goal: [One sentence explaining the goal.]

Solves flow step 1: [short description].

### 1A. [Sub-phase Name]

- [ ] [Concrete task]
- [ ] [Concrete task]

### 1B. [Sub-phase Name]

- [ ] [Concrete task]
- [ ] [Concrete task]

### 1C. Tests and Manual Verification

- [ ] [Relevant automated test]
- [ ] [Relevant manual test]
- [ ] [Expected result]

### 1D. Learning Checkpoint

- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how this phase benefits the overall system.

Suggested commit message: `[type(scope): concise commit message]`

## Final Acceptance Pass

Goal: Prove the whole feature is correct, usable, observable, and safe enough to keep.

### Final A. Full Test Pass

- [ ] [Unit tests]
- [ ] [Integration tests]
- [ ] [Build/typecheck/lint if applicable]

### Final B. User Flow Pass

- [ ] [Manual end-to-end flow]
- [ ] [Failure case]
- [ ] [Recovery or fallback case]

### Final C. Docs and Decision Pass

- [ ] [Docs update]
- [ ] [ADR or decision note if needed]
- [ ] [Open questions reviewed]

### Final D. Learning Checkpoint

- [ ] Learning: explain the full feature end to end with final code paths, diagrams when helpful, manual test commands, infrastructure involved, and tradeoffs learned.

Suggested commit message: `chore([scope]): complete acceptance pass`
```

## Planning Rules

- Keep phases incremental and commit-friendly.
- Every phase must produce a reviewable change.
- Every phase must include at least two sub-phases before the learning checkpoint.
- Use phase `0` for foundations, contracts, schemas, fixtures, or architecture scaffolding.
- Use later phases to follow the real user/system flow in order.
- Include tests inside the phase where the behavior is introduced.
- Include manual verification commands or steps when useful.
- Include production infrastructure notes only when the phase actually touches production infrastructure.
- Include documentation or ADR tasks where architecture decisions are made.
- Keep tasks concrete and implementation-oriented.
- Avoid vague tasks like “improve UX” or “make it robust” unless broken down into specific work.
- Preserve the user’s preferred stack and architecture when provided.
- If the user provides an existing plan or proposal, align the new plan to that context instead of inventing a different product.

## Learning Checkpoint Requirements

Every phase must end with a learning checkpoint task that says, in substance:

```md
- [ ] Learning: explain the code changes in small chunks with file names, short snippets, layman explanations, and how this phase benefits the overall system.
```

Adjust the final clause to match the phase when useful.

## Final Response

After creating the plan file, respond with:

- the file path created or updated
- a short summary of what the plan covers
- whether tests were run
- whether production infrastructure was touched
