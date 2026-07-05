---
name: security-review
description: LLM-driven security review of the AI Recruiter Screening System. Covers Express auth, prompt safety, committed secrets, frontend input handling, and PII in test fixtures. Runs as one combined review or one mode at a time.
modes: [all, auth-review, llm-prompt-safety, secrets-hygiene, frontend-input, test-data-pii]
default_mode: all
safe_mode_reviews: [secrets-hygiene, test-data-pii]
execution: model-reads-markdown
---

# security-review

This skill is a prompt manifest. There is no CLI command, no runner, no registry, and no Docker image. The model reads this file, follows the checklist for the selected mode, and returns findings.

## Invocation

- `run security-review` -> runs all five reviews
- `run security-review mode=<name>` -> runs only that review
- If no mode is specified, `all` is used

Valid modes: `all`, `auth-review`, `llm-prompt-safety`, `secrets-hygiene`, `frontend-input`, `test-data-pii`.

## How to use this manifest

1. Read the **Scope** section for the selected mode to know which files to inspect.
2. For each file in scope, read the full content. Do not rely on diffs alone.
3. Walk the **Checklist** for the mode. For each item, decide: present, absent, or needs verification.
4. Format findings using the **Output format** section.
5. Apply the **Safe mode rules** if the mode is `secrets-hygiene` or `test-data-pii`.
6. End every report with the **Verify before acting** footer.

## Output format (all modes)

For each review, return:

### Scope
A bullet list of files inspected.

### Findings
A bullet list. Each finding uses this shape:

- **[Severity] Category** — `path/to/file.js:lineRange`
  - Issue: one sentence describing what is wrong.
  - Suggested fix: one or two sentences describing how to address it.

Severity is one of: `High`, `Medium`, `Low`.

If no findings, return `No findings.` under this heading.

### Verify before acting
Always include the standard footer (see end of file).

---

## Mode: auth-review

### Scope
- `backend/server.js`
- `backend/controllers/authController.js`
- `backend/middleware/requireAuth.js`
- `backend/middleware/validate.js`
- `backend/routes/authRoutes.js`

### Checklist
- **JWT validation** — `jsonwebtoken.verify` is called with a strong secret from env, the algorithm is explicitly pinned (e.g. `algorithms: ["HS256"]`), and expiry is enforced.
- **JWT secret strength** — the secret read from `process.env.JWT_SECRET` (or equivalent) is at least 32 bytes of entropy, not a default or placeholder value.
- **Password hashing** — `bcrypt`/`bcryptjs` is used with a cost factor of at least 10, and comparisons are constant-time.
- **Rate limiting** — `/login` and `/register` are protected by a rate limiter (e.g. `express-rate-limit`) to slow credential stuffing.
- **Input validation** — registration and login payloads are validated for shape, length, and type before reaching the controller logic.
- **Error leakage** — error responses do not include stack traces, Mongo/Mongoose internals, or `err.message` from unexpected exceptions.
- **CORS** — `cors()` is configured with an explicit origin allowlist, not a wildcard, when credentials are involved.
- **Auth middleware** — `requireAuth` correctly rejects missing, malformed, and expired tokens, and the user lookup is bounded.
- **Logging** — passwords, tokens, and full request bodies are not logged.
- **Cookie flags** — if cookies hold the JWT, `httpOnly`, `secure`, and `sameSite` are set.

---

## Mode: llm-prompt-safety

### Scope
- `api.py`
- `backend.py`
- `backend/server.js`
- `vector_store/prompt_config.json`
- `vector_store/resume_metadata.json`
- `vector_store/resume_skills.json`
- `frontend/src/defaultPrompts.js`

