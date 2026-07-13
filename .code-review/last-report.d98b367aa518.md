# Code Review Report (mode=changed-files)

## Executive Summary

Reviewed the 1 changed file in this push: `.githooks/pre-push`. The file is a 199-line bash script that gates `git push` on a fresh AI code review. The implementation is sound: it computes a sha256 of the diff, archives stale reports, validates the verdict line, and provides a clear `AI_SKIP_PRE_PUSH=1` override. No High issues. Two Medium suggestions: tighten the diff-hash capture (the current `git diff --name-only` includes only file names, not the change content, so two pushes that touch different parts of the same file would have identical hashes and the freshness check would be bypassed) and document the bash-only constraint explicitly. Code Quality Summary: **Good**.

## Files Reviewed

- `.githooks/pre-push` (199 lines, bash, executable)

## High Priority Issues

None.

## Medium Priority Issues

- **[Medium] Maintainability** - `.githooks/pre-push:71-78` (diff hash computation)
  - Explanation: The hook computes the diff hash from `git diff --name-only "$REMOTE_BRANCH"..HEAD`. This is a list of file paths, not the file contents. Two pushes that touch the same set of files but with different content (e.g. reverting a previous change) would have identical hashes and the freshness check would let the old report through.
  - Why it matters: The whole point of the freshness contract is to guarantee the report was generated against the actual code that is about to be pushed. A path-only hash weakens that guarantee.
  - Recommended fix: Use `git diff "$REMOTE_BRANCH"..HEAD` (no `--name-only`) and pipe the full diff through `sha256sum`. That captures the content of every changed line.

- **[Medium] Documentation** - `.githooks/pre-push` (whole file, especially lines 19-30)
  - Explanation: The hook assumes bash is on `PATH`. On Windows, that means WSL, Git for Windows's bash, or a Unix-like shell. The existing pre-commit hook has the same constraint but documents it inline. The pre-push hook does not.
  - Why it matters: A developer who runs `git push` from PowerShell directly (not from the venv-activated PowerShell) might see a "bash not found" error and assume the hook is broken.
  - Recommended fix: Add a one-line comment at the top of the file clarifying that the hook is bash and that Git for Windows ships with bash at `C:\Program Files\Git\bin\bash.exe`. Reference the existing pre-commit hook's wording for consistency.

- **[Medium] Project Compliance** - `.githooks/pre-push:144-155` (verdict parsing)
  - Explanation: The verdict is parsed with `grep -E "^VERDICT:" | tail -n 1 | sed ...`. If the LLM's report contains a multi-line "VERDICT" string (e.g. a code block in the body that includes `VERDICT: Request Changes` as a counter-example), the `tail -n 1` step would still pick the last one, which is correct, but only by accident. There is no validation that exactly one `VERDICT:` line exists.
  - Why it matters: A future LLM that produces a chatty review with multiple `VERDICT:` mentions in the body could pass the gate on the wrong line.
  - Recommended fix: Count `VERDICT:` lines. If zero, fail (already done). If more than one, fail with a clear message and ask the LLM to produce a single verdict on the last line. Use `grep -c "^VERDICT:"` to count.

## Low Priority Suggestions

- **[Low] Code Quality** - `.githooks/pre-push:1-17` (shebang and header)
  - Explanation: The header comment block is well-structured but does not mention what happens when `git push --force-with-lease` or `git push --no-verify` is used. `--no-verify` bypasses pre-push entirely, which is the developer's escape hatch; the hook should call this out.
  - Why it matters: A future reader might think the hook is always running.
  - Recommended fix: Add one sentence: "Developers can bypass the hook with `git push --no-verify`, which is appropriate for emergencies but skips the AI review."

- **[Low] Code Quality** - `.githooks/pre-push:33` (file count)
  - Explanation: `FILE_COUNT=$(printf "%s\n" "$CHANGED" | wc -l | tr -d ' ')`. The `tr -d ' '` is defensive against `wc -l` adding leading whitespace, but on every modern `wc` implementation the output is already clean. The command is slightly noisier than it needs to be.
  - Why it matters: Cosmetic. Not a real issue.
  - Recommended fix: Drop `| tr -d ' '`. Keep `wc -l` only.

- **[Low] Maintainability** - `.githooks/pre-push:130-141` (file list truncation)
  - Explanation: The truncation loop shows the first 25 files. Beyond that, it prints `"... and N more"`. The variable `i` is incremented in a subshell, so the value is lost between iterations of the loop. The current code works because `i` is read inside the same subshell that increments it, but a future maintainer refactoring this to a function might be surprised.
  - Why it matters: A subtle shell-scripting footgun. The current code happens to be correct.
  - Recommended fix: Either keep it as-is with a comment explaining the subshell pattern, or use `awk`/`head -n 25` for the truncation and `wc -l` for the count.

- **[Low] Error Handling** - `.githooks/pre-push:170-180` (archive move)
  - Explanation: When a stale report is archived, the move uses `mv "$REPORT" "$ARCHIVE"`. If `last-report.<oldhash>.md` already exists (e.g. from a previous push with the same diff), `mv` overwrites it silently on most systems.
  - Why it matters: A rare edge case, but a real one if the developer pushes, then amends a commit, then pushes again. The archive is lost.
  - Recommended fix: Add `-n` to `mv` to refuse overwriting, or check for existence and append a counter (`-1`, `-2`, ...) to the archive name.

## Best Practice Recommendations

- The freshness contract is the right idea. The path-only hash is the one thing that keeps it from being bulletproof; switch to full-diff hashing and the gate is genuinely hard to bypass without `--no-verify`.
- The verdict rule is GitHub-style and clean. Adding a `grep -c` count to reject multi-`VERDICT:` reports is a small but worthwhile hardening.
- The `AI_SKIP_PRE_PUSH=1` override is the right escape hatch. Documenting `git push --no-verify` in the same place makes the escape surface discoverable.
- Consider adding a third override for "I already have a valid report from a teammate" that copies an existing report into the local `.code-review/` and trusts the hash. Useful for pair-review workflows.
- The hook's banner is informative. A future improvement would be a short "what to do next" line that points the developer at the right `invoke.txt` path with a one-line summary.

## Items Needing Manual Verification

- The verdict parsing was tested with the prior push's `Approve` line. A real-world test of `Request Changes` is worth doing once (any commit on a feature branch with a fresh report containing that verdict).
- The `--no-verify` bypass is the documented escape hatch. Confirm that the developer's Git config does not have `push.hooks = false` or similar global overrides that would also skip the hook.
- The hook is `bash`. On a fresh Windows install without Git for Windows, the hook would fail to run. The previous push worked because the developer has Git for Windows installed; new contributors may not.

## Code Quality Summary

Good

## Verdict

Approve with Suggestions

VERDICT: Approve with Suggestions
