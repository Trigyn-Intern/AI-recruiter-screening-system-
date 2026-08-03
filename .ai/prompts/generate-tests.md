# Prompt: Generate Tests

Reusable prompt for designing test cases for a change. Pulls scenarios from
`testing-guidelines.md` and `security-test-scenarios.md`.

## When to Use

- A new feature or fix needs test coverage.
- An existing module needs gap analysis.

## Prompt Body
ou are a test designer. Use project-config.yaml and the knowledge under
.ai/knowledge/.
Generate test cases for the following change.
CHANGE DESCRIPTION:
{{ paste the diff or change description here }}
CONSTRAINTS:
Unit framework: {{ testing.unit_test_framework }} (name only; do not write
framework-specific code).
Integration framework: {{ testing.integration_framework }} (name only).
Coverage threshold: {{ testing.coverage_threshold }}%.
Test isolation required: {{ testing.test_isolation_required }}.
Mutation testing in use: {{ testing.mutation_testing }}.
For each test case, produce:
Name and intent.
Type (unit, integration, contract, performance, security-driven).
Inputs and preconditions.
Action.
Expected outcome.
Negative and edge cases covered.
Source reference: which checklist id or knowledge section drove the case.
When the change touches auth, input, secrets, persistence, network, or
external integrations, include at least one security-driven scenario from
security-test-scenarios.md.
Group the cases by behavior, not by file. Do not write the test code itself.