"""
Detailed test to understand gpt-5-mini behavior and get actual output.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("=" * 60)
print("Testing gpt-5-mini with different parameters")
print("=" * 60)

# Test 1: Try with higher max_completion_tokens
print("\n1. Testing with max_completion_tokens=200...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": "Say exactly: Hello, this is a test"}
        ],
        max_completion_tokens=200
    )
    print(f"   Content: '{response.choices[0].message.content}'")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Try with stream=False explicitly
print("\n2. Testing with explicit stream=False...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": "Say exactly: Hello, this is a test"}
        ],
        max_completion_tokens=100,
        stream=False
    )
    print(f"   Content: '{response.choices[0].message.content}'")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Try with a more explicit prompt
print("\n3. Testing with explicit output instruction...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "You must always provide a text response in the content field."},
            {"role": "user", "content": "Your response must be: 'Hello, this is a test'. Do not use reasoning tokens, output text directly."}
        ],
        max_completion_tokens=100
    )
    print(f"   Content: '{response.choices[0].message.content}'")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"   Error: {e}")

# Test 4: Check if there's a refusal field
print("\n4. Checking message object for refusal or other fields...")
try:
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": "Say: Hello"}
        ],
        max_completion_tokens=50
    )
    message = response.choices[0].message
    print(f"   Content: '{message.content}'")
    print(f"   Refusal: {getattr(message, 'refusal', 'N/A')}")
    print(f"   Role: {message.role}")
    print(f"   All fields: {[k for k in dir(message) if not k.startswith('_')]}")
except Exception as e:
    print(f"   Error: {e}")

# Test 5: Compare with gpt-4o-mini to see the difference
print("\n5. Comparing with gpt-4o-mini (should work)...")
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Say exactly: Hello, this is a test"}
        ],
        max_tokens=50
    )
    print(f"   Content: '{response.choices[0].message.content}'")
    print(f"   Finish reason: {response.choices[0].finish_reason}")
    print(f"   Usage: {response.usage}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("Conclusion")
print("=" * 60)
print("If gpt-5-mini consistently returns empty content, it may be:")
print("1. A reasoning-only model that doesn't output text")
print("2. Requires different parameters or API version")
print("3. May need to use a different model for text generation")

