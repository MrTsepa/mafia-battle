# GPT-5-Mini Connectivity Test Results

## Test Date
Analysis run to diagnose LLM agent connectivity issues

## Key Findings

### ✅ API Connectivity: WORKING
- API key is valid and working
- `gpt-5-mini` model is accessible
- API calls succeed without authentication errors

### ⚠️ Critical Issue: Token Allocation

**Problem**: `gpt-5-mini` is a reasoning model that uses tokens for internal reasoning before outputting text.

**Test Results**:
- With `max_completion_tokens=50`: Returns empty content, uses all 50 tokens for reasoning
- With `max_completion_tokens=200`: Returns actual text output ("Hello, this is a test")

**Root Cause in Code**:
- **Speeches**: Use `max_speech_tokens=300` ✅ (should work)
- **Night Actions**: Use hardcoded `max_tokens=50` ❌ (too low!)

### Code Locations with Issue

All night action calls use only 50 tokens:
- Line 461: Sheriff check: `max_tokens=50`
- Line 496: Mafia kill decision: `max_tokens=50`
- Line 514: Mafia kill claim: `max_tokens=50`
- Line 545: Don check: `max_tokens=50`
- Line 574: Don kill decision: `max_tokens=50`
- Line 611: Vote choice: `max_tokens=50`

### Why This Causes Empty Responses

1. `gpt-5-mini` allocates tokens for reasoning first
2. With only 50 tokens, it uses them all for reasoning
3. No tokens remain for actual text output
4. Returns empty string `""`
5. Agent falls back to default behavior

## Test Evidence

```
Test 1: max_completion_tokens=50
  Content: ''
  Finish reason: length
  Reasoning tokens: 50

Test 2: max_completion_tokens=200
  Content: 'Hello, this is a test'
  Finish reason: stop
  Reasoning tokens: 128
  Output tokens: 15
```

## Solution

### Option 1: Increase Token Limits (Recommended)

Update all night action calls to use at least 100-150 tokens:

```python
# Current (line 461):
response = self._call_llm(prompt, max_tokens=50)

# Should be:
response = self._call_llm(prompt, max_tokens=150)
```

### Option 2: Use Different Model

Switch to `gpt-4o-mini` which doesn't require reasoning tokens:
- Works with 50 tokens
- Faster responses
- Lower cost

### Option 3: Add Configuration Parameter

Add `max_action_tokens` to config file:
```yaml
max_action_tokens: 150  # For night actions and voting
```

## Recommended Fix

**Immediate**: Increase all `max_tokens=50` to `max_tokens=150` in `llm_agent.py`

**Long-term**: 
1. Add `max_action_tokens` config parameter
2. Use it for all non-speech actions
3. Document token requirements for different models

## Model Comparison

| Model | Works with 50 tokens? | Reasoning tokens? | Recommended min |
|-------|---------------------|-------------------|------------------|
| gpt-5-mini | ❌ No | Yes (uses tokens) | 150+ |
| gpt-4o-mini | ✅ Yes | No | 50 |
| gpt-4o | ✅ Yes | No | 50 |
| gpt-3.5-turbo | ✅ Yes | No | 50 |

## Test Results Summary

✅ **API Key**: Valid  
✅ **gpt-5-mini Model**: Accessible  
✅ **gpt-4o-mini**: Works perfectly  
✅ **gpt-4o**: Works perfectly  
✅ **gpt-3.5-turbo**: Works perfectly  

❌ **gpt-5-mini with 50 tokens**: Returns empty content  
✅ **gpt-5-mini with 200 tokens**: Returns content  

## Next Steps

1. ✅ **Fix token limits** in `llm_agent.py` (change 50 → 150)
2. ✅ **Re-run game** to verify LLM agent works
3. ✅ **Update config** to document token requirements
4. ✅ **Consider model choice**: `gpt-4o-mini` may be better for this use case

## Files Created

- `test_gpt5_mini.py` - Basic connectivity test
- `test_gpt5_mini_detailed.py` - Detailed parameter testing
- This analysis document

