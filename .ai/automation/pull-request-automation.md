---
name: pull-request-automation
version: 1.0.0
applies_to: any
---

# Pull Request Automation

Defines what the AI framework expects to happen automatically when a pull
request is opened, synchronized, or reopened. This document is read by the
orchestrator and by the PR-time automation layer.

## Purpose

Make every PR review predictable. The same reviews run for the same kind of
change, regardless of who opened the PR.

## Responsibilities

- Trigger the right reviews based on the change.
- Generate a PR summary using the code-review template.
- Recommend reviewers based on the change and the policy.
- Make an initial AI verdict that the human reviewer can override.
- Track required approvals against `review_policy.*`.
- Block merge when any blocking check fails.

## Inputs

- The PR diff and metadata.
- `project-config.yaml` for review policy, risk band, and routing rules.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 2 agents and prompts.
- The Phase 3 decision trees for routing, risk, and priority.

## Outputs

- A PR summary using `.ai/templates/code-review-template.md`.
- A list of triggered reviews with their status.
- A list of recommended reviewers.
- A mergeable or blocked status with the blocking reasons.

## Execution Flow

1. **Classify the PR.** Use `priority-selection.md` and `risk-matrix.md` to
   set priority and risk band.
2. **Generate summary.** Use the `generate-pr-description` prompt and the
   code-review template.
3. **Trigger reviews.** Based on the routing rules in
   `routing-rules.md`:
   - Architecture review when the PR touches a public surface.
   - Security review when the PR touches auth, input, secrets,
     persistence, network, or external integrations.
   - Testing review when the PR changes test coverage.
   - Performance review when the PR touches a known-hot area.
   - Documentation review when the PR changes user-facing behavior.
4. **Apply checklists.** Each triggered review applies its checklist and
   produces a report.
5. **Recommend reviewers.** Use the project's reviewer-routing policy.
   Default to code owners when the project uses them.
6. **Initial AI verdict.** Aggregate the triggered reviews into a single
   `approve`, `comment`, or `request-changes` verdict. The human reviewer
   always has the final say.
7. **Track approvals.** Wait for the required number of approvals from
   `review_policy.required_reviewers` and any mandatory specialist
   reviewers.
8. **Block merge.** When any blocking check fails, block the merge and
   surface the reason.

## Automation Rules

- The PR is the unit of automation. Reviews run on the PR, not on the
  branch tip.
- The PR summary is regenerated on every synchronize event.
- A `severe` risk band requires the hotfix workflow, not the normal PR
  flow.
- Branch protection enforces required reviews and status checks before
  merge.

## Failure Handling

- A failing required check blocks merge and is surfaced in the PR
  conversation.
- A missing required reviewer is escalated to the project owner.
- A PR that cannot be classified (ambiguous intent) is routed to the
  `requirement-agent` for clarification.

## Examples

- PR touches a new public API -> architecture review, security review,
  testing review, and documentation review are all triggered. Code owners
  are recommended. Merge is blocked until all four pass and the required
  approvals are in.
- PR is a docs-only change -> documentation review is triggered, others
  are skipped. Reviewer count is reduced per the docs workflow.

## Best Practices

- Surface the AI verdict as advice, not as enforcement. The human reviewer
  is the final authority.
- Keep the PR summary short. A summary that is longer than the diff is
  noise.
- Use the same template at pre-push, PR, and merge. Consistency is the
  point.

## Reusable Enterprise Guidelines

- PR automation is part of the audit trail. Decisions are recorded.
- PR automation respects the same off-hours and on-call rules as the rest
  of the platform.
- PR automation never comments on style nits when a blocker exists. Nits
  are noise during incidents.

## Project Agnostic Design

- The PR review types are tokens, not tool names. The orchestrator
  resolves them.
- The reviewer-routing policy is a project concern, declared in
  `project-config.yaml` and resolved by the platform.