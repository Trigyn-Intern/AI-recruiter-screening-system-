# The Complete Code Review Checklist

Use this checklist as a systematic pass during code review. Tick each box, leave a one-line note for anything unchecked, and link to a follow-up issue if the fix is out of scope for this PR.

## 1. Correctness

- [ ] Does the code do what the PR description says it does?
- [ ] Are edge cases handled? (empty input, null values, boundary conditions)
- [ ] Does it handle errors gracefully - or does it silently fail?
- [ ] Are there any obvious off-by-one errors in loops or array indexing?
- [ ] Does concurrency introduce race conditions or deadlocks?
- [ ] Are database transactions used correctly? (no partial writes)
- [ ] Is business logic correct, not just technically working?

**Red flag patterns to check:**

- `catch(e) {}` - swallowed exceptions
- Unchecked array access without bounds validation
- Missing `await` on async calls

## 2. Security

- [ ] Is user input validated and sanitized before use?
- [ ] Are SQL queries parameterized? (no string concatenation with user data)
- [ ] Are secrets or credentials hardcoded anywhere? (API keys, passwords)
- [ ] Is authentication checked before accessing protected resources?
- [ ] Is authorization enforced - not just "is the user logged in?" but "can this user do this?"
- [ ] Are file paths validated to prevent path traversal attacks?
- [ ] Is sensitive data (passwords, tokens, PII) logged anywhere?
- [ ] Are dependencies introduced by this PR known-good? (no obviously suspicious packages)

**Tool to use:** DevPlaybook AI Code Review - paste your diff and get automated security analysis before human review.

## 3. Performance

- [ ] Are there N+1 query patterns? (loop that triggers a database query each iteration)
- [ ] Are expensive operations cached where appropriate?
- [ ] Does the code handle large inputs without memory issues?
- [ ] Are there unnecessary re-renders or re-computations? (frontend)
- [ ] Is pagination used for list endpoints that could return large datasets?
- [ ] Are database indexes used for the queries this code will run?

**Performance issues in code review are often subtle. The most common culprit: a loop that queries the database on every iteration.**

```python
# Bad: N+1 queries
for user_id in user_ids:
    user = db.query(User).filter(User.id == user_id).first()  # 1 query per iteration
    send_email(user)

# Good: single query
users = db.query(User).filter(User.id.in_(user_ids)).all()
for user in user:
    send_email(user)
```

## 4. Testing

- [ ] Are there tests for the new behavior?
- [ ] Do existing tests still pass? (check CI results)
- [ ] Are edge cases tested, not just the happy path?
- [ ] Are tests testing behavior, not implementation? (do not break if internals change)
- [ ] Is test data realistic? (tests that only pass with id = 1 may fail in production)
- [ ] Is there a test for the bug that was fixed? (regression test)

**A useful heuristic:** if the PR description says "fix X bug," there should be a test that would have caught the bug before the fix.

## 5. Readability and Maintainability

- [ ] Is the code readable by someone unfamiliar with this part of the codebase?
- [ ] Are function and variable names descriptive?
- [ ] Are complex sections explained with comments - not what the code does, but why?
- [ ] Is the code DRY - or is repetition justified?
- [ ] Are magic numbers replaced with named constants?
- [ ] Is the function doing one thing? (single responsibility)
- [ ] Is the diff focused? (unrelated changes mixed in?)

**Code diff tool:** Use DevPlaybook Code Diff to compare before/after versions of changed files when reviewing locally.

## 6. API and Interface Design

- [ ] Does the public API surface make sense? (naming, parameter order, return types)
- [ ] Are breaking changes documented?
- [ ] Is the API consistent with similar patterns in the codebase?
- [ ] Are deprecated functions or parameters flagged?
- [ ] Is the feature flag or rollout strategy defined for risky changes?
