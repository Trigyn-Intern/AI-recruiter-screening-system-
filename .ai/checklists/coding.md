# Coding Checklist

Apply to every change. Every item must be answered with `pass`, `violation`, or `n/a`.

## Size and Complexity

- [ ] No file exceeds `code_quality.max_file_lines`.
- [ ] No function exceeds `code_quality.max_function_lines`.
- [ ] Cyclomatic complexity stays under `code_quality.max_cyclomatic_complexity`.
- [ ] Helpers are extracted where they improve intent.

## Naming

- [ ] Identifiers follow `naming_standards.casing`.
- [ ] Files follow `naming_standards.file_naming`.
- [ ] Identifier prefixes from `naming_standards.identifier_prefixes` are applied
      consistently when used.
- [ ] Names describe intent, not implementation.

## Formatting and Linting

- [ ] `code_quality.enforce_formatting` is satisfied.
- [ ] `code_quality.enforce_linting` is satisfied.
- [ ] No lint or format rules are disabled inside the change.

## Errors and Logging

- [ ] Errors are typed and propagated, never silently swallowed.
- [ ] Logs are structured and free of secrets and PII by default.
- [ ] Failure paths are tested, not just the happy path.

## Comments and Intent

- [ ] Comments explain *why*, not *what*.
- [ ] Public APIs have intent-level doc comments.
- [ ] No commented-out code is left behind.

## Dependencies

- [ ] Any new dependency is justified and license-checked.
- [ ] Versions are pinned using the project's package manager conventions.

## Review Readiness

- [ ] The change is small, focused, tested, and documented.
- [ ] The PR description explains the *why* and the *risk*.