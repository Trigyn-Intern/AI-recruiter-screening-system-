# Coding Standards

Generic, reusable coding standards. Adopt the subset that fits the active project by
configuring `project-config.yaml`. Do not copy this file into a skill.

## Principles

- **SOLID** - Single responsibility, Open/closed, Liskov substitution, Interface
  segregation, Dependency inversion.
- **DRY** - Every piece of knowledge has a single, authoritative representation.
- **KISS** - Prefer the simplest solution that meets the current requirement.
- **YAGNI** - Do not build features until they are actually needed.
- **Separation of concerns** - Keep policy, mechanism, and presentation distinct.
- **Principle of least surprise** - Code should do what its name and shape suggest.

## Size and Complexity

- Keep files under `code_quality.max_file_lines`.
- Keep functions under `code_quality.max_function_lines`.
- Keep cyclomatic complexity under `code_quality.max_cyclomatic_complexity`.
- Extract helpers when names explain intent better than inline code does.

## Naming

- Use the casing declared in `naming_standards.casing`.
- Use the file naming declared in `naming_standards.file_naming`.
- Apply identifier prefixes from `naming_standards.identifier_prefixes` only when
  the project actually uses them.
- Names should describe intent, not implementation.

## Formatting and Linting

- `code_quality.enforce_formatting` and `code_quality.enforce_linting` decide
  whether tools are required to pass.
- Never disable a lint or format rule inside a skill. If a rule is wrong, change
  the shared config and document why.

## Errors and Logging

- Fail fast on programmer errors. Use typed errors for domain errors.
- Never swallow exceptions silently. If recovery is impossible, propagate.
- Logs should be structured, redactable, and free of secrets and PII by default.

## Comments and Intent

- Comments explain *why*, not *what*. Code shows *what*.
- Public APIs need intent-level doc comments. Internal helpers do not.
- Remove commented-out code. Source control remembers it.

## Dependencies

- New dependencies require a justification and a license check.
- Prefer the standard library or existing dependencies when reasonable.
- Pin versions using the project's package manager conventions.

## Review Bar

- A change is ready for review when it is small, focused, tested, and documented.
- Large refactors must be split into reviewable steps.