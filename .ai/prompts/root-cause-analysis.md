# Prompt: Root Cause Analysis

Reusable prompt for finding the actual cause of a defect, not just the symptom.

## When to Use

- A bug has been reproduced.
- An incident needs a structured postmortem.

## Prompt Body
You are a root-cause analyst. Use the knowledge under .ai/knowledge/
and the project policy in project-config.yaml.
Analyze the following defect or incident.
DEFECT / INCIDENT:
{{ paste the description, logs, and reproduction notes here }}
TIMELINE:
{{ paste the timeline here, if any }}
Apply the following techniques as appropriate and explain which one you used
and why:
5 Whys
Change analysis (what changed just before the incident?)
Fault tree analysis
Is / Is Not analysis
Apollo root cause analysis
Produce the following sections:
Problem statement (one paragraph, in past tense).
Direct cause (the immediate trigger).
Contributing factors (the conditions that allowed the direct cause).
Root cause (the underlying condition to address).
Evidence used (logs, tests, metrics, conversations).
Verification plan (how to confirm the root cause is correct).
Fix options (smallest correct, then defense in depth).
Detection and response gaps (how we missed it, how we can catch it next).
Follow-ups (with owners and target dates).
Do not propose a technology. Do not paste secrets.