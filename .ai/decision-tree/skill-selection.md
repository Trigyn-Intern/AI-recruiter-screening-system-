# Decision Tree: Skill Selection

Reusable routing for "which skill should I invoke now?" Use this when an agent
or a user is unsure where to start.

## Inputs

- The current task in plain language.
- The active project policy in `project-config.yaml`.
- The available artifacts (diff, requirement, design, test report).

## Root Question

> "What kind of work is this?"

## Branches

- **Designing or changing structure**
  - Use `architecture`.
  - Then route to `coding-standards` for early sizing and naming checks.
- **Writing or changing code**
  - Use `coding-standards` to set the bar.
  - Use `unit-testing` to design tests in parallel.
  - Use `security` whenever the surface is auth, input, secrets, persistence,
    network, or external integrations.
  - Use `documentation` whenever the public surface changes.
- **Reviewing a change**
  - Use `code-review` as the conductor.
  - Pull in `security`, `unit-testing`, and `documentation` as in scope.
- **Producing or updating docs**
  - Use `documentation`.
  - Pull in `architecture` when diagrams or structural docs are needed.
- **Triaging or fixing a defect**
  - Use the `bug-fix` workflow with `requirement-agent` and `bug-analysis`.
  - Use `root-cause-analysis` before the fix.
  - Use `unit-testing` to add the regression test.
  - Use `security` when the surface is in scope.
- **Releasing**
  - Use the `release` workflow.
  - Use `documentation` for release notes.
  - Use `security` for the release-level posture check.

## Multi-Skill Collaboration

- The `code-review` skill is the only one that may decide to invoke other
  skills. Other skills stay focused and refer the agent to the right skill.
- When more than one skill applies, the order is:
  1. `architecture` (if structural decisions are open)
  2. `coding-standards` (sets the bar for what follows)
  3. `unit-testing` (designs tests in parallel with code)
  4. `security` (in parallel with `unit-testing` when in scope)
  5. `documentation` (after the change shape is stable)
  6. `code-review` (final consolidation)

## When to Stop Routing

Stop and escalate to a human when:

- A `review_policy.blocking_checks` item has no checklist id.
- A required config section is missing.
- Two skills give conflicting recommendations.