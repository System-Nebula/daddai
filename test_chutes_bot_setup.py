"""Quick test to verify Chutes setup for Discord bot."""
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.clients.llm_client_factory import get_default_llm_client
from config import LLM_PROVIDER, CHUTES_API_KEY

print("=" * 60)
print("Discord Bot Chutes Setup Verification")
print("=" * 60)
print(f"LLM_PROVIDER: {LLM_PROVIDER}")
print(f"CHUTES_API_KEY: {'Set' if CHUTES_API_KEY else 'NOT SET'}")
print()

try:
    client = get_default_llm_client()
    print(f"✅ Client initialized successfully!")
    print(f"   Type: {type(client).__name__}")
    
    if hasattr(client, 'base_url'):
        print(f"   Base URL: {client.base_url}")
    if hasattr(client, 'model'):
        print(f"   Model: {client.model}")
    
    if LLM_PROVIDER == 'chutes':
        if not CHUTES_API_KEY:
            print("\n⚠️  WARNING: CHUTES_API_KEY not set!")
            print("   The bot will fail when trying to use Chutes.")
        else:
            print("\n✅ Chutes configuration looks good!")
            print("   The Discord bot should work with Chutes AI.")
    else:
        print(f"\nℹ️  Using provider: {LLM_PROVIDER}")
        print("   To use Chutes, set LLM_PROVIDER=chutes in .env")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)

