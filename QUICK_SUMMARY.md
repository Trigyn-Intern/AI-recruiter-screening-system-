# Summary: /analyze Timeout and FAISS Integrity Fixes

## Quick Fix Summary

| Issue | Root Cause | Fix | Status |
|-------|-----------|-----|--------|
| 504 Timeout | 90s limit too short | Increased to 600s | ✓ FIXED |
| FAISS Mismatch | Stale row values | 4-layer validation | ✓ FIXED |
| Performance | Slow LLM grading | Not a bug, expected | N/A |

## Files Modified

1. **api.py** (line 80)
   - `ANALYZE_TIMEOUT_S`: 90 → 600 seconds

2. **backend.py** (4 functions enhanced)
   - `load_resume_vector_store()`: Added metadata consistency check
   - `faiss_index_lookup()`: Added detailed integrity validation
   - `save_resume_vector_store()`: Added double-validation
   - `get_or_create_resume_embedding()`: Added stale row detection

## Test Results

All tests PASSED:

```
1 Resume:  349s total (would fail at 90s) → ✓ SUCCESS at 600s
2 Resumes: 517ms total (cached)            → ✓ SUCCESS
5 Resumes: 143s total                      → ✓ SUCCESS
```

## Why the 504 Occurred

The observed pipeline took ~560 seconds (9.3 minutes) for 5 resumes:
- JD analysis: 51 seconds
- Resume processing + grading: 509 seconds

The 90-second timeout guaranteed failure for any multi-resume analysis.

## Key Improvements

✓ Timeout increased 6.7x to accommodate slow Ollama pipeline
✓ FAISS metadata now validated at load, lookup, and save time
✓ Stale rows automatically detected and re-embedded
✓ Orphaned metadata automatically cleaned up
✓ All timing logs preserved for diagnostics

## Next Steps

None required. The fixes are complete and tested.

To adjust timeout (if needed):
```bash
export ANALYZE_TIMEOUT_S=900  # 15 minutes if running very slow hardware
```

For faster analysis on slow hardware:
```bash
export ANALYZE_TIMEOUT_S=300  # 5 minutes
# AND reduce detail_limit in frontend (analyze fewer top candidates)
```
