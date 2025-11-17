"""
Test script to verify Chutes model name and connection.
This helps diagnose "No matching chute found!" errors.
"""
import os
import sys
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL
import requests

print("=" * 70)
print("Chutes Model Verification Test")
print("=" * 70)
print(f"Base URL: {CHUTES_BASE_URL}")
print(f"Model: {CHUTES_MODEL}")
print(f"API Key: {'Set' if CHUTES_API_KEY else 'NOT SET'}")
print()

if not CHUTES_API_KEY:
    print("❌ ERROR: CHUTES_API_KEY not set!")
    print("   Please set it in your .env file:")
    print("   CHUTES_API_KEY=your-api-key-here")
    sys.exit(1)

# Test 1: Try to list available models
print("Test 1: Checking if /models endpoint is available...")
models = None
try:
    models_url = f"{CHUTES_BASE_URL}/models"
    headers = {
        "Authorization": f"Bearer {CHUTES_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get(models_url, headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        models = response.json()
        print(f"   ✅ Models endpoint available!")
        if 'data' in models:
            print(f"   Available models ({len(models['data'])}):")
            for model in models['data'][:10]:  # Show first 10
                model_id = model.get('id', 'unknown')
                print(f"      - {model_id}")
        else:
            print(f"   Response: {json.dumps(models, indent=2)[:500]}")
    else:
        print(f"   ⚠️  Models endpoint returned {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ⚠️  Could not access /models endpoint: {e}")

# Test 1.5: Try to list chutes (if endpoint exists)
print()
print("Test 1.5: Checking if /chutes endpoint is available...")
try:
    chutes_url = f"{CHUTES_BASE_URL}/chutes"
    headers = {
        "Authorization": f"Bearer {CHUTES_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get(chutes_url, headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        chutes = response.json()
        print(f"   ✅ Chutes endpoint available!")
        print(f"   Response: {json.dumps(chutes, indent=2)[:500]}")
    elif response.status_code == 404:
        print(f"   ⚠️  /chutes endpoint not found (this is normal)")
    else:
        print(f"   ⚠️  Chutes endpoint returned {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ⚠️  Could not access /chutes endpoint: {e}")

print()

# Test 2: Try the current model name
print(f"Test 2: Testing current model name: {CHUTES_MODEL}")
test_payload = {
    "input_args": {
        "model": CHUTES_MODEL,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 1,
        "stream": False
    }
}

try:
    chat_url = f"{CHUTES_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {CHUTES_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(chat_url, json=test_payload, headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Model '{CHUTES_MODEL}' is valid and accessible!")
    else:
        print(f"   ❌ Model '{CHUTES_MODEL}' failed with status {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        if response.status_code == 404:
            print()
            print("   💡 Suggestions:")
            print("      1. Check if the model name is correct")
            print("      2. Verify the model is configured in your Chutes account")
            print("      3. Try alternative model names:")
            print("         - deepseek-ai/DeepSeek-V3-0324-turbo")
            print("         - deepseek-ai/DeepSeek-V3")
            print("         - deepseek/DeepSeek-V3-0324")
except Exception as e:
    print(f"   ❌ Error testing model: {e}")

print()

# Test 3: Try models from the available list
print("Test 3: Testing models from available list...")
if models and 'data' in models:
    # Test a few models from the list
    test_models = [m.get('id') for m in models['data'][:5]]  # Test first 5
    
    for test_model in test_models:
        if test_model == CHUTES_MODEL:
            continue  # Skip if it's the same as current model
        
        test_payload = {
            "input_args": {
                "model": test_model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1,
                "stream": False
            }
        }
        
        try:
            chat_url = f"{CHUTES_BASE_URL}/chat/completions"
            headers = {
                "Authorization": f"Bearer {CHUTES_API_KEY}",
                "Content-Type": "application/json"
            }
            response = requests.post(chat_url, json=test_payload, headers=headers, timeout=5)
            if response.status_code == 200:
                print(f"   ✅ '{test_model}' works! Use this model name.")
                print(f"   Update your .env: CHUTES_MODEL={test_model}")
                break
            elif response.status_code == 404:
                print(f"   ❌ '{test_model}': No chute configured (404)")
            else:
                print(f"   ⚠️  '{test_model}': Status {response.status_code}")
        except Exception as e:
            pass  # Silently skip errors
else:
    print("   ⚠️  Could not test alternative models (models list not available)")

print()
print("=" * 70)
print("DIAGNOSIS:")
print("=" * 70)
print("The error 'No matching chute found!' means:")
print("  - The model exists in Chutes' model list")
print("  - BUT no 'chute' (route) is configured for it in your account")
print()
print("Chutes requires you to create a 'chute' for each model you want to use.")
print("A chute is like a route/endpoint that connects your API key to a specific model.")
print()
print("=" * 70)
print("SOLUTION:")
print("=" * 70)
print("1. Log into your Chutes dashboard: https://chutes.ai")
print("2. Create a new 'chute' (or use an existing one)")
print("3. Configure the chute to use: deepseek-ai/DeepSeek-V3-0324")
print("4. The chute will have its own identifier/name")
print("5. Use the CHUTE NAME (not the model name) in your requests")
print()
print("OR:")
print("  - Check if you have any existing chutes configured")
print("  - Use the chute identifier instead of the model name")
print("  - The chute identifier might be different from the model name")
print()
print("=" * 70)
print("Alternative: Try without input_args wrapper")
print("=" * 70)
print("Some Chutes configurations might not need the input_args wrapper.")
print("If you have a chute configured, try setting in .env:")
print("  CHUTES_USE_INPUT_ARGS_WRAPPER=false")
print("=" * 70)

