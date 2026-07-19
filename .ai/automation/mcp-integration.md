---
name: mcp-integration
version: 1.0.0
applies_to: any
---

# MCP Integration

Defines how the AI framework integrates with Model Context Protocol (MCP)
servers and similar integration layers. The framework describes the
expectations; the project configures the actual servers.

## Purpose

Make integrations explicit and safe. The framework's AI agents and
automation layers should be able to read repository context, issue
tracker context, documentation context, and file system context through
a well-defined contract.

## Responsibilities

- Define the integration categories the framework supports.
- Define the data flow per category.
- Define the authentication and authorization expectations.
- Define the security and privacy expectations.
- Define the failure and rate-limit expectations.

## Inputs

- The integration category (repository, issue tracker, knowledge base,
  file system, etc.).
- `project-config.yaml` for integration enablement and policy.
- The platform's MCP server configuration (declared outside the
  framework).

## Outputs

- A contract per integration category.
- A security and privacy checklist per integration.

## Integration Categories

| Category | Purpose | Examples |
| --- | --- | --- |
| `repository` | Read repository context | file contents, blame, history, branch state |
| `issue-tracker` | Read and write issue context | issues, comments, status, assignments |
| `documentation` | Read documentation context | wiki pages, ADRs, runbooks |
| `knowledge-base` | Read structured knowledge | search, retrieval, embeddings |
| `file-system` | Read file system context | project files, attachments, exports |
| `messaging` | Send notifications | channels, DMs, mentions |
| `identity` | Resolve identity and access | users, groups, roles, on-call |

The framework does not own the servers. It owns the contract the
servers must satisfy.

## Data Flow

The standard data flow is:

1. **Authenticate.** The integration authenticates using the project's
   declared mechanism. The framework does not store credentials.
2. **Authorize.** The integration checks the agent's or user's scope
   against the resource. Least privilege applies.
3. **Request.** The integration issues a request in the category's
   standard shape.
4. **Respond.** The integration returns a normalized response. Errors
   follow the standard error shape.
5. **Audit.** The integration records the request and the response
   summary for audit.

## Authentication Considerations

- Use the platform's identity provider. Do not invent a parallel auth
  layer.
- Use short-lived tokens. Long-lived tokens are a risk.
- Scope tokens to the minimum required for the integration.
- Rotate on suspicion of exposure, not on a fixed schedule alone.
- Never embed tokens in the AI framework's files. Tokens are
  configuration of the platform, not of the framework.

## Authorization Considerations

- The integration respects the project's existing access control. It
  does not bypass it.
- The integration's agent identity is distinct from the user's
  identity. Actions taken by an agent are attributed to the agent and
  the user on whose behalf the agent acts.
- Write operations require explicit user confirmation when the
  project's policy requires it.

## Security Considerations

- All requests and responses are encrypted in transit.
- Sensitive payloads are redacted in logs and audit records.
- The integration never echoes secrets, tokens, or PII into the AI
  framework's prompt context.
- The integration's blast radius is bounded by the token's scope.

## Privacy Considerations

- PII is treated as a sensitive class per
  `.ai/knowledge/security-guidelines.md`.
- The integration supports data minimization. The agent asks for the
  minimum data needed for the task.
- The integration supports retention controls. The agent and the
  project define the retention period for the data the integration
  returns.

## Rate Limits and Failure

- The integration respects the upstream's rate limits. It backs off and
  retries per the platform's policy.
- A rate-limited request is surfaced to the agent and the user. The
  agent does not silently retry forever.
- A failed authentication is escalated. The agent does not attempt to
  recover by trying other credentials.
- A failed authorization is surfaced as a permission error, not as a
  generic failure.

## Execution Flow

1. **Resolve integration.** The orchestrator resolves the integration
   by category from the project's MCP configuration.
2. **Authenticate.** The integration authenticates using the
   configured mechanism.
3. **Check scope.** The integration confirms the agent has the
   required scope for the action.
4. **Request.** The integration issues the request.
5. **Normalize.** The integration normalizes the response to the
   framework's standard shape.
6. **Audit.** The integration records the action.
7. **Return.** The integration returns the normalized response to the
   orchestrator.

## Best Practices

- Prefer read-only integrations by default. Add write access only when
  the workflow requires it.
- Use the smallest scope that satisfies the workflow. Broader scope is
  broader risk.
- Pin integration versions. Floating versions are a supply-chain risk.
- Document the data the integration returns. The agent and the user
  need to know what they are getting.

## Reusable Enterprise Guidelines

- Integrations are part of the audit trail. Every action is recorded.
- Integrations are reviewed. Adding a new integration is a change that
  requires the same review as a code change.
- Integrations are tested. A contract test ensures the integration
  still satisfies the framework's expectations.

## Project Agnostic Design

- Categories are tokens. The platform resolves them to the project's
  actual integrations.
- The contract is described in terms of capabilities, not vendor
  names.