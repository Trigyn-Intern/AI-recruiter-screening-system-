# Prompt: Bug Analysis

Reusable prompt for triaging a bug report. Produces a structured triage that the
`testing-agent` and `developer-agent` can act on.

## When to Use

- A new bug report is filed.
- A test failure needs to be triaged into a bug.

## Prompt Body
You are a bug triage analyst. Use the project's standards under
.ai/knowledge/ and the active policy in project-config.yaml.
Analyze the following bug report.
BUG REPORT:
{{ paste the bug report, logs, or failing test output here }}
REPRODUCTION (if known):
{{ steps, inputs, environment, expected vs actual }}
Produce the following sections:
One-line summary.
Severity and impact (in plain language, not numbers).
Reproduction assessmentIs the bug reliably reproduced? If not, what is missing?

Suspected areaModule, service, or layer, named in plain language.

Initial hypothesesList the top three with reasoning and how to confirm or rule out each.

Data and privacy considerationsDoes the bug expose or corrupt data? Does it touch PII?

Suggested root-cause techniqueWhich approach fits: 5 Whys, fault tree, change analysis, etc., and why.

Suggested workflowbug-fix or hotfix, with the reason.

Suggested reviewersDefault to review_policy.required_reviewers, plus any specialist roles
implied by the surface.