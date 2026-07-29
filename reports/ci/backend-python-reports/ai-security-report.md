# Security Report

## Required Controls

- Validate file type, size, and parser errors for every upload.
- Keep JWT signing material and AI-provider credentials only in environment variables.
- Treat resume text and job descriptions as untrusted prompt input.
- Prevent candidate PII from appearing in reports, logs, or external LLM requests without approval.
- Run Bandit and dependency scans before pull-request approval.
