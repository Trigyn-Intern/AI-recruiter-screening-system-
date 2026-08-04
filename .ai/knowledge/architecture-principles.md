# Architecture Principles

Generic, reusable architectural guidance. Adopt the subset that fits the project's
size, lifecycle, and `project-config.yaml` settings.

## Core Principles

- **Clean architecture** - Separate policy (business rules) from mechanism
  (frameworks, drivers) and from presentation (UI, API surface).
- **Stable abstractions** - Depend on the things that change least.
- **Bounded contexts** - Model each domain boundary with its own language and
  ownership.
- **Explicit contracts** - Every public interface is intentional, versioned, and
  documented.
- **Reversibility** - Prefer decisions that keep future options open.

## Modularity

- Modules own their data. Avoid shared mutable state across boundaries.
- Public surfaces are small and intent-revealing. Hide implementation details.
- Cycle-free dependency graphs. Refactor when cycles appear.
- Cohesion high, coupling low. If two modules always change together, consider
  merging them; if they never do, separate them.

## Data and Persistence

- Match the persistence model to the read and write patterns.
- Treat schema changes as migrations: versioned, reversible, and tested.
- Avoid leaking persistence concerns into business logic.
- Capture data ownership and retention up front, not after release.

## Communication

- Choose the simplest integration style that meets the consistency needs.
- Async messaging adds scalability and complexity. Use it on purpose.
- Synchronous calls across services need timeouts, retries, and circuit breakers.
- Document contracts and failure modes for every external dependency.

## Resilience and Operability

- Design for failure. Every external call can fail; plan the response.
- Health checks must be meaningful. Liveness vs. readiness are different.
- Observability is a feature: structured logs, metrics, traces from day one.
- Configuration is externalized. Code is the same across environments.

## Security in Architecture

- Threat-model before building. Revisit on every structural change.
- Identity propagates through the system; authorization is checked at boundaries.
- Blast radius is bounded by design (cells, tenants, regions, queues).
- Secrets never live in code or shared config.

## Evolution

- Prefer evolvable designs over speculative flexibility (YAGNI).
- Use ADRs (see `documentation-guidelines.md`) to record why a decision was made.
- Refactor toward the design you need when the cost of change is lower than the
  cost of staying put.
- Deprecate deliberately. Document, communicate, and remove on a plan.

## Trade-offs

- Document trade-offs explicitly. Every architecture decision forecloses others.
- Optimize for the bottleneck, not for the average case.
- A clear, simple design that ships beats a clever, perfect one that does not.