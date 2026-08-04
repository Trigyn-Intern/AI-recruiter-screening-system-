---
name: technology-selection
version: 1.0.0
applies_to: any
---

# Decision Tree: Technology Selection (Project Detection)

Reusable rules for detecting the active technology stack from repository
signals. This file does not choose technology for the user; it observes what
is already there and surfaces it as context for the agents.

## Purpose

Tell the orchestrator "this is a React project", "this is a .NET project",
or "this is a polyglot project" based on repository signals, with zero hardcoded
project names.

## Responsibilities

- Observe repository signals.
- Map signals to a normalized stack profile.
- Surface the profile to agents so they can adapt their output.
- Refuse to make technology decisions for the user.

## Decision Rules

The orchestrator asks, in order:

1. **Are any of the following files or directories present?**
   - `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`
   - `angular.json`, `nx.json`, `lerna.json`
   - `tsconfig.json`, `vite.config.*`, `next.config.*`, `nuxt.config.*`
   - `requirements.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock`
   - `pom.xml`, `build.gradle*`, `settings.gradle*`
   - `*.csproj`, `*.sln`, `*.fsproj`
   - `spfx` config indicators (SPFx manifests, gulpfile, `.yo-rc.json`
     with `@microsoft/sharepoint` generator id)
   - `go.mod`, `Cargo.toml`, `composer.json`, `Gemfile`
2. **Map the strongest signal to a normalized profile.**
   - The mapping table is below. It is keyed by signal, not by project name.
3. **If multiple signals are present, mark the profile as `polyglot` and list
   each detected profile.**
4. **If no signal is present, mark the profile as `unknown` and route to
   `requirement-agent` to confirm.**

## Inputs

- A read-only view of the repository root.
- The active project policy in `project-config.yaml`.

## Outputs

- A `stack_profile` object with:
  - `primary`: the dominant profile, or `unknown`.
  - `secondary`: any additional profiles.
  - `signals`: the list of files that triggered the profile.
  - `confidence`: `high`, `medium`, or `low`.

## Signal Map

| Signal(s) | Normalized Profile |
| --- | --- |
| `package.json` with `react` dependency | `frontend-react` |
| `package.json` with `@angular/core` dependency | `frontend-angular` |
| `package.json` with `vue` dependency | `frontend-vue` |
| `package.json` with `next` dependency | `frontend-next` |
| `package.json` with express/fastify/nest | `backend-node` |
| `pyproject.toml` or `requirements.txt` with fastapi | `backend-python-fastapi` |
| `pyproject.toml` or `requirements.txt` with django/flask | `backend-python` |
| `pom.xml` or `build.gradle*` with spring-boot | `backend-java-spring` |
| `pom.xml` or `build.gradle*` without spring-boot | `backend-java` |
| `*.csproj` with aspnet/webapi/mvc references | `backend-dotnet-web` |
| `*.csproj` without web references | `backend-dotnet` |
| SPFx manifests or `@microsoft/sharepoint` generator | `frontend-spfx` |

The `Normalized Profile` is a token, not a project name. Agents read the
profile to adapt their output, but they never see a literal project name.

## Examples

- Repo has `package.json` with `react` and `tsconfig.json` ->
  `primary=frontend-react, confidence=high`.
- Repo has `pom.xml` with `spring-boot-starter-web` and `package.json` with
  `react` -> `primary=backend-java-spring,
  secondary=frontend-react, polyglot=true`.
- Repo has `*.csproj` only -> `primary=backend-dotnet,
  confidence=medium`.
- Empty repo or no recognized signal -> `primary=unknown,
  confidence=low`. Route to `requirement-agent`.

## Best Practices

- Never hardcode a project name in the orchestrator. Use the normalized
  profile.
- When a signal is ambiguous, prefer the more specific profile
  (`backend-python-fastapi` over `backend-python`).
- Treat the profile as advisory context for agents, not as a constraint.
- Re-run detection on every new branch, not just once per repo.

## Reusable Rules

- The signal map is the only place where tokens are defined. Add new entries
  here when a new stack needs to be recognized.
- Profiles are never embedded in agent or skill files.
- Detection is read-only. It never modifies the repository.

## Project Agnostic Design

- The orchestrator never prints a project name. It prints a profile token.
- A "new project" is a repo with no recognized signal. The orchestrator routes
  it to `requirement-agent` to confirm the intended stack.