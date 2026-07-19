---
name: notification-engine
version: 1.0.0
applies_to: any
---

# Notification Engine

Defines how the AI framework routes observations, alerts, and status
updates to humans and to other systems. The framework owns the routing
rules; the platform owns the delivery.

## Purpose

Make notifications predictable. The same event always goes to the same
people through the same channel with the same urgency.

## Responsibilities

- Define the event types the framework emits.
- Define the routing rules per event type.
- Define the channel and urgency model.
- Define the off-hours and on-call rules.
- Define the deduplication and throttling rules.

## Inputs

- Events from the Phase 4 automation documents.
- `project-config.yaml` for routing, urgency, and on-call policy.
- The platform's notification capabilities.

## Outputs

- A routed notification per event.
- A delivery record per attempt.
- An audit trail per notification.

## Event Types

| Event | Default Urgency | Default Channel |
| --- | --- | --- |
| `review.completed` | low | PR conversation |
| `security.issue-found` | high | security channel, PR conversation |
| `tests.failed` | medium | PR conversation, engineering channel |
| `coverage.dropped` | medium | engineering channel |
| `documentation.outdated` | low | documentation channel |
| `release.ready` | medium | release channel, stakeholders |
| `release.failed` | high | release channel, on-call |
| `hotfix.started` | high | incident channel |
| `hotfix.landed` | medium | incident channel, release channel |
| `dependency.advisory` | high | security channel |
| `build.flaky` | low | engineering channel |
| `monitor.alert` | per severity | per severity |

## Routing Rules

- `blocker` and `critical` events page the on-call rotation.
- `high` events post to the engineering channel and require an owner.
- `medium` events post to the engineering channel and are tracked.
- `low` events post to the PR conversation or the relevant docs channel.
- Destructive failures (per `failure-handling.md`) always page the
  on-call rotation.

## Urgency Model

| Urgency | Response SLA | Channel |
| --- | --- | --- |
| `blocker` | immediate | on-call, incident channel |
| `critical` | 1 business hour | security or release channel |
| `high` | 4 business hours | engineering channel |
| `medium` | 1 business day | engineering or docs channel |
| `low` | next planning cycle | PR or docs channel |

SLAs are read from `project-config.yaml` when the project overrides
them. The framework does not invent SLAs.

## Off-Hours and On-Call

- `blocker` and `critical` events ignore off-hours.
- `high` and below respect off-hours. They queue and deliver at the
  start of the next business day unless the project's policy says
  otherwise.
- The on-call rotation is the source of truth for off-hours routing.
  The framework reads it from `project-config.yaml` or from the
  platform's on-call service.

## Deduplication and Throttling

- Identical events within a 15-minute window collapse to one
  notification with a count.
- A storm (more than 10 events of the same type per hour) is throttled
  and escalated as a platform issue.
- A resolved event posts a single follow-up, not a stream.

## Execution Flow

1. **Receive event.** The notification engine receives an event from
   any Phase 4 automation document.
2. **Classify.** Apply the event type and urgency model.
3. **Route.** Apply the routing rules and the on-call policy.
4. **Deduplicate.** Apply the deduplication and throttling rules.
5. **Deliver.** Send through the resolved channel with the standard
   payload.
6. **Record.** Log the delivery and the response SLA target.
7. **Escalate.** If undelivered or unacknowledged past the SLA,
   escalate.

## Automation Rules

- Notifications never include secrets, tokens, or PII.
- Notifications include the checklist id, the event source, and a link
  to the originating artifact.
- Notifications use the same template across event types. The payload
  is the contract.

## Failure Handling

- A failed delivery is retried with backoff up to the policy limit.
- A delivery that cannot reach any channel is escalated to the platform
  owner.
- A notification storm is throttled and the source is escalated for
  tuning.

## Examples

- A code review completes -> `low` urgency -> PR conversation.
- A security issue is found -> `high` urgency -> security channel and
  PR conversation.
- A hotfix is started -> `high` urgency -> incident channel.
- A release fails mid-promotion -> `high` urgency -> release channel
  and on-call.

## Best Practices

- Tune the deduplication window. Too short and people get spammed. Too
  long and people miss things.
- Pair every event with an owner. An event without an owner is a
  notification without a destination.
- Use the same payload across channels. The platform maps it to the
  channel format.

## Reusable Enterprise Guidelines

- Notifications are part of the audit trail. Delivery records are
  retained.
- Notifications respect the on-call rotation. The framework does not
  invent its own.
- Notifications are quiet by default. A noisy engine gets muted.

## Project Agnostic Design

- Channels and on-call rotations are tokens. The platform resolves
  them.
- SLAs are read from `project-config.yaml` when overridden.