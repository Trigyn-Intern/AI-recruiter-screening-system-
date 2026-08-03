# Decision Tree: Workflow Selection

Reusable routing for "which workflow should run this change?" Use this when a
new piece of work enters the system and you need to pick the right entry point.

## Inputs

- The type of work (feature, bug, hotfix, refactor, release, docs).
- The active project policy in `project-config.yaml`.
- The current state of the code (clean, in flight, in production).

## Root Question

> "Is this change adding behavior, fixing behavior, restructuring, or
> describing?"

## Branches

- **Adding behavior**
  - Use `feature-development.workflow.md`.
  - Start with the `requirement-agent` and the `requirement-analysis` prompt.
- **Fixing behavior**
  - Use `bug-fix.workflow.md` by default.
  - Use `hotfix.workflow.md` when the impact is severity 1 or 2, or when
    security requires an out-of-band patch.
- **Restructuring without behavior change**
  - Use `refactoring.workflow.md`.
  - Verify the test suite is green before starting.
- **Describing or documenting**
  - Use `documentation.workflow.md`.
  - Use `feature-development.workflow.md` if docs are bundled with code.
- **Promoting merged work**
  - Use `release.workflow.md`.
  - Use `documentation.workflow.md` for any doc follow-up after release.

## Chaining Rules

- A feature workflow may produce a refactor as a follow-up. Run the refactor
  workflow in a separate change.
- A bug fix may surface a refactor. File the refactor as a follow-up, do not
  bundle.
- A release may include a hotfix. Treat the hotfix as already-merged input to
  the release workflow.
- A documentation workflow may trigger a small refactor when the docs reveal a
  structural gap. Keep the refactor separate.

## Quality Gate Anchor

Whichever workflow runs, the final gate is the same:

- All `review_policy.blocking_checks` pass.
- All four checklists (coding, security when in scope, testing, documentation)
  are answered.
- Required approvals are recorded.

## When to Stop Routing

Stop and escalate when:

- A change matches more than one workflow and the priority is unclear.
- The chosen workflow would skip a `review_policy.blocking_checks` item.
- The change is a mix of behavior and restructure that cannot be cleanly
  split.