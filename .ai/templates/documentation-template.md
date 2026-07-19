# Documentation Report

## Summary

{{ one-paragraph summary }}

## Scope

- Change or system documented: {{ description }}
- Diagram format: {{ documentation.diagram_format }}
- ADR required: {{ documentation.adr_required }}
- API docs required: {{ documentation.api_docs_required }}

## Checklist Results

| Item | Status | Note |
| --- | --- | --- |
{{ each item from checklists/documentation.md: pass | gap | n/a }}

## Gaps and Proposed Edits

| Location | Current State | Proposed Edit | Audience |
| --- | --- | --- | --- |
{{ one row per gap }}

## ADR Candidate

- Title: {{ title }}
- Status: `proposed`
- Context: {{ context }}
- Decision: {{ decision }}
- Consequences: {{ consequences }}

## Follow-ups

- {{ action, owner, target }}