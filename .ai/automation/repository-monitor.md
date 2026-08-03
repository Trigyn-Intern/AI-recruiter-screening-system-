---
name: repository-monitor
version: 1.0.0
applies_to: any
---

# Repository Monitor

Defines what the AI framework expects to observe continuously about the
repository. The monitor is read-only. It informs the orchestrator and the
notification engine.

## Purpose

Catch the issues that no individual PR will surface. The monitor is the
"is the repo healthy over time" signal.

## Responsibilities

- Observe dependency changes.
- Observe large or unusual commits.
- Observe sensitive files.
- Observe test deletions and coverage drift.
- Observe configuration drift.
- Observe build and test health over time.
- Surface observations through the notification engine.

## Inputs

- The repository's commit history, file tree, and CI history (read-only).
- `project-config.yaml` for thresholds and policy.
- The Phase 1 knowledge and checklist files.
- The Phase 3 risk matrix for severity scoring.

## Outputs

- A continuous observation feed.
- A weekly or daily health summary.
- Alerts when an observation crosses a threshold.

## Observations

### Dependencies

- New direct dependency added.
- Dependency removed.
- Major or minor version bump of a direct dependency.
- License change on a direct dependency.
- New advisory on a direct or transitive dependency.

### Commits

- Commit larger than the configured size threshold.
- Commit authored outside normal hours from a new author.
- Commit that bypasses the PR flow (direct push to a protected branch).

### Sensitive Files

- File matching the project's sensitive-file pattern added or modified.
- Secret-like content detected in a non-secret path.

### Tests

- Test file deleted.
- Test file renamed in a way that breaks the project's test discovery.
- Coverage drops below `testing.coverage_threshold` over a moving window.
- Test execution time grows beyond the configured budget.

### Configuration

- Configuration file modified outside the documented change process.
- Environment-specific configuration committed to a shared path.

### Build and Test Health

- Build failure rate above the configured threshold.
- Flaky test rate above the configured threshold.
- CI runtime grows beyond the configured budget.

## Execution Flow

1. **Collect.** On a schedule, gather the observations above.
2. **Score.** Apply `risk-matrix.md` to each observation.
3. **Aggregate.** Group observations by area (dependencies, tests, build).
4. **Threshold.** Compare each aggregated area to its threshold.
5. **Alert.** Route alerts through `notification-engine.md`.
6. **Summarize.** Produce a daily or weekly summary for humans.

## Automation Rules

- The monitor is read-only. It never modifies the repository.
- The monitor never raises a PR. It only informs.
- The monitor's thresholds are declared in `automation-config.md` and
  `project-config.yaml`, not invented per project.
- The monitor respects off-hours. Alerts that can wait until business
  hours do wait.

## Failure Handling

- A monitor that cannot collect (for example, missing permission) is
  escalated to the platform owner.
- A false-positive storm is throttled and escalated for tuning.
- A missed observation (for example, a flaky scanner) is escalated as a
  platform issue, not a project issue.

## Examples

- A new direct dependency is added with a license the project has not
  approved -> the monitor raises a `medium` alert routed to the security
  channel.
- Test coverage drops from 82 to 71 over a week -> the monitor raises a
  `high` alert routed to the engineering channel.
- A direct push to `default_branch` is observed -> the monitor raises a
  `blocker` alert and pages the on-call rotation.

## Best Practices

- Tune thresholds. A monitor that cries wolf is a monitor that gets
  ignored.
- Pair the monitor with the notification engine. An observation without
  a destination is noise.
- Use moving windows, not point-in-time checks. Drift is a trend, not
  a snapshot.

## Reusable Enterprise Guidelines

- The monitor is a platform capability. The AI framework consumes its
  observations.
- The monitor's data is part of the audit trail. Retention follows the
  project's policy.
- The monitor must not be the only line of defense. Its job is to spot
  trends, not to block individual changes.

## Project Agnostic Design

- Observation types are tokens, not file names. The platform resolves
  them.
- Thresholds are read from `project-config.yaml` and
  `automation-config.md`.