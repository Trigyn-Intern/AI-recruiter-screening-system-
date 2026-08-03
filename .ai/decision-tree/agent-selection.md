---
name: agent-selection
version: 1.0.0
applies_to: any
---

# Decision Tree: Agent Selection

Reusable routing for "which agent should act on this next?" Use this when the
orchestrator needs to pick the next agent in a chain, or when a developer is
unsure which agent to talk to.

## Purpose

Make agent selection deterministic. Given an intent and the current state, pick
exactly one agent (or one parallel set) without re-deriving the rules every
time.

## Responsibilities

- Map an intent to the first agent.
- Map the current state to the next agent.
- Identify which agents can run in parallel.
- Identify the final approval agent for a change.

## Decision Rules

The orchestrator asks three questions, in order:

1. **Is the input well-formed enough to act on?**
   - No -> `requirement-agent` to clarify or restructure.
   - Yes -> continue.
2. **What kind of work is this?**
   - New behavior -> `requirement-agent`, then `architecture-agent`.
   - Bug fix -> `requirement-agent` for triage, then `developer-agent`.
   - Hotfix -> `security-agent` and `developer-agent` in parallel after triage.
   - Refactor -> `architecture-agent`, then `developer-agent`.
   - Docs only -> `documentation-agent`.
   - Release -> `release-agent`.
3. **Which agents are still owed a step before approval?**
   - The remaining agents run in the order defined by
     `decision-tree/execution-order.md`.

## Inputs

- The user's intent in plain language.
- The current state of the change (none, requirement, design, code, tested,
  reviewed, released).
- The active project policy in `project-config.yaml`.
- The list of agents defined under `.ai/agents/`.

## Outputs

- A single agent name, or a small set of agents allowed to run in parallel.
- A rationale string that the orchestrator can log or surface to the user.

## Examples

| Intent | State | Selected Agent(s) |
| --- | --- | --- |
| "Add login" | none | `requirement-agent` |
| "Add login" | requirement ready | `architecture-agent` |
| "Fix bug" | bug reported | `requirement-agent` (triage) |
| "Fix bug" | triaged | `developer-agent` |
| "Production issue" | severity 1 or 2 | `security-agent` + `developer-agent` in parallel |
| "Improve performance" | change proposed | `developer-agent` + `testing-agent` in parallel |
| "Update docs" | docs only | `documentation-agent` |
| "Release" | merge ready | `release-agent` |

## Best Practices

- Never pick an agent whose preconditions are not met.
- Prefer the `requirement-agent` as the entry point for any ambiguous request.
- Keep parallel sets small. More than two agents in parallel usually means the
  work is not well-scoped.
- Treat the `review-agent` as the conductor for code review, not as a separate
  executor.

## Reusable Rules

- The agent list is sourced from `.ai/agents/` and never hardcoded in the
  selection logic.
- Preconditions are declared in each agent's own file, not duplicated here.
- The selection is deterministic for a given (intent, state) pair.

## Project Agnostic Design

- No project names, frameworks, or runtimes appear in the decision rules.
- Every reference to policy flows through `project-config.yaml`.
- New agents can be added by creating a new file under `.ai/agents/`
  without changing this file.