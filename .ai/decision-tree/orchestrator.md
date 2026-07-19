---
name: orchestrator
version: 1.0.0
applies_to: any
---

# Decision Tree: Orchestrator

The top-level orchestrator. It is the only component allowed to call
`agent-selection`, `workflow-selection`, `skill-selection`,
`technology-selection`, `priority-selection`, `context-selection`, and
`execution-order`. Everything else is a leaf.

## Purpose

Answer the single question: "What should happen next?" for any change in any
project, without modifying the user's intent or the project's policy.

## Responsibilities

- Accept an intent from the user.
- Detect the active stack profile (read-only).
- Load only the context required for the next step.
- Pick the workflow, the priority, and the first agent (or parallel set).
- Track execution state and apply retry, rollback, and escalation rules.
- Produce a single, human-readable plan for the user.

## High-Level Flow

1. **Receive intent.** Capture the user's plain-language request and any
   attached artifacts (diff, logs, requirement).
2. **Detect stack.** Use `technology-selection` to build a read-only profile.
   Do not modify the repo.
3. **Classify intent.** Use `workflow-selection` to pick the workflow.
4. **Set priority.** Use `priority-selection` to pick the priority.
5. **Load context.** Use `context-selection` to load only what the next step
   needs.
6. **Pick the first agent (or parallel set).** Use `agent-selection`.
7. **Execute the plan.** Use `execution-order` to drive the chain.
8. **Handle failure.** Use `failure-handling` for every non-success outcome.
9. **Hand off.** When the chain completes, hand off to the next workflow
   (typically `release` or `documentation`) or return to the user.

## Inputs

- User intent (text and optional artifacts).
- Repository read-only view.
- The active project policy in `project-config.yaml`.
- The full set of decision-tree, workflow, agent, prompt, skill, knowledge,
  checklist, and template files under `.ai/`.

## Outputs

- An execution plan: workflow, priority, context set, agent chain, retry
  budget, rollback boundary, escalation owners.
- A user-facing summary of the plan in plain language.
- A log of every decision the orchestrator made, with the rule it used.

## Routing Rules (summary)

The full rules are in `routing-rules.md`. The summary is:

- New behavior -> `feature-development.workflow.md`.
- Bug -> `bug-fix.workflow.md`. Severity 1 or 2 -> `hotfix.workflow.md`.
- Refactor without behavior change -> `refactoring.workflow.md`.
- Docs only -> `documentation.workflow.md`.
- Release -> `release.workflow.md`.
- Security concern at any time -> invoke `security-agent` in parallel
  with the active workflow.

## Parallelism

- Only `testing-agent` and `security-agent` may run in parallel by default.
- The orchestrator may start `documentation-agent` early when the public
  surface is stable.
- The orchestrator never starts `release-agent` before `review-agent`
  approves.

## Retries and Rollback

- Retry budget is defined in `execution-order.md`.
- Rollback boundary is the highest step reached.
- Destructive steps are not retried; they are rolled back and escalated.

## Token Discipline

- Load the smallest context set that the next step needs.
- Drop a file from context once the rule it provides has been applied.
- Never load two templates that serve the same purpose.

## Examples

- "Add login" -> detect `frontend-react` or `backend-dotnet-web` (depends on
  the repo) -> `feature-development` -> `priority=medium` -> chain
  `requirement -> architecture -> developer -> testing + security ->
  documentation -> review`.
- "Production is down" -> `hotfix` -> `priority=blocker` ->
  `security + developer` in parallel, then `testing` and `review` with
  reduced gates.
- "Improve performance" -> `feature-development` (or `refactoring` if no
  behavior change) -> `priority=high` -> chain includes `testing-agent` for
  performance tests and `security-agent` for risk.
- "Update docs" -> `documentation` -> `priority=low` -> single-agent chain.

## Best Practices

- Surface the plan to the user before executing, when the user is present.
- Run detection, classification, and priority assignment in this order. They
  are cheap and they narrow the search space for the expensive steps.
- Keep the orchestrator stateless across requests. State is held in the
  execution plan, not in the orchestrator.

## Reusable Rules

- The orchestrator reads decision files; it does not embed their rules.
- Adding a new decision tree is a matter of dropping a new file under
  `.ai/decision-tree/` and referencing it from the orchestrator only.
- The orchestrator is the only component that may call other decision
  trees.

## Project Agnostic Design

- The orchestrator works for any repo with a valid `.ai/project-config.yaml`
  and a recognized (or unknown) stack profile.
- New projects are handled by routing to `requirement-agent` until the
  profile is confirmed.
- No project names or technology names appear in the orchestrator's
  branching logic.