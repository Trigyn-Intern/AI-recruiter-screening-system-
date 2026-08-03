# Security Checklist

Apply to any change touching auth, input, secrets, persistence, network, or
external integrations. Every item gets `pass`, `risk`, or `n/a`.

## Authentication and Authorization

- [ ] Auth model follows `security.auth_model`.
- [ ] Authorization is enforced on every request, including service-to-service.
- [ ] Privileges follow least privilege.
- [ ] Session handling uses vetted mechanisms.

## Input and Output

- [ ] External input is validated at the trust boundary.
- [ ] Allowlists are used over denylists.
- [ ] Output is encoded for its destination context.
- [ ] Input is normalized before validation.

## Secrets and Configuration

- [ ] No secrets, keys, or credentials are committed.
- [ ] Secrets use the mechanism declared in `security.secrets_management`.
- [ ] Configuration is externalized and environment-scoped.

## Cryptography

- [ ] No custom crypto, token formats, or session logic.
- [ ] Authenticated encryption is used where applicable.
- [ ] Algorithms and key lengths are modern and vetted.

## Logging and PII

- [ ] Logs are sufficient for security events, not over-shared.
- [ ] Sensitive fields are redacted at the logger boundary.
- [ ] PII is treated as a secret class.

## Web and API

- [ ] XSS, CSRF, SSRF, clickjacking, and open redirect risks are considered.
- [ ] Security headers follow safe defaults.
- [ ] Rate limiting and abuse controls are in place at the edge.
- [ ] Queries are parameterized; concatenation is not used.

## Dependencies and Supply Chain

- [ ] Dependencies are inventoried and reviewed.
- [ ] Advisories trigger a documented response.
- [ ] Build and release pipelines are tamper-resistant.

## LLM-Specific

- [ ] Applies only when `security.prompt_injection_review` is true.
- [ ] Untrusted text is treated as data, never as instructions.
- [ ] Model behavior is constrained with explicit policies and tool scopes.
- [ ] Model output cannot run unrestricted code.

## Incident Readiness

- [ ] Contact paths and severity levels are defined.
- [ ] The playbook has been practiced, not just written.