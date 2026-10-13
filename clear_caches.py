"""Clear AI analysis caches for fresh benchmark testing."""

import sys

sys.path.insert(0, ".")

# Clear the JD analysis cache
import backend

backend._JD_ANALYSIS_CACHE.clear()
print("✓ Cleared _JD_ANALYSIS_CACHE")

# Clear the in-memory AI analysis cache
backend.RUNTIME_STATE["ai_analysis_cache"] = {}
print("✓ Cleared ai_analysis_cache")

print("\nCaches cleared successfully for fresh benchmark.")
