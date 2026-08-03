# Security Test Scenarios

Reusable, threat-driven test scenarios. The `security-agent` selects from this
list; the `testing-agent` turns the selected scenarios into test cases. None of
these are tied to a specific technology.

## How to Use

1. Identify which surfaces are in scope for the change (auth, input, secrets,
   persistence, network, external integrations, LLM).
2. Pick every scenario in the matching section below.
3. For each scenario, design a test case using the `generate-tests` prompt.
4. Track each scenario by its id (e.g. `SEC-INPUT-001`) in the test report.

## Authentication

- `SEC-AUTH-001` Verify that unauthenticated requests are rejected at every
  boundary, including service-to-service calls.
- `SEC-AUTH-002` Verify that authentication failures use generic error
  messages that do not disclose whether an account exists.
- `SEC-AUTH-003` Verify that session tokens expire according to the configured
  policy and that expired tokens are rejected.
- `SEC-AUTH-004` Verify that login throttling and lockout behave per the
  configured policy and do not enable a denial-of-service against valid users.
- `SEC-AUTH-005` Verify that multi-factor flows cannot be bypassed by skipping
  steps or replaying earlier steps.

## Authorization

- `SEC-AUTHZ-001` Verify that every endpoint enforces authorization, not just
  authentication.
- `SEC-AUTHZ-002` Verify that a user with one role cannot perform an action
  reserved for another role.
- `SEC-AUTHZ-003` Verify that object-level access checks prevent access to
  resources the user does not own.
- `SEC-AUTHZ-004` Verify that privilege escalation paths (for example,
  parameter tampering, IDOR, mass assignment) are blocked.
- `SEC-AUTHZ-005` Verify that service-to-service calls carry and validate an
  identity, not just an API key.

## Input Validation

- `SEC-INPUT-001` Verify that boundary values (empty, max, max+1, unicode,
  null bytes) are handled without crash or unexpected behavior.
- `SEC-INPUT-002` Verify that allowlists are used in place of denylists when
  the field has a known shape.
- `SEC-INPUT-003` Verify that structured inputs (JSON, XML, query strings) are
  rejected or truncated when they exceed size limits.
- `SEC-INPUT-004` Verify that unexpected fields are ignored or rejected, not
  silently honored.
- `SEC-INPUT-005` Verify that normalization happens before validation, not
  after.

## Output Encoding

- `SEC-OUT-001` Verify that user-controlled data rendered in HTML is encoded
  for the active context.
- `SEC-OUT-002` Verify that user-controlled data rendered in a URL is encoded
  and that open redirects are blocked.
- `SEC-OUT-003` Verify that user-controlled data rendered in a shell or system
  command is encoded or rejected.
- `SEC-OUT-004` Verify that error responses do not include stack traces,
  internal paths, or secrets.

## Secrets and Configuration

- `SEC-SECRET-001` Verify that no secrets appear in source, fixtures, or
  examples.
- `SEC-SECRET-002` Verify that secrets are loaded only from the mechanism
  declared in `security.secrets_management`.
- `SEC-SECRET-003` Verify that rotating a secret invalidates sessions and
  cached credentials as the policy requires.
- `SEC-SECRET-004` Verify that configuration that differs between environments
  cannot leak from one environment to another.

## Cryptography

- `SEC-CRYPTO-001` Verify that deprecated algorithms and modes are rejected
  by configuration, not just at the call site.
- `SEC-CRYPTO-002` Verify that authenticated encryption is used where the
  data is at rest in motion or in storage.
- `SEC-CRYPTO-003` Verify that key material is not logged, even at debug
  verbosity.

## Logging and PII

- `SEC-LOG-001` Verify that authentication events are logged with enough
  detail to investigate, without logging the credentials themselves.
- `SEC-LOG-002` Verify that sensitive fields are redacted at the logger
  boundary, not after the fact.
- `SEC-LOG-003` Verify that PII is treated as a sensitive class and not
  written to non-production logs.

## Web and API

- `SEC-WEB-001` Verify that CSRF protections are present on every state-
  changing request that uses cookie-based auth.
- `SEC-WEB-002` Verify that security headers follow safe defaults for the
  active surface.
- `SEC-WEB-003` Verify that rate limiting and abuse controls trigger before
  the system is degraded.
- `SEC-WEB-004` Verify that server-side request forgery (SSRF) controls block
  unapproved destinations.
- `SEC-WEB-005` Verify that clickjacking protections are present on
  authenticated surfaces.

## Persistence and Queries

- `SEC-DATA-001` Verify that all queries are parameterized; concatenation is
  rejected by the project's lint or review policy.
- `SEC-DATA-002` Verify that database errors do not leak schema or row data
  to the caller.
- `SEC-DATA-003` Verify that migrations are reversible or have a documented
  rollback path.
- `SEC-DATA-004` Verify that backups exclude secrets that should not be
  retained.

## Dependency and Supply Chain

- `SEC-DEP-001` Verify that the project's dependency scan is clean for the
  active change.
- `SEC-DEP-002` Verify that pinned versions are used for security-sensitive
  dependencies.
- `SEC-DEP-003` Verify that build and release pipelines reject unsigned or
  unverified artifacts when the policy requires it.

## LLM-Specific (use only when `security.prompt_injection_review` is true)

- `SEC-LLM-001` Verify that untrusted text is treated as data, never as
  instructions, in every prompt assembly path.
- `SEC-LLM-002` Verify that model behavior is constrained by an explicit
  policy and that violations are refused, not just warned.
- `SEC-LLM-003` Verify that tool scopes are limited to the minimum required
  for the task.
- `SEC-LLM-004` Verify that model output that triggers code execution runs in
  a sandbox with the documented controls.
- `SEC-LLM-005` Verify that prompts and completions are logged with the same
  redaction rules as other logs.
  