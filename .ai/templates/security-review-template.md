# Security Review Report

## Summary

{{ one-paragraph summary }}

## Scope

- Change or system reviewed: {{ description }}
- Auth model in effect: {{ security.auth_model }}
- Secrets mechanism: {{ security.secrets_management }}
- Threat model status: {{ security.threat_model_required }}

## Trust Boundaries

- {{ boundary }}
- {{ boundary }}

## Threats Considered

- {{ threat }}
- {{ threat }}

## Checklist Results

| Item | Status | Note |
| --- | --- | --- |
{{ each item from checklists/security.md: pass | risk | n/a }}

## Findings

| Severity | Location | Description | Remediation | Checklist Ref |
| --- | --- | --- | --- | --- |
{{ findings, one row per item }}

## LLM-Specific Risks

{{ only when security.prompt_injection_review is true }}

- {{ risk, control, residual risk }}

## Residual Risk

- {{ residual risk and its accept rationale }}

## Sign-off Conditions

- {{ condition that must be met before approval }}