---
name: unit-testing
version: 1.0.0
applies_to: any
---

# Unit Testing Skill

Reusable unit-testing guidance and review. It is language-agnostic and reads
thresholds from `project-config.yaml`.

## Purpose

Encourage a healthy testing pyramid, meaningful coverage, and tests that fail for the
right reasons.

## When to Invoke

- Adding or modifying production code that needs test coverage.
- Reviewing a PR for test quality and coverage.
- Diagnosing flaky or slow tests.

## Inputs

- `project-config.yaml` (required).
- The diff or proposed change.
- Optional: existing test files and coverage report.

## Outputs

- A Test Report using `.ai/templates/test-report-template.md`.
- Concrete suggestions for missing or weak tests.

## Scope

- Unit tests (primary).
- Integration tests (secondary, when `testing.integration_framework` is set).
- Test isolation, determinism, naming, and speed.
- Coverage threshold from `testing.coverage_threshold`.
- Mutation testing only when `testing.mutation_testing` is true.

## Checklist

Apply `.ai/checklists/testing.md`. Mark each item `pass`, `gap`, or `n/a`.

## Expected Report

A Markdown report following the test template, with:

1. Scope of tests reviewed.
2. Coverage observed vs. threshold.
3. Checklist results table.
4. Gaps and suggested new test cases.
5. Flakiness or isolation concerns.

## Limitations

- Does not run the test suite.
- Does not measure coverage; it interprets the coverage report if provided.
- Does not invent numeric thresholds. Read them from `project-config.yaml`.

## Safe Rules

- Never recommend disabling tests to make CI pass.
- Never propose tests that depend on network, time, or global state without an
  abstraction that the project's test framework supports.
- Never duplicate testing standards. Reference the knowledge file.

## Verification Steps

1. Every reported threshold matches a key in `testing.*`.
2. Every checklist item is answered.
3. Suggestions are concrete (input, action, expected outcome).

## Related Knowledge

- `.ai/knowledge/testing-guidelines.md`
- `.ai/checklists/testing.md`
- `.ai/templates/test-report-template.md`