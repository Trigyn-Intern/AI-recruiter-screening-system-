---
name: agent-orchestration
version: 1.0.0
applies_to: any
---

# Decision Tree: Agent Orchestration

Reusable rules for which agent runs first, which depends on which, which run
in parallel, and which is the final approval.

## Purpose

Make the agent chain predictable. Given a workflow and a risk band, the
orchestrator must know the exact order and parallelism without guessing.

## Responsibilities

- Define the dependency graph between agents.
- Define the parallelism boundaries.
- Define the final approval agent per chain type.

## Agent Dependency Graph
requirement-agent
    |
    v
architecture-agent
    |
    v
developer-agent <------------------+
    |                              |
    v                              v
testing-agent              security-agent
    |                              |
    +-------------+----------------+
                  |
                  v
        documentation-agent
                  |
                  v
          review-agent
                  |
                  v
          release-agent




Edges mean "depends on the prior step's output." The graph is acyclic.

## Who Runs First

- `requirement-agent` runs first for every ambiguous or new request.
- For a clear bug report, the orchestrator may skip the
  `requirement-agent` and go straight to triage via `bug-analysis`.
- For a clear refactor with an existing ADR, the orchestrator may skip the
  `architecture-agent`.

## Parallel Groups

- `testing-agent` and `security-agent` form the default parallel group after
  `developer-agent`.
- `documentation-agent` may start as soon as the public surface is stable.
- `release-agent` and `review-agent` must not run in parallel.

## Final Approval

- Normal feature or bug: `review-agent` is the final approval before merge.
- Release: `release-agent` is the final approval before promotion.
- Hotfix: the on-call rotation is the final approval, with `security-agent`
  sign-off when the surface is in scope.

## Chain Templates

### Feature Chain
requirement-agent
  -> architecture-agent
     -> developer-agent
        -> { testing-agent, security-agent }
           -> documentation-agent
              -> review-agent
                 -> release-agent



### Bug Chain
requirement-agent (triage via bug-analysis)
  -> developer-agent
     -> testing-agent
        -> review-agent
           -> release-agent


### Hotfix Chain
{ security-agent, developer-agent }   # parallel
  -> testing-agent
     -> review-agent (reduced gates)
        -> release-agent (emergency)



### Refactor Chain
architecture-agent
  -> developer-agent
     -> testing-agent
        -> review-agent
           -> release-agent


### Documentation Chain

### Release Chain


release-agent
  -> review-agent (release notes)


## Inputs

- The selected workflow from `workflow-selection.md`.
- The risk band from `risk-matrix.md`.
- The active project policy in `project-config.yaml`.

## Outputs

- A linearized chain with parallel groups.
- A final approval agent.
- A rollback boundary at the highest step reached.

## Examples

- `feature-development` + `moderate` -> Feature Chain, `review-agent`
  final.
- `bug-fix` + `elevated` -> Bug Chain, `review-agent` final, with
  `security-agent` added before `review-agent`.
- `hotfix` + `severe` -> Hotfix Chain, on-call final, with
  `security-agent` mandatory.
- `documentation` + `negligible` -> Documentation Chain, `review-agent`
  final.

## Best Practices

- Default to the smallest chain that satisfies the workflow. Add agents when
  the risk band or routing rules say to, not by default.
- Treat `documentation-agent` as a first-class agent, not as a follow-up.
- Final approval is always a human-readable verdict, not just a status flag.

## Reusable Rules

- Chain templates are templates. The orchestrator fills them in with the
  selected priority, risk band, and side effects.
- No agent is allowed to call. All another agent directly handoffs go
  through the orchestrator.

## Project Agnostic Design

- The graph and the templates use agent names only. No project or
  technology terms appear.
- New agents slot into the graph at the natural point in the dependency
  table; the orchestrator picks them up by name.