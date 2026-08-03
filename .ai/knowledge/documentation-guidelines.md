# Documentation Guidelines

Generic, reusable documentation standards. Apply the subset that matches the
project's `documentation.*` configuration.

## Audience First

- Identify the audience before writing. Reader, task, and context.
- A doc that tries to serve every audience serves none of them well.
- Prefer concrete examples over abstract explanations when explaining how.

## Levels of Documentation

- **Code-level** - Intent comments on public surfaces. No narration of the obvious.
- **Module-level** - A short README per module explaining purpose and ownership.
- **Project-level** - The root README. What it is, who it is for, how to run it.
- **Decision-level** - ADRs for non-obvious decisions (when
  `documentation.adr_required` is true).
- **API-level** - Generated or hand-written API references (when
  `documentation.api_docs_required` is true).

## READMEs

- Lead with the value, not the project history.
- Include quickstart, prerequisites, configuration, and how to get help.
- Keep command examples copy-pasteable. Tested examples beat realistic ones.
- Link to deeper docs instead of inlining them.

## Architecture Decision Records

- Title, status, context, decision, consequences. That is the minimum.
- Keep ADRs short. Long ones get unread; short ones get read.
- ADRs are immutable history. Supersede, do not edit.
- When in doubt, write the ADR. Future you will thank present you.

## API Documentation

- Document the contract, not the implementation.
- Cover happy path, error path, authentication, and rate limits.
- Examples should compile or run as written.
- Version the docs with the API.

## Diagrams

- Use the diagram format declared in `documentation.diagram_format`.
- One diagram, one idea. Do not overload a single picture.
- Keep diagrams close to the text that explains them.
- Diagrams are a snapshot. Date them or link to the source.

## Style

- Use clear, short sentences. Prefer the active voice.
- Define acronyms on first use. Avoid jargon when a plain word works.
- Use consistent terminology. Maintain a glossary for cross-cutting terms.
- Write in English by default unless the project is monolingual.

## Maintenance

- Documentation rot is real. Treat it as a defect, not a stylistic complaint.
- Review docs in the same review as code when both change.
- Archive obsolete docs deliberately. Do not just leave them behind.