### Checklist
- **Prompt construction** — user-supplied text (resumes, JDs) is concatenated into prompts without escaping or length capping.
- **Length cap** — incoming resume and JD text is truncated to a safe maximum before being included in any prompt.
- **Schema validation** — model output is validated against a strict JSON schema before being returned to the client; unexpected fields are stripped.
- **Output rendering** — model output rendered in React goes through safe rendering (no `dangerouslySetInnerHTML`, no `eval`, no `new Function`).
- **System prompt integrity** — the system prompt is not derivable from user input and does not include instructions that can be overridden by user content.
- **External content fetch** — if any prompt includes fetched web content, that content is treated as untrusted and isolated.
- **Vector store injection** — content stored in `vector_store/` is treated as untrusted when retrieved and injected into prompts; no execution or eval of stored strings.
- **Sensitive data in prompts** — PII from resumes is not echoed back to the client in raw form; the response surface is reduced to the fields the UI actually needs.

---

## Mode: secrets-hygiene (safe mode)

### Scope
- `backend/.env`
- `frontend/.env`
- `backend/server.js`
- `backend/config/db.js`
- `backend/controllers/authController.js`
- `.gitignore` (to confirm `.env` is ignored locally, even if previously committed)

### Checklist
- **Committed .env files** — `backend/.env` and `frontend/.env` are tracked by git. They should be in `.gitignore` and removed from the index.
- **Hardcoded secrets in source** — any string that looks like a JWT secret, DB URI, API key, or password is read from env, not hardcoded.
- **Weak JWT secret** — the value behind `JWT_SECRET` is not empty, not a default like `"secret"`, and has sufficient entropy.
- **Database credentials** — MongoDB connection string uses a dedicated user with least-privilege access, not `root` or admin.
- **Secret rotation guidance** — once a secret has been committed to history, rotation is recommended even after `git rm --cached`.

### Safe mode rules
This mode never echoes the actual secret value. For every finding, output only:

- File path
- Line range
- Category (e.g. `committed-env`, `hardcoded-secret`, `weak-secret`, `db-credentials`)
- One-sentence description of the issue
- Suggested fix

Do not quote the secret, the env file contents, or any substring that could reconstruct the value.

---

## Mode: frontend-input

### Scope
- `frontend/src/App.jsx`
- `frontend/src/main.jsx`
- `frontend/src/defaultModels.js`
- `frontend/src/defaultPrompts.js`
- `frontend/index.html`
- `frontend/package.json`

### Checklist
- **Dangerous HTML** — no use of `dangerouslySetInnerHTML` without sanitization (e.g. DOMPurify).
- **Code execution sinks** — no use of `eval`, `new Function`, or `setTimeout`/`setInterval` with string arguments.
- **URL handling** — user-supplied URLs are validated against an allowlist or parsed safely before use in `href` or `src`.
- **External links** — links to external origins include `rel="noopener noreferrer"` and `target="_blank"` is intentional.
- **File uploads** — if the app accepts uploads, file type and size are validated server-side, not just client-side.
- **Dependency pinning** — `frontend/package.json` pins exact versions or uses caret/tilde ranges, not bare `"latest"`. Bare `latest` is a supply-chain risk.
- **Third-party scripts** — `index.html` does not load third-party scripts from untrusted CDNs without Subresource Integrity (`integrity=` and `crossorigin=`).
- **XSS surface** — user-controlled strings rendered as text rely on React''s default escaping; do not bypass it with raw HTML.

---

## Mode: test-data-pii (safe mode)

### Scope
- `tests/data/resumes/*.pdf` (text only, do not attempt to render or modify)
- `tests/data/jds/*.txt`
- `tests/data/scenarios.yaml`
- Any fixture under `tests/data/`

### Checklist
- **Real-looking names** — names that look like real people, not obviously synthetic test names.
- **Email addresses** — any string matching a common email pattern.
- **Phone numbers** — digit sequences that match phone formats.
- **Postal addresses** — street addresses, postal codes, city/state combinations that look real.
- **Government IDs** — Social Security numbers, national IDs, passport numbers, driver''s license numbers.
- **Financial data** — credit card numbers, bank account numbers, IBANs.
- **Employment data that could identify a real person** — specific employer names combined with titles and dates that match publicly known employment.

### Safe mode rules
This mode never echoes the actual PII value. For every finding, output only:

