#!/usr/bin/env python3
"""
Quick test to verify all imports work correctly after Claude removal
"""
import sys

print("=" * 60)
print("  TESTING IMPORTS AFTER CLAUDE REMOVAL")
print("=" * 60)
print()

# Test 1: Import config
print("Test 1: Import config...")
try:
    from app.config import get_settings
    settings = get_settings()
    print("✓ Config imported successfully")
    print(f"  - TEST_MODE: {settings.test_mode}")
    print(f"  - Has openai_api_key: {bool(settings.openai_api_key)}")
    print(f"  - Has perplexity_api_key: {bool(settings.perplexity_api_key)}")
except Exception as e:
    print(f"✗ Config import failed: {e}")
    sys.exit(1)

# Test 2: Import OpenAITailor
print()
print("Test 2: Import OpenAITailor...")
try:
    from app.services.openai_tailor import OpenAITailor
    print("✓ OpenAITailor imported successfully")
except Exception as e:
    print(f"✗ OpenAITailor import failed: {e}")
    sys.exit(1)

# Test 3: Check that old claude_tailor doesn't exist
print()
print("Test 3: Verify claude_tailor.py is removed...")
try:
    from app.services.claude_tailor import ClaudeTailor
    print("✗ OLD FILE STILL EXISTS: claude_tailor.py should be deleted!")
    sys.exit(1)
except ImportError:
    print("✓ claude_tailor.py correctly removed")
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)

# Test 4: Import tailoring routes
print()
print("Test 4: Import tailoring routes...")
try:
    from app.routes.tailoring import router
    print("✓ Tailoring routes imported successfully")
except Exception as e:
    print(f"✗ Tailoring routes import failed: {e}")
    print(f"  This might mean the import in tailoring.py is wrong")
    sys.exit(1)

# Test 5: Import PerplexityClient
print()
print("Test 5: Import PerplexityClient...")
try:
    from app.services.perplexity_client import PerplexityClient
    print("✓ PerplexityClient imported successfully")
except Exception as e:
    print(f"✗ PerplexityClient import failed: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("  ALL TESTS PASSED ✓")
print("=" * 60)
print()
print("Next steps:")
print("1. Set OPENAI_API_KEY in Railway environment variables")
print("2. Set PERPLEXITY_API_KEY in Railway environment variables")
print("3. Push to GitHub: git add . && git commit -m 'Remove Claude, use OpenAI' && git push")
print("4. Railway will auto-deploy")
print()
