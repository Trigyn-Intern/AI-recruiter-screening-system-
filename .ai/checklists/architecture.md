# Architecture Checklist

Apply during any architecture review or design pass. Every item must be answered.

## Structure

- [ ] Module / service boundaries are explicit and documented.
- [ ] Public interfaces are small, versioned, and intentional.
- [ ] Dependency graph is acyclic.
- [ ] Cohesion is high within each module; coupling is low between modules.
- [ ] Shared mutable state across boundaries is avoided.

## Data

- [ ] Data ownership and retention are defined.
- [ ] Schema changes are treated as versioned migrations.
- [ ] Persistence concerns do not leak into business logic.

## Communication

- [ ] Integration style fits the consistency needs.
- [ ] Cross-service calls have timeouts, retries, and circuit breakers when async.
- [ ] Contracts and failure modes are documented for every external dependency.

## Resilience

- [ ] Failure modes for every external call are defined.
- [ ] Health checks distinguish liveness from readiness.
- [ ] Observability (logs, metrics, traces) is planned, not bolted on.
- [ ] Configuration is externalized; code is identical across environments.

## Security

- [ ] Threat model exists or is acknowledged as not required.
- [ ] Identity and authorization are checked at every boundary.
- [ ] Secrets are managed outside source code.
- [ ] Blast radius is bounded by design.

## Evolution

- [ ] ADRs exist for non-obvious decisions (when `documentation.adr_required`).
- [ ] Deprecations are planned, not silent.
- [ ] Speculative flexibility is rejected (YAGNI) where it adds cost.