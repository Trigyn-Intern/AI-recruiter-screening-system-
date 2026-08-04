---
name: execution-order
version: 1.0.0
applies_to: any
---

# Decision Tree: Execution Order

Reusable definition of the canonical execution order for agents, the rules
for parallelism, and the rules for retries and recovery.

## Purpose

Make the agent execution graph deterministic. Given a workflow and a
priority, the orchestrator should know exactly which agents run, in which
order, and which can run in parallel.

## Responsibilities

- Define the canonical sequence of agents.
- Declare parallelism boundaries.
- Declare retry and rollback hooks.
- Declare the final approval agent.

## Canonical Sequence

For a normal feature change:

1. `requirement-agent`
2. `architecture-agent`
3. `developer-agent`
4. `testing-agent`
5. `security-agent` (parallel with `testing-agent` when in scope)
6. `documentation-agent`
7. `review-agent`
8. `release-agent`

The orchestrator may start `documentation-agent` as soon as the public surface
is stable, even before `review-agent`. The order above is the contract; the
optimizations are documented below.

## Parallel Execution

- `testing-agent` and `security-agent` may run in parallel after the
  `developer-agent` step, when `security-agent` is in scope.
- `documentation-agent` may run in parallel with `review-agent` when the docs
  are independent of the review findings.
- The `architecture-agent` and `developer-agent` must not run in parallel.
  Architecture precedes implementation.
- The `review-agent` and `release-agent` must not run in parallel. Release
  follows review.

## Dependencies

| Agent | Depends on |
| --- | --- |
| `requirement-agent` | nothing |
| `architecture-agent` | `requirement-agent` |
| `developer-agent` | `architecture-agent` (or `requirement-agent` for small changes) |
| `testing-agent` | `developer-agent` (for code), or `requirement-agent` (for test design) |
| `security-agent` | `developer-agent` (for code), or `architecture-agent` (for design) |
| `documentation-agent` | `developer-agent` (or `architecture-agent` for ADRs) |
| `review-agent` | all of the above for the change |
| `release-agent` | `review-agent` approval |

## Final Approval

- For a normal change, `review-agent` is the final approval before merge.
- For a release, `release-agent` is the final approval before promotion.
- For a hotfix, the on-call rotation is the final approval, with `security-agent`
  sign-off when the surface is in scope.

## Retry Logic

- An agent may retry a step up to two times when the failure is marked
  `transient` in the agent's own file.
- Retries that exceed the budget are escalated to the human owner of the
  workflow step.
- Idempotent steps (test runs, static analysis) may be retried freely.
- Non-idempotent steps (release promotion, secret rotation) must not be
  retried without explicit human approval.

## Rollback

- Each workflow step has a documented rollback action in its own file.
- The orchestrator tracks the highest step reached and uses that as the
  rollback boundary.
- Rollback is preferred over retry when the failure is marked `destructive`
  in the agent's own file.

## Failure Recovery

- The orchestrator's failure handler is defined in
  `decision-tree/failure-handling.md`.
- Recovery actions are routed through the orchestrator, not the agent, to
  keep recovery decisions centralized.

## Inputs

- The selected workflow.
- The selected priority.
- The list of agents owed for this change.

## Outputs

- A linearized execution plan with parallel groups and approval gates.
- A rollback boundary and a retry budget per step.

## Best Practices

- Keep the canonical sequence small. New agents slot in at the natural
  point in the dependency table.
- Default to sequential execution. Parallelism is an optimization, not a
  default.
- Never skip a dependency. If you need to, escalate.

## Reusable Rules

- The canonical sequence is the contract. Workflows may shorten it (for
  example, doc-only), but they may not reorder it.
- Parallel groups are explicit, not implicit. The orchestrator does not
  guess what can run in parallel.

## Project Agnostic Design

- No project names or technology names appear in the sequence.
- The dependency table is keyed by agent name and by step, not by file
  path.