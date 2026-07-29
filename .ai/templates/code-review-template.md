# Code Review Report

## Summary

{{ one-paragraph summary of the change and overall impression }}

## Scope

- Files / modules reviewed: {{ list }}
- Branch / PR: {{ branch-or-pr-id }}
- Reviewer: {{ reviewer }}
- Date: {{ date }}

## Thresholds Applied

| Setting | Source | Value |
| --- | --- | --- |
| Max file lines | `code_quality.max_file_lines` | {{ value }} |
| Max function lines | `code_quality.max_function_lines` | {{ value }} |
| Max cyclomatic complexity | `code_quality.max_cyclomatic_complexity` | {{ value }} |
| Required reviewers | `review_policy.required_reviewers` | {{ value }} |

## Checklist Results

| Item | Status | Note |
| --- | --- | --- |
{{ each checklist item as a row: pass | concern | n/a }}

## Findings

### Blockers

- {{ finding, location, suggested fix }}

### Major

- {{ finding, location, suggested fix }}

### Minor

- {{ finding, location, suggested fix }}

### Nits

- {{ finding, location, suggested fix }}

## Questions for the Author

1. {{ question }}
2. {{ question }}

## Verdict

- Decision: `approve` | `comment` | `request-changes`
- Rationale: {{ rationale }}