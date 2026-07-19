---
name: security
version: 1.0.0
applies_to: any
---

# Security Skill

Reusable security review assistance. It does not run scanners. It interprets scanner
output and applies the standards defined in the knowledge and checklist files.

## Purpose

Catch security risks early by applying a consistent, configuration-driven checklist
across every project.

## When to Invoke

- Reviewing any change that touches auth, input handling, secrets, persistence,
  network boundaries, or external integrations.
- When adding or modifying an LLM-facing surface and
  `security.prompt_injection_review` is true.
- Pre-release security gate.

## Inputs

- `project-config.yaml` (required).
- The diff or change description.
- Optional: SAST or dependency scan output.

## Outputs

- A Security Report using `.ai/templates/security-review-template.md`.

## Scope

- Authentication, authorization, and session handling.
- Input validation and output encoding.
- Secrets, keys, and configuration.
- Logging, telemetry, and PII handling.
- Dependency and supply-chain risk.
- LLM-specific risks when `security.prompt_injection_review` is true.

## Checklist

Apply `.ai/checklists/security.md`. Every item gets `pass`, `risk`, or `n/a`.
A `risk` requires a remediation suggestion.

## Expected Report

A Markdown report following the security template, with:

1. Scope and trust boundaries.
2. Threats considered.
3. Checklist results table.
4. Findings with severity, location, and remediation.
5. Residual risk and sign-off conditions.

## Limitations

- Does not perform penetration testing.
- Does not replace human review when `review_policy.require_security_review` is true.
- Does not run SAST or SCA tools; it only consumes their output.

## Safe Rules

- Never echo secrets, tokens, or credentials into the report, even in examples.
- Never recommend disabling a security control as a default fix.
- Never invent a threat model. Reference `security-guidelines.md`.

## Verification Steps

1. The auth model in the report matches `security.auth_model`.
2. Every checklist item is answered.
3. All findings map to a checklist id and a remediation.

## Related Knowledge

- `.ai/knowledge/security-guidelines.md`
- `.ai/checklists/security.md`
- `.ai/templates/security-review-template.md`