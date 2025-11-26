"""
Test script to verify OpenAI API connectivity with gpt-5-mini model.
"""

import os
import sys

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, that's okay

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: OpenAI package not installed. Install with: pip install openai")
    sys.exit(1)


def test_api_key():
    """Test if API key is available."""
    print("=" * 60)
    print("Testing OpenAI API Key")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set!")
        print("   Set it in your .env file or environment")
        return False
    
    print(f"✓ API key found (length: {len(api_key)}, starts with: {api_key[:7]}...)")
    return True, api_key


def test_gpt5_mini_direct():
    """Test direct API call to gpt-5-mini."""
    print("\n" + "=" * 60)
    print("Testing gpt-5-mini Model (Direct API Call)")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ No API key available")
        return False
    
    client = OpenAI(api_key=api_key)
    
    try:
        print("Attempting API call with gpt-5-mini...")
        print("Parameters:")
        print("  - Model: gpt-5-mini")
        print("  - max_completion_tokens: 50")
        print("  - No temperature (using default)")
        
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello, this is a test' and nothing else."}
            ],
            max_completion_tokens=50
        )
        
        content = response.choices[0].message.content
        print(f"\n✓ SUCCESS! Response received:")
        print(f"  Content: '{content}'")
        print(f"  Content type: {type(content)}")
        print(f"  Content length: {len(content) if content else 0}")
        print(f"  Is None: {content is None}")
        print(f"  Is empty string: {content == ''}")
        print(f"\n✓ Model: {response.model}")
        print(f"✓ Usage: {response.usage}")
        print(f"✓ Finish reason: {response.choices[0].finish_reason}")
        
        # Check if there's reasoning content
        if hasattr(response.choices[0].message, 'reasoning_content'):
            print(f"✓ Reasoning content: {response.choices[0].message.reasoning_content}")
        
        # Try to get the full message object
        message = response.choices[0].message
        print(f"\nMessage object attributes: {dir(message)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: API call failed")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        
        # Check for specific error types
        if "model" in str(e).lower() or "not found" in str(e).lower():
            print("\n⚠️  This suggests the model 'gpt-5-mini' may not exist or be available")
            print("   Try using 'gpt-4o-mini' or 'gpt-3.5-turbo' instead")
        elif "authentication" in str(e).lower() or "api key" in str(e).lower():
            print("\n⚠️  This suggests an authentication issue with your API key")
        elif "rate limit" in str(e).lower():
            print("\n⚠️  Rate limit exceeded - try again later")
        
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False


def test_gpt5_mini_with_temperature():
    """Test gpt-5-mini with temperature parameter (should fail if model doesn't support it)."""
    print("\n" + "=" * 60)
    print("Testing gpt-5-mini with Temperature Parameter")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ No API key available")
        return False
    
    client = OpenAI(api_key=api_key)
    
    try:
        print("Attempting API call with gpt-5-mini and temperature=0.7...")
        
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Test with temperature'"}
            ],
            max_completion_tokens=50,
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        print(f"✓ SUCCESS with temperature parameter!")
        print(f"  Response: '{content}'")
        return True
        
    except Exception as e:
        print(f"⚠️  Temperature parameter caused error (expected for gpt-5-mini):")
        print(f"   {type(e).__name__}: {str(e)}")
        print("   This is expected - gpt-5-mini may only support default temperature")
        return None  # Not a failure, just informational


def test_alternative_models():
    """Test alternative models to see what works."""
    print("\n" + "=" * 60)
    print("Testing Alternative Models")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ No API key available")
        return False
    
    client = OpenAI(api_key=api_key)
    
    alternative_models = [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-3.5-turbo",
    ]
    
    results = {}
    
    for model in alternative_models:
        print(f"\nTesting {model}...")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "Say 'OK'"}
                ],
                max_tokens=10
            )
            content = response.choices[0].message.content.strip()
            print(f"  ✓ {model} works! Response: '{content}'")
            results[model] = True
        except Exception as e:
            print(f"  ❌ {model} failed: {type(e).__name__}: {str(e)[:100]}")
            results[model] = False
    
    return results


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("GPT-5-Mini Connectivity Test")
    print("=" * 60)
    print()
    
    # Test 1: API Key
    api_key_result = test_api_key()
    if not api_key_result:
        print("\n❌ Cannot proceed without API key")
        return 1
    
    # Test 2: Direct gpt-5-mini call
    gpt5_result = test_gpt5_mini_direct()
    
    # Test 3: Temperature parameter
    temp_result = test_gpt5_mini_with_temperature()
    
    # Test 4: Alternative models
    alt_results = test_alternative_models()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    print(f"\nAPI Key: {'✓ Available' if api_key_result else '❌ Missing'}")
    print(f"gpt-5-mini: {'✓ Works' if gpt5_result else '❌ Failed'}")
    print(f"Temperature param: {'✓ Works' if temp_result else '⚠️  Not supported' if temp_result is None else '❌ Failed'}")
    
    print("\nAlternative Models:")
    for model, success in alt_results.items():
        status = "✓ Works" if success else "❌ Failed"
        print(f"  {model}: {status}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("Recommendations")
    print("=" * 60)
    
    if not gpt5_result:
        print("\n❌ gpt-5-mini is not working. Recommendations:")
        working_models = [m for m, s in alt_results.items() if s]
        if working_models:
            print(f"   → Use one of these working models instead: {', '.join(working_models)}")
            print(f"   → Update configs/simple_llm_agent.yaml: llm_model: {working_models[0]}")
        else:
            print("   → Check your API key and network connection")
            print("   → Verify your OpenAI account has access to the models")
    else:
        print("\n✓ gpt-5-mini is working!")
        if temp_result is False:
            print("   → Note: Temperature parameter not supported (use default)")
            print("   → The code already handles this correctly")
    
    return 0 if gpt5_result else 1


if __name__ == "__main__":
    sys.exit(main())

