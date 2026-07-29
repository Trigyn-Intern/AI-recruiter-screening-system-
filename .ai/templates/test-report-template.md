# Test Report

## Summary

{{ one-paragraph summary }}

## Scope

- Change or module under test: {{ description }}
- Unit framework: {{ testing.unit_test_framework }}
- Integration framework: {{ testing.integration_framework }}
- Coverage threshold: {{ testing.coverage_threshold }}%

## Coverage Observed

- Line coverage: {{ percent }}%
- Branch coverage: {{ percent }}%
- Threshold met: `yes` | `no`

## Checklist Results

| Item | Status | Note |
| --- | --- | --- |
{{ each item from checklists/testing.md: pass | gap | n/a }}

## Suggested New Tests

| Scenario | Input | Expected Outcome | Type |
| --- | --- | --- | --- |
{{ test ideas, one row per item }}

## Flakiness / Isolation

- {{ observation }}

## Follow-ups

- {{ action, owner, target }}