# Accessing Reasoning Summaries

## Current Status

✅ **IMPLEMENTED**: The codebase now uses the **Responses API** to access reasoning summaries. Reasoning summaries are extracted from `response.output[0].summary[0].text` and displayed in the web UI.

## How to Access Reasoning Summaries

### Using the Responses API

The Responses API supports reasoning summaries with the `reasoning` parameter:

```python
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.responses.create(
    model="gpt-5-mini",
    input=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Your prompt here"}
    ],
    reasoning={"summary": "auto"},  # Options: "auto", "concise", "detailed"
    max_output_tokens=200
)

# Extract reasoning summary
if response.output and len(response.output) > 0:
    first_output = response.output[0]
    if hasattr(first_output, 'summary') and first_output.summary:
        summary_list = first_output.summary
        if len(summary_list) > 0:
            reasoning_text = summary_list[0].text
            print(f"Reasoning: {reasoning_text}")

# Extract response text (if available)
# Note: Responses API structure is different from Chat Completions
```

### Response Structure

The Responses API returns:
- `response.output`: List of output items
- `response.output[0]`: First output item (ResponseReasoningItem)
- `response.output[0].summary`: List of Summary objects
- `response.output[0].summary[0].text`: The reasoning summary text

### Differences from Chat Completions

1. **Input format**: Uses `input` (list of messages) instead of `messages`
2. **Response structure**: Returns `output` list instead of `choices[0].message.content`
3. **Token limits**: Uses `max_output_tokens` instead of `max_completion_tokens`
4. **Response text**: May be in a different location (check `response.text` or `response.output_text`)

## Current Implementation

The codebase now uses the **Responses API** to enable reasoning summaries:

### Implementation Details

- **API Calls**: `_call_llm()` and `_call_llm_async()` use `client.responses.create()`
- **Parameters**: Uses `input` instead of `messages`, `max_output_tokens` instead of `max_completion_tokens`
- **Reasoning Parameter**: `reasoning={"summary": "auto"}` is included in all API calls
- **Response Processing**: `_process_llm_response()` extracts:
  - Content from `response.output[0].text` (or `.content` as fallback)
  - Reasoning from `response.output[0].summary[0].text`
- **UI Integration**: Reasoning summaries are automatically displayed in the web UI when available

### Code Locations

- **API Parameter Building**: `src/agents/llm_agent.py::_build_api_params()` (lines 77-122)
- **API Calls**: `src/agents/llm_agent.py::_call_llm()` and `_call_llm_async()` (lines 327-397)
- **Response Processing**: `src/agents/llm_agent.py::_process_llm_response()` (lines 124-325)
- **Test Mocks**: `tests/conftest.py::create_mock_agent_response()` (lines 98-123)

### Benefits

- ✅ Reasoning summaries are now available and displayed in the UI
- ✅ Simplified response parsing (no complex fallback logic needed)
- ✅ Consistent API parameter handling across all models
- ✅ Better visibility into model reasoning process

