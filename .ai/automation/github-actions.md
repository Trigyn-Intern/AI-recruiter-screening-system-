---
name: github-actions
version: 1.0.0
applies_to: any
---

# GitHub Actions Automation

Defines what the AI framework expects from the GitHub Actions layer. This
document describes behavior, not workflow files. Workflow files live in the
project repository and are configured to call the same checks this document
describes.

## Purpose

Keep the AI framework's expectations of the CI layer explicit, project-
agnostic, and reusable. The framework does not own the workflow files. It
owns the contract the workflow files must satisfy.

## Responsibilities

- Define the contract that GitHub Actions workflows must satisfy to be
  considered "AI-framework compliant."
- Map the framework's quality gates to GitHub Actions capabilities.
- Define the event triggers the framework expects.
- Define the environment and approval model the framework expects.
- Define the artifact and log contract.

## Contract

A compliant GitHub Actions setup must, at minimum, support:

- Trigger on `push` to any branch.
- Trigger on `pull_request` opened, synchronized, or reopened.
- Trigger on `workflow_dispatch` for manual runs.
- A matrix strategy for parallel jobs when the project's policy requires it.
- A clear separation between build, test, security, and deploy jobs.
- A final summary job that consolidates results for humans.

## Inputs

- The active project policy in `project-config.yaml`.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 2 agents and prompts.
- The Phase 3 decision trees for routing and risk.

## Outputs

- Pass or fail status for each job.
- A consolidated workflow summary mapped to checklist ids.
- Artifacts (build outputs, coverage reports, scan reports) retained per the
  project's retention policy.

## Execution Flow

1. **Trigger.** A push, PR, or manual dispatch starts the workflow.
2. **Build.** Build the artifact using the project's declared build tool.
3. **Test.** Run unit and integration tests. Report coverage against
   `testing.coverage_threshold`.
4. **Quality checks.** Run lint, format, and static analysis. Apply
   `checklists/coding.md`.
5. **Security checks.** Run SAST and dependency scan when enabled in
   `security.*`. Apply `checklists/security.md`.
6. **Documentation check.** Verify that any change affecting user-facing
   behavior has updated documentation. Apply
   `checklists/documentation.md`.
7. **Package validation.** Verify the artifact's integrity, signing, and
   metadata when the project's policy requires it.
8. **Consolidated gate.** Apply `quality-gates.md`. Any blocker fails the
   workflow.
9. **Notify.** Use the `notification-engine.md` rules to route results.

## Automation Rules

- The workflow is the source of truth for green or red. Local results are
  advisory.
- The workflow must be re-runnable on demand and must be deterministic for
  a given commit.
- The workflow must not silently swallow failures. Every failure is
  surfaced and routed.
- The workflow must respect `review_policy.*` for required reviewers and
  `quality-gates.md` for blockers.

## Failure Handling

- A failing job blocks the corresponding gate.
- A flaky job is retried up to the policy limit, then escalated.
- A workflow that cannot start (for example, missing secret) is escalated
  per `failure-handling.md`.
- A workflow that produces an artifact with known-vulnerable dependencies
  fails the security gate.

## Examples

- A PR opens against the default branch -> the workflow runs build, test,
  quality, security, and documentation checks. A coverage drop below
  threshold fails the test job. A missing ADR for a new public surface
  fails the documentation job.
- A push to the default branch runs the same checks plus a deploy job to
  the first target environment in `deployment.target_environments`.

## Best Practices

- Keep jobs small and parallel. A single mega-job is hard to debug.
- Use caching for dependencies. Cold installs dominate runtime.
- Pin action versions. Floating versions are a supply-chain risk.
- Use OIDC for cloud access. Long-lived secrets are a risk.

## Reusable Enterprise Guidelines

- The workflow is part of the audit trail. Logs are retained per the
  project's policy.
- The workflow must run on every change. Skipping CI for "trivial" changes
  is not allowed.
- The workflow must support branch protection. Direct pushes to protected
  branches are not allowed.

## Project Agnostic Design

- The contract is described in terms of capabilities, not tool versions.
  The orchestrator resolves versions from `project-config.yaml`.
- Adding a new check is a matter of declaring it in `quality-gates.md`
  and adding a job that calls the same check. The contract does not
  change.