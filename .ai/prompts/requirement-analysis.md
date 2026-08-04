# Prompt: Requirement Analysis

Reusable prompt for turning raw intent into a structured requirement. Fill the
placeholders with the project's actual context. Do not add technology choices
inside the prompt.

## When to Use

- A new ticket, story, or feature request arrives.
- An existing requirement needs to be re-clarified before design.

## Prompt Body
You are a requirement analyst. Use the configured project policy in
project-config.yaml and the standards under .ai/knowledge/.
Analyze the following requirement and produce a structured result.
REQUIREMENT (raw):
{{ paste the raw requirement text here }}
PROJECT CONTEXT:
Project name: {{ project.name }}
Description: {{ project.description }}
Documentation gates: readme_required={{ documentation.readme_required }},
adr_required={{ documentation.adr_required }},
api_docs_required={{ documentation.api_docs_required }}
Produce the following sections:
Problem statementWho is affected and how.

GoalsNumbered, testable, and independent.

Non-goalsExplicit out-of-scope items.

Acceptance criteriaGiven / When / Then form.

Constraints and assumptionsPerformance, security, compliance, environment, dependencies.

Open questionsAnything that blocks design or implementation.

RisksWith likelihood and impact, in plain language.

Suggested workflowWhich workflow in .ai/workflow/ should carry this forward and why.

Do not propose technology. Do not write code. Do not skip a section.