# Technical Debt Analysis

## Goal
Identify maintainability risks across the whole repository.

## Inspect
- TODO, FIXME, HACK, and deprecated code.
- Large files, long functions, and high cyclomatic complexity.
- Untested critical code paths.
- Outdated dependencies and duplicated logic.
- Temporary workarounds and missing error handling.

## Output
For each finding record: identifier, location, severity, evidence, impact,
recommended remediation, estimated effort, and suggested priority.

## Severity
- High: security, data loss, outage, or blocked delivery risk.
- Medium: maintainability or reliability risk.
- Low: readability, consistency, or minor cleanup.
