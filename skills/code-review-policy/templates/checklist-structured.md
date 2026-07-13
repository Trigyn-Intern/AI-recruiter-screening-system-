# Code Review Checklist

*This document serves as a guide for software developers to ensure quality, security, maintainability, and performance of code being reviewed before merging or releasing. Use this checklist as a systematic approach during the code review process.*

## Reviewer Information

- **Project Name:** {projectName}
- **Repository/Branch:** {repositoryBranch}
- **Reviewer:** {reviewerName}
- **Date of Review:** {reviewDate}

## General Checklist

{#generalChecklist}
- **{item}:** {comment}
{/generalChecklist}

## Code Quality

| Check | Status | Notes |
|---|---|---|
{#codeQuality}{checkItem} | {status} | {notes}{/codeQuality}

## Security Review

{#hasSecuritySection}

### Vulnerability Check

| Check | Status | Comments |
|---|---|---|
{#securityChecks}{checkItem} | {status} | {comments}{/securityChecks}

{/hasSecuritySection}

{^hasSecuritySection}

**No security-specific checks were included in this review.**

{/hasSecuritySection}

## Performance Checks

{#performanceChecks}
- **{title}:** {details}
{/performanceChecks}

## Style and Best Practices

{#stylePractices}
- **{practice}:** {issuesFound}
{/stylePractices}

## Test Coverage

- **Are tests present?** {hasTests}
- **Test Coverage % (approx):** {coveragePercent}
- **Manual Tests Needed:** {manualTestNotes}

## Additional Reviewers Feedback

{#reviewerFeedbacks}
- **{reviewerName}:** {comment}
{/reviewerFeedbacks}

## Final Notes

{finalNotes}

## Approval

- **Approved by:** {approvedBy}
- **Date of Approval:** {approvalDate}
- **Merge Status:** {mergeStatus}
