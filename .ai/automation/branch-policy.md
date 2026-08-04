---
name: branch-policy
version: 1.0.0
applies_to: any
---

# Branch Policy

Defines the branch model the AI framework expects projects to follow. The
framework reads `branch_strategy.*` from `project-config.yaml` and enforces
the policy at the automation layer, not in the AI agent.

## Purpose

Keep the branch model boring and predictable. Every project uses the same
shape; only the prefixes and the merge strategy change.

## Responsibilities

- Define the branch types and their prefixes.
- Define the merge strategy for each branch type.
- Define the protection rules for protected branches.
- Define the lifecycle of a branch from creation to deletion.

## Inputs

- `project-config.yaml` (`branch_strategy.*`).
- The platform's branch protection capabilities (configured outside the
  framework).

## Outputs

- A branch policy declaration that the platform can enforce.
- A lifecycle map for branches.

## Branch Types

| Type | Prefix (from `branch_strategy.*`) | Base | Merge Into | Strategy |
| --- | --- | --- | --- | --- |
| `feature` | `feature_prefix` | `default_branch` | `default_branch` | `squash_merges` by default |
| `release` | `release_prefix` | `default_branch` | `default_branch` | non-squash, tagged |
| `hotfix` | `hotfix_prefix` | the tagged release | `default_branch` and the release branch | non-squash, tagged |
| `chore` | `chore/` (convention) | `default_branch` | `default_branch` | `squash_merges` by default |
| `docs` | `docs/` (convention) | `default_branch` | `default_branch` | `squash_merges` by default |

The framework does not own the conventions for `chore/` and `docs/`. When
the project uses different prefixes, declare them in `project-config.yaml`.

## Execution Flow

1. **Create branch.** A developer or the orchestrator creates a branch
   using the appropriate prefix.
2. **Protect branch.** Protected branches (typically `default_branch` and
   release branches) have protection rules applied by the platform.
3. **Work in branch.** Commits land on the branch. Pre-commit and pre-push
   apply.
4. **Open PR.** A PR is opened against the appropriate base branch.
5. **Review and approve.** `pull-request-automation.md` runs.
6. **Merge.** The merge strategy from `branch_strategy.*` is applied.
7. **Tag.** Release and hotfix branches are tagged using the project's
   tagging convention.
8. **Delete.** The branch is deleted after merge, except for release
   branches that the project's policy keeps open.

## Automation Rules

- Protected branches reject direct pushes. The only path to a protected
   branch is a reviewed and approved PR.
- `default_branch` is always protected.
- Release branches are protected for the duration of the release.
- Hotfix branches are short-lived and deleted after the hotfix lands in
  both `default_branch` and the active release branch.
- `rebase_merges` are disabled unless `branch_strategy.rebase_merges` is
  true. Rebase merges make history harder to audit.

## Failure Handling

- A push to a protected branch is rejected by the platform.
- A merge that would skip a required check is blocked.
- A branch that cannot be deleted because of an open PR is escalated.

## Examples

- A developer opens `feature/add-login` from `default_branch` -> the PR
  runs the full review flow -> squash merge into `default_branch` -> branch
  is deleted.
- A release manager cuts `release/2026-Q3` from `default_branch` -> the
  release flow runs -> the branch is tagged on cut and on every promotion
  -> the branch is merged back to `default_branch` at end of life.
- An on-call engineer opens `hotfix/critical-auth-bypass` from the tagged
  release -> the hotfix flow runs with reduced gates -> the branch is
  merged into both the release branch and `default_branch` -> the branch
  is deleted.

## Best Practices

- Keep branches short-lived. Long-lived branches rot.
- Use the same prefix for the same intent across the org. The framework's
  defaults are the convention.
- Tag every release. Tags are the audit trail.
- Protect the default branch. No exceptions.

## Reusable Enterprise Guidelines

- Branch policy is part of the audit trail. The platform records who
  created, reviewed, and merged each branch.
- Branch policy is the same across projects. Differences are declared in
  `project-config.yaml`, not invented per repo.
- Branch policy is enforced by the platform, not by the AI agent. The AI
  agent reads it and respects it.

## Project Agnostic Design

- Prefixes are read from `branch_strategy.*`. No project names appear in
  the policy.
- Merge strategies are tokens (`squash`, `merge`, `rebase`) and are
  resolved by the platform.