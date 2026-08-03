---
name: routing-rules
version: 1.0.0
applies_to: any
---

# Decision Tree: Routing Rules

The single source of truth for "given an intent, route to a workflow." This
file is referenced by the orchestrator and by `workflow-selection.md`.

## Purpose

Make routing deterministic. Every intent has exactly one primary route and a
defined set of side effects (parallel agents, mandatory approvals).

## Responsibilities

- Map intent keywords to workflows.
- Define side effects for each route.
- Define fallback when an intent does not match a known route.

## Routing Table

| Intent Keyword(s) | Workflow | Priority Default | Side Effects |
| --- | --- | --- | --- |
| `add`, `implement`, `new feature`, `build` | `feature-development` | `medium` | none |
| `fix`, `bug`, `regression`, `broken` | `bug-fix` | `high` | none |
| `production`, `outage`, `incident`, `sev-1`, `sev-2` | `hotfix` | `blocker` | `security-agent` parallel |
| `refactor`, `cleanup`, `restructure` | `refactoring` | `medium` | none |
| `document`, `docs`, `readme`, `adr` | `documentation` | `low` | none |
| `release`, `deploy`, `promote` | `release` | derived from change | `security-agent` review |
| `performance`, `slow`, `latency`, `throughput` | `feature-development` or `refactoring` | `high` | `testing-agent` performance tests |
| `security`, `vulnerability`, `cve`, `exploit` | depends on impact | `critical` | `security-agent` mandatory |
| `test`, `coverage`, `flaky` | `bug-fix` (for the test) or `feature-development` | `medium` | `testing-agent` mandatory |

## Side Effects in Detail

- `security-agent parallel`: the `security-agent` runs in parallel with the
  first applicable agent in the chain. Mandatory in all chains when this
  flag is set.
- `testing-agent performance tests`: the `testing-agent` includes
  performance-driven scenarios from `knowledge/testing-guidelines.md` in its
  test plan.
- `security-agent review`: a dedicated security pass is required before the
  workflow can complete.

## Fallback

When an intent matches no row, the orchestrator:

1. Routes to `requirement-agent` to clarify.
2. Does not start a workflow.
3. Asks the user to pick from a small set of routes: feature, bug, hotfix,
   refactor, docs, release, or "other".

## Inputs

- The user's intent in plain language.
- The active project policy in `project-config.yaml`.
- The list of workflows under `.ai/workflow/`.

## Outputs

- A primary workflow name.
- A priority token from `priority-selection.md`.
- A list of side effects (parallel agents, mandatory reviews).

## Examples

- "Add a logout button" -> `feature-development`, `medium`, no side effects.
- "Login is broken on Safari" -> `bug-fix`, `high`, no side effects.
- "Production is throwing 500s" -> `hotfix`, `blocker`,
  `security-agent parallel`.
- "Refactor the auth module" -> `refactoring`, `medium`, no side effects.
- "Update the README" -> `documentation`, `low`, no side effects.
- "Cut a release" -> `release`, derived, `security-agent review`.
- "Search is slow" -> `feature-development` or `refactoring`, `high`,
  `testing-agent performance tests`.
- "CVE-XXXX reported" -> depends on impact, `critical`, `security-agent
  mandatory`.
- "Increase test coverage" -> `feature-development` (test design), `medium`,
  `testing-agent mandatory`.

## Best Practices

- Keep the keyword set small. Long keyword lists become brittle.
- Prefer the user's exact words when they match; fall back to the table.
- Always show the user the chosen route and let them override.

## Reusable Rules

- The routing table is the only place where intent keywords are mapped to
  workflows.
- Side effects are tokens, not agent calls. The orchestrator resolves the
  tokens against the agent list.
- The fallback is universal: when in doubt, ask `requirement-agent`.

## Project Agnostic Design

- Keywords are user-language, not project-language.
- Workflow names are stable across projects.
- No project names, technology names, or product terms appear in the table.