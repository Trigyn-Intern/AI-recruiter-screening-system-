---
name: failure-handling
version: 1.0.0
applies_to: any
---

# Decision Tree: Failure Handling

Reusable rules for what the orchestrator does when an agent, a workflow, a
file load, a context load, or a user request fails or is incomplete.

## Purpose

Prevent silent failure. Every failure has a known category, a known recovery
strategy, and a known escalation path.

## Responsibilities

- Classify failures.
- Pick the right recovery action.
- Escalate when the orchestrator cannot recover on its own.
- Log enough context to investigate without leaking secrets.

## Failure Categories

| Category | Examples | Default Recovery |
| --- | --- | --- |
| `agent-failure` | An agent returns an error or no result | Retry if transient; otherwise escalate to the step owner. |
| `workflow-failure` | A workflow step cannot start because a precondition fails | Block the workflow, surface the missing precondition, escalate. |
| `missing-file` | A required knowledge, checklist, or template file is absent | Block the step, log the path, escalate to the framework owner. |
| `missing-context` | A required config key is absent or empty | Block the step, log the missing key, escalate to the project owner. |
| `ambiguous-request` | The user intent is unclear or contradictory | Route to `requirement-agent` to clarify, do not start a workflow. |
| `conflicting-policy` | Two config values contradict each other | Block the step, log the conflict, escalate to the project owner. |
| `transient-dependency` | A network or external system is unavailable | Retry with backoff up to the agent's retry budget. |
| `destructive-failure` | A non-idempotent step failed mid-execution | Stop the chain, rollback the step, escalate. |

## Decision Rules

The orchestrator asks, in order:

1. **Is the failure `destructive`?**
   - Yes -> stop the chain, rollback the step, escalate.
2. **Is the failure `transient`?**
   - Yes -> retry up to the agent's retry budget.
3. **Is the failure `missing-file`, `missing-context`, or `conflicting-policy`?**
   - Yes -> block the step, log the path or key, escalate.
4. **Is the failure `ambiguous-request`?**
   - Yes -> route to `requirement-agent`. Do not start a workflow.
5. **Is the failure `agent-failure` or `workflow-failure`?**
   - Yes -> surface the failure to the step owner with the agent's output
     and the last successful step.
6. **Is the failure unknown?**
   - Yes -> treat as `destructive` until proven otherwise.

## Inputs

- The failed step's name.
- The error category from the failing component.
- The current execution state.
- The active project policy in `project-config.yaml`.

## Outputs

- A recovery action: `retry`, `rollback`, `block`, `route`, or `escalate`.
- A log entry with category, step, and a redacted error summary.
- An escalation message naming the human owner and the missing or broken
  artifact.

## Examples

- `agent-failure` from the `developer-agent` because of an unparseable diff
  -> `retry` once, then `escalate` to the step owner.
- `missing-file` because `.ai/knowledge/security-guidelines.md` is absent ->
  `block` the security step, escalate to the framework owner.
- `ambiguous-request` because the user said "make it better" with no diff ->
  `route` to `requirement-agent`.
- `destructive-failure` because the release promotion was interrupted ->
  `rollback` the promotion, escalate to the release manager.

## Best Practices

- Never silently swallow a failure. Every failure is logged and surfaced.
- Never auto-retry a `destructive` step. Recovery is human-driven.
- Prefer `block` over guessing. The orchestrator's job is to keep the
  pipeline honest, not to push things through.
- Treat unknown failures as the worst-case category until proven otherwise.

## Reusable Rules

- Recovery actions are limited to the five tokens above.
- Escalation always names a human owner and a missing or broken artifact.
- Log lines never include secrets, PII, or full stack traces from
  third-party systems.

## Project Agnostic Design

- No project names or stack-specific recovery steps appear here.
- The orchestrator's failure handler is a single document, not a per-project
  override.v