# Code Complexity Analysis

## Goal
Identify functions and modules that are difficult to understand, test, or safely change.

## Thresholds
Use `.ai/project-config.yaml` limits:
- Maximum file lines: 400.
- Maximum function lines: 60.
- Maximum cyclomatic complexity: 10.

## Output
For each violation, provide file, symbol, measured complexity, contributing branches,
test coverage indication, and a safe refactoring approach.