- File path
- Approximate line range or region
- Category (e.g. `name`, `email`, `phone`, `address`, `gov-id`, `financial`)
- One-sentence description
- Suggested fix (typically: replace with a clearly synthetic value, or move out of the repo)

Do not quote the PII, the resume text, or any substring that could reconstruct the personal data.

---

## Verify before acting

This skill produces hints to investigate, not verified vulnerabilities. Before acting on any finding:

1. Open the cited file and line. Confirm the issue exists as described.
2. Check whether the issue is reachable in the deployed app, not just in source.
3. Test the suggested fix in a non-production environment.
4. For safe-mode findings, manually inspect the file at the cited location before making changes.


---

## Report output

When invoked, this skill MUST also produce a structured HTML report, in addition to the chat findings. The report lives at `skills/reports/` and is the durable artifact of the run. Chat output is the human-friendly summary; the HTML is the machine- and review-friendly record.

### Where the files go

- Per-run report: `skills/reports/security-review-<mode>-<YYYY-MM-DD>.html`
  - `mode` is the mode flag value, lowercased (e.g. `all`, `auth-review`, `secrets-hygiene`).
  - For `all`, the per-run report covers every mode in one file.
- Index: `skills/reports/index.html` is regenerated on every run and lists all reports newest-first.

The skill must create `skills/reports/` if it does not exist.

### Report structure

Each finding becomes one `<article class="test-case">` block. Every block has these fields, in this order:

1. **Test case name** — `<h2>` inside the article. Format: `<mode> / <short-slug>`. Example: `auth-review / jwt-algorithm-not-pinned`.
2. **Description** — `<p class="description">`. One sentence. What the test was checking.
3. **Prerequisites** — `<section class="prereqs">`. Bulleted list. Files inspected, env assumptions, mode flags.
4. **Test steps** — `<section class="steps">`. Numbered list. The exact actions the LLM took to find the issue.
5. **Input data** — `<section class="input">`. The cited code (or a redacted placeholder for safe-mode reviews). Wrap in `<pre><code>`. Use `<code class="redacted">[REDACTED: high-entropy hex string]</code>` for safe-mode values.
6. **Expected result** — `<section class="expected">`. What a secure version would look like.
7. **Actual result** — `<section class="actual">`. What the code actually does.
8. **Status** — `<span class="status pass|fail|warning">`. One of:
   - `pass` — the checklist item was verified clean.
   - `fail` — a real issue was found.
   - `warning` — needs human review (LLM was not sure).
9. **Enhancement notes** — `<section class="notes">`. The suggested fix, expanded into a short paragraph.
10. **Codex prompt suggestion** — `<section class="codex-prompt">` containing a `<pre><code>` block. A copy-paste prompt the user can run in a fresh Codex chat to act on this one finding. The prompt must reference the file:line and the exact change requested.

### Report header

Above all `<article>` blocks, the HTML must include:

- Title: `security-review — <mode> — <YYYY-MM-DD>`
- Run metadata: timestamp (ISO 8601), mode(s), files in scope (list).
- Summary table: counts of `pass`, `fail`, `warning` (and a row for total findings).

### Safe-mode HTML rules

For `secrets-hygiene` and `test-data-pii` findings, the HTML must obey the same safe rules as the chat output:

- Quote only the file path, line range, and category.
- Never echo the actual secret value or PII.
- In the **Input data** field, render `<code class="redacted">[REDACTED: <category>]</code>` instead of the value.
- The **Codex prompt suggestion** for a safe-mode finding must instruct the user to open the file manually, not the model.

### Style

Inline CSS in a `<style>` block at the top of the file. Light theme, no external assets, no JavaScript. The page must render correctly when opened directly from the filesystem in a browser, with no network access required.

### Template

A reference template lives at `skills/reports/_template.html`. The skill must use it as the starting point for every per-run report and regenerate `skills/reports/index.html` from the list of files in the directory.

### Regeneration

The skill must NOT delete or modify historical reports. Each run adds a new timestamped file and rewrites `index.html` only.

