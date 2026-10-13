# Gemini Integration Investigation Report

## Investigation Summary

The AI Recruiter Screening System is experiencing 404 NOT_FOUND errors when attempting to use the `gemini-2.5-flash` model, causing the application to fall back to local grading instead of using Gemini AI.

## CONFIRMED FACTS

### 1. Gemini Package/Library Configuration
- **Package**: `google-genai` version 2.17.0 (installed)
- **Import**: `from google import genai` (both api.py and backend.py)
- **SDK Type**: Newer `google-genai` SDK (not legacy `google-generativeai`)

### 2. API Configuration
- **SDK Usage**: `genai.Client()` with `client.models.generate_content()`
- **REST API**: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
- **API Version**: v1beta (current)

### 3. Model Configuration
- **Default Model**: `gemini-2.5-flash` (configured in multiple locations)
- **Backend constant**: `GEMINI_RESUME_SKILL_MODEL = "gemini-2.5-flash"` (backend.py line 57)
- **Frontend default**: First element of `defaultGeminiModels` array (defaultModels.js line 25)
- **Model options list**: Includes gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.5-pro, gemini-3.5-flash, etc. (backend.py lines 93-101)

### 4. API Key Status
- **API Key**: Valid and properly configured in backend/.env
- **Key Length**: 53 characters
- **Access Level**: Has access to Gemini API (can list models successfully)
- **Model List**: API returns 50 total models, including 34 Gemini models

### 5. Model Availability Paradox
- **Model Listing**: `gemini-2.5-flash` APPEARS in the available models list via both REST API and SDK
- **Actual Usage**: Returns 404 NOT_FOUND when attempting to use the model
- **Error Message**: "This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use a newer model for the latest features and improvements. We recommend you to use the Interactions API"

### 6. Working Models
Tested alternative models with the same API key:
- ✅ **gemini-3.5-flash**: Works successfully via both SDK and REST API
- ✅ **gemini-flash-latest**: Works successfully via both SDK and REST API  
- ❌ **gemini-2.5-flash**: 404 NOT_FOUND (deprecated)
- ❌ **gemini-2.5-flash-lite**: 404 NOT_FOUND (deprecated)
- ❌ **gemini-2.5-pro**: 404 NOT_FOUND (deprecated)
- ❌ **gemini-pro-latest**: 429 RESOURCE_EXHAUSTED (quota issue)

### 7. Application Fallback Behavior
- **Error Handling**: `safe_gemini_json()` function catches exceptions (backend.py lines 1468-1516)
- **Fallback Logic**: Returns `CANDIDATE_GRADING_FALLBACK` when Gemini fails
- **Error Classification**: Only treats 429, 503, and UNAVAILABLE as transient errors (backend.py lines 103-109)
- **404 Handling**: 404 errors are NOT classified as transient, causing immediate fallback
- **Skip Logic**: After certain errors, sets `skip_gemini_grading=True` to avoid repeated failures (backend.py lines 2982-2999)
- **Result**: Application continues with local fallback grading instead of failing the entire analyze request

### 8. Transient Error Configuration
```python
GEMINI_TRANSIENT_ERROR_CODES = [
    "503",
    "UNAVAILABLE", 
    "429",
    "RESOURCE_EXHAUSTED",
    "Quota exceeded",
]
```
**Note**: 404 is NOT included in transient error codes, so 404 errors trigger immediate fallback.

## LIKELY CAUSE

**Google Model Deprecation Policy**: Google has deprecated the `gemini-2.5-flash` model series (2.5-flash, 2.5-flash-lite, 2.5-pro) for new users while still listing them in the model directory. This creates a confusing situation where:

1. The models appear "available" in API listings
2. But return 404 when actually called
3. Google recommends migrating to newer models (gemini-3.5-flash) or the Interactions API
4. The error message explicitly states: "no longer available to new users"

**Timeline Issue**: The project's configuration was likely created when gemini-2.5-flash was current, but Google has since deprecated this model series for new users while maintaining backward compatibility for existing users.

## RECOMMENDED FIX

### Immediate Solution (No Code Changes Required)
**Update the default model configuration** to use a currently available model:

1. **Backend Configuration Change** (backend.py line 57):
   - Change: `GEMINI_RESUME_SKILL_MODEL = "gemini-2.5-flash"`
   - To: `GEMINI_RESUME_SKILL_MODEL = "gemini-3.5-flash"`

2. **Frontend Configuration Change** (frontend/src/defaultModels.js line 25):
   - Change: Move `"gemini-3.5-flash"` to first position in array
   - Or: Reorder array to prioritize working models

3. **Model Options Update** (backend.py lines 93-101):
   - Consider removing deprecated 2.5-series models from GEMINI_MODEL_OPTIONS
   - Or: Move gemini-3.5-flash to first position

### Alternative Solutions

**Option A - User Configuration**: Users can manually select `gemini-3.5-flash` in the UI dropdown without code changes.

**Option B - Add 404 to Transient Errors**: Add "404" to `GEMINI_TRANSIENT_ERROR_CODES` to attempt retries, though this won't solve the underlying deprecation issue.

**Option C - Model Availability Check**: Add startup validation to test model availability and fall back to working models automatically.

### Verification Steps

After making the recommended changes:
1. Test with `gemini-3.5-flash` to confirm successful Gemini integration
2. Verify that grading checkpoints show "source": "gemini" instead of "local_fallback"
3. Confirm that the total pipeline time reflects actual Gemini usage (should be longer than local fallback)
4. Monitor for any additional model deprecations in the future

### Important Notes

- **API Key is Valid**: The API key works correctly with available models
- **SDK is Current**: The `google-genai` SDK version 2.17.0 is appropriate
- **No Package Updates Needed**: The issue is model configuration, not SDK version
- **Fallback Behavior is Working**: The application gracefully handles the deprecated model by using local fallback
- **Performance Impact**: The current 9.10s pipeline time likely reflects local fallback performance, not true Gemini performance
